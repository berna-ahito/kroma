import React, { useState, useMemo, useEffect } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import StudySources from './StudySources.jsx'

function valueToText(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(valueToText).filter(Boolean).join('\n')
  if (typeof value !== 'object') return String(value)
  if (value.text != null && value.text !== '') return valueToText(value.text)
  if (value.area != null && value.area !== '') {
    const detail = value.detail ? `: ${valueToText(value.detail)}` : ''
    return `${valueToText(value.area)}${detail}`
  }
  if (value.detail != null && value.detail !== '') return valueToText(value.detail)
  if (value.question != null && value.question !== '') return valueToText(value.question)
  if (value.answer != null && value.answer !== '') return valueToText(value.answer)
  return JSON.stringify(value)
}

function sourceIdsFor(value) {
  return Array.isArray(value?.source_ids) ? value.source_ids : []
}

export default function FlashcardsView({ data, loading, error, onBack }) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  // Reset state when new data arrives
  useEffect(() => {
    setCurrentIndex(0)
    setFlipped(false)
  }, [data])

  const sourceMap = useMemo(() => {
    const map = new Map()
    if (data?.sources) {
      data.sources.forEach(src => map.set(src.id, src))
    }
    return map
  }, [data])

  const flashcards = data?.flashcards || []
  const hasCards = flashcards.length > 0
  const currentCard = hasCards ? flashcards[currentIndex] : null

  const handleNext = () => {
    if (currentIndex < flashcards.length - 1) {
      setCurrentIndex(c => c + 1)
      setFlipped(false)
    }
  }

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(c => c - 1)
      setFlipped(false)
    }
  }

  return (
    <div className="tool-shell">
      <div className="tool-header">
        <div className="tool-heading">
          <h2>Flashcards</h2>
          <p className="tool-subtitle">Review question and answer cards from the selected documents.</p>
        </div>
        <button onClick={onBack} className="tool-back-button">
          Back to chat
        </button>
      </div>

      <div className="tool-body">
        {loading && <div className="tool-state">Loading flashcards...</div>}
        {error && <div className="tool-error">{error.message || 'Error generating flashcards'}</div>}
        
        {!loading && !error && !hasCards && <div className="tool-state">No flashcards available.</div>}
        
        {!loading && !error && hasCards && currentCard && (
          <div className="flashcard-stage">
            <div className="tool-progress">
              Card {currentIndex + 1} of {flashcards.length}
            </div>
            
            <div 
              className={`study-flashcard-card${flipped ? ' is-flipped' : ''}`}
            >
              {!flipped ? (
                <div className="study-flashcard-face">
                  <span className="tool-kicker">Question</span>
                  <h3>
                    <SafeMarkdown content={valueToText(currentCard.question)} inline />
                  </h3>
                </div>
              ) : (
                <div className="study-flashcard-face study-flashcard-answer">
                  <span className="tool-kicker">Answer</span>
                  <div className="study-flashcard-answer-text">
                    <SafeMarkdown content={valueToText(currentCard.answer)} inline />
                  </div>
                  {sourceIdsFor(currentCard).length > 0 && (
                    <StudySources 
                      sourceIds={sourceIdsFor(currentCard)}
                      sourceMap={sourceMap} 
                      showUnsourced={true} 
                    />
                  )}
                </div>
              )}
            </div>
            
            <div className="tool-actions flashcard-actions">
              <button
                className="btn-secondary"
                onClick={handlePrev}
                disabled={currentIndex === 0}
              >
                Previous
              </button>
              
              <button
                className="btn-primary"
                onClick={() => setFlipped(!flipped)}
              >
                {flipped ? 'Show Question' : 'Flip'}
              </button>
              
              <button
                className="btn-secondary"
                onClick={handleNext}
                disabled={currentIndex === flashcards.length - 1}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
