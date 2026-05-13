"""
Note-Taking App — Serverless Flask Application (DynamoDB)
Features: Categories, Search, Pin, Archive, Markdown, Export, Import, Avatars, S3
"""
import os
import re
import uuid
import base64
import secrets
import json
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from dotenv import load_dotenv
import markdown
import bleach

load_dotenv()

# Resolve repository root and prefer serving the top-level `static/` folder
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DEFAULT_STATIC = os.path.join(REPO_ROOT, 'static')

if os.path.isdir(DEFAULT_STATIC):
    app = Flask(__name__, static_folder=DEFAULT_STATIC, static_url_path='/static')
else:
    app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
CSRF_TOKEN_SESSION_KEY = '_csrf_token'

from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


def get_csrf_token():
    token = session.get(CSRF_TOKEN_SESSION_KEY)
    if not token:
        token = secrets.token_hex(32)
        session[CSRF_TOKEN_SESSION_KEY] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {'csrf_token': get_csrf_token}


@app.before_request
def enforce_csrf_protection():
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        expected = session.get(CSRF_TOKEN_SESSION_KEY)
        provided = (
            request.form.get('csrf_token')
            or request.headers.get('X-CSRFToken')
            or request.headers.get('X-CSRF-Token')
        )
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            return jsonify({'error': 'CSRF validation failed'}), 400

# Upload configuration (Lambda /tmp is the only writable space)
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    # Prefer repo-level static/uploads if present
    if os.path.isdir(DEFAULT_STATIC):
        UPLOAD_FOLDER = os.path.join(DEFAULT_STATIC, 'uploads')
    else:
        UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception as e:
    print(f"Note: Could not create upload folder locally: {e}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


# AWS S3 configuration
S3_BUCKET = os.getenv('S3_BUCKET', '')
S3_REGION = os.getenv('S3_REGION', os.getenv('AWS_REGION', 'us-east-1'))
APP_DOMAIN = (os.getenv('APP_DOMAIN') or '').strip().rstrip('/')
S3_ENABLED = False
s3_client = None

try:
    import boto3
    if S3_BUCKET:
        s3_client = boto3.client('s3', region_name=S3_REGION)
        S3_ENABLED = True
        print(f"\u2705 S3 enabled: bucket={S3_BUCKET}")
except ImportError:
    pass
except Exception as e:
    print(f"\u26a0\ufe0f S3 init failed (falling back to local): {e}")

import db

def upload_file_to_storage(file_data, filename, content_type='image/jpeg', folder='avatars'):
    """Upload file to S3 if available, otherwise save locally. Returns URL."""
    if S3_ENABLED and s3_client:
        try:
            key = f"{folder}/{filename}"
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=file_data,
                ContentType=content_type
            )
            return url_for('get_s3_file', folder=folder, filename=filename)
        except Exception as e:
            print(f"S3 upload failed, falling back to local: {e}")

    local_folder = os.path.join(UPLOAD_FOLDER, folder)
    os.makedirs(local_folder, exist_ok=True)
    filepath = os.path.join(local_folder, filename)
    with open(filepath, 'wb') as f:
        f.write(file_data)
    return f"/static/uploads/{folder}/{filename}"


from auth import auth_bp, login_required, get_current_user
app.register_blueprint(auth_bp)

ALLOWED_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'ul', 'ol', 'li',
    'code', 'pre', 'blockquote', 'a', 'br', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'img',
    'del', 'ins', 'sup', 'sub', 'mark'
]
ALLOWED_ATTRS = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    '*': ['class']
}


def render_markdown(text):
    """Convert markdown to sanitized HTML."""
    html = markdown.markdown(text, extensions=[
        'extra', 'nl2br', 'sane_lists', 'smarty'
    ])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)


def build_share_url(token):
    """Build the public share URL using the configured app domain when available."""
    if APP_DOMAIN:
        if APP_DOMAIN.startswith('http://') or APP_DOMAIN.startswith('https://'):
            base = APP_DOMAIN.rstrip('/')
        else:
            base = f"https://{APP_DOMAIN}"
        return f"{base}/shared/{token}"

    return url_for('view_shared', token=token, _external=True)


