'use client'

import { useState, useEffect } from 'react'
import { api, type SubjectListItem, type SubjectDetail } from '@/lib/api'
import { PageHeader, SectionLabel, Card, Alert, Spinner } from '@/components/ui'

export default function SettingsPage() {
  const [health, setHealth] = useState<{ status: string; message?: string; model?: string } | null>(null)
  const [checkingHealth, setCheckingHealth] = useState(false)
  const [msg, setMsg] = useState('')

  const [subjectsList, setSubjectsList] = useState<SubjectListItem[]>([])
  const [activeSubject, setActiveSubject] = useState<SubjectDetail | null>(null)
  const [selectedDeleteId, setSelectedDeleteId] = useState<string>('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadSubjectData()
  }, [])

  async function loadSubjectData() {
    try {
      const list = await api.listSubjects()
      setSubjectsList(list)
      const { active_subject_id } = await api.getActiveSubjectId()
      if (active_subject_id) {
        setSelectedDeleteId(active_subject_id)
        const detail = await api.getSubject(active_subject_id).catch(() => null)
        if (detail) setActiveSubject(detail)
      } else if (list.length > 0) {
        setSelectedDeleteId(list[0].subject_id)
        const detail = await api.getSubject(list[0].subject_id).catch(() => null)
        if (detail) setActiveSubject(detail)
      }
    } catch (_) {}
  }

  async function checkHealth() {
    setCheckingHealth(true)
    try {
      const res = await api.getLLMHealth()
      setHealth(res)
    } finally { setCheckingHealth(false) }
  }

  async function handleDeleteSubject() {
    if (!selectedDeleteId) return
    const subj = subjectsList.find(s => s.subject_id === selectedDeleteId)
    const name = subj ? subj.course_name : selectedDeleteId

    const confirmed = window.confirm(
      `Are you ABSOLUTELY SURE you want to delete "${name}"?\n\n` +
      `This will permanently delete ALL data for this subject:\n` +
      `• All Question Bank items & AI Generated questions\n` +
      `• All Question Paper sets, schemes & validation reports\n` +
      `• Lesson Plan & Course structure information\n` +
      `• Usage history and audit logs\n\n` +
      `This action CANNOT be undone.`
    )
    if (!confirmed) return

    setDeleting(true)
    try {
      await api.deleteSubject(selectedDeleteId)
      setMsg(`✅ Subject "${name}" and all associated data deleted successfully.`)
      await loadSubjectData()
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('activeSubjectChanged', { detail: { subjectId: selectedDeleteId } }))
      }
    } catch (err: unknown) {
      alert(`Delete failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="LLM configuration, privacy controls, paper rules, and subject management" />

      {msg && <Alert variant="success">{msg}</Alert>}

      {/* LLM Status */}
      <SectionLabel style={{ marginTop: '1rem' }}>LLM Connection</SectionLabel>
      <Card>
        <div className="flex justify-between items-start">
          <div>
            <div className="font-semibold mb-1">API Health Check</div>
            <div className="text-sm text-muted">Test connectivity to the configured LLM provider</div>
            {health && (
              <div className="mt-3">
                {health.status === 'ok' ? (
                  <Alert variant="success">Connected — {health.model} — {health.message}</Alert>
                ) : (
                  <Alert variant="error">{health.message}</Alert>
                )}
              </div>
            )}
          </div>
          <button className="btn btn-secondary" onClick={checkHealth} disabled={checkingHealth}>
            {checkingHealth ? <Spinner size={14} /> : '🔌 Test Connection'}
          </button>
        </div>
      </Card>

      {/* Paper Rules */}
      <SectionLabel style={{ marginTop: '1.5rem' }}>Paper Rules</SectionLabel>
      <Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {[
            { label: 'Minor: Total printed questions', value: '6 (4 bank + 2 AI)', fixed: true },
            { label: 'End-Sem: Total printed questions', value: '16 (11 bank + 5 AI)', fixed: true },
            { label: 'Marks per sub-question', value: '10 marks', fixed: true },
            { label: 'Minor: Answer any N of M', value: '2 of 3 questions', fixed: true },
            { label: 'Bloom taxonomy levels', value: 'L2 (Understand) + L3 (Apply)', fixed: true },
          ].map(rule => (
            <div key={rule.label} className="flex justify-between items-center"
              style={{ padding: '0.625rem 0', borderBottom: '1px solid var(--border-light)' }}>
              <div className="text-sm font-medium">{rule.label}</div>
              <div className="text-sm text-muted font-semibold">{rule.value}</div>
            </div>
          ))}
        </div>
        <div className="alert alert-info mt-4" style={{ marginTop: '1rem' }}>
          ℹ️ Paper rules are fixed per university regulations and cannot be changed.
        </div>
      </Card>

      {/* Privacy */}
      <SectionLabel style={{ marginTop: '1.5rem' }}>Privacy & Security</SectionLabel>
      <Card>
        <div className="font-semibold mb-1">Confidentiality Notice</div>
        <div className="text-sm text-muted" style={{ lineHeight: 1.7 }}>
          All generated question papers are confidential academic documents.
          Access is restricted to authorised faculty members only.
          Generated papers are stored locally and are never transmitted externally.
        </div>
        <div className="confidential mt-4" style={{ textAlign: 'left' }}>
          ⚠ CONFIDENTIAL — Unauthorized access or distribution is strictly prohibited
        </div>
      </Card>

      {/* Danger Zone: Delete Subject */}
      <SectionLabel style={{ marginTop: '1.5rem' }}>Danger Zone — Delete Subject</SectionLabel>
      <Card style={{ borderColor: 'rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.03)' }}>
        <div className="flex justify-between items-start" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div className="font-bold text-red mb-1" style={{ fontSize: '1rem', color: 'var(--red)' }}>
              Delete Subject &amp; All Associated Data
            </div>
            <div className="text-sm text-muted" style={{ lineHeight: 1.6 }}>
              Select a subject to permanently delete. Deleting a subject will destroy its <strong>question bank, paper sets, lesson plans, valuation schemes, and audit history</strong>.
            </div>
            {subjectsList.length > 0 && (
              <div className="mt-3 flex items-center gap-2" style={{ marginTop: '0.75rem' }}>
                <label htmlFor="delete-subject-select" className="text-xs font-semibold text-muted">Subject to delete:</label>
                <select
                  id="delete-subject-select"
                  className="form-select"
                  style={{ maxWidth: 280, padding: '0.35rem 0.65rem', fontSize: '0.82rem', borderColor: 'var(--border)' }}
                  value={selectedDeleteId}
                  onChange={e => setSelectedDeleteId(e.target.value)}
                >
                  {subjectsList.map(s => (
                    <option key={s.subject_id} value={s.subject_id}>
                      {s.course_name} {s.course_code ? `(${s.course_code})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div>
            <button
              className="btn btn-danger"
              onClick={handleDeleteSubject}
              disabled={deleting || subjectsList.length <= 1}
              style={{ padding: '0.5rem 1.25rem' }}
            >
              {deleting ? <Spinner size={14} /> : '🗑 Delete Subject'}
            </button>
          </div>
        </div>
        {subjectsList.length <= 1 && (
          <div className="alert alert-warning mt-3" style={{ fontSize: '0.78rem', marginTop: '0.75rem' }}>
            ℹ️ Cannot delete the last remaining subject. At least one subject must remain configured in Prashnopatra.
          </div>
        )}
      </Card>

      {/* About */}
      <SectionLabel style={{ marginTop: '1.5rem' }}>About</SectionLabel>
      <Card>
        <div className="flex justify-between items-center">
          <div>
            <div className="font-semibold">Prashnopatra</div>
            <div className="text-sm text-muted mt-1">AI Question Paper Setting Agent v1.0.0</div>
            <div className="text-xs text-muted mt-1">FastAPI backend · Next.js frontend · SQLite DB</div>
          </div>
          <div className="badge badge-blue">v1.0.0</div>
        </div>
      </Card>
    </>
  )
}
