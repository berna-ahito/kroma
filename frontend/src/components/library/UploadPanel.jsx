export default function UploadPanel({
  onUpload,
  onProcess,
  uploading,
  processing,
  uploadError,
  uploadMessage,
  processError,
  processMessage,
}) {
  return (
    <>
      <div className="sidebar-label">Upload</div>
      <label className="upload-area" id="uploadArea">
        <input
          type="file"
          id="fileInput"
          accept=".pdf,.txt,.md,.markdown"
          multiple
          style={{ display: 'none' }}
          onChange={onUpload}
          disabled={uploading || processing}
        />
        <svg className="upload-icon ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/>
          <path d="M14 2v5h5"/>
          <path d="M9 13h6"/>
          <path d="M9 17h4"/>
        </svg>
        <span className="upload-title">{uploading ? 'Uploading...' : 'Click or drag to upload'}</span>
        <span className="upload-hint">{uploading ? 'Please wait...' : 'PDF, TXT, Markdown · 25MB max'}</span>
      </label>
      {uploadError && <div style={{ color: 'var(--danger-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{uploadError}</div>}
      {uploadMessage && <div style={{ color: 'var(--warning-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{uploadMessage}</div>}

      <button
        className="btn-primary"
        id="processBtn"
        onClick={onProcess}
        disabled={uploading || processing}
        style={{ marginTop: '0.75rem' }}
      >
        {processing ? 'Processing...' : 'Process Documents'}
      </button>
      {processError && <div style={{ color: 'var(--danger-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{processError}</div>}
      {processMessage && <div style={{ color: 'var(--warning-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{processMessage}</div>}
    </>
  )
}
