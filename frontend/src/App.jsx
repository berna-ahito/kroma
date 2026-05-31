import React, { useState, useRef, useEffect } from 'react'
import { sendChat, getStatus } from './api/kromaApi.js'
import SourceList from './components/chat/SourceList.jsx'
import SafeMarkdown from './components/chat/SafeMarkdown.jsx'

// Stable unique id for React keys — no external lib needed
function genId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : String(Date.now() + Math.random())
}

export default function App() {
  const [inputValue, setInputValue] = useState('')
  const [messages,   setMessages]   = useState([])
  const [isLoading,  setIsLoading]  = useState(false)
  const [error,      setError]      = useState(null)

  // Status state — fetched once on mount
  const [status,        setStatus]        = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError,   setStatusError]   = useState(null)

  const chatEndRef   = useRef(null)
  const textareaRef  = useRef(null)

  // Auto-scroll: fires when a new message arrives or loading state changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Textarea auto-resize: collapse first so deletions shrink the box
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [inputValue])

  // Fetch backend status on mount (read-only, no refresh on chat send)
  useEffect(() => {
    let cancelled = false
    setStatusLoading(true)
    setStatusError(null)
    getStatus()
      .then(data => {
        if (!cancelled) {
          setStatus(data)
          setStatusLoading(false)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setStatusError(err.message || 'Failed to load status')
          setStatusLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  // Derived values from status
  const docCount   = status?.docs?.length ?? 0
  const pageCount  = status?.stats?.total_pages ?? 0
  const chunkCount = status?.stats?.total_chunks ?? 0
  const docList    = status?.docs ?? []

  async function handleSend() {
    const trimmed = inputValue.trim()
    if (!trimmed || isLoading) return

    // Capture prior messages BEFORE appending the new user message.
    // history = prior turns only; current question is sent separately.
    const priorMessages = messages.map(({ role, content }) => ({ role, content }))

    const userMsg = { id: genId(), role: 'user', content: trimmed }

    setMessages(prev => [...prev, userMsg])
    setInputValue('')
    // Reset textarea height so it returns to single-row after send
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setError(null)
    setIsLoading(true)

    try {
      const data = await sendChat({
        question: trimmed,
        history: priorMessages,
        selectedDocs: [],
      })
      const answer = data?.answer ?? 'No response received.'
      const sources = data?.sources ?? []
      const showSources = Boolean(data?.show_sources) && sources.length > 0
      const assistantMsg = { id: genId(), role: 'assistant', content: answer, sources, showSources }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    // Shift+Enter: browser inserts newline — no code needed
  }

  const canSend = inputValue.trim() !== '' && !isLoading

  return (
    <>
      {/* SIDEBAR */}
      <aside className="sidebar">
        <a href="/" className="logo" style={{ textDecoration: 'none', padding: '0.25rem 0' }}>
          <svg width="100%" height="80" viewBox="140 55 400 120" role="img">
            <rect x="155" y="60" width="90" height="90" rx="20" fill="#1c1917" stroke="#eab308" strokeWidth="2"/>
            <path d="M175 78 L223 78 L237 92 L237 138 L175 138 Z" fill="#292524" stroke="#3c3330" strokeWidth="1"/>
            <path d="M223 78 L223 92 L237 92 Z" fill="#1c1917" stroke="#3c3330" strokeWidth="1"/>
            <rect x="188" y="92" width="7" height="34" rx="2" fill="#eab308"/>
            <path d="M195 109 L209 94" stroke="#eab308" strokeWidth="7" strokeLinecap="round" fill="none"/>
            <path d="M195 109 L211 126" stroke="#eab308" strokeWidth="7" strokeLinecap="round" fill="none"/>
            <line x1="188" y1="132" x2="205" y2="132" stroke="#eab308" strokeWidth="2" strokeLinecap="round" opacity="0.8"/>
            <line x1="188" y1="137" x2="217" y2="137" stroke="#eab308" strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
            <line x1="188" y1="142" x2="211" y2="142" stroke="#eab308" strokeWidth="2" strokeLinecap="round" opacity="0.3"/>
            <text x="262" y="122" fontFamily="'Outfit', sans-serif" fontSize="58" fontWeight="800" fill="#fafaf9" letterSpacing="-2">Kroma</text>
            <circle cx="270" cy="72" r="5" fill="#eab308"/>
            <text x="265" y="152" fontFamily="'DM Mono', monospace" fontSize="13" fontWeight="500" fill="#eab308" letterSpacing="4">ASK. LEARN. KNOW.</text>
          </svg>
        </a>

        <div className="sidebar-label">Demo access</div>
        <input
          id="demoKeyInput"
          type="password"
          placeholder="Demo key if required"
          autoComplete="off"
          style={{
            width: '100%',
            background: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            color: 'var(--text)',
            padding: '0.65rem 0.75rem',
            fontFamily: "'Outfit',sans-serif",
            fontSize: '0.9rem',
            outline: 'none'
          }}
          readOnly
        />

        <hr className="divider" />

        <div className="sidebar-label">Upload</div>
        <label className="upload-area" id="uploadArea">
          <input type="file" id="fileInput" accept=".pdf,.txt,.md,.markdown" multiple style={{ display: 'none' }} disabled />
          <svg className="upload-icon ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/>
            <path d="M14 2v5h5"/>
            <path d="M9 13h6"/>
            <path d="M9 17h4"/>
          </svg>
          <span className="upload-title">Click or drag to upload</span>
          <span className="upload-hint">PDF, TXT, Markdown · 25MB max</span>
        </label>

        <button className="btn-primary" id="processBtn">
          Process Documents
        </button>

        <hr className="divider" />

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
              <div key={filename} style={{ padding: '0.25rem 0', fontSize: '0.85rem', color: 'var(--text-2)', wordBreak: 'break-all' }}>
                {filename}
              </div>
            ))
          )}
        </div>

        <hr className="divider" />

        <div className="btn-row">
          <button className="btn-secondary">Clear all</button>
          <button className="btn-secondary">New chat</button>
        </div>

        <hr className="divider" />

        <div className="sidebar-label">Tools</div>
        <button className="btn-primary" id="flashcardBtn">
          <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M8 6h11"/>
            <path d="M8 12h11"/>
            <path d="M8 18h11"/>
            <path d="M4 6h.01"/>
            <path d="M4 12h.01"/>
            <path d="M4 18h.01"/>
          </svg>
          <span>Flashcards</span>
        </button>
        <button className="btn-primary" id="quizBtn" style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
          <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <circle cx="12" cy="12" r="9"/>
            <path d="M9.5 9a2.5 2.5 0 0 1 4.5 1.5c0 1.8-2 2.2-2 3.5"/>
            <path d="M12 17h.01"/>
          </svg>
          <span>Quiz me</span>
        </button>
        <button className="btn-primary" id="summaryBtn" style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
          <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M9 4h6"/>
            <path d="M9 4a2 2 0 0 0-2 2v1h10V6a2 2 0 0 0-2-2"/>
            <path d="M7 7H5v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7h-2"/>
            <path d="M9 13h6"/>
            <path d="M9 17h4"/>
          </svg>
          <span>Summarize</span>
        </button>
        <button className="btn-primary" id="businessCopilotBtn" style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
          <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <rect x="4" y="6" width="16" height="13" rx="2" stroke="currentColor" fill="none" strokeWidth="2" strokeLinejoin="round"/>
            <path d="M4 11 L20 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <path d="M10 6 L10 19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <span>Knowledge Copilot</span>
        </button>
        <button className="btn-primary" id="knowledgeAuditBtn" style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
          <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" fill="none" strokeWidth="2" strokeLinejoin="round"/>
            <path d="M14 2v6h6" stroke="currentColor" fill="none" strokeWidth="2" strokeLinejoin="round"/>
            <path d="M9 15l2 2 4-4" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>Knowledge Audit</span>
        </button>

        <hr className="divider" />
        <div className="sidebar-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>History</span>
          <button style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: '0.7rem', cursor: 'pointer', fontFamily: "'Outfit',sans-serif" }}>Clear</button>
        </div>
        <div className="library-list" id="historyList">
          <span className="empty-lib">No saved chats yet.</span>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="main">
        <div className="topbar">
          <div>
            <div className="topbar-title" id="topbarTitle">Kroma</div>
            <div className="topbar-sub" id="topbarSub">Your source-grounded study assistant</div>
          </div>
          <button className="btn-secondary" id="exportBtn" style={{ width: 'auto', padding: '0.5rem 1.25rem', display: 'none', flexShrink: 0, whiteSpace: 'nowrap', maxWidth: '140px' }}>
            <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 3v12"/>
              <path d="m7 10 5 5 5-5"/>
              <path d="M5 21h14"/>
            </svg>
            <span>Export Chat</span>
          </button>
        </div>

        {/* METRICS */}
        <div className="metrics" id="metrics">
          <div className="metric-card">
            <span className="label">Documents</span>
            <span className="value" id="metDocs">{statusLoading ? '…' : docCount}</span>
          </div>
          <div className="metric-card">
            <span className="label">Pages</span>
            <span className="value" id="metPages">{statusLoading ? '…' : pageCount}</span>
          </div>
          <div className="metric-card">
            <span className="label">Chunks</span>
            <span className="value" id="metChunks">{statusLoading ? '…' : chunkCount}</span>
          </div>
        </div>

        {/* CHAT AREA */}
        <div className="chat-wrapper" id="chatWrapper">

          {/* Empty state — hidden once messages exist */}
          {messages.length === 0 && !isLoading && (
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
                  <span>Click <strong style={{ color: 'var(--gold)' }}>Process Documents</strong> to prepare your files</span>
                </div>
                <div className="step">
                  <span className="step-num">3</span>
                  <span>Ask questions and review the cited sources</span>
                </div>
              </div>
            </div>
          )}

          {/* Message list */}
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

          {/* Loading indicator — reuses existing .thinking / .dots CSS */}
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

          {/* Error banner */}
          {error && (
            <div
              role="alert"
              aria-live="assertive"
              style={{
                background: 'rgba(127,29,29,0.25)',
                border: '1px solid #7f1d1d',
                borderRadius: '10px',
                color: '#fca5a5',
                padding: '0.75rem 1rem',
                fontSize: '0.9rem',
                lineHeight: 1.5,
              }}
            >
              {error}
            </div>
          )}

          {/* Auto-scroll sentinel — scrollIntoView targets this element */}
          <div ref={chatEndRef} aria-hidden="true" />
        </div>

        {/* INPUT BAR */}
        <div className="input-bar">
          <textarea
            ref={textareaRef}
            id="chatInput"
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your documents..."
            rows={1}
            disabled={isLoading}
            aria-label="Chat input"
          />
          <button
            className="btn-send"
            id="sendBtn"
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            title="Send message"
          >
            <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 19V5"/>
              <path d="m5 12 7-7 7 7"/>
            </svg>
          </button>
        </div>
      </main>
    </>
  )
}

