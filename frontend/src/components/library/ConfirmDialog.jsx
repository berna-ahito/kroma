export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
  isBusy = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null

  return (
    <div className="confirm-overlay" role="presentation">
      <div
        className="confirm-box"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-message"
      >
        <div className="confirm-title" id="confirm-title">{title}</div>
        <div className="confirm-msg" id="confirm-message">{message}</div>
        <div className="confirm-btns">
          <button
            type="button"
            className="btn-secondary confirm-cancel"
            onClick={onCancel}
            disabled={isBusy}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn-primary confirm-action${danger ? ' is-danger' : ''}`}
            onClick={onConfirm}
            disabled={isBusy}
          >
            {isBusy ? 'Working...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
