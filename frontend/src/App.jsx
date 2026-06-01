import React, { useState, useRef, useEffect, useMemo } from 'react'
import { sendChat, getStatus, uploadDocument, processDocuments, deleteDocument, clearLibrary, generateSuggestions, generateSummary, generateFlashcards, generateQuiz, runKnowledgeCopilot, runKnowledgeAudit } from './api/kromaApi.js'
import { setDemoKey } from './api/demoKey.js'
import SourceList from './components/chat/SourceList.jsx'
import SafeMarkdown from './components/chat/SafeMarkdown.jsx'
import MetricsBar from './components/chat/MetricsBar.jsx'
import ExportButton from './components/chat/ExportButton.jsx'
import KromaLogo from './components/layout/KromaLogo.jsx'
import DemoKeyPanel from './components/library/DemoKeyPanel.jsx'
import UploadPanel from './components/library/UploadPanel.jsx'
import LibraryList from './components/library/LibraryList.jsx'
import ToolButtons from './components/library/ToolButtons.jsx'
import HistoryList from './components/history/HistoryList.jsx'
import SummaryView from './components/study/SummaryView.jsx'
import FlashcardsView from './components/study/FlashcardsView.jsx'
import QuizView from './components/study/QuizView.jsx'
import KnowledgeCopilotView from './components/business/KnowledgeCopilotView.jsx'
import KnowledgeAuditView from './components/business/KnowledgeAuditView.jsx'

// Stable unique id for React keys — no external lib needed
function genId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : String(Date.now() + Math.random())
}

const MAX_SELECTED_DOCS = 25
const EMPTY_DOC_LIST = []

function getUploadedFilenames(response, fallbackName) {
  const candidates = [
    response?.filename,
    response?.file_name,
    response?.name,
    response?.filenames,
    response?.files,
    response?.docs,
    response?.documents,
  ].flat()

  const names = candidates
    .map(item => (typeof item === 'string' ? item : item?.filename || item?.file_name || item?.name))
    .filter(Boolean)

  return names.length ? names : [fallbackName]
}

