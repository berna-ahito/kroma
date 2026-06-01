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
    <div className="study-view">
      <div className="study-header">
        <button className="btn-secondary" onClick={onBack} disabled={loading}>
          ← Back to chat
        </button>
        <h2 className="study-title">Knowledge Copilot</h2>
        <div style={{ flex: 1 }}></div>
      </div>

      <div className="study-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '1rem', overflowY: 'auto' }}>
        
        {/* Input Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: 'var(--surface-2)', padding: '1.5rem', borderRadius: '12px', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-2)' }}>Task Type</label>
              <select 
                value={taskType} 
                onChange={e => setTaskType(e.target.value)} 
                disabled={loading}
                style={{ width: '100%', padding: '0.65rem', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
              >
                <option value="answer_from_sources">Answer from Sources</option>
                <option value="draft_reply">Draft Reply</option>
                <option value="summarize_for_team">Summarize for Team</option>
                <option value="extract_action_items">Extract Action Items</option>
                <option value="risk_check">Risk Check</option>
              </select>
            </div>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-2)' }}>Audience</label>
              <select 
                value={audience} 
                onChange={e => setAudience(e.target.value)} 
                disabled={loading}
                style={{ width: '100%', padding: '0.65rem', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
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

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-2)' }}>Request / Context</label>
            <textarea 
              value={requestText}
              onChange={e => { setRequestText(e.target.value); setValidationError(''); }}
              disabled={loading}
              placeholder="e.g., Draft an email explaining the recent policy changes..."
              style={{ width: '100%', minHeight: '100px', padding: '0.75rem', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)', resize: 'vertical', fontFamily: 'inherit' }}
            />
            {validationError && <div style={{ color: '#fca5a5', fontSize: '0.85rem', marginTop: '0.5rem' }}>{validationError}</div>}
          </div>

          <button className="btn-primary" onClick={handleGenerate} disabled={loading} style={{ alignSelf: 'flex-start' }}>
            {loading ? 'Generating...' : 'Generate'}
          </button>
        </div>

        {/* Error State */}
        {error && (
          <div style={{ padding: '1rem', background: 'rgba(127,29,29,0.25)', border: '1px solid #7f1d1d', borderRadius: '8px', color: '#fca5a5' }}>
            {error.message || 'An error occurred during generation.'}
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            {result.needs_human_review?.required && (
              <div style={{ padding: '1rem', background: 'rgba(180,83,9,0.2)', border: '1px solid #b45309', borderRadius: '8px', color: '#fcd34d' }}>
                <strong style={{ display: 'block', marginBottom: '0.5rem' }}>⚠️ Human Review Required</strong>
                <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
                  {result.needs_human_review.reasons?.map((reason, i) => <li key={i}>{reason}</li>)}
                </ul>
              </div>
            )}

            {result.suggested_draft && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Suggested Draft</div>
                <div style={{ padding: '1.5rem' }}>
                  <SafeMarkdown content={result.suggested_draft} />
                </div>
              </div>
            )}

            {result.verified_facts?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Verified Facts</div>
                <ul style={{ padding: '1rem 1rem 1rem 2.5rem', margin: 0 }}>
                  {result.verified_facts.map((fact, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{fact}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.missing_information?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Missing Information</div>
                <ul style={{ padding: '1rem 1rem 1rem 2.5rem', margin: 0 }}>
                  {result.missing_information.map((info, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{info}</li>
                  ))}
                </ul>
              </div>
            )}

            <BusinessSources sourceIds={result.sources_used} sources={sources} />

          </div>
        )}

      </div>
    </div>
  )
}
