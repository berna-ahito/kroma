import React, { useMemo } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import StudySources from './StudySources.jsx'

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
  if (value.heading != null && value.heading !== '') return valueToText(value.heading)
  if (value.title != null && value.title !== '') return valueToText(value.title)
  return JSON.stringify(value)
}

function sourceIdsFor(value) {
  return Array.isArray(value?.source_ids) ? value.source_ids : []
}

export default function SummaryView({ data, loading, error, onBack }) {
  const sourceMap = useMemo(() => {
    const map = new Map()
    if (data?.sources) {
      data.sources.forEach(src => map.set(src.id, src))
    }
    return map
  }, [data])

  return (
    <div className="tool-shell">
      <div className="tool-header">
        <div className="tool-heading">
          <h2>Document Summary</h2>
          <p className="tool-subtitle">A source-grounded overview of the selected documents.</p>
        </div>
        <button onClick={onBack} className="tool-back-button">
          Back to chat
        </button>
      </div>

      <div className="tool-body">
        {loading && <div className="tool-state">Loading summary...</div>}
        {error && <div className="tool-error">{error.message || 'Error generating summary'}</div>}
        
        {!loading && !error && data?.summary?.sections && (
          <div className="tool-grid">
            {data.summary.sections.length === 0 && <div className="tool-state">No summary available.</div>}
            {data.summary.sections.map((section, idx) => (
              <section key={idx} className="tool-card summary-section">
                <h3 className="tool-section-title">{valueToText(section.heading || section.title || `Section ${idx + 1}`)}</h3>
                
                {section.text && (
                  <div className="tool-markdown">
                    <SafeMarkdown content={valueToText(section.text)} />
                  </div>
                )}
                
                {sourceIdsFor(section).length > 0 && (
                  <div className="tool-sources-compact">
                    <StudySources sourceIds={sourceIdsFor(section)} sourceMap={sourceMap} showUnsourced={false} />
                  </div>
                )}
                
                {section.bullets && section.bullets.length > 0 && (
                  <ul className="tool-list">
                    {section.bullets.map((bullet, bIdx) => (
                      <li key={bIdx}>
                        <SafeMarkdown content={valueToText(bullet)} inline />
                        {sourceIdsFor(bullet).length > 0 && (
                          <div className="tool-sources-compact">
                            <StudySources sourceIds={sourceIdsFor(bullet)} sourceMap={sourceMap} showUnsourced={false} />
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
