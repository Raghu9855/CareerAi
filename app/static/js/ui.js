/**
 * CareerAI — UI & Interaction System
 * Implements Toast notifications, Apple-style confirmation sheets,
 * modal lifecycle management, and fluid Drag-and-Drop for Kanban.
 */

const UI = (() => {
  // -------------------------------------------------------------
  // TOAST NOTIFICATIONS (Replaces browser alert)
  // -------------------------------------------------------------
  function getToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(message, type = 'info', duration = 3500) {
    const container = getToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    } else if (type === 'error') {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-exit');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 250);
    }, duration);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // -------------------------------------------------------------
  // CONFIRMATION DIALOG (Replaces browser confirm)
  // -------------------------------------------------------------
  function showConfirm(title, message, confirmText = 'Confirm', isDestructive = false) {
    return new Promise((resolve) => {
      const modal = document.getElementById('modal-confirm');
      if (!modal) {
        resolve(window.confirm(`${title}\n\n${message}`));
        return;
      }

      document.getElementById('confirm-title').textContent = title;
      document.getElementById('confirm-message').textContent = message;
      
      const confirmBtn = document.getElementById('confirm-action-btn');
      confirmBtn.textContent = confirmText;
      confirmBtn.className = isDestructive ? 'btn btn-danger' : 'btn btn-primary';

      const cancelBtn = document.getElementById('confirm-cancel-btn');

      const cleanup = () => {
        closeModal('modal-confirm');
        confirmBtn.removeEventListener('click', onConfirm);
        cancelBtn.removeEventListener('click', onCancel);
      };

      const onConfirm = () => {
        cleanup();
        resolve(true);
      };

      const onCancel = () => {
        cleanup();
        resolve(false);
      };

      confirmBtn.addEventListener('click', onConfirm);
      cancelBtn.addEventListener('click', onCancel);

      openModal('modal-confirm');
    });
  }

  // -------------------------------------------------------------
  // MODAL MANAGEMENT
  // -------------------------------------------------------------
  function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
      // Focus first input or button
      const focusable = modal.querySelector('input:not([type="hidden"]), select, textarea, button:not(.modal-close-btn)');
      if (focusable) focusable.focus();
    }
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
    }
  }

  // Global ESC handler for modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const openModalEl = document.querySelector('.modal-backdrop.open');
      if (openModalEl) {
        closeModal(openModalEl.id);
      }
    }
  });

  // -------------------------------------------------------------
  // KANBAN DRAG & DROP ENGINE
  // -------------------------------------------------------------
  let draggedCardId = null;

  function initKanbanDragAndDrop(onCardMoved) {
    const columns = document.querySelectorAll('.pipeline-column');

    columns.forEach(col => {
      col.addEventListener('dragover', (e) => {
        e.preventDefault();
        col.classList.add('drag-over');
      });

      col.addEventListener('dragleave', (e) => {
        // Prevent child element flickering
        if (!col.contains(e.relatedTarget)) {
          col.classList.remove('drag-over');
        }
      });

      col.addEventListener('drop', (e) => {
        e.preventDefault();
        col.classList.remove('drag-over');
        const targetStage = col.getAttribute('data-stage');
        if (draggedCardId && targetStage) {
          onCardMoved(draggedCardId, targetStage);
        }
      });
    });
  }

  function makeCardDraggable(cardEl, appId) {
    cardEl.setAttribute('draggable', 'true');

    cardEl.addEventListener('dragstart', (e) => {
      draggedCardId = appId;
      cardEl.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', appId);
    });

    cardEl.addEventListener('dragend', () => {
      draggedCardId = null;
      cardEl.classList.remove('dragging');
      document.querySelectorAll('.pipeline-column').forEach(c => c.classList.remove('drag-over'));
    });
  }

  return {
    showToast,
    showConfirm,
    openModal,
    closeModal,
    escapeHtml,
    initKanbanDragAndDrop,
    makeCardDraggable
  };
})();
