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
    <div className="chat-container">
      <div className="chat-history">
        <button onClick={onBack} className="btn" style={{ marginBottom: '1rem' }}>
          Back to chat
        </button>
        
        <h2>Flashcards</h2>
        
        {loading && <div style={{ opacity: 0.7, margin: '1rem 0' }}>Loading flashcards...</div>}
        {error && <div style={{ color: 'red', margin: '1rem 0' }}>{error.message || 'Error generating flashcards'}</div>}
        
        {!loading && !error && !hasCards && <div>No flashcards available.</div>}
        
        {!loading && !error && hasCards && currentCard && (
          <div style={{ marginTop: '1rem', maxWidth: '600px', margin: '1rem auto' }}>
            <div style={{ textAlign: 'center', marginBottom: '1rem', opacity: 0.8 }}>
              Card {currentIndex + 1} of {flashcards.length}
            </div>
            
            <div 
              style={{
                padding: '2rem',
                border: '1px solid #ccc',
                borderRadius: '8px',
                minHeight: '200px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                textAlign: 'center',
                backgroundColor: flipped ? '#f9f9f9' : '#fff'
              }}
            >
              {!flipped ? (
                <div>
                  <h3 style={{ margin: 0 }}>
                    <SafeMarkdown content={currentCard.question} inline />
                  </h3>
                </div>
              ) : (
                <div style={{ width: '100%', textAlign: 'left' }}>
                  <div style={{ marginBottom: '1rem', fontWeight: 'bold' }}>
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
            
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1.5rem', alignItems: 'center' }}>
              <button 
                className="btn" 
                onClick={handlePrev} 
                disabled={currentIndex === 0}
              >
                Previous
              </button>
              
              <button 
                className="btn" 
                style={{ fontWeight: 'bold' }}
                onClick={() => setFlipped(!flipped)}
              >
                {flipped ? 'Show Question' : 'Flip'}
              </button>
              
              <button 
                className="btn" 
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
