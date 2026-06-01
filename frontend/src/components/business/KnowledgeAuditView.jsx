import React from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import BusinessSources from './BusinessSources.jsx'

export default function KnowledgeAuditView({ onBack, onRun, data, loading, error }) {
  const result = data?.result
  const sources = data?.sources || []

  return (
    <div className="study-view">
      <div className="study-header">
        <button className="btn-secondary" onClick={onBack} disabled={loading}>
          ← Back to chat
        </button>
        <h2 className="study-title">Knowledge Audit</h2>
        <div style={{ flex: 1 }}></div>
      </div>

      <div className="study-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '1rem', overflowY: 'auto' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--surface-2)', padding: '1.5rem', borderRadius: '12px', border: '1px solid var(--border)' }}>
          <div>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>Evaluate Knowledge Base</h3>
            <p style={{ margin: 0, color: 'var(--text-2)', fontSize: '0.9rem' }}>Run an audit to find gaps, assess readiness, and uncover risk areas in the selected documents.</p>
          </div>
          <button className="btn-primary" onClick={onRun} disabled={loading}>
            {loading ? 'Running Audit...' : 'Run Audit'}
          </button>
        </div>

        {error && (
          <div style={{ padding: '1rem', background: 'rgba(127,29,29,0.25)', border: '1px solid #7f1d1d', borderRadius: '8px', color: '#fca5a5' }}>
            {error.message || 'An error occurred during the audit.'}
          </div>
        )}

        {result && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            {result.readiness_verdict && (
              <div style={{ padding: '1.5rem', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '1rem' }}>
                  <span style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>Readiness Verdict:</span>
                  <span style={{ 
                    fontSize: '1.2rem', 
                    fontWeight: 'bold', 
                    color: result.readiness_verdict.level === 'High' ? '#34d399' : result.readiness_verdict.level === 'Medium' ? '#fbbf24' : '#f87171' 
                  }}>
                    {result.readiness_verdict.level || 'Unknown'}
                  </span>
                </div>
                {result.readiness_verdict.reasons?.length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: '1.5rem', color: 'var(--text-2)' }}>
                    {result.readiness_verdict.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                  </ul>
                )}
              </div>
            )}

            {result.coverage_summary?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Coverage Summary</div>
                <ul style={{ padding: '1rem 1rem 1rem 2.5rem', margin: 0 }}>
                  {result.coverage_summary.map((cov, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{cov}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.missing_knowledge?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Missing Knowledge</div>
                <ul style={{ padding: '1rem 1rem 1rem 2.5rem', margin: 0 }}>
                  {result.missing_knowledge.map((miss, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{miss}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.risk_areas?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Risk Areas</div>
                <ul style={{ padding: '1rem 1rem 1rem 2.5rem', margin: 0 }}>
                  {result.risk_areas.map((risk, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{risk}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.automation_readiness?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Automation Readiness</div>
                <div style={{ padding: '1rem' }}>
                  {result.automation_readiness.map((ar, i) => (
                    <div key={i} style={{ marginBottom: i < result.automation_readiness.length - 1 ? '1rem' : 0 }}>
                      <strong style={{ display: 'block', marginBottom: '0.25rem' }}>{ar.category}</strong>
                      <ul style={{ margin: 0, paddingLeft: '1.5rem', color: 'var(--text-2)' }}>
                        {ar.items?.map((item, j) => <li key={j}>{item}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.suggested_next_documents?.length > 0 && (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--surface-3)', padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', fontWeight: 'bold' }}>Suggested Next Documents</div>
                <ul style={{ padding: '1rem 1rem 1rem 2.5rem', margin: 0 }}>
                  {result.suggested_next_documents.map((doc, i) => (
                    <li key={i} style={{ marginBottom: '0.5rem' }}>{doc}</li>
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
