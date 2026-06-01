import React from 'react'
import SourceCard from '../chat/SourceCard.jsx'

export function normalizeSourceIds(sourceIds) {
  if (!Array.isArray(sourceIds)) return []
  return sourceIds
    .map(id => (typeof id === 'string' || typeof id === 'number' ? String(id) : null))
    .filter(Boolean)
}

function sourceKey(source) {
  return String(
    source?.doc_chunk_id ||
    source?.chunk_id ||
    source?.id ||
    `${source?.source || 'unknown'}:${source?.page || ''}:${source?.preview || ''}`
  )
}

function sourceLabel(source) {
  const filename = source?.source || 'Unknown source'
  const location = source?.location_label || (source?.page != null && source?.page !== '' ? `Page ${source.page}` : 'Document')
  return `${filename}, ${location}`
}

export function resolveBusinessSourceRefs(sourceIds = [], sources = []) {
  const ids = normalizeSourceIds(sourceIds)

  const idMap = new Map()
  const docChunkIdMap = new Map()
  const chunkIdMap = new Map()
  const keyMap = new Map()

  for (const src of sources) {
    if (src.id) idMap.set(String(src.id), src)
    if (src.doc_chunk_id) docChunkIdMap.set(String(src.doc_chunk_id), src)
    if (src.chunk_id) chunkIdMap.set(String(src.chunk_id), src)
    keyMap.set(sourceKey(src), src)
  }

  const resolvedSources = []
  const unresolvedIds = []
  const seen = new Set()
  
  for (const sid of ids) {
    let resolved = idMap.get(sid)
    if (!resolved) resolved = docChunkIdMap.get(sid)
    if (!resolved) resolved = chunkIdMap.get(sid)
    if (!resolved) resolved = keyMap.get(sid)
    
    if (resolved) {
      const key = sourceKey(resolved)
      if (!seen.has(key)) {
        seen.add(key)
        resolvedSources.push(resolved)
      }
    } else if (!unresolvedIds.includes(sid)) {
      unresolvedIds.push(sid)
    }
  }

  return { ids, resolvedSources, unresolvedIds }
}

export function BusinessSourceRefs({ sourceIds = [], sources = [] }) {
  const { ids, resolvedSources, unresolvedIds } = resolveBusinessSourceRefs(sourceIds, sources)

  if (ids.length === 0) return null

  const labels = resolvedSources.map(sourceLabel)
  const title = [...labels, ...unresolvedIds.map(id => `Source ref ${id}`)].join('\n')
  const count = resolvedSources.length + unresolvedIds.length

  return (
    <span className="business-source-ref" title={title || undefined}>
      {count} source{count === 1 ? '' : 's'}
    </span>
  )
}

export default function BusinessSources({ sourceIds = [], sources = [], showAllWhenUnreferenced = false }) {
  const refs = resolveBusinessSourceRefs(sourceIds, sources)
  const ids = showAllWhenUnreferenced && refs.ids.length === 0 && sources.length > 0
    ? sources.map(source => sourceKey(source))
    : refs.ids
  const { resolvedSources, unresolvedIds } = ids === refs.ids
    ? refs
    : resolveBusinessSourceRefs(ids, sources)

  if (ids.length === 0) {
    return <div className="business-sources-empty">No sources referenced.</div>
  }

  if (resolvedSources.length === 0 && unresolvedIds.length === 0) {
    return <div className="business-sources-empty">No sources referenced.</div>
  }

  return (
    <div className="business-sources">
      <div className="business-sources-title">Sources Used</div>
      {resolvedSources.length > 0 && (
        <div className="source-list">
          {resolvedSources.map((source, i) => {
            const key = sourceKey(source) || `fallback-${i}`
            return <SourceCard key={key} source={source} />
          })}
        </div>
      )}
      {unresolvedIds.length > 0 && (
        <div className="business-unresolved-sources">
          Unresolved source refs: {unresolvedIds.join(', ')}
        </div>
      )}
    </div>
  )
}
