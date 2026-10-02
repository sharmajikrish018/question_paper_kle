'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { api, type Stats, type AuditLog, type Completeness, type SubjectDetail } from '@/lib/api'
import { StatCard, SectionLabel, Hero, Card, EmptyState, ProgressBar } from '@/components/ui'
import { SubjectSwitcher } from '@/components/SubjectSwitcher'

export default function DashboardPage() {
  const router = useRouter()
  const [activeSubject, setActiveSubjectDetail] = useState<SubjectDetail | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [completeness, setCompleteness] = useState<Completeness[]>([])
  const [loading, setLoading] = useState(true)

  const loadDashboardData = useCallback(async () => {
    setLoading(true)
    try {
      // 1. Get active subject ID
      const { active_subject_id } = await api.getActiveSubjectId()
      let subjDetail: SubjectDetail | null = null
      if (active_subject_id) {
        try {
          subjDetail = await api.getSubject(active_subject_id)
        } catch { /* subject detail fetch fallback */ }
      }

      setActiveSubjectDetail(subjDetail)

      if (!subjDetail) {
        setStats(null)
        setLogs([])
        setCompleteness([])
        return
      }

      // 2. Fetch stats, logs, completeness for current active subject
      const [s, l, c] = await Promise.all([
        api.getStats().catch(() => null),
        api.getLogs(8).catch(() => []),
        api.getCompleteness().catch(() => []),
      ])

      setStats(s)
      setLogs(l)
      setCompleteness(c)
    } catch {
      /* ignore loading errors */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboardData()

    const handleSubjectChange = () => {
      loadDashboardData()
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('activeSubjectChanged', handleSubjectChange)
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('activeSubjectChanged', handleSubjectChange)
      }
    }
  }, [loadDashboardData])

  const qb = stats?.question_bank
  const papers = stats?.papers

  const totalUnits = activeSubject?.units?.length ?? 0
  const totalChapters = activeSubject?.units?.reduce((sum, u) => sum + (u.chapters?.length ?? 0), 0) ?? 0

  const ACTION_ICONS: Record<string, string> = {
    GENERATE: '⚡', APPROVE: '✅', REJECT: '❌',
    EXPORT: '📤', SAVE_DRAFT: '💾', IMPORT: '📥',
    EDIT: '✏️',
  }

  function actionIcon(action: string) {
    return Object.entries(ACTION_ICONS).find(([k]) => action.toUpperCase().includes(k))?.[1] ?? '•'
  }

  function formatDate(iso?: string) {
    if (!iso) return '—'
    return new Date(iso).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  // Find unit number for a chapter from activeSubject units structure
  function getUnitForChapter(chNum: number): number {
    if (!activeSubject?.units) return 1
    for (const u of activeSubject.units) {
      if (u.chapters?.some(ch => ch.chapter_number === chNum)) {
        return u.unit_number
      }
    }
    return chNum <= 2 ? 1 : chNum <= 5 ? 2 : 3
  }

  if (loading && !activeSubject) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <div style={{ textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem', width: 32, height: 32 }} />
        <div className="text-muted text-sm">Loading dashboard…</div>
      </div>
    </div>
  )

  return (
    <>
      {/* Hero */}
      <Hero
        eyebrow="Active Course Scope"
        title={activeSubject?.course_name || 'Select Subject'}
        sub={`${totalUnits} Unit${totalUnits !== 1 ? 's' : ''} · ${totalChapters} Chapter${totalChapters !== 1 ? 's' : ''} · Bloom L2 & L3 Scoped Context`}
        right={
          <div className="badge badge-green">🟢 Active Context: {activeSubject?.course_code || 'Ready'}</div>
        }
      />

      <div className="confidential">
        ⚠ CONFIDENTIAL — Question papers are restricted academic documents
      </div>

      {/* Question bank stats */}
      <SectionLabel>Question Bank Statistics ({activeSubject?.course_name || 'Active Subject'})</SectionLabel>
      <div className="stat-grid">
        <StatCard value={qb?.total ?? 0} label="Total Questions" icon="📋" />
        <StatCard value={qb?.l2 ?? 0} label="L2 Understand" icon="🔵" />
        <StatCard value={qb?.l3 ?? 0} label="L3 Apply" icon="🟣" />
        <StatCard value={`${qb?.completeness_pct ?? 0}%`} label="Bank Complete" icon="✅" />
      </div>

      {/* Paper stats */}
      <SectionLabel style={{ marginTop: '1.5rem' }}>Generated Paper Sets ({activeSubject?.course_name || 'Active Subject'})</SectionLabel>
      <div className="stat-grid">
        <StatCard value={papers?.total ?? 0} label="Total Sets" icon="📄" />
        <StatCard value={papers?.pending ?? 0} label="In Review" icon="⏳" />
        <StatCard value={papers?.approved ?? 0} label="Approved" icon="✅" />
        <StatCard value={papers?.exported ?? 0} label="Exported" icon="📤" />
      </div>

      {/* Chapter completeness + Activity */}
      <div className="grid-2 mt-6" style={{ gridTemplateColumns: '3fr 2fr', alignItems: 'start' }}>

        {/* Completeness matrix */}
        <div>
          <SectionLabel>Chapter Completeness</SectionLabel>
          {completeness.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Unit</th>
                    <th>Chapter</th>
                    <th>L2</th>
                    <th>L3</th>
                    <th>Progress</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {completeness.map(c => {
                    const unitNum = getUnitForChapter(c.chapter_number)
                    const pct = Math.min(100, Math.round((c.total / 20) * 100))
                    return (
                      <tr key={c.chapter_number}>
                        <td className="text-muted text-sm">Unit {unitNum}</td>
                        <td className="font-medium">Ch {c.chapter_number}</td>
                        <td>
                          <span className={c.l2_ok ? 'text-green font-medium' : 'text-muted'}>
                            {c.l2_count}/10
                          </span>
                        </td>
                        <td>
                          <span className={c.l3_ok ? 'text-green font-medium' : 'text-muted'}>
                            {c.l3_count}/10
                          </span>
                        </td>
                        <td style={{ minWidth: 100 }}>
                          <ProgressBar value={pct} />
                        </td>
                        <td>
                          {c.complete
                            ? <span className="badge badge-green">Ready</span>
                            : <span className="badge badge-orange">Incomplete</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon="📭" title="No question bank data" sub="Upload or import a question bank for this subject" />
          )}
        </div>

        {/* Activity feed */}
        <div>
          <SectionLabel>Subject Activity Log</SectionLabel>
          {logs.length > 0 ? (
            <div className="card" style={{ overflow: 'hidden' }}>
              {logs.map((log, i) => (
                <div key={log.id ?? i} style={{
                  display: 'flex', alignItems: 'center', gap: '0.75rem',
                  padding: '0.75rem 1.25rem',
                  borderBottom: i < logs.length - 1 ? '1px solid var(--border-light)' : 'none',
                }}>
                  <span style={{ fontSize: '1rem', flexShrink: 0 }}>{actionIcon(log.action)}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="font-medium text-sm truncate">
                      {log.action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      {log.paper_set_id && (
                        <span className="text-muted" style={{ fontWeight: 400 }}> · {log.paper_set_id}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-muted" style={{ flexShrink: 0 }}>
                    {formatDate(log.timestamp)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon="🕐" title="No activity for this subject" />
          )}
        </div>
      </div>

      {/* Quick actions */}
      <SectionLabel style={{ marginTop: '2rem' }}>Quick Actions</SectionLabel>
      <div className="grid-4">
        <button className="btn btn-secondary btn-full" onClick={() => router.push('/questions')}>
          📋 Question Bank
        </button>
        <button className="btn btn-secondary btn-full" onClick={() => router.push('/course')}>
          📖 Course Setup
        </button>
        <button className="btn btn-primary btn-full" onClick={() => router.push('/generate')}>
          ⚡ Generate Paper
        </button>
        <button className="btn btn-secondary btn-full" onClick={() => router.push('/review')}>
          👩‍🏫 Faculty Review
        </button>
      </div>
    </>
  )
}