# =============================================================================
# MAIN ROUTES
# =============================================================================

@app.route('/favicon.ico')
def favicon():
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'),
                               'logo.png', mimetype='image/png')


@app.route('/')
@login_required
def index():
    """Display all notes with filters."""
    user_id = session['user_id']
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '')
    show_archived = request.args.get('archived', '0') == '1'

    try:
        categories = db.list_categories(user_id)
        notes = db.list_notes(
            user_id,
            archived=show_archived,
            search=search_query or None,
            category_id=category_filter or None,
        )

        for note in notes:
            note['content_html'] = render_markdown(note.get('content', ''))

        stats = db.get_stats(user_id)
        user = get_current_user()

        return render_template('index.html',
                             notes=notes,
                             categories=categories,
                             stats=stats,
                             user=user,
                             search_query=search_query,
                             category_filter=category_filter,
                             show_archived=show_archived)
    except Exception as e:
        flash(f'Error loading notes: {e}', 'error')
        return render_template('index.html', notes=[], categories=[], stats={}, user=get_current_user())


# =============================================================================
# PROFILE ROUTES
# =============================================================================

@app.route('/profile/setup')
@login_required
def profile_setup():
    """Show profile setup page for new users."""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    if user.get('profile_complete'):
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user, is_setup=True)


@app.route('/profile')
@login_required
def profile():
    """Show profile page."""
    user = get_current_user()
    return render_template('profile.html', user=user, is_setup=False)


@app.route('/profile', methods=['POST'])
@login_required
def save_profile():
    """Save profile changes."""
    user_id = session['user_id']

    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    display_name = request.form.get('display_name', '').strip()
    bio = request.form.get('bio', '').strip()
    timezone = request.form.get('timezone', 'UTC')

    if not display_name:
        flash('Display name is required!', 'error')
        return redirect(url_for('profile'))

    try:
        db.update_user(user_id,
                       first_name=first_name,
                       last_name=last_name,
                       display_name=display_name,
                       bio=bio,
                       timezone=timezone,
                       profile_complete=True)

        session['display_name'] = display_name
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating profile: {e}', 'error')

    if request.form.get('is_setup') == 'true':
        return redirect(url_for('index'))
    return redirect(url_for('profile'))


@app.route('/profile/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload and save user avatar."""
    user_id = session['user_id']
    avatar_url = None

    if request.is_json:
        data = request.get_json()
        image_data = data.get('image', '')
        if not image_data:
            return jsonify({'error': 'No image data'}), 400

        match = re.match(r'data:image/(\w+);base64,(.*)', image_data)
        if not match:
            return jsonify({'error': 'Invalid image format'}), 400

        ext = match.group(1)
        if ext == 'jpeg':
            ext = 'jpg'
        raw = base64.b64decode(match.group(2))
        filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
        avatar_url = upload_file_to_storage(raw, filename, f'image/{ext}')

    elif 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                flash('Invalid file type. Use PNG, JPG, GIF, or WebP.', 'error')
                return redirect(url_for('profile'))
            filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
            raw = file.read()
            avatar_url = upload_file_to_storage(raw, filename, file.content_type)

    if not avatar_url:
        flash('No image provided.', 'error')
        return redirect(url_for('profile'))

    try:
        db.update_user(user_id, avatar_url=avatar_url)
        if request.is_json:
            return jsonify({'url': avatar_url, 'message': 'Avatar updated!'})
        flash('Avatar updated!', 'success')
    except Exception as e:
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Error saving avatar: {e}', 'error')

    return redirect(url_for('profile'))


@app.route('/s3/<folder>/<path:filename>')
@login_required
def get_s3_file(folder, filename):
    """Serve S3 file through the backend (proxy)."""
    if not S3_ENABLED or not s3_client:
        return jsonify({'error': 'S3 not enabled'}), 404

    try:
        if folder not in ['avatars', 'attachments']:
            return jsonify({'error': 'Invalid folder'}), 403

        file_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=f'{folder}/{filename}')
        return Response(
            file_obj['Body'].read(),
            mimetype=file_obj.get('ContentType', 'application/octet-stream'),
            headers={'Cache-Control': 'public, max-age=31536000'}
        )
    except Exception as e:
        if 'NoSuchKey' in str(e):
            return jsonify({'error': 'File not found'}), 404
        return jsonify({'error': str(e)}), 500


