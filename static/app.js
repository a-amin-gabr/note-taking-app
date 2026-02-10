document.addEventListener('DOMContentLoaded', () => {
    // Initialize components
    const shortcutsModal = document.getElementById('shortcuts-modal');

    initTheme();
    initEditModal();
    initKeyboardShortcuts();
    initLiveSearch();
    initDeleteConfirmation();
    initAutoFocus();

    // New Initializations
    initGreetingClock();
    initWordCount();
    initImportHandler();
    initEditTabs();
    initViewModal();
});

// ============================================
// Theme Toggle
// ============================================

function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const html = document.documentElement;
    const themeIcon = themeToggle.querySelector('.theme-icon');

    // Check saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    themeToggle.addEventListener('click', () => {
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';

        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    });

    function updateThemeIcon(theme) {
        // Moon icon for dark mode (default in HTML is moon?)
        // Actually the SVG path changes probably.
        // For simplicity, we just toggle class or let user handle SVGs if they were dynamic.
        // In this app, the icon is static in HTML, maybe CSS handles it?
        // Let's assume CSS handles it or we leave it as is.
    }
}

// ============================================
// Keyboard Shortcuts
// ============================================

function initKeyboardShortcuts() {
    const shortcutsModal = document.getElementById('shortcuts-modal');
    let isTyping = false;

    // Track typing status to disable shortcuts
    document.addEventListener('focusin', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            isTyping = true;
        }
    });

    document.addEventListener('focusout', () => {
        isTyping = false;
    });

    document.addEventListener('keydown', (e) => {
        const noteContent = document.getElementById('note-content');

        // Ctrl+K - Focus Search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('search-input');
            if (searchInput) searchInput.focus();
        }

        // Ctrl+T - Toggle Theme
        if (e.ctrlKey && e.key === 't') {
            e.preventDefault();
            const themeToggle = document.getElementById('theme-toggle');
            if (themeToggle) themeToggle.click();
        }

        // Ctrl+Enter - Submit note form
        if (e.ctrlKey && e.key === 'Enter') {
            if (noteContent && document.activeElement === noteContent) {
                e.preventDefault();
                noteContent.closest('form').submit();
            }

            // Also for edit modal
            const editContent = document.getElementById('edit-content');
            if (editContent && document.activeElement === editContent) {
                e.preventDefault();
                document.getElementById('edit-form').submit();
            }
        }

        // Escape - Close modals
        if (e.key === 'Escape') {
            closeAllModals();
        }

        // ? - Show shortcuts
        if (e.key === '?' && !isTyping) {
            e.preventDefault();
            if (shortcutsModal) {
                shortcutsModal.classList.toggle('active');
            }
        }
    });

    // Close shortcuts modal
    const shortcutsClose = document.querySelector('.shortcuts-close');
    if (shortcutsClose) {
        shortcutsClose.addEventListener('click', () => {
            shortcutsModal.classList.remove('active');
        });
    }
}

// ============================================
// Edit Modal
// ============================================

function initEditModal() {
    const modal = document.getElementById('edit-modal');
    const editForm = document.getElementById('edit-form');
    const closeBtn = document.getElementById('modal-close');
    const cancelBtn = document.getElementById('modal-cancel');

    if (!modal || !editForm) return;

    // Shared Open Modal Function
    const openModal = async (noteId, initialTab = 'raw') => {
        try {
            const response = await fetch(`/api/note/${noteId}`);
            if (!response.ok) throw new Error('Note not found');
            const note = await response.json();

            // Populate form
            document.getElementById('edit-title').value = note.title || '';
            document.getElementById('edit-content').value = note.content || '';

            const categorySelect = document.getElementById('edit-category');
            if (categorySelect && note.category_id) {
                categorySelect.value = note.category_id;
            }

            // Set form action
            editForm.action = `/edit/${noteId}`;

            // Show modal
            modal.classList.add('active');

            // Handle Tab Selection
            const tabRaw = document.getElementById('tab-raw');
            const tabPreview = document.getElementById('tab-preview');
            const noteContent = document.getElementById('edit-content');
            const previewDiv = document.getElementById('edit-preview');

            // Reset to Raw tab always upon opening edit
            // Unless specifically asked for preview (which we are not doing for edits anymore)
            if (tabRaw) tabRaw.click();
            document.getElementById('edit-content').focus();

        } catch (error) {
            console.error('Error loading note:', error);
            alert('Failed to load note');
        }
    };

    // Edit button click handlers
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent card click
            openModal(btn.dataset.noteId, 'raw');
        });
    });

    // Close handlers
    if (closeBtn) {
        closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => modal.classList.remove('active'));
    }

    // Click outside to close
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}

