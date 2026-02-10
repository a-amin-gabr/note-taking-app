"""
Note-Taking App - Enhanced Flask Application
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
import mysql.connector
from mysql.connector import Error
import markdown
import bleach
# Load environment variables
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# AWS S3 configuration (optional)
S3_BUCKET = os.getenv('S3_BUCKET', '')
S3_REGION = os.getenv('S3_REGION', os.getenv('AWS_REGION', 'us-east-1'))
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


def upload_file_to_storage(file_data, filename, content_type='image/jpeg'):
    """Upload file to S3 if available, otherwise save locally. Returns URL."""
    if S3_ENABLED and s3_client:
        try:
            key = f"avatars/{filename}"
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=file_data,
                ContentType=content_type
            )
            return url_for('get_s3_avatar', filename=filename)
        except Exception as e:
            print(f"S3 upload failed, falling back to local: {e}")
    
    # Local fallback
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, 'wb') as f:
        f.write(file_data)
    return f"/static/uploads/{filename}"
# Import and register auth blueprint
from auth import auth_bp, login_required, get_current_user
app.register_blueprint(auth_bp)
# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'notes_db'),
    'port': int(os.getenv('DB_PORT', 3306))
}
# Allowed HTML tags for markdown
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
def get_db_connection():
    """Create and return a database connection."""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MariaDB: {e}")
        return None
def init_db():
    """Initialize database tables."""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cognito_sub VARCHAR(255) UNIQUE,
                email VARCHAR(255),
                display_name VARCHAR(100),
                first_name VARCHAR(50),
                last_name VARCHAR(50),
                bio TEXT,
                avatar_url VARCHAR(512),
                timezone VARCHAR(50) DEFAULT 'UTC',
                profile_complete BOOLEAN DEFAULT FALSE,
                is_guest BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(50) NOT NULL,
                color VARCHAR(7) DEFAULT '#6366f1',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                category_id INT,
                title VARCHAR(255) DEFAULT '',
                content TEXT NOT NULL,
                is_pinned BOOLEAN DEFAULT FALSE,
                is_archived BOOLEAN DEFAULT FALSE,
                is_public BOOLEAN DEFAULT FALSE,
                share_token VARCHAR(64) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        connection.commit()
    except Error as e:
        print(f"Error initializing database: {e}")
    finally:
        cursor.close()
        connection.close()
def render_markdown(text):
    """Convert markdown to sanitized HTML."""
    html = markdown.markdown(text, extensions=[
        'extra',        # Tables, fenced code, footnotes, attrib, def types
        'nl2br',        # Newlines to <br>
        'sane_lists',   # Better list handling
        'smarty'        # Smart quotes
    ])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
# =============================================================================
# MAIN ROUTES
# =============================================================================
@app.route('/')
@login_required
def index():
    """Display all notes with filters."""
    user_id = session['user_id']
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '')
    show_archived = request.args.get('archived', '0') == '1'
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return render_template('index.html', notes=[], categories=[], stats={})
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get categories
        cursor.execute('SELECT * FROM categories WHERE user_id = %s ORDER BY name', (user_id,))
        categories = cursor.fetchall()
        
        # Build notes query
        query = '''
            SELECT n.*, c.name as category_name, c.color as category_color
            FROM notes n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.user_id = %s AND n.is_archived = %s
        '''
        params = [user_id, show_archived]
        
        if search_query:
            query += ' AND (n.title LIKE %s OR n.content LIKE %s)'
            search_term = f'%{search_query}%'
            params.extend([search_term, search_term])
        
        if category_filter:
            query += ' AND n.category_id = %s'
            params.append(category_filter)
        
        query += ' ORDER BY n.is_pinned DESC, n.updated_at DESC'
        
        cursor.execute(query, params)
        notes = cursor.fetchall()
        
        # Render markdown for each note
        for note in notes:
            note['content_html'] = render_markdown(note['content'])
        
        # Get statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_archived = FALSE THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN is_pinned = TRUE THEN 1 ELSE 0 END) as pinned,
                SUM(CASE WHEN is_archived = TRUE THEN 1 ELSE 0 END) as archived
            FROM notes WHERE user_id = %s
        ''', (user_id,))
        stats = cursor.fetchone()
        
        user = get_current_user()
        
        return render_template('index.html', 
                             notes=notes, 
                             categories=categories, 
                             stats=stats,
                             user=user,
                             search_query=search_query,
                             category_filter=category_filter,
                             show_archived=show_archived)
    except Error as e:
        flash(f'Error loading notes: {e}', 'error')
        return render_template('index.html', notes=[], categories=[], stats={})
    finally:
        cursor.close()
        connection.close()
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
    
    # If profile already complete, go to profile page
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
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('profile'))
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE users SET 
                first_name = %s,
                last_name = %s,
                display_name = %s,
                bio = %s,
                timezone = %s,
                profile_complete = TRUE
            WHERE id = %s
        ''', (first_name, last_name, display_name, bio, timezone, user_id))
        connection.commit()
        
        # Update session
        session['display_name'] = display_name
        
        flash('Profile updated successfully!', 'success')
    except Error as e:
        flash(f'Error updating profile: {e}', 'error')
    finally:
        cursor.close()
        connection.close()
    
    # If was setup, redirect to dashboard
    if request.form.get('is_setup') == 'true':
        return redirect(url_for('index'))
    
    return redirect(url_for('profile'))


@app.route('/profile/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload and save user avatar (accepts base64 or file upload)."""
    user_id = session['user_id']
    avatar_url = None

    # Handle base64 upload (from client-side compression)
    if request.is_json:
        data = request.get_json()
        image_data = data.get('image', '')
        if not image_data:
            return jsonify({'error': 'No image data'}), 400

        # Parse data URI
        match = re.match(r'data:image/(\w+);base64,(.*)', image_data)
        if not match:
            return jsonify({'error': 'Invalid image format'}), 400

        ext = match.group(1)
        if ext == 'jpeg':
            ext = 'jpg'
        raw = base64.b64decode(match.group(2))

        filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
        avatar_url = upload_file_to_storage(raw, filename, f'image/{ext}')

    # Handle multipart file upload
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

    # Save to database
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute('UPDATE users SET avatar_url = %s WHERE id = %s', (avatar_url, user_id))
            connection.commit()
            if request.is_json:
                return jsonify({'url': avatar_url, 'message': 'Avatar updated!'})
            flash('Avatar updated!', 'success')
        except Error as e:
            if request.is_json:
                return jsonify({'error': str(e)}), 500
            flash(f'Error saving avatar: {e}', 'error')
        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('profile'))


