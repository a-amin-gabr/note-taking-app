"""
Authentication module for Note-Taking App
Supports AWS Cognito and Guest mode
"""
import os
import secrets
import functools
from flask import Blueprint, session, redirect, url_for, request, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# AWS Cognito configuration (optional)
COGNITO_REGION = os.getenv('AWS_REGION', 'us-east-1')
COGNITO_USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID', '')
COGNITO_CLIENT_ID = os.getenv('COGNITO_CLIENT_ID', '')
COGNITO_CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET', '')
COGNITO_DOMAIN = os.getenv('COGNITO_DOMAIN', '')

# Check if Cognito is configured
COGNITO_ENABLED = bool(COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID and COGNITO_DOMAIN)


def get_db_connection():
    """Import from app to avoid circular imports."""
    from app import get_db_connection as db_conn
    return db_conn()


def login_required(f):
    """Decorator to require authentication (Cognito or Guest)."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in or continue as guest.', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if profile setup is needed (skip for profile routes)
        if request.endpoint not in ['profile_setup', 'save_profile']:
            user = get_current_user()
            if user and not user.get('profile_complete') and not user.get('is_guest'):
                return redirect(url_for('profile_setup'))
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the current user from session."""
    if 'user_id' not in session:
        return None
    
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cursor.fetchone()
        return user
    finally:
        cursor.close()
        connection.close()


@auth_bp.route('/login')
def login():
    """Show login page."""
    from flask import render_template
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html', cognito_enabled=COGNITO_ENABLED)


@auth_bp.route('/guest', methods=['POST'])
def guest_login():
    """Create a guest session with full functionality."""
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        cursor = connection.cursor()
        # Create guest user
        guest_name = f"Guest_{secrets.token_hex(4)}"
        cursor.execute(
            'INSERT INTO users (display_name, is_guest) VALUES (%s, TRUE)',
            (guest_name,)
        )
        connection.commit()
        
        # Set session
        session['user_id'] = cursor.lastrowid
        session['display_name'] = guest_name
        session['is_guest'] = True
        
        flash(f'Welcome, {guest_name}! Create an account to save your notes permanently.', 'info')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error creating guest session: {e}', 'error')
        return redirect(url_for('auth.login'))
    finally:
        cursor.close()
        connection.close()


@auth_bp.route('/cognito')
def cognito_login():
    """Redirect to Cognito hosted UI."""
    if not COGNITO_ENABLED:
        flash('Cognito authentication is not configured.', 'error')
        return redirect(url_for('auth.login'))
    
    # Build Cognito authorization URL
    callback_url = url_for('auth.cognito_callback', _external=True)
    auth_url = (
        f"https://{COGNITO_DOMAIN}/login?"
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
        import requests
        from jose import jwt
        
        # Exchange code for tokens
        callback_url = url_for('auth.cognito_callback', _external=True)
        token_url = f"https://{COGNITO_DOMAIN}/oauth2/token"
        
        response = requests.post(token_url, data={
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
        
        # Decode token (skip verification for simplicity - add in production)
        claims = jwt.get_unverified_claims(id_token)
        cognito_sub = claims.get('sub')
        email = claims.get('email', '')
        name = claims.get('name', email.split('@')[0] if email else 'User')
        
        # Find or create user
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM users WHERE cognito_sub = %s', (cognito_sub,))
        user = cursor.fetchone()
        
        if not user:
            # Check if guest user exists in session to migrate
            if session.get('is_guest') and session.get('user_id'):
                # Migrate guest to full user
                cursor.execute(
                    '''UPDATE users SET cognito_sub = %s, email = %s, 
                       display_name = %s, is_guest = FALSE 
                       WHERE id = %s''',
                    (cognito_sub, email, name, session['user_id'])
                )
                connection.commit()
                user_id = session['user_id']
                flash('Your guest notes have been saved to your account!', 'success')
            else:
                # Create new user
                cursor.execute(
                    'INSERT INTO users (cognito_sub, email, display_name) VALUES (%s, %s, %s)',
                    (cognito_sub, email, name)
                )
                connection.commit()
                user_id = cursor.lastrowid
        else:
            user_id = user['id']
        
        cursor.close()
        connection.close()
        
        # Determine the name to show in greeting
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
        
        # Set session
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
    
    # Optionally delete guest user data
    if is_guest and user_id:
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute('DELETE FROM users WHERE id = %s AND is_guest = TRUE', (user_id,))
                connection.commit()
            finally:
                cursor.close()
                connection.close()
    
    session.clear()
    flash('You have been logged out.', 'info')
    
    if COGNITO_ENABLED and not is_guest:
        # Redirect to Cognito logout
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
            'id': user['id'],
            'display_name': user['display_name'],
            'email': user.get('email', ''),
            'is_guest': user['is_guest']
        })
    return jsonify({'error': 'Not authenticated'}), 401
