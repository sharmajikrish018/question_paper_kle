/**
 * lib/subjectContext.ts
 * Subject context save/restore and switch protocol.
 * Context = {page, filters, drafts, scroll, wizard state, etc.}
 */

import { api, setActiveSubject, getActiveSubject } from './api'

const CTX_PREFIX = 'ctx:'

/** Save context for a subject: PUT to API and mirror to localStorage. */
export async function saveContext(
  subjectId: string,
  ctx: Record<string, unknown>
): Promise<void> {
  if (!subjectId) return
  try {
    // Mirror to localStorage immediately (instant restore on next load)
    if (typeof window !== 'undefined') {
      localStorage.setItem(`${CTX_PREFIX}${subjectId}`, JSON.stringify(ctx))
    }
    // Persist to backend (best-effort — don't block UI)
    await api.putSubjectContext(subjectId, ctx)
  } catch {
    // Silently ignore — localStorage copy is still good
  }
}

/** Load context for a subject: GET from API, fall back to localStorage. */
export async function loadContext(
  subjectId: string
): Promise<Record<string, unknown>> {
  if (!subjectId) return {}
  try {
    const ctx = await api.getSubjectContext(subjectId)
    // Sync winner to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem(`${CTX_PREFIX}${subjectId}`, JSON.stringify(ctx))
    }
    return ctx
  } catch {
    // Fallback to localStorage
    if (typeof window !== 'undefined') {
      const raw = localStorage.getItem(`${CTX_PREFIX}${subjectId}`)
      if (raw) {
        try { return JSON.parse(raw) } catch { /* ignore */ }
      }
    }
    return {}
  }
}

/** Clear all client-side state/caches for the previous subject. */
export function clearClientState(): void {
  // Nothing to clear beyond what the new subject load already replaces.
  // Individual pages refetch when subject changes.
  // (Add React Query / SWR cache invalidation here if adopted later.)
}

/**
 * Full subject switch protocol:
 * (a) flush current subject's context
 * (b) abort stale requests + set new active subject
 * (c) clear client-side state
 * (d) load new subject's context
 * (e) call onSwitch callback (e.g. router.refresh or state setter)
 */
export async function switchSubject(
  toSubjectId: string,
  opts: {
    currentContext?: Record<string, unknown>
    onSwitch?: (ctx: Record<string, unknown>) => void
  } = {}
): Promise<Record<string, unknown>> {
  const from = getActiveSubject()

  // (a) Flush current context
  if (from && opts.currentContext) {
    await saveContext(from, opts.currentContext)
  }

  // (b) Set new active (aborts in-flight requests for old subject)
  setActiveSubject(toSubjectId)

  // Persist to backend
  try {
    await api.setActiveSubjectId(toSubjectId)
  } catch { /* ignore — local state is already updated */ }

  // (c) Clear stale state
  clearClientState()

  // (d) Load new context
  const newCtx = await loadContext(toSubjectId)

  // (e) Notify
  opts.onSwitch?.(newCtx)

  return newCtx
}
