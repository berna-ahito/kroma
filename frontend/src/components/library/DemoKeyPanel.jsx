export default function DemoKeyPanel({
  demoKeyInput,
  setDemoKeyInput,
  demoKeyMessage,
  onApplyDemoKey,
  onClearDemoKey,
}) {
  return (
    <>
      <div className="sidebar-label">Demo access</div>
      <input
        id="demoKeyInput"
        type="password"
        placeholder="Demo key if required"
        autoComplete="off"
        value={demoKeyInput}
        onChange={event => {
          setDemoKeyInput(event.target.value)
        }}
        onKeyDown={event => {
          if (event.key === 'Enter') {
            event.preventDefault()
            onApplyDemoKey()
          }
        }}
        style={{
          width: '100%',
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          color: 'var(--text)',
          padding: '0.65rem 0.75rem',
          fontFamily: "'Outfit',sans-serif",
          fontSize: '0.9rem',
          outline: 'none'
        }}
      />
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
        <button
          type="button"
          className="btn-primary"
          onClick={onApplyDemoKey}
          style={{ flex: 1, padding: '0.55rem 0.75rem' }}
        >
          Apply
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={onClearDemoKey}
          style={{ flex: 1, padding: '0.55rem 0.75rem' }}
        >
          Clear
        </button>
      </div>
      {demoKeyMessage && <div style={{ color: 'var(--warning-text)', fontSize: '0.85rem', marginTop: '0.4rem', wordBreak: 'break-word', padding: '0 0.2rem' }}>{demoKeyMessage}</div>}
    </>
  )
}
