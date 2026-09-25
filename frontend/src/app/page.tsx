'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api, type Stats, type AuditLog, type Completeness } from '@/lib/api'
import { StatCard, SectionLabel, Hero, Card, EmptyState, ProgressBar } from '@/components/ui'

export default function DashboardPage() {
  const router = useRouter()
  const [stats, setStats] = useState<Stats | null>(null)
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [completeness, setCompleteness] = useState<Completeness[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getStats(), api.getLogs(8), api.getCompleteness()])
      .then(([s, l, c]) => { setStats(s); setLogs(l); setCompleteness(c) })
      .finally(() => setLoading(false))
  }, [])

  const qb = stats?.question_bank
  const papers = stats?.papers

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

  if (loading) return (
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
        eyebrow="Active Course"
        title="Generative AI"
        sub="3 Units · 7 Chapters · Bloom L2 & L3"
        right={
          <div className="badge badge-green">🟢 Live API</div>
        }
      />

      <div className="confidential">
        ⚠ CONFIDENTIAL — Question papers are restricted academic documents
      </div>

      {/* Question bank stats */}
      <SectionLabel>Question Bank</SectionLabel>
      <div className="stat-grid">
        <StatCard value={qb?.total ?? 0} label="Total Questions" icon="📋" />
        <StatCard value={qb?.l2 ?? 0} label="L2 Understand" icon="🔵" />
        <StatCard value={qb?.l3 ?? 0} label="L3 Apply" icon="🟣" />
        <StatCard value={`${qb?.completeness_pct ?? 0}%`} label="Bank Complete" icon="✅" />
      </div>

      {/* Paper stats */}
      <SectionLabel style={{ marginTop: '1.5rem' }}>Paper Sets</SectionLabel>
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
                    const unitNum = c.chapter_number <= 2 ? 1 : c.chapter_number <= 5 ? 2 : 3
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
            <EmptyState icon="📭" title="No question bank yet" sub="Upload a question bank to get started" />
          )}
        </div>

        {/* Activity feed */}
        <div>
          <SectionLabel>Recent Activity</SectionLabel>
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
            <EmptyState icon="🕐" title="No activity yet" />
          )}
        </div>
      </div>

      {/* Quick actions */}
      <SectionLabel style={{ marginTop: '2rem' }}>Quick Actions</SectionLabel>
      <div className="grid-4">
        <button className="btn btn-secondary btn-full" onClick={() => router.push('/questions')}>
          📋 Upload Question Bank
        </button>
        <button className="btn btn-secondary btn-full" onClick={() => router.push('/lesson-plan')}>
          📖 Upload Lesson Plan
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
