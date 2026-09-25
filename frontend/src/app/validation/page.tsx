'use client'

import { useState, useEffect } from 'react'
import { api, type PaperListItem, type ValidationReport } from '@/lib/api'
import { PageHeader, SectionLabel, Badge, Alert, Spinner, EmptyState } from '@/components/ui'

export default function ValidationPage() {
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [report, setReport] = useState<ValidationReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { api.listPapers().then(setPapers).catch(() => {}) }, [])

  async function loadReport(id: string) {
    setSelected(id); setReport(null); setLoading(true)
    try { setReport(await api.getValidation(id)) }
    finally { setLoading(false) }
  }

  function statusColor(s: string) {
    return s === 'PASS' ? 'green' : s === 'PASS_WITH_WARNINGS' ? 'orange' : 'red'
  }

  function severityBadge(s: string) {
    return s === 'ERROR'
      ? <Badge variant="red">ERROR</Badge>
      : <Badge variant="orange">WARNING</Badge>
  }

  return (
    <>
      <PageHeader title="Validation Reports" subtitle="View per-paper-set validation results and rule findings" />

      <div className="flex gap-6" style={{ alignItems: 'flex-start' }}>
        {/* List */}
        <div style={{ width: 240, flexShrink: 0 }}>
          <SectionLabel>Paper Sets</SectionLabel>
          <div className="card" style={{ overflow: 'hidden' }}>
            {papers.length === 0
              ? <div className="text-sm text-muted" style={{ padding: '1rem' }}>No papers yet</div>
              : papers.map((p, i) => (
                <div key={p.set_id} onClick={() => loadReport(p.set_id)}
                  style={{
                    padding: '0.875rem 1.25rem',
                    borderBottom: i < papers.length - 1 ? '1px solid var(--border-light)' : 'none',
                    cursor: 'pointer',
                    background: selected === p.set_id ? 'var(--blue-light)' : 'transparent',
                  }}>
                  <div className="font-semibold text-sm"
                    style={{ color: selected === p.set_id ? 'var(--blue)' : 'var(--text)' }}>
                    {p.set_id}
                  </div>
                  <div className="text-xs text-muted mt-1">{p.status}</div>
                </div>
              ))}
          </div>
        </div>

        {/* Report detail */}
        <div style={{ flex: 1 }}>
          {!selected && <EmptyState icon="📊" title="Select a paper set" sub="View its validation report" />}
          {loading && <div className="text-center" style={{ padding: '3rem' }}><Spinner size={28} /></div>}
          {report && (
            <>
              <div className="flex items-center gap-3 mb-6">
                <Badge variant={statusColor(report.status) as any}>
                  {report.status === 'PASS' ? '✅ PASS'
                    : report.status === 'PASS_WITH_WARNINGS' ? '⚠️ PASS WITH WARNINGS'
                    : '❌ FAIL'}
                </Badge>
                <span className="text-sm text-muted">{report.set_id} · {report.exam_type}</span>
              </div>

              {/* Metrics */}
              <div className="grid-4 mb-6" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                {[
                  { label: 'Total Questions', val: report.total_printed },
                  { label: 'From Bank', val: `${report.source_bank_count} (${report.source_bank_percent}%)` },
                  { label: 'AI Generated', val: `${report.source_ai_count} (${report.source_ai_percent}%)` },
                  { label: 'Total Marks', val: report.marks_total },
                ].map(m => (
                  <div key={m.label} className="card card-pad text-center">
                    <div className="font-bold" style={{ fontSize: '1.5rem', color: 'var(--blue)' }}>{m.val}</div>
                    <div className="text-xs text-muted mt-1">{m.label}</div>
                  </div>
                ))}
              </div>

              {/* Bloom */}
              <div className="card card-pad mb-6">
                <div className="font-semibold mb-3">Bloom Distribution</div>
                <div className="flex gap-6">
                  <div>
                    <div className="text-xs text-muted">L2 (Understand)</div>
                    <div className="font-bold text-green">{report.bloom_l2_count} ({report.bloom_l2_percent}%)</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted">L3 (Apply)</div>
                    <div className="font-bold" style={{ color: 'var(--orange-text)' }}>
                      {report.bloom_l3_count} ({report.bloom_l3_percent}%)
                    </div>
                  </div>
                </div>
              </div>

              {/* Findings */}
              <SectionLabel>Rule Findings ({report.findings.length})</SectionLabel>
              {report.findings.length === 0 ? (
                <Alert variant="success">All validation rules passed.</Alert>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {report.findings.map((f, i) => (
                    <div key={i} className="card card-pad" style={{
                      borderLeft: `3px solid ${f.severity === 'ERROR' ? 'var(--red)' : 'var(--orange)'}`,
                    }}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-sm">{f.rule_id}</span>
                        {severityBadge(f.severity)}
                      </div>
                      <div className="text-sm">{f.message}</div>
                      {(f.expected || f.actual) && (
                        <div className="flex gap-4 mt-2 text-xs text-muted">
                          {f.expected && <span>Expected: <strong>{f.expected}</strong></span>}
                          {f.actual && <span>Actual: <strong>{f.actual}</strong></span>}
                        </div>
                      )}
                      {f.suggested_action && (
                        <div className="text-xs mt-1" style={{ color: 'var(--blue)' }}>
                          💡 {f.suggested_action}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}
