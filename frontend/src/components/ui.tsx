'use client'

import { useEffect, useRef, ReactNode, useState, useCallback, createContext, useContext } from 'react'
import { api, type SubjectDetail } from '@/lib/api'

export function StatCard({ value, label, icon }: { value: string | number; label: string; icon?: string }) {
  return (
    <div className="stat-card">
      {icon && <div className="stat-icon">{icon}</div>}
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

type BadgeVariant = 'blue' | 'green' | 'orange' | 'red' | 'purple' | 'gray'
export function Badge({ children, variant = 'gray' }: { children: ReactNode; variant?: BadgeVariant }) {
  return <span className={`badge badge-${variant}`}>{children}</span>
}

export function Card({ children, className = '', style }: { children: ReactNode; className?: string; style?: React.CSSProperties }) {
  return <div className={`card card-pad ${className}`} style={style}>{children}</div>
}

export function SectionLabel({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return <div className="section-label" style={style}>{children}</div>
}

export function Spinner({ size = 20 }: { size?: number }) {
  return <div className="spinner" style={{ width: size, height: size }} />
}

type AlertVariant = 'info' | 'success' | 'warning' | 'error'
export function Alert({ children, variant = 'info' }: { children: ReactNode; variant?: AlertVariant }) {
  return (
    <div className={`alert alert-${variant}`}>
      <span>{children}</span>
    </div>
  )
}

export function ConfidentialBanner({ text = 'CONFIDENTIAL — Question papers are restricted academic documents' }: { text?: string }) {
  return <div className="confidential">{text}</div>
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="page-header">
      <h1 className="page-title">{title}</h1>
      {subtitle && <p className="page-subtitle">{subtitle}</p>}
    </div>
  )
}

export function Hero({ eyebrow, title, sub, right }: {
  eyebrow: string; title: string; sub: string; right?: ReactNode
}) {
  return (
    <div className="hero mb-8">
      <div className="flex justify-between items-start" style={{ gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <div className="hero-eyebrow">{eyebrow}</div>
          <div className="hero-title">{title}</div>
          <div className="hero-sub">{sub}</div>
        </div>
        {right && <div>{right}</div>}
      </div>
    </div>
  )
}

export function FileDropzone({
  onFile, accept, label, sublabel, disabled = false
}: {
  onFile: (f: File) => void
  accept: string
  label?: string
  sublabel?: string
  disabled?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }

  return (
    <div
      className="dropzone"
      style={{ opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? 'none' : 'auto' }}
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }}
      onDragLeave={e => e.currentTarget.classList.remove('drag-over')}
      onDrop={handleDrop}
    >
      <div className="dropzone-label">{label ?? 'Click or drag file here'}</div>
      <div className="dropzone-sub">{sublabel ?? accept}</div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f) }}
      />
    </div>
  )
}


interface Toast { id: number; message: string; type: 'success' | 'error' | 'info' }
const ToastCtx = createContext<{ toast: (msg: string, type?: Toast['type']) => void }>({
  toast: () => {}
})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)

  const toast = useCallback((message: string, type: Toast['type'] = 'success') => {
    const id = ++idRef.current
    setToasts(t => [...t, { id, message, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }, [])

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>{t.message}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() { return useContext(ToastCtx) }

export function ProgressBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="progress-bar">
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  )
}

export function EmptyState({ icon, title, sub, action }: {
  icon?: string; title: string; sub?: string; action?: ReactNode
}) {
  return (
    <div className="card card-pad text-center" style={{ padding: '3rem 2rem' }}>
      {icon && <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>{icon}</div>}
      <div className="font-semibold" style={{ marginBottom: '0.3rem' }}>{title}</div>
      {sub && <div className="text-sm text-muted" style={{ marginBottom: '1rem' }}>{sub}</div>}
      {action}
    </div>
  )
}

/**
 * ActiveSubjectBanner
 * Displays the currently active subject on every page.
 * Listens to "activeSubjectChanged" and refreshes automatically.
 * showLink prop (default true) shows "Edit in Course Setup" link.
 */
export function ActiveSubjectBanner({
  subject: externalSubject,
  showLink = true,
}: {
  subject?: SubjectDetail | null
  showLink?: boolean
}) {
  const [subject, setSubject] = useState<SubjectDetail | null>(externalSubject ?? null)
  const [loading, setLoading] = useState(!externalSubject)

  const fetchSubject = useCallback(async () => {
    setLoading(true)
    try {
      const { active_subject_id } = await api.getActiveSubjectId()
      if (active_subject_id) {
        const detail = await api.getSubject(active_subject_id)
        setSubject(detail)
      } else {
        setSubject(null)
      }
    } catch {
      // silently ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // If a subject was passed as prop, don't auto-fetch
    if (externalSubject !== undefined) {
      setSubject(externalSubject)
      return
    }
    fetchSubject()
    const handler = () => fetchSubject()
    window.addEventListener('activeSubjectChanged', handler)
    return () => window.removeEventListener('activeSubjectChanged', handler)
  }, [fetchSubject, externalSubject])

  if (loading) {
    return (
      <div className="active-subject-banner" style={{ opacity: 0.6 }}>
        <div className="active-subject-banner-icon">📚</div>
        <div className="active-subject-banner-body">
          <div className="active-subject-banner-label">Active Subject</div>
          <div className="active-subject-banner-name" style={{ color: 'var(--text-3)' }}>Loading…</div>
        </div>
      </div>
    )
  }

  if (!subject) {
    return (
      <div className="alert alert-info mb-4" style={{ borderRadius: '12px', padding: '0.85rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span>👉</span> <strong>Please select a subject to continue.</strong>
      </div>
    )
  }

  return (
    <div className="active-subject-banner">
      <div className="active-subject-banner-icon">📚</div>
      <div className="active-subject-banner-body">
        <div className="active-subject-banner-label">Active Subject</div>
        <div className="active-subject-banner-name">{subject.course_name}</div>
        <div className="active-subject-banner-meta">
          {subject.course_code && (
            <span className="badge badge-blue">{subject.course_code}</span>
          )}
          {subject.semester && (
            <span className="badge badge-gray">Semester {subject.semester}</span>
          )}
          {subject.department && (
            <span className="badge badge-gray">{subject.department}</span>
          )}
        </div>
      </div>
      {showLink && (
        <div className="active-subject-banner-action">
          <a
            href="/course"
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.75rem' }}
          >
            ✏ Course Setup
          </a>
        </div>
      )}
    </div>
  )
}
