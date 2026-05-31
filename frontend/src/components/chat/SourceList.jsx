import React, { useState, useId } from 'react'
import SourceCard from './SourceCard.jsx'

const CHAT_SOURCE_PREVIEW_LIMIT = 3

// Stable key for React list rendering.
// Priority: doc_chunk_id → chunk_id → id → fallback composite string
function sourceKey(source, index) {
  return (
    source?.doc_chunk_id ||
    source?.chunk_id ||
    source?.id ||
    `${source?.source || 'unknown'}-${source?.location_label || source?.page || 'document'}-${index}`
  )
}

// Port of sourceLocationLabel from static/app.js:340-345
function sourceLocationLabel(source) {
  if (source?.location_label) return source.location_label
  if (source?.page !== undefined && source?.page !== null && source?.page !== '')
    return `Page ${source.page}`
  return 'Document'
}

// Port of formatSourceSummary from static/app.js:351-361
function formatSourceSummary(sources) {
  const first = sources[0] || {}
  const filename = first?.source || 'Unknown source'
  const firstLocation = `${filename} \u00b7 ${sourceLocationLabel(first)}`
  const uniqueLocations = new Set(
    sources.map(s => `${s?.source || 'Unknown source'} \u00b7 ${sourceLocationLabel(s)}`)
  )
  const more = uniqueLocations.size > 1 ? ` + ${uniqueLocations.size - 1} more` : ''
  const chunks = sources.length === 1 ? '1 chunk' : `${sources.length} chunks`
  return `Sources used: ${firstLocation}${more} \u00b7 ${chunks}`
}

// Port of appendChatSources from static/app.js:408-470
// Props:
//   sources — non-empty array of source objects (caller guarantees this)
export default function SourceList({ sources }) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)

  // useId produces a stable, unique id per component instance (React 18+)
  const reactId = useId()
  const detailId = `chatSources-${reactId.replace(/:/g, '')}`

  const summaryText = formatSourceSummary(sources)
  const chunkCount = sources.length
  const chunkLabel = chunkCount === 1 ? 'chunk' : 'chunks'

  function handleToggle() {
    setDetailsOpen(open => !open)
  }

  function handleShowAll() {
    setShowAll(true)
  }

  return (
    <>
      {/* Summary bar — mirrors .source-summary in static app */}
      <div className="source-summary">
        <span className="source-summary-text">{summaryText}</span>
        <button
          type="button"
          className="source-toggle"
          aria-expanded={detailsOpen}
          aria-controls={detailId}
          aria-label={
            detailsOpen
              ? 'Hide source details'
              : `Show source details for ${chunkCount} ${chunkLabel}`
          }
          onClick={handleToggle}
        >
          {detailsOpen ? 'Hide details' : 'Show details'}
        </button>
      </div>

      {/* Source card list — mirrors .sources.chat-sources in static app */}
      <div
        className="sources chat-sources"
        id={detailId}
        hidden={!detailsOpen}
      >
        {sources.map((src, i) => {
          const visible = showAll || i < CHAT_SOURCE_PREVIEW_LIMIT
          if (!visible) return null
          return <SourceCard key={sourceKey(src, i)} source={src} />
        })}

        {/* Show all sources — disappears after clicked (not just hidden) */}
        {!showAll && sources.length > CHAT_SOURCE_PREVIEW_LIMIT && (
          <button
            type="button"
            className="source-show-all"
            aria-expanded={detailsOpen}
            aria-controls={detailId}
            aria-label={`Show all ${chunkCount} source cards`}
            onClick={handleShowAll}
          >
            Show all sources
          </button>
        )}
      </div>
    </>
  )
}
