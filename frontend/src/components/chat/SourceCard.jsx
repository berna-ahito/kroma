import React from 'react'

// Port of sourceLocationLabel from static/app.js:340-345
function sourceLocationLabel(source) {
  if (source?.location_label) return source.location_label
  if (source?.page !== undefined && source?.page !== null && source?.page !== '')
    return `Page ${source.page}`
  return 'Document'
}

// Port of createSourceCard from static/app.js:363-387
export default function SourceCard({ source }) {
  const filename = source?.source || 'Unknown source'
  const location = sourceLocationLabel(source)
  const score = Number.isFinite(Number(source?.score))
    ? `${source.score}%`
    : 'unknown score'

  return (
    <div className="source-tag">
      <div className="source-meta">
        {filename} {'•'} {location} {'•'} {'Relevance'} {score}
      </div>
      {source?.preview && (
        <div className="source-preview">{source.preview}</div>
      )}
    </div>
  )
}