// ============================================
// View Modal (Read-Only)
// ============================================

function initViewModal() {
    const modal = document.getElementById('view-modal');
    const closeBtn = document.getElementById('view-modal-close');
    const editBtn = document.getElementById('view-edit-btn');

    if (!modal) return;

    const openViewModal = async (noteId) => {
        try {
            // Show loading state
            document.getElementById('view-content').innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Loading...</div>';
            document.getElementById('view-title').textContent = 'Loading...';
            modal.classList.add('active');

            const response = await fetch(`/api/note/${noteId}`);
            if (!response.ok) throw new Error('Note not found');
            const note = await response.json();

            // Populate content
            document.getElementById('view-title').textContent = note.title || 'Untitled Note';
            document.getElementById('view-content').innerHTML = note.content_html || '<p>No content</p>';

            // Populate metadata
            // Format: Feb 12, 2024 at 10:30 AM
            const dateStr = note.updated_at ? new Date(note.updated_at).toLocaleString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: 'numeric'
            }) : 'Unknown date';
            document.getElementById('view-date').textContent = `Last active: ${dateStr}`;

            const catSpan = document.getElementById('view-category');
            if (note.category_name) {
                catSpan.textContent = note.category_name;
                catSpan.style.color = note.category_color || 'var(--text-secondary)';
                catSpan.style.display = 'inline';
            } else {
                catSpan.style.display = 'none';
            }

            // Setup Edit Button
            if (editBtn) {
                // Clear previous listeners to avoid duplicates if using addEventListener
                // Or just use onclick property
                editBtn.onclick = () => {
                    modal.classList.remove('active');
                    // Find the edit button for this note and click it
                    const cardEditBtn = document.querySelector(`.edit-btn[data-note-id="${noteId}"]`);
                    if (cardEditBtn) cardEditBtn.click();
                };
            }

        } catch (error) {
            console.error('Error viewing note:', error);
            document.getElementById('view-content').innerHTML = '<div style="color: var(--error); padding: 1rem;">Failed to load note.</div>';
        }
    };

    // Card click handlers
    document.querySelectorAll('.note-card').forEach(card => {
        card.addEventListener('click', (e) => {
            // Ignore if clicking interactive elements
            if (e.target.closest('button') || e.target.closest('a') || e.target.closest('.note-actions-bar') || e.target.closest('.delete-form')) return;

            const btn = card.querySelector('.edit-btn');
            if (btn) {
                openViewModal(btn.dataset.noteId);
            }
        });
    });

    // Close handlers
    if (closeBtn) {
        closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    }

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });

    // Esc key is handled globally
}

// ============================================
// Edit Tabs (Raw/Preview)
// ============================================

function initEditTabs() {
    const tabRaw = document.getElementById('tab-raw');
    const tabPreview = document.getElementById('tab-preview');
    const noteContent = document.getElementById('edit-content');
    const previewDiv = document.getElementById('edit-preview');

    if (!tabRaw || !tabPreview) return;

    tabRaw.addEventListener('click', () => {
        tabRaw.classList.add('active');
        tabPreview.classList.remove('active');
        noteContent.classList.remove('hidden');
        previewDiv.classList.add('hidden');
        noteContent.focus();
    });

    tabPreview.addEventListener('click', async () => {
        tabPreview.classList.add('active');
        tabRaw.classList.remove('active');
        noteContent.classList.add('hidden');
        previewDiv.classList.remove('hidden');

        // Show loading state
        previewDiv.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Loading preview...</div>';

        try {
            const response = await fetch('/api/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: noteContent.value })
            });

            if (!response.ok) throw new Error('Preview failed');

            const data = await response.json();
            previewDiv.innerHTML = data.html;
        } catch (error) {
            console.error('Preview error:', error);
            previewDiv.innerHTML = '<div style="color: var(--error); padding: 1rem;">Failed to load preview</div>';
        }
    });
}