@app.route('/api/note/<note_id>/attachments/<att_id>/file')
@login_required
def get_attachment_file(note_id, att_id):
    """Serve a note attachment only to the owning user."""
    user_id = session['user_id']
    note = db.get_note(user_id, note_id)
    if not note:
        return jsonify({'error': 'Note not found'}), 404

    att = db.get_attachment(note_id, att_id)
    if not att:
        return jsonify({'error': 'Attachment not found'}), 404

    s3_key = att.get('s3_key', '')
    if S3_ENABLED and s3_client:
        try:
            file_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            return Response(
                file_obj['Body'].read(),
                mimetype=file_obj.get('ContentType', att.get('file_type', 'application/octet-stream')),
                headers={'Cache-Control': 'private, max-age=31536000'}
            )
        except Exception as e:
            if 'NoSuchKey' in str(e):
                return jsonify({'error': 'File not found'}), 404
            return jsonify({'error': str(e)}), 500

    local_path = os.path.join(UPLOAD_FOLDER, s3_key)
    if not os.path.isfile(local_path):
        return jsonify({'error': 'File not found'}), 404

    from flask import send_file
    return send_file(local_path, mimetype=att.get('file_type', 'application/octet-stream'))


# =============================================================================
# ATTACHMENTS
# =============================================================================

