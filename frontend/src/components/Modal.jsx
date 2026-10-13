import { useEffect, useId, useRef } from 'react';
import PropTypes from 'prop-types';

/**
 * Accessible dialog: focuses the first field on open, closes on Escape or
 * backdrop click, returns focus to whatever opened it.
 */
export default function Modal({
  title, description, onClose, children, footer, wide,
}) {
  const titleId = useId();
  const panel = useRef(null);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });

  // Runs once on open (not on every render, which would steal focus while typing)
  useEffect(() => {
    const previouslyFocused = document.activeElement;
    const focusable = panel.current?.querySelector('input, select, textarea, button:not(.icon-button)');
    (focusable || panel.current)?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') closeRef.current();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, []);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div
        className={`modal ${wide ? 'modal--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={panel}
        tabIndex={-1}
      >
        <div className="modal-head">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">×</button>
        </div>
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

Modal.propTypes = {
  title: PropTypes.node.isRequired,
  description: PropTypes.node,
  onClose: PropTypes.func.isRequired,
  children: PropTypes.node,
  footer: PropTypes.node,
  wide: PropTypes.bool,
};

/** Yes/no confirmation built on Modal. */
export function ConfirmDialog({
  title, message, confirmLabel, danger, busy, error, onConfirm, onClose,
}) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={(
        <>
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className={`button ${danger ? 'button--danger' : 'button--primary'}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </>
      )}
    >
      <p>{message}</p>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
    </Modal>
  );
}

ConfirmDialog.propTypes = {
  title: PropTypes.node.isRequired,
  message: PropTypes.node.isRequired,
  confirmLabel: PropTypes.string.isRequired,
  danger: PropTypes.bool,
  busy: PropTypes.bool,
  error: PropTypes.string,
  onConfirm: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};
