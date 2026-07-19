import { useEffect, useRef } from 'react'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { useAiChat } from '../hooks/useAiChat'
import AiChatLog from '../components/AiChatLog'
import './AiAssistant.css'

const EXAMPLE_PROMPTS = [
  "Don't let anyone work more than 5 days in a row",
  'Require at least 8 hours of rest between shifts',
  "Generate next week's schedule",
]

function AiAssistant() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()
  const {
    messages,
    input,
    setInput,
    sending,
    error,
    sendMessage,
    handleGenerateNow,
    handleCancelSchedule,
    handleClear,
  } = useAiChat(restaurant?.restaurant_id)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  if (restaurantLoading) return <p>Loading...</p>
  if (restaurantError) return <p className="form-error">{restaurantError}</p>

  return (
    <div className="ai-page">
      <div className="ai-page-header">
        <div>
          <h1>AI Assistant</h1>
          <p className="ai-intro">
            Chat in plain English to configure scheduling rules or generate a week's schedule. Constraint
            changes apply as soon as I have enough information — I'll ask if something's missing.
          </p>
        </div>
        {messages.length > 0 && (
          <button type="button" className="ai-clear-button" onClick={handleClear}>
            Clear conversation
          </button>
        )}
      </div>

      {messages.length === 0 && (
        <div className="ai-examples">
          {EXAMPLE_PROMPTS.map((example) => (
            <button key={example} type="button" className="ai-example-chip" onClick={() => sendMessage(example)}>
              {example}
            </button>
          ))}
        </div>
      )}

      <div className="ai-chat-log">
        <AiChatLog
          messages={messages}
          sending={sending}
          onGenerateNow={handleGenerateNow}
          onCancelSchedule={handleCancelSchedule}
        />
        <div ref={bottomRef} />
      </div>

      {error && <p className="form-error">Could not reach the AI assistant: {error}</p>}

      <div className="ai-prompt-row">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. Require at least 2 leaders present on Saturdays  (Enter to send, Shift+Enter for a new line)"
          rows={2}
        />
        <button onClick={() => sendMessage(input)} disabled={sending || !input.trim()}>
          {sending ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default AiAssistant
