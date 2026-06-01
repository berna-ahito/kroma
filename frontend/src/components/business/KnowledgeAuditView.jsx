import React from 'react'
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
    ['Category', value.category],
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
      if (Array.isArray(value.items)) visit(value.items)
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

function AuditListItem({ item, sources }) {
  const sourceIds = itemSourceIds(item)
  return (
    <li className="tool-result-row">
      <div className="tool-result-text">
        <SafeMarkdown content={valueToText(item)} inline />
      </div>
      {sourceIds.length > 0 && (
        <BusinessSourceRefs sourceIds={sourceIds} sources={sources} />
      )}
    </li>
  )
}

function automationGroups(readiness) {
  if (!Array.isArray(readiness)) return []
  return readiness.map(item => {
    if (typeof item === 'object' && item !== null) {
      const items = Array.isArray(item.items) ? item.items : []
      return {
        category: valueToText(item.category || item.area || item.title || item.text || item.detail || `Item`),
        items: items.length ? items : [item],
      }
    }
    return { category: 'Item', items: [item] }
  })
}

export default function KnowledgeAuditView({ onBack, onRun, data, loading, error }) {
  const result = data?.result
  const sources = data?.sources || []
  const readinessGroups = automationGroups(result?.automation_readiness)
  const mainSourceIds = result ? collectSourceIds(
    normalizeSourceIds(result.sources_used),
    result.readiness_verdict?.reasons,
    result.coverage_summary,
    result.missing_knowledge,
    result.risk_areas,
    result.automation_readiness,
    result.suggested_next_documents
  ) : []
  const fallbackSourceIds = mainSourceIds.length ? mainSourceIds : sourceIdsFromSources(sources)

  return (
    <div className="tool-shell">
      <div className="tool-header">
        <div className="tool-heading">
          <h2>Knowledge Audit</h2>
          <p className="tool-subtitle">Assess coverage, missing knowledge, risks, and automation readiness.</p>
        </div>
        <button className="tool-back-button" onClick={onBack} disabled={loading}>
          Back to chat
        </button>
      </div>

      <div className="tool-body">
        
        <div className="tool-card audit-intro">
          <div>
            <h3 className="tool-section-title">Evaluate Knowledge Base</h3>
            <p className="tool-subtitle">Run an audit against the selected documents. No selection means all documents.</p>
            <p className="tool-helper-note">This checks whether the selected documents contain enough grounded information for reliable AI workflows.</p>
          </div>
          <button className="btn-primary" onClick={onRun} disabled={loading}>
            {loading ? 'Running Audit...' : 'Run Audit'}
          </button>
        </div>

        {error && (
          <div className="tool-error">
            {error.message || 'An error occurred during the audit.'}
          </div>
        )}

        {loading && <div className="tool-state">Running audit...</div>}

        {result && !loading && (
          <div className="tool-grid">
            
            {result.readiness_verdict && (
              <section className="tool-card readiness-card">
                <span className="tool-kicker">Readiness Verdict</span>
                <strong className={`readiness-badge readiness-${String(result.readiness_verdict.level || 'unknown').toLowerCase()}`}>
                    {valueToText(result.readiness_verdict.level || 'Unknown')}
                </strong>
                {result.readiness_verdict.reasons?.length > 0 && (
                  <ul className="tool-list">
                    {result.readiness_verdict.reasons.map((reason, i) => <AuditListItem key={i} item={reason} sources={sources} />)}
                  </ul>
                )}
              </section>
            )}

            {result.coverage_summary?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Coverage Summary</h3>
                <ul className="tool-list">
                  {result.coverage_summary.map((cov, i) => (
                    <AuditListItem key={i} item={cov} sources={sources} />
                  ))}
                </ul>
              </section>
            )}

            {result.missing_knowledge?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Missing Knowledge</h3>
                <ul className="tool-list">
                  {result.missing_knowledge.map((miss, i) => (
                    <AuditListItem key={i} item={miss} sources={sources} />
                  ))}
                </ul>
              </section>
            )}

            {result.risk_areas?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Risk Areas</h3>
                <ul className="tool-list">
                  {result.risk_areas.map((risk, i) => (
                    <AuditListItem key={i} item={risk} sources={sources} />
                  ))}
                </ul>
              </section>
            )}

            {readinessGroups.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Automation Readiness</h3>
                <div className="tool-nested-list">
                  {readinessGroups.map((ar, i) => (
                    <div key={i} className="tool-nested-group">
                      <strong>{ar.category}</strong>
                      <ul className="tool-list">
                        {ar.items.map((item, j) => <AuditListItem key={j} item={item} sources={sources} />)}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {result.suggested_next_documents?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Suggested Next Documents</h3>
                <ul className="tool-list">
                  {result.suggested_next_documents.map((doc, i) => (
                    <AuditListItem key={i} item={doc} sources={sources} />
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
