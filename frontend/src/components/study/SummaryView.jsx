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
    <div className="chat-container">
      <div className="chat-history">
        <button onClick={onBack} className="btn" style={{ marginBottom: '1rem' }}>
          Back to chat
        </button>
        
        <h2>Document Summary</h2>
        
        {loading && <div style={{ opacity: 0.7, margin: '1rem 0' }}>Loading summary...</div>}
        {error && <div style={{ color: 'red', margin: '1rem 0' }}>{error.message || 'Error generating summary'}</div>}
        
        {!loading && !error && data?.summary?.sections && (
          <div className="summary-content">
            {data.summary.sections.length === 0 && <div>No summary available.</div>}
            {data.summary.sections.map((section, idx) => (
              <div key={idx} style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginTop: '1.5rem', marginBottom: '0.5rem' }}>{section.heading}</h3>
                
                {section.text && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <SafeMarkdown content={section.text} />
                  </div>
                )}
                
                {section.source_ids && section.source_ids.length > 0 && (
                  <StudySources sourceIds={section.source_ids} sourceMap={sourceMap} showUnsourced={false} />
                )}
                
                {section.bullets && section.bullets.length > 0 && (
                  <ul style={{ paddingLeft: '1.5rem', marginTop: '0.5rem' }}>
                    {section.bullets.map((bullet, bIdx) => (
                      <li key={bIdx} style={{ marginBottom: '0.5rem' }}>
                        <SafeMarkdown content={bullet.text} inline />
                        {bullet.source_ids && bullet.source_ids.length > 0 && (
                          <div style={{ marginTop: '0.25rem' }}>
                            <StudySources sourceIds={bullet.source_ids} sourceMap={sourceMap} showUnsourced={false} />
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
