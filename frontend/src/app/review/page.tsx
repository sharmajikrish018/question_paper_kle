'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, type PaperListItem, type PaperSet, type PaperQuestion } from '@/lib/api'
import { PageHeader, ConfidentialBanner, SectionLabel, Badge, Alert, Spinner, EmptyState } from '@/components/ui'

export default function ReviewPage() {
  const [papers, setPapers] = useState<PaperListItem[]>([])
  const [loadingList, setLoadingList] = useState(true)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<PaperSet | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [approving, setApproving] = useState(false)
  const [msg, setMsg] = useState('')
  const [updatingSlot, setUpdatingSlot] = useState<string | null>(null)
  const [editingSlot, setEditingSlot] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const refreshPapers = useCallback(async () => {
    setLoadingList(true)
    try {
      const list = await api.listPapers()
      setPapers(list)
    } catch {
      // silently ignore
    } finally {
      setLoadingList(false)
    }
  }, [])

  // Fetch on mount
  useEffect(() => {
    refreshPapers()
  }, [refreshPapers])

  // Re-fetch whenever the user switches back to this tab
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') refreshPapers()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [refreshPapers])

  async function loadDetail(id: string) {
    setSelected(id)
    setDetail(null)
    setLoadingDetail(true)
    try {
      setDetail(await api.getPaper(id))
    } finally { setLoadingDetail(false) }
  }

  async function handleApprove() {
    if (!selected) return
    setApproving(true)
    try {
      await api.approvePaper(selected)
      setMsg('✅ Paper set approved!')
      setPapers(p => p.map(x => x.set_id === selected ? { ...x, status: 'APPROVED' } : x))
      setDetail(d => d ? { ...d, status: 'APPROVED' } : null)
      setTimeout(() => setMsg(''), 3000)
    } finally { setApproving(false) }
  }

  async function updateQ(slotId: string, status: string, text?: string) {
    if (!selected) return
    setUpdatingSlot(slotId)
    try {
      const updated = await api.updateQuestionStatus(selected, slotId, status, text)
      setDetail(d => d ? {
        ...d,
        questions: d.questions.map(q => q.slot_id === slotId ? updated : q)
      } : null)
    } finally {
      setUpdatingSlot(null)
      setEditingSlot(null)
      setEditText('')
    }
  }

  function statusBadge(status: string) {
    if (status === 'APPROVED') return <Badge variant="green">✅ Approved</Badge>
    if (status === 'REJECTED') return <Badge variant="red">❌ Rejected</Badge>
    return <Badge variant="orange">⏳ Pending</Badge>
  }

  function paperStatusBadge(status: string) {
    const map: Record<string, string> = {
      APPROVED: 'green', EXPORTED: 'blue', GENERATED: 'orange', UNDER_REVIEW: 'orange', CHANGES_REQUESTED: 'red'
    }
    return <Badge variant={(map[status] ?? 'gray') as any}>{status.replace('_', ' ')}</Badge>
  }

  const pendingCount = detail?.questions.filter(q => q.approval_status === 'PENDING').length ?? 0

  return (
    <>
      <PageHeader title="Faculty Review" subtitle="Review, approve and export generated question papers" />
      <ConfidentialBanner />

      {msg && <Alert variant="success">{msg}</Alert>}

      <div className="flex gap-6" style={{ alignItems: 'flex-start' }}>
        {/* Paper list sidebar */}
        <div style={{ width: 260, flexShrink: 0 }}>
          <div className="flex justify-between items-center" style={{ marginBottom: '0.5rem' }}>
            <SectionLabel style={{ margin: 0 }}>Paper Sets</SectionLabel>
            <button
              className="btn btn-secondary btn-sm"
              onClick={refreshPapers}
              disabled={loadingList}
              title="Refresh paper list"
              style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}
            >
              {loadingList ? <Spinner size={12} /> : '↺ Refresh'}
            </button>
          </div>
          {loadingList && papers.length === 0 ? (
            <div className="text-center" style={{ padding: '2rem' }}><Spinner size={22} /></div>
          ) : papers.length === 0 ? (
            <EmptyState icon="📄" title="No papers yet" sub="Generate papers first" />
          ) : (
            <div className="card" style={{ overflow: 'hidden' }}>
              {papers.map((p, i) => (
                <div key={p.set_id}
                  onClick={() => loadDetail(p.set_id)}
                  style={{
                    padding: '0.875rem 1.25rem',
                    borderBottom: i < papers.length - 1 ? '1px solid var(--border-light)' : 'none',
                    cursor: 'pointer',
                    background: selected === p.set_id ? 'var(--blue-light)' : 'transparent',
                    transition: 'background 0.15s',
                  }}>
                  <div className="font-semibold text-sm" style={{ color: selected === p.set_id ? 'var(--blue)' : 'var(--text)' }}>
                    {p.set_id}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {paperStatusBadge(p.status)}
                    <span className="text-xs text-muted">{p.question_count}q</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Paper detail */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!selected && (
            <EmptyState icon="👈" title="Select a paper set" sub="Choose from the list on the left" />
          )}

          {loadingDetail && (
            <div className="text-center" style={{ padding: '3rem' }}><Spinner size={28} /></div>
          )}

          {detail && (
            <>
              {/* Header */}
              <div className="flex justify-between items-center mb-4">
                <div>
                  <div className="font-bold" style={{ fontSize: '1.25rem' }}>{detail.set_id}</div>
                  <div className="flex gap-2 mt-1">
                    {paperStatusBadge(detail.status)}
                    <Badge variant="gray">{detail.exam_type}</Badge>
                    <Badge variant="blue">{detail.question_count} questions</Badge>
                  </div>
                </div>
                <div className="flex gap-3">
                  {pendingCount > 0 && (
                    <span className="badge badge-orange">{pendingCount} pending</span>
                  )}
                  <button className="btn btn-secondary btn-sm"
                    onClick={() => window.open(api.exportDocxUrl(detail.set_id))}>
                    📥 DOCX
                  </button>
                  <button className="btn btn-secondary btn-sm"
                    onClick={() => window.open(api.exportPdfUrl(detail.set_id))}>
                    📄 PDF
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={handleApprove}
                    disabled={approving || detail.status === 'APPROVED'}>
                    {approving ? <Spinner size={14} /> : detail.status === 'APPROVED' ? '✅ Approved' : 'Approve All'}
                  </button>
                </div>
              </div>

              {/* Questions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                {detail.questions.map(q => (
                  <div key={q.slot_id} className="card card-pad" style={{ borderLeft: `3px solid ${
                    q.approval_status === 'APPROVED' ? 'var(--green)' :
                    q.approval_status === 'REJECTED' ? 'var(--red)' : 'var(--orange)'
                  }` }}>
                    <div className="flex justify-between items-start gap-4">
                      <div style={{ flex: 1 }}>
                        <div className="flex gap-2 mb-2">
                          <span className="font-semibold text-sm text-muted">{q.slot_id}</span>
                          {q.bloom_level === 'L2'
                            ? <Badge variant="green">L2</Badge>
                            : <Badge variant="orange">L3</Badge>}
                          {q.source.includes('BANK')
                            ? <Badge variant="blue">Bank</Badge>
                            : <Badge variant="purple">AI</Badge>}
                          <span className="text-xs text-muted">Ch {q.chapter_number} · {q.marks} marks</span>
                        </div>

                        {editingSlot === q.slot_id ? (
                          <div>
                            <textarea className="form-textarea" value={editText}
                              onChange={e => setEditText(e.target.value)} rows={3} />
                            <div className="flex gap-2 mt-2">
                              <button className="btn btn-primary btn-sm"
                                onClick={() => updateQ(q.slot_id, 'PENDING', editText)}
                                disabled={updatingSlot === q.slot_id}>
                                {updatingSlot === q.slot_id ? <Spinner size={12} /> : 'Save Edit'}
                              </button>
                              <button className="btn btn-secondary btn-sm" onClick={() => setEditingSlot(null)}>
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm" style={{ lineHeight: 1.6 }}>{q.question_text}</p>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col gap-2" style={{ flexShrink: 0 }}>
                        {statusBadge(q.approval_status)}
                        <button className="btn btn-sm"
                          style={{ background: 'var(--green-light)', color: 'var(--green-text)' }}
                          onClick={() => updateQ(q.slot_id, 'APPROVED')}
                          disabled={updatingSlot === q.slot_id || q.approval_status === 'APPROVED'}>
                          ✅ Approve
                        </button>
                        <button className="btn btn-sm btn-danger"
                          onClick={() => updateQ(q.slot_id, 'REJECTED')}
                          disabled={updatingSlot === q.slot_id || q.approval_status === 'REJECTED'}>
                          ❌ Reject
                        </button>
                        <button className="btn btn-secondary btn-sm"
                          onClick={() => { setEditingSlot(q.slot_id); setEditText(q.question_text) }}>
                          ✏️ Edit
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