@app.route('/s3/avatars/<path:filename>')
@login_required
def get_s3_avatar(filename):
    """Serve S3 avatar through the backend (proxy)."""
    if not S3_ENABLED or not s3_client:
        return jsonify({'error': 'S3 not enabled'}), 404
    
    try:
        # Fetch from S3
        file_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=f'avatars/{filename}')
        
        # Stream response
        return Response(
            file_obj['Body'].read(),
            mimetype=file_obj.get('ContentType', 'image/jpeg'),
            headers={
                'Cache-Control': 'public, max-age=31536000'
            }
        )
    except Exception as e:
        # Check if 404
        if 'NoSuchKey' in str(e):
             return jsonify({'error': 'File not found'}), 404
        return jsonify({'error': str(e)}), 500


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
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('index'))
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            'INSERT INTO notes (user_id, title, content, category_id) VALUES (%s, %s, %s, %s)',
            (user_id, title, content, category_id)
        )
        connection.commit()
        flash('Note created successfully!', 'success')
    except Error as e:
        flash(f'Error creating note: {e}', 'error')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('index'))
@app.route('/edit/<int:note_id>', methods=['POST'])
@login_required
def edit_note(note_id):
    """Update an existing note."""
    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    category_id = request.form.get('category_id') or None
    
    if not content:
        flash('Note content cannot be empty!', 'error')
        return redirect(url_for('index'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('index'))
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            '''UPDATE notes SET title = %s, content = %s, category_id = %s, 
               updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s''',
            (title, content, category_id, note_id, user_id)
        )
        connection.commit()
        flash('Note updated successfully!', 'success')
    except Error as e:
        flash(f'Error updating note: {e}', 'error')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('index'))
