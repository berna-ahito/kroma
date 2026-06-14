export default function HistoryList({
  savedChats,
  loadedChatId,
  onLoadChat,
  onDeleteHistoryChat,
  onClearHistory,
}) {
  return (
    <>
      <div className="sidebar-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>History</span>
        {savedChats.length > 0 && (
          <button
            style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: '0.7rem', cursor: 'pointer', fontFamily: "'Outfit',sans-serif" }}
            onClick={onClearHistory}
          >
            Clear
          </button>
        )}
      </div>
      <div className="library-list" id="historyList">
        {savedChats.length === 0 ? (
          <span className="empty-lib">No saved chats yet.</span>
        ) : (
          savedChats.map(chat => (
            <div
              key={chat.id}
              className="history-item"
              onClick={() => onLoadChat(chat)}
              style={{
                background: chat.id === loadedChatId ? 'var(--surface-2)' : 'var(--bg)',
                borderColor: chat.id === loadedChatId ? 'var(--primary)' : 'var(--border)'
              }}
            >
              <div className="history-info">
                <div className="history-title">{chat.title}</div>
                <div className="history-date">
                  {new Date(chat.updatedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                </div>
              </div>
              <button
                className="history-delete"
                onClick={(e) => onDeleteHistoryChat(chat.id, e)}
                title="Delete chat"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none">
                  <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
                </svg>
              </button>
            </div>
          ))
        )}
      </div>
    </>
  )
}
