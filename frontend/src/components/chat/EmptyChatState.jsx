export default function EmptyChatState() {
  return (
    <div className="empty-state" id="emptyState">
      <svg className="empty-icon ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <path d="M7 12h10"/>
        <path d="M7 16h6"/>
      </svg>
      <h3>Ask your documents anything</h3>
      <p>No processed documents are available. Upload and process a document first.</p>
      <div className="steps">
        <div className="step">
          <span className="step-num">1</span>
          <span>Upload a supported file from your computer</span>
        </div>
        <div className="step">
          <span className="step-num">2</span>
          <span>Click <strong style={{ color: 'var(--primary-hover)' }}>Process Documents</strong> to prepare your files</span>
        </div>
        <div className="step">
          <span className="step-num">3</span>
          <span>Ask questions and review the cited sources</span>
        </div>
      </div>
    </div>
  )
}
