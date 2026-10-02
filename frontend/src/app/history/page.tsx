'use client'

import { useEffect, useState } from 'react'
import { api, type AuditLog, type PaperListItem } from '@/lib/api'
import { PageHeader, SectionLabel, Badge, EmptyState, ActiveSubjectBanner } from '@/components/ui'

export default function HistoryPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [papers, setPapers] = useState<PaperListItem[]>([])

  const loadHistory = () => {
    api.getLogs(50).then(setLogs).catch(() => {})
    api.listPapers().then(setPapers).catch(() => {})
  }

  useEffect(() => {
    loadHistory()

    if (typeof window !== 'undefined') {
      window.addEventListener('activeSubjectChanged', loadHistory)
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('activeSubjectChanged', loadHistory)
      }
    }
  }, [])

  function formatDate(iso?: string) {
    if (!iso) return '—'
    return new Date(iso).toLocaleString('en-IN', {
      dateStyle: 'medium', timeStyle: 'short'
    })
  }

  const ACTION_ICONS: Record<string, string> = {
    GENERATE: '⚡', APPROVE: '✅', REJECT: '❌',
    EXPORT: '📤', SAVE_DRAFT: '💾', IMPORT: '📥', EDIT: '✏️',
  }
  function actionIcon(a: string) {
    return Object.entries(ACTION_ICONS).find(([k]) => a.toUpperCase().includes(k))?.[1] ?? '•'
  }

  function paperStatusBadge(s: string) {
    const map: Record<string, any> = { APPROVED: 'green', EXPORTED: 'blue', GENERATED: 'orange', UNDER_REVIEW: 'orange' }
    return <Badge variant={map[s] ?? 'gray'}>{s.replace('_', ' ')}</Badge>
  }

  return (
    <>
      <PageHeader title="Usage History" subtitle="Complete audit trail and paper history" />

      <ActiveSubjectBanner />

      <div className="grid-2" style={{ gap: '2rem', alignItems: 'start' }}>
        {/* Audit log */}
        <div>
          <SectionLabel>Audit Log</SectionLabel>
          {logs.length === 0 ? (
            <EmptyState icon="🕐" title="No activity yet" />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th></th>
                    <th>Action</th>
                    <th>Paper Set</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log, i) => (
                    <tr key={log.id ?? i}>
                      <td style={{ width: 32 }}>{actionIcon(log.action)}</td>
                      <td className="font-medium text-sm">
                        {log.action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </td>
                      <td className="text-xs text-muted">{log.paper_set_id ?? '—'}</td>
                      <td className="text-xs text-muted">{formatDate(log.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Paper history */}
        <div>
          <SectionLabel>Paper Sets</SectionLabel>
          {papers.length === 0 ? (
            <EmptyState icon="📄" title="No papers generated yet" />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Set ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Questions</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {papers.map(p => (
                    <tr key={p.set_id}>
                      <td className="font-medium text-sm">{p.set_id}</td>
                      <td className="text-sm">{p.exam_type}</td>
                      <td>{paperStatusBadge(p.status)}</td>
                      <td className="text-sm">{p.question_count}</td>
                      <td className="text-xs text-muted">{formatDate(p.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
