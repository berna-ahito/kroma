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
    <div className="tool-shell">
      <div className="tool-header">
        <div className="tool-heading">
          <h2>Quiz</h2>
          <p className="tool-subtitle">Answer each question, then submit to reveal explanations and sources.</p>
        </div>
        <button onClick={onBack} className="tool-back-button">
          Back to chat
        </button>
      </div>

      <div className="tool-body">
        {submitted && (
          <div className="tool-card quiz-score-card">
            <span className="tool-kicker">Score</span>
            <strong>{score} / {questions.length}</strong>
          </div>
        )}

        {loading && <div className="tool-state">Loading quiz...</div>}
        {error && <div className="tool-error">{error.message || 'Error generating quiz'}</div>}
        
        {!loading && !error && !hasQuestions && <div className="tool-state">No questions available.</div>}
        
        {!loading && !error && hasQuestions && (
          <div className="quiz-tool-list">
            {questions.map((q, qIndex) => {
              const selectedChoice = answers[qIndex]
              const isCorrect = submitted && normalizeLetter(selectedChoice) === normalizeLetter(q.answer)
              const isWrong = submitted && !isCorrect
              
              return (
                <div 
                  key={qIndex} 
                  className={`tool-card quiz-question-card${submitted ? (isCorrect ? ' is-correct' : ' is-incorrect') : ''}`}
                >
                  <div className="tool-kicker">Question {qIndex + 1}</div>
                  <h3 className="quiz-question-title"><SafeMarkdown content={q.question} inline /></h3>
                  
                  <div className="tool-choice-list">
                    {q.choices.map((choice, cIndex) => {
                      const isSelected = selectedChoice === choice
                      const isActualAnswer = submitted && normalizeLetter(choice) === normalizeLetter(q.answer)
                      const choiceClass = [
                        'tool-choice',
                        isSelected ? 'tool-choice--selected' : '',
                        isActualAnswer ? 'tool-choice--correct' : '',
                        submitted && isSelected && !isActualAnswer ? 'tool-choice--incorrect' : '',
                      ].filter(Boolean).join(' ')
                      
                      return (
                        <div 
                          key={cIndex} 
                          className={choiceClass}
                          onClick={() => handleSelect(qIndex, cIndex, choice)}
                        >
                          <input 
                            type="radio" 
                            name={`q-${qIndex}`}
                            checked={isSelected}
                            readOnly
                          />
                          <div className="tool-choice-text">
                            <SafeMarkdown content={choice} inline />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  
                  {submitted && (
                    <div className="quiz-feedback">
                      <div className={`tool-pill${isCorrect ? ' tool-success' : ' tool-error-pill'}`}>
                        {isCorrect ? 'Correct' : 'Incorrect'}
                        {!isCorrect && ` (Answer: ${normalizeLetter(q.answer)})`}
                      </div>
                      
                      {q.explanation && (
                        <div className="tool-markdown">
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
              <div className="tool-actions quiz-submit-row">
                <button
                  className="btn-primary"
                  onClick={handleSubmit}
                >
                  Submit Quiz
                </button>
                {submitError && <span className="tool-inline-error">{submitError}</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
