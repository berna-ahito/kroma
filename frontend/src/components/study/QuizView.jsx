import React, { useState, useMemo, useEffect } from 'react'
import SafeMarkdown from '../chat/SafeMarkdown.jsx'
import StudySources from './StudySources.jsx'

export default function QuizView({ data, loading, error, onBack }) {
  const [answers, setAnswers] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [submitError, setSubmitError] = useState('')

  // Reset state when new data arrives
  useEffect(() => {
    setAnswers({})
    setSubmitted(false)
    setSubmitError('')
  }, [data])

  const sourceMap = useMemo(() => {
    const map = new Map()
    if (data?.sources) {
      data.sources.forEach(src => map.set(src.id, src))
    }
    return map
  }, [data])

  const questions = data?.questions || []
  const hasQuestions = questions.length > 0

  const handleSelect = (qIndex, choiceIndex, choiceText) => {
    if (submitted) return
    setAnswers(prev => ({
      ...prev,
      [qIndex]: choiceText
    }))
    setSubmitError('')
  }

  const normalizeLetter = (text) => {
    if (!text) return ''
    return String(text).trim().charAt(0).toUpperCase()
  }

  const handleSubmit = () => {
    if (Object.keys(answers).length < questions.length) {
      setSubmitError('Please answer all questions before submitting.')
      return
    }
    setSubmitted(true)
    setSubmitError('')
  }

  // Calculate score if submitted
  const score = useMemo(() => {
    if (!submitted) return 0
    let correct = 0
    questions.forEach((q, idx) => {
      const selected = answers[idx]
      if (normalizeLetter(selected) === normalizeLetter(q.answer)) {
        correct++
      }
    })
    return correct
  }, [submitted, answers, questions])

  return (
    <div className="chat-container">
      <div className="chat-history">
        <button onClick={onBack} className="btn" style={{ marginBottom: '1rem' }}>
          Back to chat
        </button>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Quiz</h2>
          {submitted && (
            <div style={{ fontWeight: 'bold', fontSize: '1.2rem' }}>
              Score: {score} / {questions.length}
            </div>
          )}
        </div>
        
        {loading && <div style={{ opacity: 0.7, margin: '1rem 0' }}>Loading quiz...</div>}
        {error && <div style={{ color: 'red', margin: '1rem 0' }}>{error.message || 'Error generating quiz'}</div>}
        
        {!loading && !error && !hasQuestions && <div style={{ marginTop: '1rem' }}>No questions available.</div>}
        
        {!loading && !error && hasQuestions && (
          <div style={{ marginTop: '1.5rem' }}>
            {questions.map((q, qIndex) => {
              const selectedChoice = answers[qIndex]
              const isCorrect = submitted && normalizeLetter(selectedChoice) === normalizeLetter(q.answer)
              const isWrong = submitted && !isCorrect
              
              return (
                <div 
                  key={qIndex} 
                  style={{ 
                    marginBottom: '2rem', 
                    padding: '1.5rem',
                    border: '1px solid #ddd',
                    borderRadius: '8px',
                    backgroundColor: submitted ? (isCorrect ? '#f0fdf4' : '#fef2f2') : 'transparent'
                  }}
                >
                  <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>
                    {qIndex + 1}. <SafeMarkdown content={q.question} inline />
                  </h3>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {q.choices.map((choice, cIndex) => {
                      const isSelected = selectedChoice === choice
                      const isActualAnswer = submitted && normalizeLetter(choice) === normalizeLetter(q.answer)
                      
                      let choiceStyle = {
                        padding: '0.75rem',
                        border: '1px solid #ccc',
                        borderRadius: '4px',
                        cursor: submitted ? 'default' : 'pointer',
                        backgroundColor: isSelected ? '#eef2ff' : 'transparent',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '0.5rem'
                      }
                      
                      if (submitted) {
                        if (isActualAnswer) {
                          choiceStyle.backgroundColor = '#dcfce7'
                          choiceStyle.borderColor = '#22c55e'
                        } else if (isSelected && !isActualAnswer) {
                          choiceStyle.backgroundColor = '#fee2e2'
                          choiceStyle.borderColor = '#ef4444'
                        }
                      }
                      
                      return (
                        <div 
                          key={cIndex} 
                          style={choiceStyle}
                          onClick={() => handleSelect(qIndex, cIndex, choice)}
                        >
                          <input 
                            type="radio" 
                            name={`q-${qIndex}`}
                            checked={isSelected}
                            readOnly
                            style={{ marginTop: '0.2rem' }}
                          />
                          <div style={{ flex: 1 }}>
                            <SafeMarkdown content={choice} inline />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  
                  {submitted && (
                    <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid #ddd' }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: isCorrect ? '#166534' : '#991b1b' }}>
                        {isCorrect ? '✓ Correct' : '✗ Incorrect'} 
                        {!isCorrect && ` (Answer: ${normalizeLetter(q.answer)})`}
                      </div>
                      
                      {q.explanation && (
                        <div style={{ marginBottom: '1rem' }}>
                          <SafeMarkdown content={q.explanation} />
                        </div>
                      )}
                      
                      <StudySources 
                        sourceIds={q.source_ids || []} 
                        sourceMap={sourceMap} 
                        showUnsourced={true} 
                      />
                    </div>
                  )}
                </div>
              )
            })}
            
            {!submitted && (
              <div style={{ marginTop: '2rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <button 
                  className="btn" 
                  onClick={handleSubmit}
                  style={{ fontWeight: 'bold', padding: '0.75rem 1.5rem' }}
                >
                  Submit Quiz
                </button>
                {submitError && <span style={{ color: 'red' }}>{submitError}</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
