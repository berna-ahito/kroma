import React from 'react'
import SourceCard from '../chat/SourceCard.jsx'

export default function BusinessSources({ sourceIds = [], sources = [] }) {
  if (!sourceIds || sourceIds.length === 0) {
    return <div className="business-sources-empty">No sources referenced.</div>
  }

  // Build maps for efficient and flexible resolution
  const idMap = new Map()
  const docChunkIdMap = new Map()
  const chunkIdMap = new Map()

  for (const src of sources) {
    if (src.id) idMap.set(src.id, src)
    if (src.doc_chunk_id) docChunkIdMap.set(src.doc_chunk_id, src)
    if (src.chunk_id) chunkIdMap.set(src.chunk_id, src)
  }

  const resolvedSources = []
  
  for (const sid of sourceIds) {
    let resolved = idMap.get(sid)
    if (!resolved) resolved = docChunkIdMap.get(sid)
    if (!resolved) resolved = chunkIdMap.get(sid)
    
    if (resolved) {
      // Ensure uniqueness if multiple IDs resolve to the same source
      if (!resolvedSources.includes(resolved)) {
        resolvedSources.push(resolved)
      }
    }
  }

  if (resolvedSources.length === 0) {
    return <div className="business-sources-empty">No sources referenced.</div>
  }

  return (
    <div className="business-sources">
      <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: 'var(--text-2)' }}>Sources Used:</div>
      <div className="source-list">
        {resolvedSources.map((source, i) => {
          const key = source.doc_chunk_id || source.chunk_id || source.id || `fallback-${i}`
          return <SourceCard key={key} source={source} />
        })}
      </div>
    </div>
  )
}
