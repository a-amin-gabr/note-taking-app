"""
Note-Taking App - Enhanced Flask Application
Features: Categories, Search, Pin, Archive, Markdown, Export, Attachments
"""
import os
import secrets
import json
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
ALLOWED_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'a', 'br']
ALLOWED_ATTRS = {'a': ['href', 'title']}
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
    html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
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
 