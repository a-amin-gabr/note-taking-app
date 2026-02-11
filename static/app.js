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
    initShareModal();
    initMobileMenu();
});

// ============================================
// Theme Toggle
// ============================================

function initTheme() {
    const html = document.documentElement;
    const toggles = [
        document.getElementById('theme-toggle'),
        document.getElementById('theme-toggle-mobile')
    ].filter(el => el !== null);

    // Check saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-theme', savedTheme);

    toggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    });
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
    const btnAttach = document.getElementById('btn-attach');
    const attachInput = document.getElementById('attach-input');
    const attachmentList = document.getElementById('attachment-list');
    const editStatus = document.getElementById('edit-status');

    if (!modal || !editForm) return;

    // Helper to format bytes
    const formatBytes = (bytes, decimals = 2) => {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    };

    // Helper: Insert text at cursor position (Undo-Safe)
    const insertAtCursor = (text) => {
        const textarea = document.getElementById('edit-content');
        if (!textarea) return;

        textarea.focus();

        // Use execCommand to preserve undo history (Standard for text editors)
        // Although deprecated, it is the only reliable way to handle undo stack programmatically
        const success = document.execCommand('insertText', false, text);

        // Fallback if execCommand fails (e.g. some mobile browsers)
        if (!success) {
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const before = textarea.value.substring(0, start);
            const after = textarea.value.substring(end);
            textarea.value = before + text + after;
            textarea.selectionStart = textarea.selectionEnd = start + text.length;
            textarea.dispatchEvent(new Event('input'));
        }
    };

    // Helper to render attachment item
    const createAttachmentEl = (att, isReadOnly = false) => {
        const div = document.createElement('div');
        div.className = 'attachment-item';
        div.id = `att-${att.id}`;

        // File Icon based on type
        let icon = '<svg class="icon" viewBox="0 0 24 24"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/></svg>';
        let isImage = false;

        if (att.type?.startsWith('image/')) {
            isImage = true;
            // Use the actual image as the icon
            icon = `<img src="${att.url}" alt="${att.filename}" class="attachment-thumbnail">`;
        }

        div.innerHTML = `
            <div class="attachment-icon">${icon}</div>
            <a href="${att.url}" target="_blank" title="${att.filename}">${att.filename}</a>
            <span class="att-size">(${formatBytes(att.size || 0)})</span>
            ${!isReadOnly ? `
            <button type="button" class="delete-att-btn" data-id="${att.id}" title="Remove attachment">
                <svg class="icon" viewBox="0 0 24 24" style="width:16px;height:16px"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>` : ''}
        `;

        if (!isReadOnly) {
            const delBtn = div.querySelector('.delete-att-btn');
            delBtn.addEventListener('click', async (e) => {
                e.stopPropagation(); // Prevent insert trigger
                if (!confirm('Remove this attachment?')) return;
                const noteId = editForm.dataset.noteId;
                try {
                    const res = await fetch(`/api/note/${noteId}/attach/${att.id}`, { method: 'DELETE' });
                    const data = await res.json();
                    if (data.success) {
                        div.remove();
                    } else {
                        alert('Failed to delete attachment: ' + (data.error || 'Unknown error'));
                    }
                } catch (e) {
                    console.error(e);
                    alert('Error deleting attachment');
                }
            });

            // Click to Insert Logic
            div.addEventListener('click', () => {
                const md = att.type?.startsWith('image/') ?
                    `![${att.filename}](${att.url})` :
                    `[${att.filename}](${att.url})`;

                if (typeof insertAtCursor === 'function') {
                    insertAtCursor(md);
                    // Visual feedback
                    const originalBg = div.style.backgroundColor;
                    div.style.backgroundColor = 'var(--bg-card-hover)';
                    div.style.borderColor = 'var(--success)';
                    setTimeout(() => {
                        div.style.backgroundColor = originalBg;
                        div.style.borderColor = '';
                    }, 300);
                }
            });

            div.title = "Click to insert into note";
        }
        return div;
    };

    // Shared Open Modal Function
    const openModal = async (noteId, initialTab = 'raw') => {
        try {
            // Reset UI
            editForm.reset();
            attachmentList.innerHTML = '';
            editForm.dataset.noteId = noteId;
            editStatus.textContent = '';

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

            // Populate attachments
            if (note.attachments && note.attachments.length > 0) {
                note.attachments.forEach(att => {
                    attachmentList.appendChild(createAttachmentEl(att));
                });
            }

            // Set form action
            editForm.action = `/edit/${noteId}`;

            // Show modal
            modal.classList.add('active');

            // Handle Tab Selection
            const tabRaw = document.getElementById('tab-raw');
            if (tabRaw) tabRaw.click();
            document.getElementById('edit-content').focus();

        } catch (error) {
            console.error('Error loading note:', error);
            alert('Failed to load note');
        }
    };

    // Attachment Upload Handler
    if (btnAttach && attachInput) {
        btnAttach.addEventListener('click', () => attachInput.click());

        attachInput.addEventListener('change', async () => {
            if (!attachInput.files.length) return;
            const file = attachInput.files[0];
            const noteId = editForm.dataset.noteId;

            if (!noteId) return;

            // Show loading spinner
            const originalBtnContent = btnAttach.innerHTML;
            btnAttach.innerHTML = '<span class="spinner-sm"></span>';
            btnAttach.disabled = true;
            editStatus.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(`/api/note/${noteId}/attach`, {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (data.success && data.attachment) {
                    // Add to list
                    const el = createAttachmentEl(data.attachment);
                    attachmentList.appendChild(el);

                    // Add Click-to-Insert for new item
                    el.addEventListener('click', (e) => {
                        if (e.target.closest('.delete-att-btn')) return;
                        const md = data.attachment.type.startsWith('image/') ?
                            `![${data.attachment.filename}](${data.attachment.url})` :
                            `[${data.attachment.filename}](${data.attachment.url})`;
                        insertAtCursor(md);
                    });

                    // Auto-Insert at Cursor
                    const md = data.attachment.type.startsWith('image/') ?
                        `![${data.attachment.filename}](${data.attachment.url})` :
                        `[${data.attachment.filename}](${data.attachment.url})`;
                    insertAtCursor(md);

                    editStatus.textContent = 'Attached & Link Inserted';
                    setTimeout(() => editStatus.textContent = '', 3000);
                } else {
                    alert('Upload failed: ' + (data.error || 'Unknown error'));
                    editStatus.textContent = 'Failed';
                }
            } catch (e) {
                console.error(e);
                alert('Upload error');
                editStatus.textContent = 'Error';
            } finally {
                btnAttach.innerHTML = originalBtnContent;
                btnAttach.disabled = false;
                attachInput.value = ''; // Reset input
            }
        });
    }

    // Edit button click handlers
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent card click
            openModal(btn.dataset.noteId, 'raw');
        });
    });

    // Close handlers
    if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.remove('active'));
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });

    // Validating global 'openEditModal' if needed, but we use event listeners
    // If we wanted to expose it:
    // window.openEditModal = openModal;
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

            // Populate attachments
            const viewAttachments = document.getElementById('view-attachments');
            viewAttachments.innerHTML = '';
            if (note.attachments && note.attachments.length > 0) {
                note.attachments.forEach(att => {
                    // Re-use rendering logic? We defined it in initEditModal scope...
                    // We should duplicates or move helper to global scope.
                    // For now, duplicate simple rendering for read-only
                    const div = document.createElement('div');
                    div.className = 'attachment-item';

                    let icon = '<svg class="icon" viewBox="0 0 24 24"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/></svg>';
                    if (att.type?.startsWith('image/')) {
                        icon = '<svg class="icon" viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>';
                    }

                    div.innerHTML = `
                        ${icon}
                        <a href="${att.url}" target="_blank" title="${att.filename}">${att.filename}</a>
                        <span class="att-size" style="margin-left:auto">(${Math.round((att.size || 0) / 1024)} KB)</span>
                    `;
                    viewAttachments.appendChild(div);
                });
                viewAttachments.style.display = 'flex';
            } else {
                viewAttachments.style.display = 'none';
            }

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

