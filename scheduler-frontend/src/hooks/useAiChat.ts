import { useState } from 'react'
import { chatWithAi, confirmAiProposal, type ChatTurn, type PendingSchedule } from '../api'
import { emitConstraintApplied } from '../aiConstraintEvents'

export interface AiChatMessage {
  role: 'user' | 'assistant'
  content: string
  pendingSchedule?: PendingSchedule
  scheduleStatus?: 'pending' | 'generating' | 'done' | 'error' | 'cancelled'
  scheduleResult?: string
}

/** Shared conversation state/logic for the AI assistant chat -- used by
 * both the full AiAssistant page and the floating AiChatWidget so the
 * send/generate/clear behavior only lives in one place. Each caller
 * gets its own independent conversation (the widget and the full page
 * do not share history). */
export function useAiChat(restaurantId: number | undefined) {
  const [messages, setMessages] = useState<AiChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function sendMessage(text: string) {
    if (!restaurantId || !text.trim() || sending) return

    const history: ChatTurn[] = messages.map((m) => ({ role: m.role, content: m.content }))
    const userMessage: AiChatMessage = { role: 'user', content: text.trim() }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setSending(true)
    setError(null)

    try {
      const result = await chatWithAi(restaurantId, text.trim(), history)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.reply,
          pendingSchedule: result.pending_schedule ?? undefined,
          scheduleStatus: result.pending_schedule ? 'pending' : undefined,
        },
      ])
      if (result.applied) {
        emitConstraintApplied()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSending(false)
    }
  }

  function updateMessageScheduleStatus(index: number, patch: Partial<AiChatMessage>) {
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, ...patch } : m)))
  }

  async function handleGenerateNow(index: number, pending: PendingSchedule) {
    if (!restaurantId) return
    updateMessageScheduleStatus(index, { scheduleStatus: 'generating' })
    try {
      const result = (await confirmAiProposal(restaurantId, {
        action: 'generate_schedule',
        week_start: pending.week_start,
        time_limit: pending.time_limit,
        validation_errors: [],
        warnings: [],
      })) as {
        assignments_saved: number
        total_cost: number
        understaffed_shifts: number
      }
      updateMessageScheduleStatus(index, {
        scheduleStatus: 'done',
        scheduleResult: `Generated — ${result.assignments_saved} assignments saved, total cost $${result.total_cost.toLocaleString()}, ${result.understaffed_shifts} understaffed shift(s).`,
      })
    } catch (err) {
      updateMessageScheduleStatus(index, {
        scheduleStatus: 'error',
        scheduleResult: err instanceof Error ? err.message : String(err),
      })
    }
  }

  function handleCancelSchedule(index: number) {
    updateMessageScheduleStatus(index, { scheduleStatus: 'cancelled' })
  }

  function handleClear() {
    setMessages([])
    setError(null)
  }

  return {
    messages,
    input,
    setInput,
    sending,
    error,
    sendMessage,
    handleGenerateNow,
    handleCancelSchedule,
    handleClear,
  }
}
