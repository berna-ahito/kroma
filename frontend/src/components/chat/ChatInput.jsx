export default function ChatInput({
  inputValue,
  onInputChange,
  onSend,
  isLoading,
  textareaRef,
}) {
  const canSend = inputValue.trim() !== '' && !isLoading

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="input-bar">
      <textarea
        ref={textareaRef}
        id="chatInput"
        value={inputValue}
        onChange={e => onInputChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything about your documents..."
        rows={1}
        disabled={isLoading}
        aria-label="Chat input"
      />
      <button
        className="btn-send"
        id="sendBtn"
        onClick={onSend}
        disabled={!canSend}
        aria-label="Send message"
        title="Send message"
      >
        <svg className="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M12 19V5"/>
          <path d="m5 12 7-7 7 7"/>
        </svg>
      </button>
    </div>
  )
}
