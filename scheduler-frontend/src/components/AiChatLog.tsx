import type { AiChatMessage } from '../hooks/useAiChat'
import type { PendingSchedule } from '../api'
import './AiChatLog.css'

interface Props {
  messages: AiChatMessage[]
  sending: boolean
  onGenerateNow: (index: number, pending: PendingSchedule) => void
  onCancelSchedule: (index: number) => void
}

function AiChatLog({ messages, sending, onGenerateNow, onCancelSchedule }: Props) {
  return (
    <>
      {messages.map((m, i) => (
        <div key={i} className={`ai-message ai-message-${m.role}`}>
          <div className="ai-bubble">
            <p>{m.content}</p>

            {m.pendingSchedule && m.scheduleStatus === 'pending' && (
              <div className="ai-schedule-actions">
                <button type="button" onClick={() => onGenerateNow(i, m.pendingSchedule!)}>
                  Generate now
                </button>
                <button type="button" onClick={() => onCancelSchedule(i)}>
                  Never mind
                </button>
              </div>
            )}
            {m.scheduleStatus === 'generating' && <p className="ai-schedule-status">Generating...</p>}
            {m.scheduleStatus === 'done' && <p className="ai-schedule-status ai-success">{m.scheduleResult}</p>}
            {m.scheduleStatus === 'error' && <p className="ai-schedule-status ai-errors">{m.scheduleResult}</p>}
            {m.scheduleStatus === 'cancelled' && <p className="ai-schedule-status">Cancelled.</p>}
          </div>
        </div>
      ))}
      {sending && (
        <div className="ai-message ai-message-assistant">
          <div className="ai-bubble ai-thinking">Thinking...</div>
        </div>
      )}
    </>
  )
}

export default AiChatLog
