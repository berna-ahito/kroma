import React, { useState } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import BusinessSources, { BusinessSourceRefs, normalizeSourceIds } from './BusinessSources.jsx'

function valueToText(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(valueToText).filter(Boolean).join('\n')
  if (typeof value !== 'object') return String(value)

  if (value.text != null && value.text !== '') return valueToText(value.text)
  if (value.area != null && value.area !== '') {
    const detail = value.detail ? `: ${valueToText(value.detail)}` : ''
    return `${valueToText(value.area)}${detail}`
  }
  if (value.detail != null && value.detail !== '') return valueToText(value.detail)

  const fields = [
    ['Task', value.task],
    ['Owner', value.owner],
    ['Due date', value.due_date || value.dueDate],
    ['Status', value.status],
    ['Priority', value.priority],
    ['Description', value.description],
    ['Reason', value.reason],
  ]
    .filter(([, fieldValue]) => fieldValue != null && fieldValue !== '')
    .map(([label, fieldValue]) => `${label}: ${valueToText(fieldValue)}`)

  return fields.length ? fields.join('\n') : JSON.stringify(value)
}

function itemSourceIds(value) {
  return Array.isArray(value?.source_ids) ? value.source_ids : []
}

function collectSourceIds(...values) {
  const ids = []
  const visit = (value) => {
    if (!value) return
    if (typeof value === 'string' || typeof value === 'number') {
      ids.push(value)
      return
    }
    if (Array.isArray(value)) {
      value.forEach(visit)
      return
    }
    if (typeof value === 'object') {
      ids.push(...itemSourceIds(value))
    }
  }
  values.forEach(visit)
  return Array.from(new Set(normalizeSourceIds(ids)))
}

function sourceIdsFromSources(sources) {
  return sources
    .map(source => source?.doc_chunk_id || source?.chunk_id || source?.id)
    .filter(Boolean)
}

function ResultListItem({ item, sources, card = false }) {
  const sourceIds = itemSourceIds(item)
  return (
    <li className={card ? 'tool-result-row tool-result-row--card' : 'tool-result-row'}>
      <div className="tool-result-text">
        <SafeMarkdown content={valueToText(item)} inline />
      </div>
      {sourceIds.length > 0 && (
        <BusinessSourceRefs sourceIds={sourceIds} sources={sources} />
      )}
    </li>
  )
}

function normalizeReview(review) {
  if (review == null || review === false) return null
  if (typeof review === 'boolean') return { required: review, reasons: [] }
  if (typeof review === 'object') {
    return {
      required: Boolean(review.required),
      reasons: Array.isArray(review.reasons) ? review.reasons : [],
    }
  }
  return { required: false, reasons: [review] }
}

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
  const humanReview = normalizeReview(result?.needs_human_review)
  const mainSourceIds = result ? collectSourceIds(
    normalizeSourceIds(result.sources_used),
    result.suggested_draft,
    result.answer,
    result.summary,
    result.response,
    result.final,
    result.action_items,
    result.risks,
    result.verified_facts,
    result.missing_information,
    humanReview?.reasons
  ) : []
  const fallbackSourceIds = mainSourceIds.length ? mainSourceIds : sourceIdsFromSources(sources)

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
            
            {humanReview && (
              <div className={`tool-card review-flag${humanReview.required ? ' is-required' : ''}`}>
                <span className="tool-kicker">Human Review</span>
                <strong>{humanReview.required ? 'Required' : 'Not required'}</strong>
                {humanReview.reasons.length > 0 && (
                  <ul className="tool-list">
                    {humanReview.reasons.map((reason, i) => <ResultListItem key={i} item={reason} sources={sources} />)}
                  </ul>
                )}
              </div>
            )}

            {result.suggested_draft && (
              <section className="tool-card">
                <h3 className="tool-section-title">Suggested Draft</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={valueToText(result.suggested_draft)} />
                </div>
                {itemSourceIds(result.suggested_draft).length > 0 && (
                  <div className="tool-sources-compact">
                    <BusinessSourceRefs sourceIds={itemSourceIds(result.suggested_draft)} sources={sources} />
                  </div>
                )}
              </section>
            )}

            {result.answer && (
              <section className="tool-card">
                <h3 className="tool-section-title">Answer</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={valueToText(result.answer)} />
                </div>
              </section>
            )}

            {result.summary && (
              <section className="tool-card">
                <h3 className="tool-section-title">Summary</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={valueToText(result.summary)} />
                </div>
              </section>
            )}

            {result.action_items?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Action Items</h3>
                <ul className="tool-list">
                  {result.action_items.map((item, i) => (
                    <ResultListItem key={i} item={item} sources={sources} />
                  ))}
                </ul>
              </section>
            )}

            {result.risks?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Risks</h3>
                <ul className="tool-list">
                  {result.risks.map((risk, i) => (
                    <ResultListItem key={i} item={risk} sources={sources} />
                  ))}
                </ul>
              </section>
            )}

            {result.response && !result.suggested_draft && !result.answer && !result.summary && (
              <section className="tool-card">
                <h3 className="tool-section-title">Result</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={valueToText(result.response)} />
                </div>
              </section>
            )}

            {result.final && !result.suggested_draft && !result.answer && !result.summary && !result.response && (
              <section className="tool-card">
                <h3 className="tool-section-title">Result</h3>
                <div className="tool-markdown">
                  <SafeMarkdown content={valueToText(result.final)} />
                </div>
              </section>
            )}

            {result.verified_facts?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Verified Facts</h3>
                <ul className="tool-fact-list">
                  {result.verified_facts.map((fact, i) => (
                    <ResultListItem key={i} item={fact} sources={sources} card />
                  ))}
                </ul>
              </section>
            )}

            {result.missing_information?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Missing Information</h3>
                <ul className="tool-list">
                  {result.missing_information.map((info, i) => (
                    <ResultListItem key={i} item={info} sources={sources} />
                  ))}
                </ul>
              </section>
            )}

            {(fallbackSourceIds.length > 0 || sources.length > 0) && (
              <div className="tool-card">
                <BusinessSources sourceIds={fallbackSourceIds} sources={sources} showAllWhenUnreferenced />
              </div>
            )}

          </div>
        )}

      </div>
    </div>
  )
}
