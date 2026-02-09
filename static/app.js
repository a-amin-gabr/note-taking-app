/**
 * Note Taking App - JavaScript
 * Theme toggle, keyboard shortcuts, edit modal, live search
 */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initMobileMenu();
    initKeyboardShortcuts();
    initEditModal();
    initDeleteConfirmation();
    initAutoFocus();
});

// ============================================
// Theme Toggle
// ============================================

function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeToggleMobile = document.getElementById('theme-toggle-mobile');
    const html = document.documentElement;

    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    html.setAttribute('data-theme', savedTheme);

    const toggleTheme = () => {
        const current = html.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    };

    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    if (themeToggleMobile) {
        themeToggleMobile.addEventListener('click', toggleTheme);
    }
}

// ============================================
// Mobile Menu
// ============================================

function initMobileMenu() {
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (!menuToggle || !sidebar) return;

    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('active');
    });

    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }
}

// ============================================
// Keyboard Shortcuts
// ============================================

function initKeyboardShortcuts() {
    const searchInput = document.getElementById('search-input');
    const noteContent = document.getElementById('note-content');
    const shortcutsModal = document.getElementById('shortcuts-modal');

    document.addEventListener('keydown', (e) => {
        // Don't trigger shortcuts when typing in inputs
        const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);

        // Ctrl+K - Focus search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            if (searchInput) searchInput.focus();
        }

        // Ctrl+T - Toggle theme
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

    // Edit button click handlers
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const noteId = btn.dataset.noteId;

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
                document.getElementById('edit-content').focus();
            } catch (error) {
                console.error('Error loading note:', error);
                alert('Failed to load note for editing');
            }
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
