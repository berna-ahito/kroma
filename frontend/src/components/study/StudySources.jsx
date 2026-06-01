import React from 'react'
import SourceCard from '../chat/SourceCard.jsx'

export default function StudySources({ sourceIds = [], sourceMap = new Map(), showUnsourced = true }) {
  const resolved = sourceIds
    .map(id => sourceMap.get(id))
    .filter(Boolean)

  if (resolved.length === 0) {
    return showUnsourced ? (
      <div className="source-tag" style={{ opacity: 0.7 }}>
        <div className="source-meta">Unsourced</div>
      </div>
    ) : null
  }

  return (
    <div className="sources-container">
      {resolved.map((source, idx) => {
        const key = source.doc_chunk_id || source.chunk_id || source.id || `${source.source}-${source.location_label}-${idx}`
        return <SourceCard key={key} source={source} />
      })}
    </div>
  )
}
