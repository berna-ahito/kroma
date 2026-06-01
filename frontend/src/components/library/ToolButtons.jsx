export default function ToolButtons({
  currentView: _currentView,
  studyBusy,
  businessLoading,
  onGenerateSummary,
  onGenerateFlashcards,
  onGenerateQuiz,
  onOpenKnowledgeCopilot,
  onOpenKnowledgeAudit,
}) {
  return (
    <>
      <div className="sidebar-label">Tools</div>
      <button className="btn-primary" id="flashcardBtn" onClick={onGenerateFlashcards} disabled={studyBusy}>
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
      <button className="btn-primary" id="quizBtn" onClick={onGenerateQuiz} disabled={studyBusy} style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
        <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="9"/>
          <path d="M9.5 9a2.5 2.5 0 0 1 4.5 1.5c0 1.8-2 2.2-2 3.5"/>
          <path d="M12 17h.01"/>
        </svg>
        <span>Quiz me</span>
      </button>
      <button className="btn-primary" id="summaryBtn" onClick={onGenerateSummary} disabled={studyBusy} style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
        <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M9 4h6"/>
          <path d="M9 4a2 2 0 0 0-2 2v1h10V6a2 2 0 0 0-2-2"/>
          <path d="M7 7H5v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7h-2"/>
          <path d="M9 13h6"/>
          <path d="M9 17h4"/>
        </svg>
        <span>Summarize</span>
      </button>
      <button className="btn-primary" id="businessCopilotBtn" onClick={onOpenKnowledgeCopilot} disabled={studyBusy || businessLoading} style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
        <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <rect x="4" y="6" width="16" height="13" rx="2" stroke="currentColor" fill="none" strokeWidth="2" strokeLinejoin="round"/>
          <path d="M4 11 L20 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M10 6 L10 19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <span>Knowledge Copilot</span>
      </button>
      <button className="btn-primary" id="knowledgeAuditBtn" onClick={onOpenKnowledgeAudit} disabled={studyBusy || businessLoading} style={{ background: 'var(--surface-2)', color: 'var(--text-2)', marginTop: '-0.3rem' }}>
        <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" fill="none" strokeWidth="2" strokeLinejoin="round"/>
          <path d="M14 2v6h6" stroke="currentColor" fill="none" strokeWidth="2" strokeLinejoin="round"/>
          <path d="M9 15l2 2 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span>Knowledge Audit</span>
      </button>
    </>
  )
}
