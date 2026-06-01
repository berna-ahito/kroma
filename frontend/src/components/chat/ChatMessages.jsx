import SafeMarkdown from './SafeMarkdown.jsx'
import SourceList from './SourceList.jsx'

export default function ChatMessages({ messages, isLoading, chatEndRef, children }) {
  return (
    <>
      {messages.map(msg => (
        <div
          key={msg.id}
          className={`message${msg.role === 'user' ? ' user' : ''}`}
        >
          <div className={`avatar${msg.role === 'user' ? ' user' : ' ai'}`}>
            {msg.role === 'user' ? 'YOU' : 'AI'}
          </div>
          <div className="bubble">
            {msg.role === 'assistant'
              ? <SafeMarkdown content={msg.content} />
              : msg.content
            }
            {msg.role === 'assistant' && msg.showSources && msg.sources.length > 0 && (
              <SourceList sources={msg.sources} />
            )}
          </div>
        </div>
      ))}

      {isLoading && (
        <div className="thinking" aria-live="polite" aria-label="Loading response">
          <div className="dots" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span>Thinking…</span>
        </div>
      )}

      {children}

      <div ref={chatEndRef} aria-hidden="true" />
    </>
  )
}
