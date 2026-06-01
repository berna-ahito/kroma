export default function ExportButton({ visible, onExport }) {
  if (!visible) {
    return null
  }

  return (
    <button className="btn-secondary" id="exportBtn" onClick={onExport} style={{ width: 'auto', padding: '0.5rem 1.25rem', flexShrink: 0, whiteSpace: 'nowrap', maxWidth: '140px' }}>
      <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M12 3v12"/>
        <path d="m7 10 5 5 5-5"/>
        <path d="M5 21h14"/>
      </svg>
      <span>Export Chat</span>
    </button>
  )
}