@app.route('/api/note/<note_id>/attach', methods=['POST'])
@login_required
def attach_file(note_id):
    """Attach a file to a note."""
    user_id = session['user_id']

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No selected file'}), 400

    note = db.get_note(user_id, note_id)
    if not note:
        return jsonify({'error': 'Note not found'}), 404

    try:
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        content_type = file.mimetype or 'application/octet-stream'

        file_data = file.read()
        upload_file_to_storage(file_data, unique_filename, content_type, folder='attachments')
        s3_key = f"attachments/{unique_filename}"
        file_size = len(file_data)

        att = db.create_attachment(
            note_id=note_id,
            filename=original_filename,
            s3_key=s3_key,
            file_type=content_type,
            file_size=file_size,
        )

        file_url = url_for('get_attachment_file', note_id=note_id, att_id=att['att_id'])

        return jsonify({
            'success': True,
            'attachment': {
                'id': att['att_id'],
                'filename': original_filename,
                'url': file_url,
                'size': file_size,
                'type': content_type
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/note/<note_id>/attach/<att_id>', methods=['DELETE'])
@login_required
def delete_attachment_route(note_id, att_id):
    """Delete an attachment."""
    user_id = session['user_id']

    note = db.get_note(user_id, note_id)
    if not note:
        return jsonify({'error': 'Note not found'}), 404

    att = db.get_attachment(note_id, att_id)
    if not att:
        return jsonify({'error': 'Attachment not found'}), 404

    db.delete_attachment(note_id, att_id)

    if S3_ENABLED and s3_client:
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=att['s3_key'])
        except Exception:
            pass

    return jsonify({'success': True})


# =============================================================================
# NOTE CRUD
# =============================================================================

@app.route('/add', methods=['POST'])
@login_required
def add_note():
    """Create a new note."""
    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    category_id = request.form.get('category_id') or None

    if not content:
        flash('Note content cannot be empty!', 'error')
        return redirect(url_for('index'))

    try:
        db.create_note(user_id=user_id, title=title, content=content, category_id=category_id)
        flash('Note created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating note: {e}', 'error')

    return redirect(url_for('index'))


@app.route('/edit/<note_id>', methods=['POST'])
@login_required
def edit_note(note_id):
    """Update an existing note."""
    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    category_id = request.form.get('category_id') or ""

    if not content:
        flash('Note content cannot be empty!', 'error')
        return redirect(url_for('index'))

    try:
        db.update_note(user_id, note_id, title=title, content=content, category_id=category_id)
        flash('Note updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating note: {e}', 'error')

    return redirect(url_for('index'))


@app.route('/delete/<note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    """Permanently delete a note."""
    user_id = session['user_id']

    try:
        db.delete_note(user_id, note_id)
        flash('Note deleted permanently!', 'success')
    except Exception as e:
        flash(f'Error deleting note: {e}', 'error')

    return redirect(url_for('index'))


# =============================================================================
# PIN & ARCHIVE
# =============================================================================

@app.route('/pin/<note_id>', methods=['POST'])
@login_required
def toggle_pin(note_id):
    """Toggle pin status of a note."""
    user_id = session['user_id']
    db.toggle_pin(user_id, note_id)
    return redirect(url_for('index'))


@app.route('/archive/<note_id>', methods=['POST'])
@login_required
def toggle_archive(note_id):
    """Toggle archive status of a note."""
    user_id = session['user_id']
    db.toggle_archive(user_id, note_id)
    flash('Note archive status updated!', 'success')
    return redirect(url_for('index'))


# =============================================================================
# SHARE
# =============================================================================

@app.route('/api/note/<note_id>')
@login_required
def get_note_api(note_id):
    """Get note details (JSON) for modals."""
    user_id = session['user_id']

    note = db.get_note(user_id, note_id)
    if not note:
        return jsonify({'error': 'Note not found'}), 404

    attachments = db.list_attachments(note_id)
    formatted = []
    for att in attachments:
        att_url = url_for('get_attachment_file', note_id=note_id, att_id=att['att_id'])

        formatted.append({
            'id': att['att_id'],
            'filename': att['filename'],
            'url': att_url,
            'size': att.get('file_size', 0),
            'type': att.get('file_type', '')
        })

    note['content_html'] = render_markdown(note.get('content', ''))
    note['attachments'] = formatted
    # Map IDs for template compatibility
    note['id'] = note['note_id']

    return jsonify(note)


@app.route('/api/note/<note_id>/share', methods=['POST'])
@login_required
def api_share_note(note_id):
    """Enable sharing for a note and return the link."""
    user_id = session['user_id']

    token = db.share_note(user_id, note_id)
    if not token:
        return jsonify({'error': 'Note not found'}), 404

    share_url = build_share_url(token)
    return jsonify({'share_url': share_url, 'is_public': True})


@app.route('/api/note/<note_id>/share', methods=['DELETE'])
@login_required
def api_unshare_note(note_id):
    """Disable sharing for a note."""
    user_id = session['user_id']
    db.unshare_note(user_id, note_id)
    return jsonify({'success': True, 'is_public': False})


@app.route('/shared/<token>')
def view_shared(token):
    """View a publicly shared note."""
    note = db.get_shared_note(token)
    if not note:
        return render_template('shared.html', error="This note is not available or the link has expired."), 404
    note['content_html'] = render_markdown(note.get('content', ''))
    return render_template('shared.html', note=note)


# =============================================================================
# CATEGORIES
# =============================================================================

@app.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    """List and create categories."""
    user_id = session['user_id']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#6366f1')

        if name:
            try:
                db.create_category(user_id=user_id, name=name, color=color)
                flash('Category created!', 'success')
            except Exception as e:
                flash(f'Error creating category: {e}', 'error')

        return redirect(url_for('manage_categories'))

    categories = db.list_categories(user_id)
    return render_template('categories.html', categories=categories)


@app.route('/categories/<cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    """Delete a category."""
    user_id = session['user_id']
    db.delete_category(user_id, cat_id)
    flash('Category deleted!', 'success')
    return redirect(url_for('manage_categories'))


# =============================================================================
# EXPORT
# =============================================================================

@app.route('/export')
@login_required
def export_notes():
    """Export all notes as JSON or TXT."""
    user_id = session['user_id']
    format_type = request.args.get('format', 'json')

    notes = db.list_notes(user_id)
    # Also include archived
    archived = db.list_notes(user_id, archived=True)
    all_notes = notes + archived

    export_data = []
    for note in all_notes:
        export_data.append({
            'title': note.get('title', ''),
            'content': note.get('content', ''),
            'category': note.get('category_name'),
            'created_at': note.get('created_at'),
            'updated_at': note.get('updated_at'),
        })

    if format_type == 'txt':
        content = ""
        for note in export_data:
            content += f"{'=' * 50}\n"
            content += f"Title: {note['title'] or 'Untitled'}\n"
            content += f"Category: {note['category'] or 'None'}\n"
            content += f"Created: {note['created_at']}\n"
            content += f"{'=' * 50}\n"
            content += f"{note['content']}\n\n"

        return Response(
            content,
            mimetype='text/plain',
            headers={'Content-Disposition': 'attachment; filename=notes_export.txt'}
        )
    else:
        return Response(
            json.dumps(export_data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=notes_export.json'}
        )


# =============================================================================
# IMPORT
# =============================================================================

@app.route('/import', methods=['POST'])
@login_required
def import_notes():
    """Import notes from JSON or TXT file."""
    user_id = session['user_id']

    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('index'))

    file = request.files['file']
    if not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('index'))

    filename = file.filename.lower()
    content = file.read().decode('utf-8', errors='replace')
    notes_to_import = []

    if filename.endswith('.json'):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                notes_to_import = data
            elif isinstance(data, dict):
                notes_to_import = [data]
            else:
                flash('Invalid JSON format.', 'error')
                return redirect(url_for('index'))
        except json.JSONDecodeError:
            flash('Invalid JSON file.', 'error')
            return redirect(url_for('index'))

    elif filename.endswith('.txt'):
        blocks = re.split(r'={10,}', content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split('\n')
            note = {'title': '', 'content': '', 'category': None}
            content_lines = []
            for line in lines:
                if line.startswith('Title: '):
                    note['title'] = line[7:].strip()
                    if note['title'] == 'Untitled':
                        note['title'] = ''
                elif line.startswith('Category: '):
                    cat = line[10:].strip()
                    note['category'] = cat if cat != 'None' else None
                elif line.startswith('Created: '):
                    pass
                else:
                    content_lines.append(line)
            note['content'] = '\n'.join(content_lines).strip()
            if note['content']:
                notes_to_import.append(note)
    else:
        flash('Unsupported format. Use .json or .txt files.', 'error')
        return redirect(url_for('index'))

    if not notes_to_import:
        flash('No notes found in file.', 'error')
        return redirect(url_for('index'))

    try:
        categories = db.list_categories(user_id)
        cat_cache = {c['name'].lower(): c['cat_id'] for c in categories}
        imported = 0

        for note in notes_to_import:
            title = note.get('title', '').strip()
            note_content = note.get('content', '').strip()
            category_name = note.get('category')
            category_id = None

            if not note_content:
                continue

            if category_name:
                cat_key = category_name.lower()
                if cat_key in cat_cache:
                    category_id = cat_cache[cat_key]
                else:
                    new_cat = db.create_category(user_id=user_id, name=category_name)
                    category_id = new_cat['cat_id']
                    cat_cache[cat_key] = category_id

            db.create_note(user_id=user_id, title=title, content=note_content, category_id=category_id)
            imported += 1

        flash(f'Successfully imported {imported} note{"s" if imported != 1 else ""}!', 'success')
    except Exception as e:
        flash(f'Import error: {e}', 'error')

    return redirect(url_for('index'))


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/api/stats')
@login_required
def api_stats():
    """Get user statistics as JSON."""
    user_id = session['user_id']
    stats = db.get_stats(user_id)
    return jsonify(stats)


@app.route('/api/preview', methods=['POST'])
@login_required
def api_preview_markdown():
    """Render markdown for preview."""
    data = request.get_json()
    content = data.get('content', '')
    html = render_markdown(content)
    return jsonify({'html': html})


# =============================================================================
# MAIN (local dev only — Lambda uses lambda_handler.py)
# =============================================================================

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=debug_mode)
