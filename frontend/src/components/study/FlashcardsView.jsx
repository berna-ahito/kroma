import React, { useState, useMemo, useEffect } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import StudySources from './StudySources.jsx'

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
                    <SafeMarkdown content={currentCard.question} inline />
                  </h3>
                </div>
              ) : (
                <div className="study-flashcard-face study-flashcard-answer">
                  <span className="tool-kicker">Answer</span>
                  <div className="study-flashcard-answer-text">
                    <SafeMarkdown content={currentCard.answer} inline />
                  </div>
                  {currentCard.source_ids && currentCard.source_ids.length > 0 && (
                    <StudySources 
                      sourceIds={currentCard.source_ids} 
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
