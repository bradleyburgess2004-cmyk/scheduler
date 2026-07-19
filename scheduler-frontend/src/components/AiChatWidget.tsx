import { useEffect, useRef, useState } from 'react'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import { useAiChat } from '../hooks/useAiChat'
import AiChatLog from './AiChatLog'
import './AiChatWidget.css'

/** Floating AI assistant chat, mounted once in Layout so it's available
 * (and keeps its conversation) while browsing any page -- Schedule,
 * Employees, etc. Runs its own independent conversation from the full
 * /ai-assistant page's chat. */
function AiChatWidget() {
  const { restaurant } = useCurrentRestaurant()
  const [open, setOpen] = useState(false)
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
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <>
      {open && (
        <div className="ai-widget-panel">
          <div className="ai-widget-header">
            <span>AI Assistant</span>
            <div className="ai-widget-header-actions">
              {messages.length > 0 && (
                <button type="button" className="ai-widget-icon-button" title="Clear conversation" onClick={handleClear}>
                  ↺
                </button>
              )}
              <button type="button" className="ai-widget-icon-button" title="Close" onClick={() => setOpen(false)}>
                ×
              </button>
            </div>
          </div>

          <div className="ai-widget-log">
            {messages.length === 0 && (
              <p className="ai-widget-empty">
                Ask me to configure a scheduling rule or generate a week's schedule.
              </p>
            )}
            <AiChatLog
              messages={messages}
              sending={sending}
              onGenerateNow={handleGenerateNow}
              onCancelSchedule={handleCancelSchedule}
            />
            <div ref={bottomRef} />
          </div>

          {error && <p className="form-error ai-widget-error">{error}</p>}

          <div className="ai-widget-input-row">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message the AI assistant..."
              rows={2}
            />
            <button onClick={() => sendMessage(input)} disabled={sending || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        className="ai-widget-fab"
        title="AI Assistant"
        aria-label="Open AI Assistant chat"
        onClick={() => setOpen((prev) => !prev)}
      >
        <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">
          <path d="M12 2 L14.2 9.8 22 12 14.2 14.2 12 22 9.8 14.2 2 12 9.8 9.8 Z" />
        </svg>
      </button>
    </>
  )
}

export default AiChatWidget
