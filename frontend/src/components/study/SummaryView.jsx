import React, { useMemo } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import StudySources from './StudySources.jsx'

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
                <h3 className="tool-section-title">{section.heading}</h3>
                
                {section.text && (
                  <div className="tool-markdown">
                    <SafeMarkdown content={section.text} />
                  </div>
                )}
                
                {section.source_ids && section.source_ids.length > 0 && (
                  <div className="tool-sources-compact">
                    <StudySources sourceIds={section.source_ids} sourceMap={sourceMap} showUnsourced={false} />
                  </div>
                )}
                
                {section.bullets && section.bullets.length > 0 && (
                  <ul className="tool-list">
                    {section.bullets.map((bullet, bIdx) => (
                      <li key={bIdx}>
                        <SafeMarkdown content={bullet.text} inline />
                        {bullet.source_ids && bullet.source_ids.length > 0 && (
                          <div className="tool-sources-compact">
                            <StudySources sourceIds={bullet.source_ids} sourceMap={sourceMap} showUnsourced={false} />
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
