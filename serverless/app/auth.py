"""
Authentication module for Note-Taking App (Serverless / DynamoDB)
Supports AWS Cognito and Guest mode
"""
import os
import secrets
import functools
from flask import Blueprint, session, redirect, url_for, request, flash, jsonify
import hmac
import hashlib
import base64
import boto3
import botocore.exceptions
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

COGNITO_REGION = os.getenv('AWS_REGION', 'us-east-1')
COGNITO_USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID', '')
COGNITO_CLIENT_ID = os.getenv('COGNITO_CLIENT_ID', '')
COGNITO_CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET', '')
COGNITO_DOMAIN = os.getenv('COGNITO_DOMAIN', '')

APP_DOMAIN = os.getenv('APP_DOMAIN', '')

COGNITO_ENABLED = bool(COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID and COGNITO_DOMAIN)


def login_required(f):
    """Decorator to require authentication (Cognito or Guest)."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in or continue as guest.', 'error')
            return redirect(url_for('auth.login'))

        if request.endpoint not in ['profile_setup', 'save_profile']:
            from db import get_user
            user = get_user(session['user_id'])
            if user and not user.get('profile_complete') and not user.get('is_guest'):
                return redirect(url_for('profile_setup'))

        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the current user from session."""
    if 'user_id' not in session:
        return None
    from db import get_user
    return get_user(session['user_id'])


