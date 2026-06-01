export default function MetricsBar({ statusLoading, docCount, pageCount, chunkCount }) {
  return (
    <div className="metrics" id="metrics">
      <div className="metric-card">
        <span className="label">Documents</span>
        <span className="value" id="metDocs">{statusLoading ? '…' : docCount}</span>
      </div>
      <div className="metric-card">
        <span className="label">Pages</span>
        <span className="value" id="metPages">{statusLoading ? '…' : pageCount}</span>
      </div>
      <div className="metric-card">
        <span className="label">Chunks</span>
        <span className="value" id="metChunks">{statusLoading ? '…' : chunkCount}</span>
      </div>
    </div>
  )
}
