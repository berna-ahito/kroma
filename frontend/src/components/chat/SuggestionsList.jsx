export default function SuggestionsList({ suggestions, onSelectSuggestion }) {
  return (
    <div className="suggestions" style={{ borderBottom: 'none', padding: '1rem 0' }}>
      <div className="suggestions-label">Suggested Questions</div>
      <div className="suggestions-row">
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            className="suggestion-btn"
            onClick={() => onSelectSuggestion(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}
