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
  if (value.label != null && value.label !== '') return valueToText(value.label)
  return JSON.stringify(value)
}

function sourceIdsFor(value) {
  return Array.isArray(value?.source_ids) ? value.source_ids : []
}

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
      if (normalizeLetter(selected) === normalizeLetter(valueToText(q.answer))) {
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
              const choices = Array.isArray(q.choices) ? q.choices : []
              const selectedChoice = answers[qIndex]
              const isCorrect = submitted && normalizeLetter(selectedChoice) === normalizeLetter(valueToText(q.answer))
              const isWrong = submitted && !isCorrect
              
              return (
                <div 
                  key={qIndex} 
                  className={`tool-card quiz-question-card${submitted ? (isCorrect ? ' is-correct' : ' is-incorrect') : ''}`}
                >
                  <div className="tool-kicker">Question {qIndex + 1}</div>
                  <h3 className="quiz-question-title"><SafeMarkdown content={valueToText(q.question)} inline /></h3>
                  
                  <div className="tool-choice-list">
                    {choices.map((choice, cIndex) => {
                      const choiceText = valueToText(choice)
                      const isSelected = selectedChoice === choiceText
                      const isActualAnswer = submitted && normalizeLetter(choiceText) === normalizeLetter(valueToText(q.answer))
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
                          onClick={() => handleSelect(qIndex, cIndex, choiceText)}
                        >
                          <input 
                            type="radio" 
                            name={`q-${qIndex}`}
                            checked={isSelected}
                            readOnly
                          />
                          <div className="tool-choice-text">
                            <SafeMarkdown content={choiceText} inline />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  
                  {submitted && (
                    <div className="quiz-feedback">
                      <div className={`tool-pill${isCorrect ? ' tool-success' : ' tool-error-pill'}`}>
                        {isCorrect ? 'Correct' : 'Incorrect'}
                        {!isCorrect && ` (Answer: ${normalizeLetter(valueToText(q.answer))})`}
                      </div>
                      
                      {q.explanation && (
                        <div className="tool-markdown">
                          <SafeMarkdown content={valueToText(q.explanation)} />
                        </div>
                      )}
                      
                      <StudySources 
                        sourceIds={sourceIdsFor(q)}
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