function closeAllModals() {
    document.querySelectorAll('.modal.active').forEach(modal => {
        modal.classList.remove('active');
    });
}

// ============================================
// Delete Confirmation
// ============================================

function initDeleteConfirmation() {
    document.querySelectorAll('.delete-form').forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!confirm('Are you sure you want to delete this note permanently?')) {
                e.preventDefault();
            }
        });
    });
}

// ============================================
// Auto Focus
// ============================================

function initAutoFocus() {
    // Auto-focus search if query exists
    const searchInput = document.getElementById('search-input');
    if (searchInput && searchInput.value) {
        searchInput.focus();
        searchInput.select();
    }
}

// ============================================
// Live Search (Optional - for client-side filtering)
// ============================================

function initLiveSearch() {
    const searchInput = document.getElementById('search-input');
    const noteCards = document.querySelectorAll('.note-card');

    if (!searchInput || !noteCards.length) return;

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();

        noteCards.forEach(card => {
            const title = card.querySelector('.note-title')?.textContent.toLowerCase() || '';
            const content = card.querySelector('.note-content')?.textContent.toLowerCase() || '';

            if (title.includes(query) || content.includes(query)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    });
}

// ============================================
// Flash Message Auto-dismiss
// ============================================

setTimeout(() => {
    document.querySelectorAll('.flash').forEach(flash => {
        flash.style.transition = 'opacity 0.5s ease';
        flash.style.opacity = '0';
        setTimeout(() => flash.remove(), 500);
    });
}, 5000);

// ============================================
// Greeting Clock
// ============================================

function initGreetingClock() {
    const clockEl = document.getElementById('greeting-clock');
    const greetingEl = document.getElementById('greeting-message');
    if (!clockEl) return;

    const timezone = document.body.dataset.timezone || 'UTC';

    function updateClock() {
        const now = new Date();
        const opts = { timeZone: timezone };

        // Greeting based on hour
        const hour = parseInt(now.toLocaleString('en-US', { ...opts, hour: 'numeric', hour12: false }));
        let greeting = 'Good evening';
        if (hour >= 5 && hour < 12) greeting = 'Good morning';
        else if (hour >= 12 && hour < 17) greeting = 'Good afternoon';

        if (greetingEl) {
            const name = greetingEl.textContent.split(',')[1] || '';
            greetingEl.textContent = `${greeting},${name}`;
        }

        // Format: Mon, Feb 10 · 07:14 AM
        const dateStr = now.toLocaleDateString('en-US', {
            ...opts,
            weekday: 'short',
            month: 'short',
            day: 'numeric'
        });
        const timeStr = now.toLocaleTimeString('en-US', {
            ...opts,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        });

        clockEl.textContent = `${dateStr} \u00b7 ${timeStr}`;
    }

    updateClock();
    setInterval(updateClock, 1000);
}

// ============================================
// Word Count
// ============================================

function initWordCount() {
    const textarea = document.getElementById('note-content');
    const counter = document.getElementById('word-count');
    if (!textarea || !counter) return;

    function update() {
        const text = textarea.value.trim();
        const words = text ? text.split(/\s+/).length : 0;
        const chars = textarea.value.length;
        counter.textContent = `${words} word${words !== 1 ? 's' : ''} \u00b7 ${chars} character${chars !== 1 ? 's' : ''}`;
    }

    textarea.addEventListener('input', update);
    update();
}

// ============================================
// Import Handler
// ============================================

function initImportHandler() {
    const fileInput = document.getElementById('import-file');
    const form = document.getElementById('import-form');
    if (!fileInput || !form) return;

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const ext = file.name.split('.').pop().toLowerCase();
            if (ext !== 'json' && ext !== 'txt') {
                alert('Please select a .json or .txt file');
                fileInput.value = '';
                return;
            }
            if (confirm(`Import notes from "${file.name}"?`)) {
                form.submit();
            } else {
                fileInput.value = '';
            }
        }
    });
}
