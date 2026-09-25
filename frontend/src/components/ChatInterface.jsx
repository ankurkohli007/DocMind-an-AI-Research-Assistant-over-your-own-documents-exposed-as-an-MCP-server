import { useState, useRef, useEffect } from 'react'

function ChatInterface({ backendUrl }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const question = input.trim()
    setInput('')
    setLoading(true)
    setError(null)

    // Add user message immediately
    setMessages((prev) => [...prev, { role: 'user', content: question }])

    try {
      const res = await fetch(`${backendUrl}/api/v1/queries/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      const data = await res.json()
      console.log('QUERY RESPONSE:', data)
      console.log('CITATIONS:', JSON.stringify(data.citations, null, 2))

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to get answer')
      }

      // Add assistant message with answer and citations
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          citations: data.citations || [],
        },
      ])
    } catch (err) {
      setError(err.message)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}`,
          isError: true,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-interface">
      <h2>Ask Questions</h2>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Upload a PDF document and start asking questions about its content.</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.isError ? (
                <div className="error-message">{msg.content}</div>
              ) : (
                <div className="message-text">{msg.content}</div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="citations">
                  <h4>Sources:</h4>
                  <ul>
                    {msg.citations.map((cite, i) => (
                      <li key={i}>
                        <strong>{cite.filename}</strong>
                        <span className="snippet">"{cite.snippet}"</span>
                        <span className="similarity">
                          (similarity: {Math.round(cite.similarity_score * 100)}%)
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {error && !loading && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="chat-form">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents..."
          disabled={loading}
          className="chat-input"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="btn btn-primary"
        >
          {loading ? 'Thinking...' : 'Ask'}
        </button>
      </form>
    </div>
  )
}

export default ChatInterface