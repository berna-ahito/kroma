import React, { useState } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import BusinessSources from './BusinessSources.jsx'

export default function KnowledgeCopilotView({ onBack, onRun, data, loading, error }) {
  const [taskType, setTaskType] = useState('answer_from_sources')
  const [audience, setAudience] = useState('internal_team')
  const [requestText, setRequestText] = useState('')
  const [validationError, setValidationError] = useState('')

  const handleGenerate = () => {
    const trimmed = requestText.trim()
    if (!trimmed) {
      setValidationError('Please enter a request or context.')
      return
    }
    setValidationError('')
    onRun({ taskType, audience, request: trimmed })
  }

  const result = data?.result
  const sources = data?.sources || []

  return (
    <div className="tool-shell">
      <div className="tool-header">
        <div className="tool-heading">
          <h2>Knowledge Copilot</h2>
          <p className="tool-subtitle">Generate source-grounded business output from the selected documents.</p>
        </div>
        <button className="tool-back-button" onClick={onBack} disabled={loading}>
          Back to chat
        </button>
      </div>

      <div className="tool-body">
        <div className="tool-card tool-form-card">
          <div className="tool-form-grid">
            <div className="tool-field">
              <label>Task Type</label>
              <select 
                value={taskType} 
                onChange={e => setTaskType(e.target.value)} 
                disabled={loading}
              >
                <option value="answer_from_sources">Answer from Sources</option>
                <option value="draft_reply">Draft Reply</option>
                <option value="summarize_for_team">Summarize for Team</option>
                <option value="extract_action_items">Extract Action Items</option>
                <option value="risk_check">Risk Check</option>
              </select>
            </div>
            <div className="tool-field">
              <label>Audience</label>
              <select 
                value={audience} 
                onChange={e => setAudience(e.target.value)} 
                disabled={loading}
              >
                <option value="internal_team">Internal Team</option>
                <option value="customer">Customer</option>
                <option value="partner">Partner</option>
                <option value="investor">Investor</option>
                <option value="distributor">Distributor</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div className="tool-field">
            <label>Request / Context</label>
            <textarea 
              value={requestText}
              onChange={e => { setRequestText(e.target.value); setValidationError(''); }}
              disabled={loading}
              placeholder="e.g., Draft an email explaining the recent policy changes..."
            />
            {validationError && <div className="tool-inline-error">{validationError}</div>}
          </div>

          <button className="btn-primary tool-generate-button" onClick={handleGenerate} disabled={loading}>
            {loading ? 'Generating...' : 'Generate'}
          </button>
        </div>

        {error && (
          <div className="tool-error">
            {error.message || 'An error occurred during generation.'}
          </div>
        )}

        {loading && <div className="tool-state">Generating...</div>}

        {result && !loading && (
          <div className="tool-grid">
            
            {result.needs_human_review && (
              <div className={`tool-card review-flag${result.needs_human_review.required ? ' is-required' : ''}`}>
                <span className="tool-kicker">Human Review</span>
                <strong>{result.needs_human_review.required ? 'Required' : 'Not required'}</strong>
                {result.needs_human_review.reasons?.length > 0 && (
                  <ul className="tool-list">
                    {result.needs_human_review.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                  </ul>
                )}
              </div>
            )}

            {result.suggested_draft && (
              <section className="tool-card">
                <h3 className="tool-section-title">Suggested Draft</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={result.suggested_draft} />
                </div>
              </section>
            )}

            {result.answer && (
              <section className="tool-card">
                <h3 className="tool-section-title">Answer</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={result.answer} />
                </div>
              </section>
            )}

            {result.summary && (
              <section className="tool-card">
                <h3 className="tool-section-title">Summary</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={result.summary} />
                </div>
              </section>
            )}

            {result.action_items?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Action Items</h3>
                <ul className="tool-list">
                  {result.action_items.map((item, i) => (
                    <li key={i}>{typeof item === 'string' ? item : item.task || item.text || JSON.stringify(item)}</li>
                  ))}
                </ul>
              </section>
            )}

            {result.risks?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Risks</h3>
                <ul className="tool-list">
                  {result.risks.map((risk, i) => (
                    <li key={i}>{typeof risk === 'string' ? risk : risk.description || risk.text || JSON.stringify(risk)}</li>
                  ))}
                </ul>
              </section>
            )}

            {result.response && !result.suggested_draft && !result.answer && !result.summary && (
              <section className="tool-card">
                <h3 className="tool-section-title">Result</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={result.response} />
                </div>
              </section>
            )}

            {result.final && !result.suggested_draft && !result.answer && !result.summary && !result.response && (
              <section className="tool-card">
                <h3 className="tool-section-title">Result</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={result.final} />
                </div>
              </section>
            )}

            {result.verified_facts?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Verified Facts</h3>
                <ul className="tool-list">
                  {result.verified_facts.map((fact, i) => (
                    <li key={i}>{fact}</li>
                  ))}
                </ul>
              </section>
            )}

            {result.missing_information?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Missing Information</h3>
                <ul className="tool-list">
                  {result.missing_information.map((info, i) => (
                    <li key={i}>{info}</li>
                  ))}
                </ul>
              </section>
            )}

            <div className="tool-card">
              <BusinessSources sourceIds={result.sources_used} sources={sources} />
            </div>

          </div>
        )}

      </div>
    </div>
  )
}
