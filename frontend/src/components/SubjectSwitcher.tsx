'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api, setActiveSubject, getActiveSubject, initActiveSubjectFromStorage } from '@/lib/api'
import { switchSubject } from '@/lib/subjectContext'
import type { SubjectListItem } from '@/lib/api'

interface Props {
  /** If true, render an expanded card version for the dashboard. Sidebar uses compact mode. */
  variant?: 'sidebar' | 'dashboard'
}

export function SubjectSwitcher({ variant = 'sidebar' }: Props) {
  const router = useRouter()
  const [subjects, setSubjects] = useState<SubjectListItem[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [pendingSwitch, setPendingSwitch] = useState<string | null>(null)
  const [showUnsavedModal, setShowUnsavedModal] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Boot: init from localStorage, then fetch from server
  useEffect(() => {
    const stored = initActiveSubjectFromStorage()
    if (stored) setActiveId(stored)

    api.getActiveSubjectId().then(({ active_subject_id }) => {
      if (active_subject_id) {
        setActiveId(active_subject_id)
        setActiveSubject(active_subject_id)
        if (typeof window !== 'undefined') {
          localStorage.setItem('activeSubjectId', active_subject_id)
        }
      } else {
        setActiveId(null)
        setActiveSubject(null)
        if (typeof window !== 'undefined') {
          localStorage.removeItem('activeSubjectId')
        }
      }
    }).catch(() => {})

    api.listSubjects().then(setSubjects).catch(() => {})

    // Close dropdown on outside click
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const active = subjects.find(s => s.subject_id === activeId)

  async function doSwitch(toId: string) {
    if (toId === activeId || switching) return
    setSwitching(true)
    setOpen(false)
    try {
      await switchSubject(toId, {
        onSwitch: () => {
          setActiveId(toId)
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('activeSubjectChanged', { detail: { subjectId: toId } }))
          }
          // Trigger a soft navigation to reload data on the current page
          router.refresh()
        },
      })
    } catch { /* ignore */ } finally {
      setSwitching(false)
    }
  }

  function handleSelect(toId: string) {
    // Check for unsaved edits via a custom DOM event (pages can intercept)
    const evt = new CustomEvent('subjectSwitchRequested', {
      detail: { toId },
      bubbles: true,
      cancelable: true,
    })
    const cancelled = !document.dispatchEvent(evt)
    if (cancelled) {
      // Page signalled it has unsaved edits — show modal
      setPendingSwitch(toId)
      setShowUnsavedModal(true)
    } else {
      doSwitch(toId)
    }
  }

  // ── SIDEBAR variant ────────────────────────────────────────────────────────────────────
  if (variant === 'sidebar') {
    const activeLabel = active
      ? `${active.course_name}${active.course_code ? ` (${active.course_code})` : ''}`
      : 'Select Subject'

    return (
      <div className="sidebar-subject-container" ref={dropdownRef}>
        {showUnsavedModal && (
          <div className="subject-modal-backdrop" onClick={() => setShowUnsavedModal(false)}>
            <div className="subject-modal" onClick={e => e.stopPropagation()}>
              <div className="subject-modal-title">Unsaved Changes</div>
              <div className="subject-modal-body">You have unsaved edits in this subject. What would you like to do?</div>
              <div className="subject-modal-actions">
                <button className="btn btn-sm btn-primary" onClick={() => {
                  setShowUnsavedModal(false)
                  if (pendingSwitch) doSwitch(pendingSwitch)
                }}>Discard &amp; Switch</button>
                <button className="btn btn-sm" onClick={() => setShowUnsavedModal(false)}>Cancel</button>
              </div>
            </div>
          </div>
        )}

        <div className="sidebar-subject-label">ACTIVE SUBJECT</div>

        <div className="sidebar-subject-dropdown-wrap">
          <button
            className="sidebar-subject-btn"
            onClick={() => setOpen(o => !o)}
            aria-label="Switch subject"
            disabled={switching}
            title={activeLabel}
          >
            <span className="sidebar-subject-name">
              {switching ? 'Switching…' : activeLabel}
            </span>
            <span className="sidebar-subject-chevron">{open ? '▲' : '▼'}</span>
          </button>

          {open && (
            <div className="sidebar-subject-dropdown">
              {subjects.map(s => {
                const label = `${s.course_name}${s.course_code ? ` (${s.course_code})` : ''}`
                return (
                  <button
                    key={s.subject_id}
                    className={`sidebar-subject-option${s.subject_id === activeId ? ' active' : ''}`}
                    onClick={() => handleSelect(s.subject_id)}
                    title={label}
                  >
                    <div className="sidebar-subject-option-name">{label}</div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <a href="/course" className="sidebar-subject-add-btn">
          ＋ Add Subject
        </a>

        <div className="sidebar-subject-divider" />
      </div>
    )
  }

  // ── DASHBOARD variant ────────────────────────────────────────────────────────────────────
  return (
    <div className="dashboard-subject-card" ref={dropdownRef}>
      {showUnsavedModal && (
        <div className="subject-modal-backdrop" onClick={() => setShowUnsavedModal(false)}>
          <div className="subject-modal" onClick={e => e.stopPropagation()}>
            <div className="subject-modal-title">Unsaved Changes</div>
            <div className="subject-modal-body">You have unsaved edits in this subject. Discard and switch?</div>
            <div className="subject-modal-actions">
              <button className="btn btn-sm btn-primary" onClick={() => {
                setShowUnsavedModal(false)
                if (pendingSwitch) doSwitch(pendingSwitch)
              }}>Discard &amp; Switch</button>
              <button className="btn btn-sm" onClick={() => setShowUnsavedModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="dashboard-subject-header">
        <div className="dashboard-subject-label">Active Subject</div>
        <a href="/course" className="dashboard-subject-new-btn">＋ New Subject</a>
      </div>

      {active ? (
        <div className="dashboard-subject-active">
          <div className="dashboard-subject-active-name">{active.course_name}</div>
          {active.course_code && (
            <div className="dashboard-subject-active-meta">
              <span className="badge badge-blue">{active.course_code}</span>
              {active.semester && <span className="badge badge-gray">{active.semester}</span>}
              {active.department && <span className="badge badge-gray">{active.department}</span>}
            </div>
          )}
        </div>
      ) : (
        <div className="dashboard-subject-empty">
          No subject selected — <a href="/course">add a subject in Course Setup</a> to get started.
        </div>
      )}

      {subjects.length > 0 && (
        <div className="dashboard-subject-switch-row" style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <label className="dashboard-subject-switch-label" htmlFor="dashboard-subject-select" style={{ fontWeight: 500, fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Switch Course:
          </label>
          <select
            id="dashboard-subject-select"
            className="form-select"
            style={{ width: 'auto', minWidth: 220, padding: '0.4rem 0.75rem', fontSize: '0.875rem', borderRadius: 'var(--radius-sm)' }}
            value={activeId || ''}
            onChange={e => handleSelect(e.target.value)}
            disabled={switching}
          >
            {subjects.map(s => (
              <option key={s.subject_id} value={s.subject_id}>
                {s.course_name}{s.course_code ? ` (${s.course_code})` : ''}
              </option>
            ))}
          </select>
          {switching && <span className="text-xs text-muted">Switching…</span>}
        </div>
      )}
    </div>
  )
}