@app.route('/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    """Permanently delete a note."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('index'))
    
    try:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM notes WHERE id = %s AND user_id = %s', (note_id, user_id))
        connection.commit()
        flash('Note deleted permanently!', 'success')
    except Error as e:
        flash(f'Error deleting note: {e}', 'error')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('index'))
# =============================================================================
# PIN & ARCHIVE
# =============================================================================
@app.route('/pin/<int:note_id>', methods=['POST'])
@login_required
def toggle_pin(note_id):
    """Toggle pin status of a note."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                'UPDATE notes SET is_pinned = NOT is_pinned WHERE id = %s AND user_id = %s',
                (note_id, user_id)
            )
            connection.commit()
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('index'))
@app.route('/archive/<int:note_id>', methods=['POST'])
@login_required
def toggle_archive(note_id):
    """Toggle archive status of a note."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                'UPDATE notes SET is_archived = NOT is_archived, is_pinned = FALSE WHERE id = %s AND user_id = %s',
                (note_id, user_id)
            )
            connection.commit()
            flash('Note archive status updated!', 'success')
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('index'))
# =============================================================================
# SHARE
# =============================================================================
@app.route('/share/<int:note_id>', methods=['POST'])
@login_required
def toggle_share(note_id):
    """Generate or remove share link for a note."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT is_public, share_token FROM notes WHERE id = %s AND user_id = %s', (note_id, user_id))
            note = cursor.fetchone()
            
            if note:
                if note['is_public']:
                    # Remove sharing
                    cursor.execute(
                        'UPDATE notes SET is_public = FALSE, share_token = NULL WHERE id = %s',
                        (note_id,)
                    )
                    flash('Note is now private.', 'info')
                else:
                    # Enable sharing
                    token = secrets.token_urlsafe(32)
                    cursor.execute(
                        'UPDATE notes SET is_public = TRUE, share_token = %s WHERE id = %s',
                        (token, note_id)
                    )
                    share_url = url_for('view_shared', token=token, _external=True)
                    flash(f'Share link: {share_url}', 'success')
                
                connection.commit()
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('index'))
@app.route('/shared/<token>')
def view_shared(token):
    """View a publicly shared note."""
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            '''SELECT n.*, c.name as category_name, c.color as category_color
               FROM notes n LEFT JOIN categories c ON n.category_id = c.id
               WHERE n.share_token = %s AND n.is_public = TRUE''',
            (token,)
        )
        note = cursor.fetchone()
        
        if not note:
            flash('Note not found or no longer shared.', 'error')
            return redirect(url_for('auth.login'))
        
        note['content_html'] = render_markdown(note['content'])
        return render_template('shared.html', note=note)
    finally:
        cursor.close()
        connection.close()
# =============================================================================
# CATEGORIES
# =============================================================================
@app.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    """List and create categories."""
    user_id = session['user_id']
    connection = get_db_connection()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#6366f1')
        
        if name and connection:
            try:
                cursor = connection.cursor()
                cursor.execute(
                    'INSERT INTO categories (user_id, name, color) VALUES (%s, %s, %s)',
                    (user_id, name, color)
                )
                connection.commit()
                flash('Category created!', 'success')
            finally:
                cursor.close()
        
        return redirect(url_for('manage_categories'))
    
    categories = []
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT * FROM categories WHERE user_id = %s ORDER BY name', (user_id,))
            categories = cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
    
    return render_template('categories.html', categories=categories)
@app.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    """Delete a category."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute('DELETE FROM categories WHERE id = %s AND user_id = %s', (cat_id, user_id))
            connection.commit()
            flash('Category deleted!', 'success')
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('manage_categories'))
# =============================================================================
# EXPORT
# =============================================================================
@app.route('/export')
@login_required
def export_notes():
    """Export all notes as JSON."""
    user_id = session['user_id']
    format_type = request.args.get('format', 'json')
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('index'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            '''SELECT n.title, n.content, n.created_at, n.updated_at, c.name as category
               FROM notes n LEFT JOIN categories c ON n.category_id = c.id
               WHERE n.user_id = %s ORDER BY n.created_at DESC''',
            (user_id,)
        )
        notes = cursor.fetchall()
        
        # Convert datetime to string
        for note in notes:
            note['created_at'] = note['created_at'].isoformat() if note['created_at'] else None
            note['updated_at'] = note['updated_at'].isoformat() if note['updated_at'] else None
        
        if format_type == 'txt':
            # Plain text format
            content = ""
            for note in notes:
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
            # JSON format
            return Response(
                json.dumps(notes, indent=2),
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=notes_export.json'}
            )
    finally:
        cursor.close()
        connection.close()


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
        # Parse TXT format matching our export
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
                    pass  # skip timestamp
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

    connection = get_db_connection()
    if not connection:
        flash('Database connection failed.', 'error')
        return redirect(url_for('index'))

    try:
        cursor = connection.cursor(dictionary=True)
        imported = 0

        # Build category cache
        cursor.execute('SELECT id, name FROM categories WHERE user_id = %s', (user_id,))
        cat_cache = {row['name'].lower(): row['id'] for row in cursor.fetchall()}

        for note in notes_to_import:
            title = note.get('title', '').strip()
            note_content = note.get('content', '').strip()
            category_name = note.get('category')
            category_id = None

            if not note_content:
                continue

            # Resolve or create category
            if category_name:
                cat_key = category_name.lower()
                if cat_key in cat_cache:
                    category_id = cat_cache[cat_key]
                else:
                    cursor.execute(
                        'INSERT INTO categories (user_id, name) VALUES (%s, %s)',
                        (user_id, category_name)
                    )
                    category_id = cursor.lastrowid
                    cat_cache[cat_key] = category_id

            cursor.execute(
                'INSERT INTO notes (user_id, title, content, category_id) VALUES (%s, %s, %s, %s)',
                (user_id, title, note_content, category_id)
            )
            imported += 1

        connection.commit()
        flash(f'Successfully imported {imported} note{"s" if imported != 1 else ""}!', 'success')
    except Error as e:
        flash(f'Import error: {e}', 'error')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('index'))