export default function App() {
  const [currentView, setCurrentView] = useState('chat')
  const [studyLoading, setStudyLoading] = useState(false)
  const [studyError, setStudyError] = useState(null)
  const [summaryData, setSummaryData] = useState(null)
  const [flashcardData, setFlashcardData] = useState(null)
  const [quizData, setQuizData] = useState(null)

  const [businessLoading, setBusinessLoading] = useState(false)
  const [businessError, setBusinessError] = useState(null)
  const [copilotData, setCopilotData] = useState(null)
  const [auditData, setAuditData] = useState(null)

  const [inputValue, setInputValue] = useState('')
  const [messages,   setMessages]   = useState([])
  const [isLoading,  setIsLoading]  = useState(false)
  const [error,      setError]      = useState(null)

  // Status state — fetched once on mount
  const [status,        setStatus]        = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError,   setStatusError]   = useState(null)
  const [demoKeyInput,  setDemoKeyInput]  = useState('')
  const [demoKeyMessage, setDemoKeyMessage] = useState(null)

  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadMessage, setUploadMessage] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [processError, setProcessError] = useState(null)
  const [processMessage, setProcessMessage] = useState(null)

  const [selectedDocs, setSelectedDocs] = useState([])
  const [deletingDoc, setDeletingDoc] = useState(null)
  const [deleteError, setDeleteError] = useState(null)
  const [deleteMessage, setDeleteMessage] = useState(null)
  const [clearing, setClearing] = useState(false)
  const [clearError, setClearError] = useState(null)
  const [clearMessage, setClearMessage] = useState(null)

  // Suggestions state
  const [suggestions, setSuggestions] = useState([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionsError, setSuggestionsError] = useState(null)

  // History state
  const [savedChats, setSavedChats] = useState([])
  const [loadedChatId, setLoadedChatId] = useState(null)

  const libraryBusy = uploading || processing || Boolean(deletingDoc) || clearing
  const studyBusy = studyLoading || uploading || processing || Boolean(deletingDoc) || clearing || isLoading

  const chatWrapperRef = useRef(null)
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

  const fetchStatus = async () => {
    setStatusLoading(true)
    setStatusError(null)
    try {
      const data = await getStatus()
      setStatus(data)
    } catch (err) {
      setStatusError(err.message || 'Failed to load status')
    } finally {
      setStatusLoading(false)
    }
  }

  // Fetch backend status on mount (read-only, no refresh on chat send in R3B)
  useEffect(() => {
    fetchStatus()
  }, [])

  const applyDemoKey = async () => {
    const value = demoKeyInput.trim()
    setDemoKey(value)
    setDemoKeyInput('')
    setDemoKeyMessage(value ? 'Demo key saved for this session.' : 'Demo key cleared for this session.')
    await fetchStatus()
  }

  const clearDemoKey = async () => {
    setDemoKey('')
    setDemoKeyInput('')
    setDemoKeyMessage('Demo key cleared for this session.')
    await fetchStatus()
  }

  useEffect(() => {
    if (!uploadMessage) return undefined
    const timer = window.setTimeout(() => setUploadMessage(null), 4000)
    return () => window.clearTimeout(timer)
  }, [uploadMessage])

  useEffect(() => {
    if (!processMessage) return undefined
    const timer = window.setTimeout(() => setProcessMessage(null), 4000)
    return () => window.clearTimeout(timer)
  }, [processMessage])

  useEffect(() => {
    if (!deleteMessage) return undefined
    const timer = window.setTimeout(() => setDeleteMessage(null), 4000)
    return () => window.clearTimeout(timer)
  }, [deleteMessage])

  useEffect(() => {
    if (!clearMessage) return undefined
    const timer = window.setTimeout(() => setClearMessage(null), 4000)
    return () => window.clearTimeout(timer)
  }, [clearMessage])

  // Derived values from status
  const docCount   = status?.docs?.length ?? 0
  const pageCount  = status?.stats?.total_pages ?? 0
  const chunkCount = status?.stats?.total_chunks ?? 0
  const docList    = status?.docs ?? EMPTY_DOC_LIST
  const isIndexed  = Boolean(status?.indexed)
  const docNames   = useMemo(() => new Set(docList), [docList])
  const activeSelectedDocs = useMemo(
    () => selectedDocs.filter(filename => docNames.has(filename)),
    [selectedDocs, docNames]
  )

  useEffect(() => {
    if (selectedDocs.length !== activeSelectedDocs.length) {
      setSelectedDocs(activeSelectedDocs)
    }
  }, [selectedDocs, activeSelectedDocs])

  // --- HISTORY HELPERS ---
  const getSavedChats = () => {
    try {
      const stored = localStorage.getItem('kroma_chat_history')
      if (stored) return JSON.parse(stored)
    } catch (err) {}
    return []
  }

  const setSavedChatsSafe = (chats) => {
    try {
      localStorage.setItem('kroma_chat_history', JSON.stringify(chats))
      setSavedChats(chats)
    } catch (err) {}
  }

  useEffect(() => {
    setSavedChats(getSavedChats())
  }, [])

  const saveCurrentChat = (msgs, chatId) => {
    if (msgs.length === 0) return null
    let history = getSavedChats()
    let currentId = chatId
    if (!currentId) {
      currentId = genId()
    }
    const userMsg = msgs.find(m => m.role === 'user')
    const title = userMsg ? userMsg.content.slice(0, 50) : 'Untitled chat'
    
    const existingIndex = history.findIndex(h => h.id === currentId)
    const chatEntry = {
      id: currentId,
      title,
      createdAt: existingIndex >= 0 ? history[existingIndex].createdAt : new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages: msgs.map(m => {
        const msgData = { id: m.id, role: m.role, content: m.content }
        if (m.role === 'assistant') {
          msgData.sources = m.sources || []
          msgData.showSources = Boolean(m.showSources)
        }
        return msgData
      })
    }
    
    if (existingIndex >= 0) {
      history[existingIndex] = chatEntry
    } else {
      history.unshift(chatEntry)
    }
    
    if (history.length > 20) history = history.slice(0, 20)
    setSavedChatsSafe(history)
    return currentId
  }

  const loadChat = (entry) => {
    if (messages.length > 0) {
      saveCurrentChat(messages, loadedChatId)
    }
    setMessages(entry.messages || [])
    setLoadedChatId(entry.id)
    setInputValue('')
    setError(null)
  }

  const deleteHistoryChat = (id, e) => {
    if (e) e.stopPropagation()
    const history = getSavedChats().filter(h => h.id !== id)
    setSavedChatsSafe(history)
    if (id === loadedChatId) {
      setMessages([])
      setLoadedChatId(null)
    }
  }

  const clearHistory = () => {
    setSavedChatsSafe([])
  }

  const handleNewChat = () => {
    if (messages.length > 0) {
      saveCurrentChat(messages, loadedChatId)
    }
    setMessages([])
    setInputValue('')
    setError(null)
    setLoadedChatId(null)
    setCurrentView('chat')
  }

  // --- SUGGESTIONS LOGIC ---
  useEffect(() => {
    const canFetchSuggestions =
      currentView === 'chat' &&
      messages.length === 0 &&
      inputValue.trim() === '' &&
      docList.length > 0 &&
      isIndexed &&
      !statusLoading &&
      !isLoading &&
      !statusError &&
      activeSelectedDocs.length <= MAX_SELECTED_DOCS

    if (canFetchSuggestions) {
      let isMounted = true
      setSuggestionsLoading(true)
      setSuggestionsError(null)
      generateSuggestions({ selectedDocs: activeSelectedDocs })
        .then(res => {
          if (isMounted && res.questions) {
            setSuggestions(res.questions)
          }
        })
        .catch(err => {
          if (!isMounted) return
          setSuggestions([])
          if (err?.status !== 400) {
            setSuggestionsError(err.message || 'Failed to load suggestions')
          }
        })
        .finally(() => {
          if (isMounted) setSuggestionsLoading(false)
        })
      return () => { isMounted = false }
    } else {
      setSuggestions([])
      setSuggestionsLoading(false)
      setSuggestionsError(null)
    }
  }, [currentView, docList.length, isIndexed, statusLoading, messages.length, inputValue, isLoading, statusError, activeSelectedDocs])

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (!files.length) return
    setUploading(true)
    setUploadError(null)
    setUploadMessage(null)
    setProcessError(null)

    let hasError = false
    const uploadedFilenames = []
    try {
      for (const file of files) {
        try {
          const response = await uploadDocument(file)
          uploadedFilenames.push(...getUploadedFilenames(response, file.name))
        } catch (err) {
          setUploadError(err.message || `Failed to upload ${file.name}`)
          hasError = true
          break
        }
      }
      if (!hasError) {
        setUploadMessage(`Uploaded ${files.length} file(s).`)
        await fetchStatus()
        setSelectedDocs(prev => Array.from(new Set([...prev, ...uploadedFilenames])))
      }
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleProcess = async () => {
    setProcessing(true)
    setProcessError(null)
    setProcessMessage(null)
    
    try {
      await processDocuments()
      setProcessMessage('Documents processed.')
      await fetchStatus()
    } catch (err) {
      setProcessError(err.message || 'Processing failed.')
    } finally {
      setProcessing(false)
    }
  }

  const handleDelete = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete ${filename}?`)) return
    
    setDeletingDoc(filename)
    setDeleteError(null)
    setDeleteMessage(null)
    setClearError(null)
    setClearMessage(null)
    
    try {
      await deleteDocument(filename)
      setSelectedDocs(prev => prev.filter(f => f !== filename))
      setDeleteMessage(`Deleted ${filename}.`)
      await fetchStatus()
    } catch (err) {
      setDeleteError(err.message || `Failed to delete ${filename}`)
    } finally {
      setDeletingDoc(null)
    }
  }

  const handleClear = async () => {
    if (!window.confirm('Are you sure you want to clear the entire library?')) return
    
    setClearing(true)
    setClearError(null)
    setClearMessage(null)
    setDeleteError(null)
    setDeleteMessage(null)
    
    try {
      await clearLibrary()
      setSelectedDocs([])
      setClearMessage('Library cleared.')
      await fetchStatus()
    } catch (err) {
      setClearError(err.message || 'Failed to clear library')
    } finally {
      setClearing(false)
    }
  }

  const handleToggleDoc = (filename) => {
    setSelectedDocs(prev =>
      prev.includes(filename)
        ? prev.filter(f => f !== filename)
        : [...prev, filename]
    )
  }

  const handleGenerateSummary = async () => {
    setCurrentView('summary')
    setStudyLoading(true)
    setStudyError(null)
    try {
      const data = await generateSummary({ selectedDocs: activeSelectedDocs.length ? activeSelectedDocs : [] })
      setSummaryData(data)
    } catch (err) {
      setStudyError(err)
    } finally {
      setStudyLoading(false)
    }
  }

  const handleGenerateFlashcards = async () => {
    setCurrentView('flashcards')
    setStudyLoading(true)
    setStudyError(null)
    try {
      const data = await generateFlashcards({ count: 8, selectedDocs: activeSelectedDocs.length ? activeSelectedDocs : [] })
      setFlashcardData(data)
    } catch (err) {
      setStudyError(err)
    } finally {
      setStudyLoading(false)
    }
  }

  const handleGenerateQuiz = async () => {
    setCurrentView('quiz')
    setStudyLoading(true)
    setStudyError(null)
    try {
      const data = await generateQuiz({ difficulty: 'medium', count: 8, selectedDocs: activeSelectedDocs.length ? activeSelectedDocs : [] })
      setQuizData(data)
    } catch (err) {
      setStudyError(err)
    } finally {
      setStudyLoading(false)
    }
  }

  const handleRunKnowledgeCopilot = async ({ taskType, audience, request }) => {
    setBusinessLoading(true)
    setBusinessError(null)
    try {
      const data = await runKnowledgeCopilot({ taskType, audience, request, selectedDocs: activeSelectedDocs.length ? activeSelectedDocs : [] })
      setCopilotData(data)
    } catch (err) {
      setBusinessError(err)
    } finally {
      setBusinessLoading(false)
    }
  }

  const handleRunKnowledgeAudit = async () => {
    setBusinessLoading(true)
    setBusinessError(null)
    try {
      const data = await runKnowledgeAudit({ selectedDocs: activeSelectedDocs.length ? activeSelectedDocs : [] })
      setAuditData(data)
    } catch (err) {
      setBusinessError(err)
    } finally {
      setBusinessLoading(false)
    }
  }

  async function handleSend() {
    const trimmed = inputValue.trim()
    if (!trimmed || isLoading) return

    // Capture prior messages BEFORE appending the new user message.
    // history = prior turns only; current question is sent separately.
    const priorMessages = messages.map(({ role, content }) => ({ role, content }))

    const userMsg = { id: genId(), role: 'user', content: trimmed }
    const messagesWithUser = [...messages, userMsg]

    setMessages(messagesWithUser)
    setInputValue('')
    // Reset textarea height so it returns to single-row after send
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setError(null)
    setIsLoading(true)

    try {
      const data = await sendChat({
        question: trimmed,
        history: priorMessages,
        selectedDocs: activeSelectedDocs,
      })
      const answer = data?.answer ?? 'No response received.'
      const sources = data?.sources ?? []
      const showSources = Boolean(data?.show_sources) && sources.length > 0
      const assistantMsg = { id: genId(), role: 'assistant', content: answer, sources, showSources }
      
      const nextMessages = [...messagesWithUser, assistantMsg]
      setMessages(nextMessages)

      const savedId = saveCurrentChat(nextMessages, loadedChatId)
      if (!loadedChatId) setLoadedChatId(savedId)
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

  function handleExport() {
    if (messages.length === 0) {
      setError('No chat to export.')
      return
    }

    const wrapper = chatWrapperRef.current
    if (!wrapper) {
      window.print()
      return
    }

    const existingHeader = wrapper.querySelector('.print-header')
    if (existingHeader) existingHeader.remove()

    const header = document.createElement('div')
    header.className = 'print-header'
    header.innerHTML = `
      <h1>Kroma — Chat Export</h1>
      <p>${new Date().toLocaleString()}</p>
    `

    const cleanup = () => {
      if (header.parentNode) {
        header.parentNode.removeChild(header)
      }
      window.removeEventListener('afterprint', cleanup)
    }

    wrapper.insertBefore(header, wrapper.firstChild)
    window.addEventListener('afterprint', cleanup, { once: true })

    try {
      window.print()
    } finally {
      cleanup()
    }
  }

  const canSend = inputValue.trim() !== '' && !isLoading

  return (
    <>
      {/* SIDEBAR */}
      <aside className="sidebar">
        <KromaLogo />

        <DemoKeyPanel
          demoKeyInput={demoKeyInput}
          setDemoKeyInput={value => {
            setDemoKeyInput(value)
            setDemoKeyMessage(null)
          }}
          demoKeyMessage={demoKeyMessage}
          onApplyDemoKey={applyDemoKey}
          onClearDemoKey={clearDemoKey}
        />

        <hr className="divider" />

        <UploadPanel
          onUpload={handleUpload}
          onProcess={handleProcess}
          uploading={uploading}
          processing={processing}
          uploadError={uploadError}
          uploadMessage={uploadMessage}
          processError={processError}
          processMessage={processMessage}
        />

        <hr className="divider" />

        <LibraryList
          statusLoading={statusLoading}
          statusError={statusError}
          docList={docList}
          selectedDocs={selectedDocs}
          onToggleDoc={handleToggleDoc}
          onDeleteDoc={handleDelete}
          deletingDoc={deletingDoc}
          libraryBusy={libraryBusy}
          deleteError={deleteError}
          deleteMessage={deleteMessage}
          clearError={clearError}
          clearMessage={clearMessage}
          onClearLibrary={handleClear}
          clearing={clearing}
        >
          <button className="btn-secondary" onClick={handleNewChat}>New chat</button>
        </LibraryList>

        <hr className="divider" />

        <ToolButtons
          currentView={currentView}
          studyBusy={studyBusy}
          businessLoading={businessLoading}
          onGenerateSummary={handleGenerateSummary}
          onGenerateFlashcards={handleGenerateFlashcards}
          onGenerateQuiz={handleGenerateQuiz}
          onOpenKnowledgeCopilot={() => { setCurrentView('knowledge-copilot'); setCopilotData(null); setBusinessError(null); }}
          onOpenKnowledgeAudit={() => { setCurrentView('knowledge-audit'); setAuditData(null); setBusinessError(null); }}
        />
        <hr className="divider" />
        <HistoryList
          savedChats={savedChats}
          loadedChatId={loadedChatId}
          onLoadChat={loadChat}
          onDeleteHistoryChat={deleteHistoryChat}
          onClearHistory={clearHistory}
        />
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="main">
        {currentView === 'chat' && (
          <div className="topbar">
            <div>
              <div className="topbar-title" id="topbarTitle">Kroma</div>
              <div className="topbar-sub" id="topbarSub">Your source-grounded study assistant</div>
            </div>
            <ExportButton visible={messages.length > 0} onExport={handleExport} />
          </div>
        )}

        {currentView === 'chat' ? (
          <>
            {/* METRICS */}
            <MetricsBar
              statusLoading={statusLoading}
              docCount={docCount}
              pageCount={pageCount}
              chunkCount={chunkCount}
            />

            {/* CHAT AREA */}
            <div className="chat-wrapper" id="chatWrapper" ref={chatWrapperRef}>

              {/* Empty state — hidden once messages exist */}
              {messages.length === 0 && !isLoading && (
                <>
                  {!isIndexed && (
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

                  {inputValue.trim() === '' && suggestions.length > 0 && (
                    <div className="suggestions" style={{ borderBottom: 'none', padding: '1rem 0' }}>
                      <div className="suggestions-label">Suggested Questions</div>
                      <div className="suggestions-row">
                        {suggestions.map((s, idx) => (
                          <button 
                            key={idx} 
                            className="suggestion-btn" 
                            onClick={() => setInputValue(s)}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
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
          </>
        ) : currentView === 'summary' ? (
          <SummaryView 
            data={summaryData} 
            loading={studyLoading} 
            error={studyError} 
            onBack={() => setCurrentView('chat')} 
          />
        ) : currentView === 'flashcards' ? (
          <FlashcardsView 
            data={flashcardData} 
            loading={studyLoading} 
            error={studyError} 
            onBack={() => setCurrentView('chat')} 
          />
        ) : currentView === 'quiz' ? (
          <QuizView 
            data={quizData} 
            loading={studyLoading} 
            error={studyError} 
            onBack={() => setCurrentView('chat')} 
          />
        ) : currentView === 'knowledge-copilot' ? (
          <KnowledgeCopilotView 
            data={copilotData} 
            loading={businessLoading} 
            error={businessError} 
            onRun={handleRunKnowledgeCopilot}
            onBack={() => setCurrentView('chat')} 
          />
        ) : currentView === 'knowledge-audit' ? (
          <KnowledgeAuditView 
            data={auditData} 
            loading={businessLoading} 
            error={businessError} 
            onRun={handleRunKnowledgeAudit}
            onBack={() => setCurrentView('chat')} 
          />
        ) : null}
      </main>
    </>
  )
}
