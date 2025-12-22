/**
 * File Converter SaaS - Main JavaScript
 */

// CSRF Token helper for Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Global file upload handler
function initUploadArea(uploadAreaId, fileInputId, filePreviewId, fileNameId) {
    const uploadArea = document.getElementById(uploadAreaId);
    const fileInput = document.getElementById(fileInputId);
    const filePreview = document.getElementById(filePreviewId);
    const fileName = document.getElementById(fileNameId);

    if (!uploadArea || !fileInput) return;

    uploadArea.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            fileInput.click();
        }
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            fileInput.dispatchEvent(new Event('change'));
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length && filePreview && fileName) {
            const files = fileInput.files;
            if (files.length === 1) {
                fileName.textContent = files[0].name;
            } else {
                fileName.textContent = `${files.length} files selected`;
            }
            filePreview.hidden = false;
            const content = uploadArea.querySelector('.upload-content');
            if (content) content.hidden = true;
        }
    });
}

// Format file size
function formatSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format duration
function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// API helper
async function apiRequest(url, formData) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        const contentType = response.headers.get('content-type');

        if (contentType && contentType.includes('application/json')) {
            return {
                ok: response.ok,
                data: await response.json()
            };
        } else {
            return {
                ok: response.ok,
                blob: await response.blob()
            };
        }
    } catch (error) {
        return {
            ok: false,
            error: error.message
        };
    }
}

// Initialize on DOM ready - DO NOT auto-init upload areas
// Each page handles its own file input logic to prevent conflicts
document.addEventListener('DOMContentLoaded', () => {
    // Removed auto-init: initUploadArea('upload-area', 'file-input', 'file-preview', 'file-name');
    // Pages use label-based file inputs which don't need JS click handlers
});