# API ENDPOINTS
# =============================================================================
@app.route('/api/stats')
@login_required
def api_stats():
    """Get user statistics as JSON."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute('''
            SELECT 
                COUNT(*) as total_notes,
                SUM(CASE WHEN is_archived = FALSE THEN 1 ELSE 0 END) as active_notes,
                SUM(CASE WHEN is_pinned = TRUE THEN 1 ELSE 0 END) as pinned_notes,
                SUM(CASE WHEN is_archived = TRUE THEN 1 ELSE 0 END) as archived_notes,
                SUM(LENGTH(content)) as total_characters
            FROM notes WHERE user_id = %s
        ''', (user_id,))
        stats = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) as count FROM categories WHERE user_id = %s', (user_id,))
        cat_count = cursor.fetchone()
        stats['total_categories'] = cat_count['count']
        
        return jsonify(stats)
    finally:
        cursor.close()
        connection.close()


@app.route('/api/preview', methods=['POST'])
@login_required
def api_preview_markdown():
    """Render markdown for preview."""
    data = request.get_json()
    content = data.get('content', '')
    html = render_markdown(content)
    return jsonify({'html': html})


@app.route('/api/note/<int:note_id>')
@login_required
def api_get_note(note_id):
    """Get single note as JSON for editing."""
    user_id = session['user_id']
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            'SELECT * FROM notes WHERE id = %s AND user_id = %s',
            (note_id, user_id)
        )
        note = cursor.fetchone()
        
        if note:
            note['created_at'] = note['created_at'].isoformat() if note['created_at'] else None
            note['updated_at'] = note['updated_at'].isoformat() if note['updated_at'] else None
            note['content_html'] = render_markdown(note['content'])
            return jsonify(note)
        return jsonify({'error': 'Note not found'}), 404
    finally:
        cursor.close()
        connection.close()
# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    init_db()
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=debug_mode)
 