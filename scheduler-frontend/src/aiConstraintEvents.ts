/** The floating AiChatWidget (mounted once in Layout) can apply a
 * constraint change from any page, including while the user is sitting
 * on the Constraints page. Constraints.tsx has no other way to learn
 * that happened, so useAiChat broadcasts this event whenever a chat
 * turn actually writes a restaurant_constraints row, and Constraints.tsx
 * listens for it to refresh the "Currently configured" table. */
const AI_CONSTRAINT_APPLIED_EVENT = 'ai-constraint-applied'

export function emitConstraintApplied() {
  window.dispatchEvent(new Event(AI_CONSTRAINT_APPLIED_EVENT))
}

export function onConstraintApplied(callback: () => void): () => void {
  window.addEventListener(AI_CONSTRAINT_APPLIED_EVENT, callback)
  return () => window.removeEventListener(AI_CONSTRAINT_APPLIED_EVENT, callback)
}