def get_secret_hash(username):
    """Generate SecretHash for Cognito Client ID + Secret."""
    if not COGNITO_CLIENT_SECRET:
        return None
    msg = username + COGNITO_CLIENT_ID
    dig = hmac.new(str(COGNITO_CLIENT_SECRET).encode('utf-8'),
                   msg.encode('utf-8'), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()


@auth_bp.route('/login')
def login():
    """Show landing page."""
    from flask import render_template
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html', cognito_enabled=COGNITO_ENABLED)


@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    """Show sign-in page and handle native email/password login."""
    from flask import render_template
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('auth.signin'))
            
        try:
            client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            
            kwargs = {
                'ClientId': COGNITO_CLIENT_ID,
                'AuthFlow': 'USER_PASSWORD_AUTH',
                'AuthParameters': {
                    'USERNAME': email,
                    'PASSWORD': password
                }
            }
            if COGNITO_CLIENT_SECRET:
                kwargs['AuthParameters']['SECRET_HASH'] = get_secret_hash(email)
                
            response = client.initiate_auth(**kwargs)
            
            id_token = response['AuthenticationResult']['IdToken']
            from jose import jwt
            from db import get_user_by_cognito_sub, create_user
            
            claims = jwt.get_unverified_claims(id_token)
            cognito_sub = claims.get('sub')
            
            user = get_user_by_cognito_sub(cognito_sub)
            if not user:
                name = claims.get('name', email.split('@')[0])
                new_user = create_user(cognito_sub=cognito_sub, email=email, display_name=name)
                user_id = new_user['user_id']
                display_name = new_user['display_name']
            else:
                user_id = user['user_id']
                display_name = user['display_name']
                
            session['user_id'] = user_id
            session['display_name'] = display_name
            session['email'] = email
            session['is_guest'] = False
            
            flash(f'Welcome back, {display_name}!', 'success')
            return redirect(url_for('index'))
            
        except client.exceptions.UserNotConfirmedException:
            flash('Please verify your email address before logging in.', 'error')
            return redirect(url_for('auth.verify', email=email))
        except client.exceptions.NotAuthorizedException:
            flash('Incorrect email or password.', 'error')
        except client.exceptions.UserNotFoundException:
            flash('Incorrect email or password.', 'error')
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            
    return render_template('signin.html', cognito_enabled=COGNITO_ENABLED)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Show register page and handle native sign up."""
    from flask import render_template
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password or not name:
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.register'))
            
        try:
            import uuid
            client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            
            username = str(uuid.uuid4())
            kwargs = {
                'ClientId': COGNITO_CLIENT_ID,
                'Username': username,
                'Password': password,
                'UserAttributes': [
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name}
                ]
            }
            if COGNITO_CLIENT_SECRET:
                kwargs['SecretHash'] = get_secret_hash(username)
                
            client.sign_up(**kwargs)
            # Store the UUID username in session so verify can use it
            session['pending_verification_username'] = username
            session['pending_verification_email'] = email
            flash('Registration successful! Please check your email for the verification code.', 'success')
            return redirect(url_for('auth.verify', email=email))
            
        except client.exceptions.UsernameExistsException:
            flash('An account with this email already exists.', 'error')
        except client.exceptions.InvalidPasswordException as e:
            flash('Password must be at least 8 characters and contain numbers, uppercase, lowercase, and symbols.', 'error')
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'error')
            
    return render_template('register.html')


@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    """Verify email with code."""
    from flask import render_template
    email = request.args.get('email', '')
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        code = request.form.get('code', '').strip()
        
        if not email or not code:
            flash('Email and verification code are required.', 'error')
            return redirect(url_for('auth.verify', email=email))
            
        try:
            client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            
            # Use the UUID username stored during registration if available
            username = session.pop('pending_verification_username', None) or email
            
            kwargs = {
                'ClientId': COGNITO_CLIENT_ID,
                'Username': username,
                'ConfirmationCode': code
            }
            if COGNITO_CLIENT_SECRET:
                kwargs['SecretHash'] = get_secret_hash(username)
                
            client.confirm_sign_up(**kwargs)
            session.pop('pending_verification_email', None)
            flash('Email verified successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except client.exceptions.CodeMismatchException:
            flash('Invalid verification code. Please try again.', 'error')
        except client.exceptions.ExpiredCodeException:
            flash('Verification code expired. Please request a new one.', 'error')
        except Exception as e:
            flash(f'Verification error: {str(e)}', 'error')
            
    return render_template('verify.html', email=email)


@auth_bp.route('/guest', methods=['GET', 'POST'])
def guest_login():
    """Create a guest session with full functionality."""
    from db import create_user

    try:
        guest_name = f"Guest_{secrets.token_hex(4)}"
        user = create_user(display_name=guest_name, is_guest=True)

        session['user_id'] = user['user_id']
        session['display_name'] = guest_name
        session['is_guest'] = True

        flash(f'Welcome, {guest_name}! Create an account to save your notes permanently.', 'info')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error creating guest session: {e}', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/cognito')
def cognito_login():
    """Redirect to Cognito hosted UI."""
    if not COGNITO_ENABLED:
        flash('Cognito authentication is not configured.', 'error')
        return redirect(url_for('auth.login'))

    if APP_DOMAIN:
        callback_url = f"https://{APP_DOMAIN}/auth/cognito/callback"
    else:
        callback_url = url_for('auth.cognito_callback', _external=True)

    auth_url = (
        f"https://{COGNITO_DOMAIN}/oauth2/authorize?"
        f"identity_provider=Google&"
        f"client_id={COGNITO_CLIENT_ID}&"
        f"response_type=code&"
        f"scope=openid+email+profile&"
        f"redirect_uri={callback_url}"
    )
    return redirect(auth_url)


@auth_bp.route('/cognito/callback')
def cognito_callback():
    """Handle Cognito OAuth callback."""
    if not COGNITO_ENABLED:

        return redirect(url_for('auth.login'))

    code = request.args.get('code')
    if not code:
        flash('Authentication failed.', 'error')
        return redirect(url_for('auth.login'))

    try:
        import requests as http_requests
        from jose import jwt
        from db import get_user_by_cognito_sub, create_user, migrate_guest_to_cognito

        if APP_DOMAIN:
            callback_url = f"https://{APP_DOMAIN}/auth/cognito/callback"
        else:
            callback_url = url_for('auth.cognito_callback', _external=True)

        token_url = f"https://{COGNITO_DOMAIN}/oauth2/token"


        response = http_requests.post(token_url, data={
            'grant_type': 'authorization_code',
            'client_id': COGNITO_CLIENT_ID,
            'client_secret': COGNITO_CLIENT_SECRET,
            'code': code,
            'redirect_uri': callback_url
        }, headers={'Content-Type': 'application/x-www-form-urlencoded'})

        if response.status_code != 200:
            flash('Token exchange failed.', 'error')
            return redirect(url_for('auth.login'))

        tokens = response.json()
        id_token = tokens.get('id_token')

        claims = jwt.get_unverified_claims(id_token)
        cognito_sub = claims.get('sub')
        email = claims.get('email', '')
        name = claims.get('name', email.split('@')[0] if email else 'User')

        user = get_user_by_cognito_sub(cognito_sub)

        if not user:
            if session.get('is_guest') and session.get('user_id'):
                migrate_guest_to_cognito(session['user_id'], cognito_sub, email, name)
                user_id = session['user_id']
                flash('Your guest notes have been saved to your account!', 'success')
            else:
                new_user = create_user(cognito_sub=cognito_sub, email=email, display_name=name)
                user_id = new_user['user_id']
        else:
            user_id = user['user_id']

        greeting_name = name
        if user:
            f_name = user.get('first_name')
            l_name = user.get('last_name')
            d_name = user.get('display_name')
            if f_name and l_name:
                greeting_name = f"{f_name} {l_name}"
            elif f_name:
                greeting_name = f_name
            elif d_name:
                greeting_name = d_name

        session['user_id'] = user_id
        session['display_name'] = name
        session['email'] = email
        session['is_guest'] = False

        flash(f'Welcome back, {greeting_name}!', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        flash(f'Authentication error: {e}', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    """Clear session and logout."""
    is_guest = session.get('is_guest', False)
    user_id = session.get('user_id')

    if is_guest and user_id:
        from db import delete_user
        try:
            delete_user(user_id)
        except Exception:
            pass

    session.clear()
    flash('You have been logged out.', 'info')

    if COGNITO_ENABLED and not is_guest:
        logout_url = (
            f"https://{COGNITO_DOMAIN}/logout?"
            f"client_id={COGNITO_CLIENT_ID}&"
            f"logout_uri={url_for('auth.login', _external=True)}"
        )
        return redirect(logout_url)

    return redirect(url_for('auth.login'))


@auth_bp.route('/user')
@login_required
def user_info():
    """Get current user info as JSON."""
    user = get_current_user()
    if user:
        return jsonify({
            'id': user['user_id'],
            'display_name': user['display_name'],
            'email': user.get('email', ''),
            'is_guest': user['is_guest']
        })
    return jsonify({'error': 'Not authenticated'}), 401