// ============================================
// Share Modal
// ============================================

function initShareModal() {
    const modal = document.getElementById('share-modal');
    const closeBtn = document.getElementById('share-modal-close');
    const privateState = document.getElementById('share-private-state');
    const publicState = document.getElementById('share-public-state');
    const linkInput = document.getElementById('share-link-input');
    const generateBtn = document.getElementById('btn-generate-link');
    const copyBtn = document.getElementById('btn-copy-link');
    const stopBtn = document.getElementById('btn-stop-sharing');

    if (!modal) return;

    let currentNoteId = null;

    // Open Modal
    const openShareModal = async (noteId) => {
        currentNoteId = noteId;
        modal.classList.add('active');

        // Reset and Show Loading
        privateState.classList.add('hidden');
        publicState.classList.add('hidden');

        try {
            const response = await fetch(`/api/note/${noteId}`);
            if (!response.ok) throw new Error('Note not found');
            const note = await response.json();

            if (note.is_public && note.share_token) {
                // Show Public State
                publicState.classList.remove('hidden');
                linkInput.value = `${window.location.origin}/shared/${note.share_token}`;
            } else {
                // Show Private State
                privateState.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error sharing note:', error);
            alert('Failed to load share status');
            modal.classList.remove('active');
        }
    };

    // Card Button Listeners
    const cardBtns = document.querySelectorAll('.share-btn');
    cardBtns.forEach(btn => {
        // Remove existing listener if any? No, init calls are once.
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // prevent opening preview
            openShareModal(btn.dataset.noteId);
        });
    });

    // Generate Link
    if (generateBtn) {
        generateBtn.onclick = async () => {
            if (!currentNoteId) return;
            generateBtn.disabled = true;
            const originalText = generateBtn.innerHTML;
            generateBtn.innerHTML = 'Generating...';

            try {
                const res = await fetch(`/api/note/${currentNoteId}/share`, { method: 'POST' });
                const data = await res.json();

                if (data.share_url) {
                    privateState.classList.add('hidden');
                    publicState.classList.remove('hidden');
                    linkInput.value = data.share_url;

                    // Update icon on card instantly without reload
                    const cardBtn = document.querySelector(`.share-btn[data-note-id="${currentNoteId}"]`);
                    if (cardBtn) {
                        cardBtn.innerHTML = `
                            <svg class="icon" viewBox="0 0 24 24">
                                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                            </svg>`;
                    }
                }
            } catch (error) {
                console.error(error);
                alert('Failed to generate link');
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = `
                        <svg class="icon" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/></svg>
                        Generate Public Link`;
            }
        };
    }

    // Stop Sharing
    if (stopBtn) {
        stopBtn.onclick = async () => {
            if (!confirm('Are you sure? The link will stop working for everyone.')) return;
            stopBtn.disabled = true;

            try {
                const res = await fetch(`/api/note/${currentNoteId}/share`, { method: 'DELETE' });
                const data = await res.json();

                if (data.success) {
                    publicState.classList.add('hidden');
                    privateState.classList.remove('hidden');

                    // Update icon on card
                    const cardBtn = document.querySelector(`.share-btn[data-note-id="${currentNoteId}"]`);
                    if (cardBtn) {
                        cardBtn.innerHTML = `
                            <svg class="icon" viewBox="0 0 24 24">
                                <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                            </svg>`;
                    }
                }
            } catch (error) {
                console.error(error);
                alert('Failed to stop sharing');
            } finally {
                stopBtn.disabled = false;
            }
        };
    }

    // Copy Link
    if (copyBtn) {
        copyBtn.onclick = () => {
            linkInput.select();
            document.execCommand('copy');

            // Visual feedback
            const originalHTML = copyBtn.innerHTML;
            copyBtn.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; // Checkmark
            copyBtn.classList.add('btn-success');

            setTimeout(() => {
                copyBtn.innerHTML = originalHTML;
                copyBtn.classList.remove('btn-success');
            }, 2000);
        };
    }

    // Close handlers
    if (closeBtn) {
        closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    }

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}

// ============================================
// Mobile Menu
// ============================================

function initMobileMenu() {
    const toggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (!toggle || !sidebar || !overlay) return;

    const toggleMenu = () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
    };

    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleMenu();
    });

    overlay.addEventListener('click', toggleMenu);

    // Close sidebar on link click
    sidebar.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('button')) {
            // Don't close for theme toggle if it's in sidebar (desktop only but safe)
            if (e.target.closest('#theme-toggle')) return;

            if (sidebar.classList.contains('open')) {
                toggleMenu();
            }
        }
    });
}
