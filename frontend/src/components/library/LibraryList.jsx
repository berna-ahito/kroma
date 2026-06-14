export default function LibraryList({
  statusLoading,
  statusError,
  docList,
  selectedDocs,
  onToggleDoc,
  onDeleteDoc,
  deletingDoc,
  libraryBusy,
  deleteError,
  deleteMessage,
  clearError,
  clearMessage,
  onClearLibrary,
  clearing,
  children,
}) {
  return (
    <>
      <div className="sidebar-label">Library</div>
      <div className="library-list" id="libraryList">
        {statusLoading ? (
          <span className="empty-lib">Loading…</span>
        ) : statusError ? (
          <span className="empty-lib">Unable to load library.</span>
        ) : docList.length === 0 ? (
          <span className="empty-lib">No documents yet.</span>
        ) : (
          docList.map(filename => (
            <div key={filename} style={{ padding: '0.25rem 0', fontSize: '0.85rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', wordBreak: 'break-all' }}>
                <input
                  type="checkbox"
                  checked={selectedDocs.includes(filename)}
                  onChange={() => onToggleDoc(filename)}
                  disabled={libraryBusy}
                />
                {filename}
              </label>
              <button
                className="btn-delete"
                onClick={() => onDeleteDoc(filename)}
                disabled={libraryBusy}
                type="button"
                title={deletingDoc === filename ? `Deleting ${filename}` : `Delete ${filename}`}
                aria-label={deletingDoc === filename ? `Deleting ${filename}` : `Delete ${filename}`}
              >
                <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" strokeWidth="2" fill="none" aria-hidden="true" focusable="false">
                  <path d="M3 6h18"/>
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                  <path d="M10 11v6"/>
                  <path d="M14 11v6"/>
                </svg>
              </button>
            </div>
          ))
        )}
      </div>
      {deleteError && <div style={{ color: 'var(--danger-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{deleteError}</div>}
      {deleteMessage && <div style={{ color: 'var(--warning-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{deleteMessage}</div>}

      <hr className="divider" />

      <div className="btn-row">
        <button
          className="btn-secondary"
          onClick={onClearLibrary}
          disabled={libraryBusy || docList.length === 0}
        >
          {clearing ? 'Clearing...' : 'Clear library'}
        </button>
        {children}
      </div>
      {clearError && <div style={{ color: 'var(--danger-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{clearError}</div>}
      {clearMessage && <div style={{ color: 'var(--warning-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{clearMessage}</div>}
    </>
  )
}
