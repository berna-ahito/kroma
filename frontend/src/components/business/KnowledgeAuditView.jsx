import React from 'react'
import BusinessSources from './BusinessSources.jsx'

export default function KnowledgeAuditView({ onBack, onRun, data, loading, error }) {
  const result = data?.result
  const sources = data?.sources || []

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
                    {result.readiness_verdict.level || 'Unknown'}
                </strong>
                {result.readiness_verdict.reasons?.length > 0 && (
                  <ul className="tool-list">
                    {result.readiness_verdict.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                  </ul>
                )}
              </section>
            )}

            {result.coverage_summary?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Coverage Summary</h3>
                <ul className="tool-list">
                  {result.coverage_summary.map((cov, i) => (
                    <li key={i}>{cov}</li>
                  ))}
                </ul>
              </section>
            )}

            {result.missing_knowledge?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Missing Knowledge</h3>
                <ul className="tool-list">
                  {result.missing_knowledge.map((miss, i) => (
                    <li key={i}>{miss}</li>
                  ))}
                </ul>
              </section>
            )}

            {result.risk_areas?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Risk Areas</h3>
                <ul className="tool-list">
                  {result.risk_areas.map((risk, i) => (
                    <li key={i}>{risk}</li>
                  ))}
                </ul>
              </section>
            )}

            {result.automation_readiness?.length > 0 && (
              <section className="tool-card">
                <h3 className="tool-section-title">Automation Readiness</h3>
                <div className="tool-nested-list">
                  {result.automation_readiness.map((ar, i) => (
                    <div key={i} className="tool-nested-group">
                      <strong>{ar.category}</strong>
                      <ul className="tool-list">
                        {ar.items?.map((item, j) => <li key={j}>{item}</li>)}
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
                    <li key={i}>{doc}</li>
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
