'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import {
  api,
  type SubjectListItem,
  type SubjectDetail,
  type UnitData,
  type ChapterData,
  type MinorConfig,
  type LpParseResult,
  type ParsedUnit,
} from '@/lib/api'
import {
  PageHeader, Card, SectionLabel, Alert, Spinner, FileDropzone,
} from '@/components/ui'

// ── Types used locally ────────────────────────────────────────────────────────

interface LocalChapter {
  _key: string       // client-side stable key
  chapter_number: number
  title: string
  topics: string[]
}

interface LocalUnit {
  _key: string
  unit_number: number
  title: string
  chapters: LocalChapter[]
}

interface FormState {
  course_name: string
  course_code: string
  department: string
  semester: string
  academic_year: string
  units: LocalUnit[]
  minor_configuration: MinorConfig
}

type View = 'list' | 'choose-method' | 'manual-form' | 'lp-upload' | 'lp-review'

// ── Helpers ───────────────────────────────────────────────────────────────────

let _keyCounter = 0
function newKey() { return `k${++_keyCounter}` }

function emptyForm(): FormState {
  return {
    course_name: '',
    course_code: '',
    department: '',
    semester: '',
    academic_year: '',
    units: [],
    minor_configuration: { minor1: [], minor2: [] },
  }
}

function subjectDetailToForm(s: SubjectDetail): FormState {
  return {
    course_name: s.course_name,
    course_code: s.course_code,
    department: s.department,
    semester: s.semester,
    academic_year: s.academic_year,
    units: s.units.map(u => ({
      _key: newKey(),
      unit_number: u.unit_number,
      title: u.title,
      chapters: u.chapters.map(ch => ({
        _key: newKey(),
        chapter_number: ch.chapter_number,
        title: ch.title,
        topics: ch.topics,
      })),
    })),
    minor_configuration: {
      minor1: (s.minor_configuration as Partial<MinorConfig>)?.minor1 ?? [],
      minor2: (s.minor_configuration as Partial<MinorConfig>)?.minor2 ?? [],
    },
  }
}

function lpParseToForm(parsed: LpParseResult): FormState {
  return {
    course_name: parsed.course_name ?? '',
    course_code: parsed.course_code ?? '',
    department: parsed.department ?? '',
    semester: parsed.semester ?? '',
    academic_year: parsed.academic_year ?? '',
    units: parsed.units.map(u => ({
      _key: newKey(),
      unit_number: u.unit_number,
      title: u.unit_name || `Unit ${u.unit_number}`,
      chapters: u.chapters.map(ch => ({
        _key: newKey(),
        chapter_number: ch.chapter_number,
        title: ch.title,
        topics: ch.topics,
      })),
    })),
    minor_configuration: {
      minor1: parsed.minor_configuration?.minor1 ?? [],
      minor2: parsed.minor_configuration?.minor2 ?? [],
    },
  }
}

function formToSubjectIn(form: FormState, lpMeta?: LpParseResult) {
  return {
    course_name: form.course_name,
    course_code: form.course_code,
    department: form.department,
    semester: form.semester,
    academic_year: form.academic_year,
    units: form.units.map(u => ({
      unit_number: u.unit_number,
      title: u.title,
      chapters: u.chapters.map(ch => ({
        chapter_number: ch.chapter_number,
        title: ch.title,
        topics: ch.topics,
      })),
    })),
    minor_configuration: form.minor_configuration,
    lp_metadata: lpMeta
      ? {
          confidence: lpMeta.confidence,
          warnings: lpMeta.warnings,
          source_filename: '',
          raw_text_length: lpMeta.raw_text_preview.length,
        }
      : null,
  }
}

// ── LP loading steps ──────────────────────────────────────────────────────────

const LP_STEPS = [
  'Analyzing LP with Qwen…',
  'Extracting course information…',
  'Detecting units and chapters…',
  'Preparing course setup…',
]

// ══════════════════════════════════════════════════════════════════════════════
// Subject Form Component
// ══════════════════════════════════════════════════════════════════════════════

function SubjectForm({
  form,
  setForm,
  onSave,
  onCancel,
  saving,
  lpWarnings = [],
  lpConfidence,
  title,
}: {
  form: FormState
  setForm: (f: FormState) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
  lpWarnings?: string[]
  lpConfidence?: number
  title: string
}) {
  // ── Unit / Chapter helpers ──────────────────────────────────────────────────

  function addUnit() {
    const nextNum = (form.units[form.units.length - 1]?.unit_number ?? 0) + 1
    setForm({
      ...form,
      units: [
        ...form.units,
        { _key: newKey(), unit_number: nextNum, title: `Unit ${nextNum}`, chapters: [] },
      ],
    })
  }

  function removeUnit(uKey: string) {
    setForm({ ...form, units: form.units.filter(u => u._key !== uKey) })
  }

  function updateUnit(uKey: string, patch: Partial<LocalUnit>) {
    setForm({
      ...form,
      units: form.units.map(u => u._key === uKey ? { ...u, ...patch } : u),
    })
  }

  function addChapter(uKey: string) {
    setForm({
      ...form,
      units: form.units.map(u => {
        if (u._key !== uKey) return u
        const nextNum = (u.chapters[u.chapters.length - 1]?.chapter_number ?? 0) + 1
        return {
          ...u,
          chapters: [
            ...u.chapters,
            { _key: newKey(), chapter_number: nextNum, title: '', topics: [] },
          ],
        }
      }),
    })
  }

  function removeChapter(uKey: string, cKey: string) {
    setForm({
      ...form,
      units: form.units.map(u =>
        u._key === uKey ? { ...u, chapters: u.chapters.filter(c => c._key !== cKey) } : u
      ),
    })
  }

  function updateChapter(uKey: string, cKey: string, patch: Partial<LocalChapter>) {
    setForm({
      ...form,
      units: form.units.map(u =>
        u._key === uKey
          ? { ...u, chapters: u.chapters.map(c => c._key === cKey ? { ...c, ...patch } : c) }
          : u
      ),
    })
  }

  const allUnitNums = form.units.map(u => u.unit_number)

  function toggleMinor(which: 'minor1' | 'minor2', unitNum: number) {
    const cur = form.minor_configuration[which]
    const next = cur.includes(unitNum) ? cur.filter(n => n !== unitNum) : [...cur, unitNum]
    setForm({ ...form, minor_configuration: { ...form.minor_configuration, [which]: next } })
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="section-label" style={{ marginBottom: '0.25rem' }}>{title}</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
            Subject Configuration
          </h2>
        </div>
        <div className="flex gap-3">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={onSave} disabled={saving}>
            {saving ? <><Spinner size={14} />&nbsp;Saving…</> : '✓ Save Subject'}
          </button>
        </div>
      </div>

      {/* LP parse warnings */}
      {lpWarnings.length > 0 && (
        <div className="mb-8">
          {lpConfidence !== undefined && lpConfidence < 0.5 && (
            <Alert variant="warning">
              ⚠️ Qwen confidence is low ({Math.round(lpConfidence * 100)}%).
              Please review all fields carefully.
            </Alert>
          )}
          <div style={{ marginTop: '0.75rem' }}>
            {lpWarnings.map((w, i) => (
              <Alert key={i} variant="warning" >{w}</Alert>
            ))}
          </div>
        </div>
      )}

      {/* ── Course Info ── */}
      <SectionLabel style={{ marginTop: '0' }}>Course Information</SectionLabel>
      <Card className="mb-8">
        <div className="form-row">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">
              Course Name
              {form.course_name === '' && <span style={{ color: 'var(--orange)', marginLeft: '0.4rem' }}>⚠ needs input</span>}
            </label>
            <input
              className="form-input"
              value={form.course_name}
              onChange={e => setForm({ ...form, course_name: e.target.value })}
              placeholder="e.g. Agentic AI"
            />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Course Code</label>
            <input
              className="form-input"
              value={form.course_code}
              onChange={e => setForm({ ...form, course_code: e.target.value })}
              placeholder="e.g. 26ECAC401"
            />
          </div>
        </div>
        <div className="form-row" style={{ marginTop: '1rem' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Department</label>
            <input
              className="form-input"
              value={form.department}
              onChange={e => setForm({ ...form, department: e.target.value })}
              placeholder="e.g. Computer Science and Engineering"
            />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Semester</label>
            <select
              className="form-select"
              value={form.semester}
              onChange={e => setForm({ ...form, semester: e.target.value })}
            >
              {['', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th'].map(s => (
                <option key={s} value={s}>{s || 'Select semester'}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="form-group" style={{ marginTop: '1rem', marginBottom: 0 }}>
          <label className="form-label">Academic Year</label>
          <input
            className="form-input"
            value={form.academic_year}
            onChange={e => setForm({ ...form, academic_year: e.target.value })}
            placeholder="e.g. 2024-25"
            style={{ maxWidth: 200 }}
          />
        </div>
      </Card>

      {/* ── Units & Chapters ── */}
      <div className="flex items-center justify-between mb-4">
        <SectionLabel style={{ margin: 0 }}>Unit & Chapter Structure</SectionLabel>
        <button className="btn btn-secondary btn-sm" onClick={addUnit}>+ Add Unit</button>
      </div>

      {form.units.length === 0 ? (
        <Card className="mb-8">
          <div className="text-center" style={{ padding: '2rem', color: 'var(--text-3)' }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📚</div>
            <div className="font-semibold">No units yet</div>
            <div className="text-sm mt-2">Click "+ Add Unit" to start building the course structure.</div>
            <button className="btn btn-secondary btn-sm" style={{ marginTop: '1rem' }} onClick={addUnit}>
              + Add Unit
            </button>
          </div>
        </Card>
      ) : (
        <div className="mb-8" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {form.units.map((unit) => (
            <div key={unit._key} style={{
              background: 'var(--surface)',
              borderRadius: 'var(--radius)',
              boxShadow: 'var(--shadow)',
              overflow: 'hidden',
            }}>
              {/* Unit header */}
              <div style={{
                background: 'linear-gradient(135deg, var(--blue-light), rgba(110,64,201,0.06))',
                padding: '0.875rem 1.25rem',
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                borderBottom: '1px solid var(--border-light)',
              }}>
                <div style={{
                  background: 'var(--blue)', color: 'white', borderRadius: '6px',
                  width: 28, height: 28, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700, flexShrink: 0,
                }}>
                  {unit.unit_number}
                </div>
                <input
                  className="form-input"
                  value={unit.title}
                  onChange={e => updateUnit(unit._key, { title: e.target.value })}
                  placeholder={`Unit ${unit.unit_number} Title`}
                  style={{ flex: 1, background: 'transparent', border: '1px solid rgba(0,0,0,0.10)' }}
                />
                <input
                  className="form-input"
                  type="number" min={1} max={20}
                  value={unit.unit_number}
                  onChange={e => updateUnit(unit._key, { unit_number: Number(e.target.value) })}
                  style={{ width: 60, background: 'transparent', border: '1px solid rgba(0,0,0,0.10)', padding: '0.3rem 0.5rem' }}
                  title="Unit number"
                />
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => removeUnit(unit._key)}
                  style={{ flexShrink: 0 }}
                >
                  Remove
                </button>
              </div>

              {/* Chapters */}
              <div style={{ padding: '0.75rem 1.25rem' }}>
                {unit.chapters.length === 0 && (
                  <div className="text-sm text-muted" style={{ padding: '0.5rem 0', marginBottom: '0.5rem' }}>
                    No chapters yet.
                  </div>
                )}
                {unit.chapters.map((ch, ci) => (
                  <div key={ch._key} style={{
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    padding: '0.4rem 0',
                    borderBottom: ci < unit.chapters.length - 1 ? '1px solid var(--border-light)' : 'none',
                  }}>
                    <span style={{
                      fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-3)',
                      width: 70, flexShrink: 0,
                    }}>
                      Ch.
                      <input
                        type="number" min={1} max={99}
                        value={ch.chapter_number}
                        onChange={e => updateChapter(unit._key, ch._key, { chapter_number: Number(e.target.value) })}
                        style={{
                          width: 40, border: 'none', background: 'transparent',
                          fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-3)',
                          outline: 'none', padding: 0, marginLeft: '0.25rem',
                        }}
                      />
                    </span>
                    <input
                      className="form-input"
                      value={ch.title}
                      onChange={e => updateChapter(unit._key, ch._key, { title: e.target.value })}
                      placeholder="Chapter title"
                      style={{ flex: 1 }}
                    />
                    <input
                      className="form-input"
                      value={ch.topics.join(', ')}
                      onChange={e => updateChapter(unit._key, ch._key, {
                        topics: e.target.value.split(',').map(t => t.trim()).filter(Boolean),
                      })}
                      placeholder="Topics (comma-separated, optional)"
                      style={{ flex: 1 }}
                    />
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => removeChapter(unit._key, ch._key)}
                      style={{ flexShrink: 0 }}
                    >
                      ×
                    </button>
                  </div>
                ))}
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => addChapter(unit._key)}
                  style={{ marginTop: '0.5rem' }}
                >
                  + Add Chapter
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Minor Configuration ── */}
      <SectionLabel>Minor Exam Configuration</SectionLabel>
      <Card className="mb-8">
        {allUnitNums.length === 0 ? (
          <div className="text-sm text-muted">Add units above to configure minor exam mappings.</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            {(['minor1', 'minor2'] as const).map(which => (
              <div key={which}>
                <div className="form-label" style={{ marginBottom: '0.75rem' }}>
                  {which === 'minor1' ? 'Minor 1' : 'Minor 2'} — select units covered
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {form.units.map(u => (
                    <label
                      key={u._key}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                        cursor: 'pointer', fontSize: '0.875rem',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={form.minor_configuration[which].includes(u.unit_number)}
                        onChange={() => toggleMinor(which, u.unit_number)}
                        style={{ accentColor: 'var(--blue)', width: 15, height: 15 }}
                      />
                      Unit {u.unit_number} — {u.title || `Unit ${u.unit_number}`}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="text-sm text-muted" style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-light)' }}>
          This mapping is subject-specific and does not affect other subjects.
        </div>
      </Card>

      {/* Bottom actions */}
      <div className="flex justify-end gap-3">
        <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary btn-lg" onClick={onSave} disabled={saving}>
          {saving ? <><Spinner size={14} />&nbsp;Saving…</> : '✓ Save Subject'}
        </button>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// Main Page Component
// ══════════════════════════════════════════════════════════════════════════════

export default function CoursePage() {
  const [view, setView] = useState<View>('list')
  const [subjects, setSubjects] = useState<SubjectListItem[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [selectedSubject, setSelectedSubject] = useState<SubjectDetail | null>(null)
  const [editingSubjectId, setEditingSubjectId] = useState<string | null>(null)

  const [form, setForm] = useState<FormState>(emptyForm())
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ text: string; variant: 'success' | 'error' | 'warning' } | null>(null)

  // LP state
  const [lpFile, setLpFile] = useState<File | null>(null)
  const [lpParsing, setLpParsing] = useState(false)
  const [lpStep, setLpStep] = useState(0)
  const [lpResult, setLpResult] = useState<LpParseResult | null>(null)
  const [lpError, setLpError] = useState<string | null>(null)

  // ── Load subjects on mount ──────────────────────────────────────────────────
  const isMounted = useRef(true)

  const loadSubjects = useCallback(async () => {
    try {
      const [list, activeRes] = await Promise.all([
        api.listSubjects(),
        api.getActiveSubjectId(),
      ])
      if (!isMounted.current) return
      setSubjects(list)
      setActiveId(activeRes.active_subject_id)
      // Auto-select active subject
      const active = list.find(s => s.subject_id === activeRes.active_subject_id)
      if (active) {
        const detail = await api.getSubject(active.subject_id)
        if (!isMounted.current) return
        setSelectedSubject(detail)
      } else if (list.length > 0) {
        const detail = await api.getSubject(list[0].subject_id)
        if (!isMounted.current) return
        setSelectedSubject(detail)
        setActiveId(list[0].subject_id)
      }
    } catch (_) {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    isMounted.current = true
    loadSubjects()
    return () => { isMounted.current = false }
  }, [loadSubjects])


  function showMsg(text: string, variant: 'success' | 'error' | 'warning' = 'success') {
    setMsg({ text, variant })
    setTimeout(() => setMsg(null), 4000)
  }

  // ── Subject switching ───────────────────────────────────────────────────────
  async function switchSubject(id: string) {
    try {
      await api.setActiveSubjectId(id)
      setActiveId(id)
      const detail = await api.getSubject(id)
      setSelectedSubject(detail)
    } catch (e: unknown) {
      showMsg(`Failed to switch subject: ${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  // ── Start Add New Subject ───────────────────────────────────────────────────
  function startAddNew() {
    setForm(emptyForm())
    setEditingSubjectId(null)
    setLpResult(null)
    setLpError(null)
    setLpFile(null)
    setView('choose-method')
  }

  // ── Start Edit ──────────────────────────────────────────────────────────────
  async function startEdit() {
    if (!selectedSubject) return
    setEditingSubjectId(selectedSubject.subject_id)
    setForm(subjectDetailToForm(selectedSubject))
    setLpResult(null)
    setLpError(null)
    setView('manual-form')
  }

  // ── Save subject ────────────────────────────────────────────────────────────
  async function saveSubject() {
    if (!form.course_name.trim()) {
      showMsg('Course Name is required.', 'error')
      return
    }
    setSaving(true)
    try {
      const payload = formToSubjectIn(form, lpResult ?? undefined)
      let result: SubjectDetail
      if (editingSubjectId) {
        result = await api.updateSubject(editingSubjectId, payload)
        showMsg(`✅ "${result.course_name}" updated successfully!`)
      } else {
        result = await api.createSubject(payload)
        showMsg(`✅ "${result.course_name}" created successfully!`)
      }
      await loadSubjects()
      await switchSubject(result.subject_id)
      setView('list')
    } catch (e: unknown) {
      showMsg(`Failed to save: ${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  // ── Delete subject ──────────────────────────────────────────────────────────
  async function deleteSubject(id: string) {
    if (!window.confirm('Delete this subject? This cannot be undone.')) return
    try {
      await api.deleteSubject(id)
      showMsg('Subject deleted.')
      await loadSubjects()
      if (activeId === id) {
        setSelectedSubject(null)
        setActiveId(null)
      }
    } catch (e: unknown) {
      showMsg(`Delete failed: ${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  // ── LP parse ────────────────────────────────────────────────────────────────
  async function parseLP(file: File) {
    setLpFile(file)
    setLpParsing(true)
    setLpError(null)
    setLpResult(null)

    // Cycle through loading steps
    let stepIdx = 0
    setLpStep(0)
    const stepInterval = setInterval(() => {
      stepIdx = Math.min(stepIdx + 1, LP_STEPS.length - 1)
      setLpStep(stepIdx)
    }, 2500)

    try {
      const result = await api.parseLP(file)
      clearInterval(stepInterval)
      setLpParsing(false)
      setLpResult(result)
      setForm(lpParseToForm(result))
      setView('lp-review')
    } catch (e: unknown) {
      clearInterval(stepInterval)
      setLpParsing(false)
      setLpError(e instanceof Error ? e.message : String(e))
    }
  }

  function cancelForm() {
    setView('list')
    setEditingSubjectId(null)
    setLpResult(null)
    setLpError(null)
    setLpFile(null)
  }

  // ══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════

  return (
    <>
      <PageHeader
        title="Course Setup"
        subtitle="Manage independent subjects — each with its own course structure, units, and exam configuration"
      />

      {msg && (
        <Alert variant={msg.variant} >
          {msg.text}
        </Alert>
      )}

      {/* ─────────────── VIEW: LIST / SUBJECT SELECTOR ─────────────── */}
      {view === 'list' && (
        <>
          {/* Toolbar */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.75rem',
            marginBottom: '1.5rem', flexWrap: 'wrap',
          }}>
            {subjects.length > 0 && (
              <select
                className="form-select"
                value={activeId ?? ''}
                onChange={e => switchSubject(e.target.value)}
                style={{ maxWidth: 320, fontWeight: 600 }}
              >
                {subjects.map(s => (
                  <option key={s.subject_id} value={s.subject_id}>
                    {s.course_name || '(Unnamed)'} {s.course_code ? `— ${s.course_code}` : ''}
                  </option>
                ))}
              </select>
            )}
            <button type="button" className="btn btn-primary" onClick={startAddNew}>+ Add New Subject</button>
            {selectedSubject && (
              <button type="button" className="btn btn-secondary" onClick={startEdit}>✏ Edit Subject</button>
            )}
            {selectedSubject && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() => deleteSubject(selectedSubject.subject_id)}
              >
                🗑 Delete
              </button>
            )}
          </div>

          {/* No subjects state */}
          {subjects.length === 0 && (
            <Card>
              <div className="text-center" style={{ padding: '3rem 2rem' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>📖</div>
                <div className="font-semibold" style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>
                  No subjects configured yet
                </div>
                <div className="text-sm text-muted" style={{ marginBottom: '1.5rem' }}>
                  Create your first subject to get started.
                </div>
                <button type="button" className="btn btn-primary btn-lg" onClick={startAddNew}>
                  + Add New Subject
                </button>
              </div>
            </Card>
          )}

          {/* Selected subject detail */}
          {selectedSubject && (
            <>
              {/* Summary card */}
              <div style={{
                background: 'linear-gradient(135deg, var(--blue) 0%, var(--purple) 100%)',
                borderRadius: 'var(--radius-lg)',
                padding: '1.75rem 2rem',
                color: 'white',
                marginBottom: '1.5rem',
                position: 'relative',
                overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute', top: '-40%', right: '-10%', width: '50%', height: '200%',
                  background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 65%)',
                  pointerEvents: 'none',
                }} />
                <div style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.7, marginBottom: '0.4rem' }}>
                  Active Subject
                </div>
                <div style={{ fontSize: '1.6rem', fontWeight: 700, letterSpacing: '-0.03em', marginBottom: '0.25rem' }}>
                  {selectedSubject.course_name || '(Unnamed Course)'}
                </div>
                <div style={{ opacity: 0.85, fontSize: '0.875rem' }}>
                  {[selectedSubject.course_code, selectedSubject.department, selectedSubject.semester ? `Semester ${selectedSubject.semester}` : '', selectedSubject.academic_year]
                    .filter(Boolean).join(' · ')}
                </div>
              </div>

              {/* Stats row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
                {[
                  { label: 'Units', value: selectedSubject.units.length },
                  { label: 'Chapters', value: selectedSubject.units.reduce((acc, u) => acc + u.chapters.length, 0) },
                  {
                    label: 'Minor Config',
                    value: ((selectedSubject.minor_configuration as Partial<MinorConfig>)?.minor1?.length ?? 0) > 0 ||
                           ((selectedSubject.minor_configuration as Partial<MinorConfig>)?.minor2?.length ?? 0) > 0
                           ? '✓ Set' : '— Not set',
                  },
                ].map(({ label, value }) => (
                  <div key={label} style={{
                    background: 'var(--surface)', borderRadius: 'var(--radius)',
                    boxShadow: 'var(--shadow)', padding: '1.25rem',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--blue)', letterSpacing: '-0.03em' }}>
                      {value}
                    </div>
                    <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-3)', marginTop: '0.25rem' }}>
                      {label}
                    </div>
                  </div>
                ))}
              </div>

              {/* Units detail */}
              <SectionLabel>Unit & Chapter Structure</SectionLabel>
              {selectedSubject.units.length === 0 ? (
                <Card>
                  <div className="text-center" style={{ padding: '2rem', color: 'var(--text-3)' }}>
                    <div style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>📂</div>
                    <div className="font-semibold">No units defined</div>
                    <div className="text-sm mt-2">Click "Edit Subject" to add units and chapters.</div>
                  </div>
                </Card>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
                  {selectedSubject.units.map(unit => (
                    <div key={unit.id ?? unit.unit_number} style={{
                      background: 'var(--surface)', borderRadius: 'var(--radius)',
                      boxShadow: 'var(--shadow)', overflow: 'hidden',
                    }}>
                      <div style={{
                        background: 'var(--blue-light)', padding: '0.75rem 1.25rem',
                        fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem',
                        borderBottom: '1px solid var(--border-light)',
                      }}>
                        <span style={{
                          background: 'var(--blue)', color: 'white', borderRadius: '5px',
                          padding: '0.15rem 0.5rem', fontSize: '0.72rem', fontWeight: 700,
                        }}>
                          Unit {unit.unit_number}
                        </span>
                        {unit.title}
                      </div>
                      <div style={{ padding: '0.625rem 1.25rem' }}>
                        {unit.chapters.map((ch, ci) => (
                          <div key={ch.id ?? ch.chapter_number} style={{
                            padding: '0.4rem 0',
                            borderBottom: ci < unit.chapters.length - 1 ? '1px solid var(--border-light)' : 'none',
                            display: 'flex', alignItems: 'center', gap: '0.5rem',
                            fontSize: '0.875rem',
                          }}>
                            <span style={{ color: 'var(--text-3)', fontWeight: 600, minWidth: 60 }}>
                              Ch. {ch.chapter_number}
                            </span>
                            {ch.title}
                            {ch.topics.length > 0 && (
                              <span style={{ color: 'var(--text-3)', fontSize: '0.75rem' }}>
                                — {ch.topics.join(', ')}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Minor config detail */}
              {(((selectedSubject.minor_configuration as Partial<MinorConfig>)?.minor1?.length ?? 0) > 0 ||
                ((selectedSubject.minor_configuration as Partial<MinorConfig>)?.minor2?.length ?? 0) > 0) && (
                <>
                  <SectionLabel>Minor Exam Mapping</SectionLabel>
                  <Card>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                      {(['minor1', 'minor2'] as const).map(which => {
                        const units = (selectedSubject.minor_configuration as Partial<MinorConfig>)?.[which] ?? []
                        return (
                          <div key={which}>
                            <div className="form-label" style={{ marginBottom: '0.5rem' }}>
                              {which === 'minor1' ? 'Minor 1' : 'Minor 2'}
                            </div>
                            {units.length === 0 ? (
                              <span className="text-sm text-muted">Not configured</span>
                            ) : (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {units.map((n: number) => (
                                  <span key={n} style={{
                                    background: 'var(--blue-light)', color: 'var(--blue)',
                                    borderRadius: '6px', padding: '0.2rem 0.65rem',
                                    fontSize: '0.78rem', fontWeight: 600,
                                  }}>
                                    Unit {n}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </Card>
                </>
              )}

              {/* Other subjects */}
              {subjects.length > 1 && (
                <>
                  <SectionLabel style={{ marginTop: '1.5rem' }}>All Subjects</SectionLabel>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {subjects.map(s => (
                      <div key={s.subject_id} style={{
                        background: 'var(--surface)',
                        borderRadius: 'var(--radius)',
                        boxShadow: s.subject_id === activeId ? 'var(--shadow-lg)' : 'var(--shadow-sm)',
                        padding: '0.875rem 1.25rem',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        border: s.subject_id === activeId ? '1px solid var(--blue)' : '1px solid transparent',
                        cursor: 'pointer', transition: 'all 0.15s ease',
                      }} onClick={() => switchSubject(s.subject_id)}>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: '0.15rem' }}>
                            {s.course_name || '(Unnamed)'}
                            {s.subject_id === activeId && (
                              <span style={{
                                background: 'var(--blue)', color: 'white',
                                borderRadius: '4px', padding: '0.1rem 0.4rem',
                                fontSize: '0.65rem', fontWeight: 700, marginLeft: '0.5rem',
                              }}>
                                ACTIVE
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>
                            {[s.course_code, s.department, s.semester ? `Sem ${s.semester}` : '']
                              .filter(Boolean).join(' · ')}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button className="btn btn-secondary btn-sm" onClick={e => { e.stopPropagation(); switchSubject(s.subject_id) }}>
                            Select
                          </button>
                          <button className="btn btn-danger btn-sm" onClick={e => { e.stopPropagation(); deleteSubject(s.subject_id) }}>
                            🗑
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </>
      )}

      {/* ─────────────── VIEW: CHOOSE METHOD ─────────────── */}
      {view === 'choose-method' && (
        <>
          <div className="flex items-center gap-3 mb-8">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setView('list')}>← Back</button>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
              Add New Subject — Choose Setup Method
            </h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', maxWidth: 720 }}>
            {[
              {
                icon: '📝',
                title: 'Manual Course Setup',
                desc: 'Enter all course details, units, and chapters by hand.',
                action: () => { setForm(emptyForm()); setView('manual-form') },
              },
              {
                icon: '📄',
                title: 'Setup from Lesson Plan',
                desc: 'Upload a PDF or DOCX lesson plan. Qwen will extract the course structure automatically.',
                action: () => setView('lp-upload'),
              },
            ].map(({ icon, title, desc, action }) => (
              <div
                key={title}
                onClick={action}
                className="card card-pad card-hover"
                style={{ cursor: 'pointer', textAlign: 'center', padding: '2rem 1.5rem' }}
              >
                <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>{icon}</div>
                <div style={{ fontWeight: 700, fontSize: '1.05rem', marginBottom: '0.5rem' }}>{title}</div>
                <div className="text-sm text-muted">{desc}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ─────────────── VIEW: LP UPLOAD ─────────────── */}
      {view === 'lp-upload' && (
        <>
          <div className="flex items-center gap-3 mb-8">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setView('choose-method')}>← Back</button>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
              Upload Lesson Plan
            </h2>
          </div>

          {lpParsing ? (
            <Card>
              <div className="text-center" style={{ padding: '3rem 2rem' }}>
                <Spinner size={40} />
                <div style={{ marginTop: '1.5rem', fontSize: '1rem', fontWeight: 600 }}>
                  {LP_STEPS[lpStep]}
                </div>
                <div className="text-sm text-muted" style={{ marginTop: '0.5rem' }}>
                  {lpFile?.name}
                </div>
                <div style={{ marginTop: '1.5rem' }}>
                  <div style={{
                    height: 4, background: 'rgba(0,0,0,0.06)',
                    borderRadius: '9999px', overflow: 'hidden',
                    maxWidth: 300, margin: '0 auto',
                  }}>
                    <div style={{
                      height: '100%',
                      background: 'linear-gradient(90deg, var(--blue), var(--purple))',
                      borderRadius: '9999px',
                      width: `${((lpStep + 1) / LP_STEPS.length) * 100}%`,
                      transition: 'width 0.5s ease',
                    }} />
                  </div>
                </div>
              </div>
            </Card>
          ) : lpError ? (
            <Card>
              <Alert variant="error">
                <strong>Parsing failed:</strong> {lpError}
              </Alert>
              <div className="flex gap-3" style={{ marginTop: '1.25rem' }}>
                <button className="btn btn-secondary" onClick={() => { setLpError(null); setLpFile(null) }}>
                  Try Again
                </button>
                <button className="btn btn-primary" onClick={() => { setLpError(null); setForm(emptyForm()); setView('manual-form') }}>
                  Switch to Manual Setup
                </button>
              </div>
            </Card>
          ) : (
            <Card>
              <div style={{ marginBottom: '1rem' }}>
                <SectionLabel style={{ margin: 0 }}>Upload Lesson Plan / Course Plan Document</SectionLabel>
                <div className="text-sm text-muted" style={{ marginTop: '0.4rem' }}>
                  Qwen will read approximately the first 8 pages to extract course information and structure.
                  You can review and edit the extracted data before saving.
                </div>
              </div>
              <FileDropzone
                accept=".pdf,.docx,.txt,.md"
                label="Click or drag to upload LP document"
                sublabel="PDF, DOCX, TXT or MD — max 50 MB"
                onFile={parseLP}
              />
              <div className="flex justify-end" style={{ marginTop: '1.25rem' }}>
                <button className="btn btn-secondary" onClick={() => { setForm(emptyForm()); setView('manual-form') }}>
                  Skip — Use Manual Setup Instead
                </button>
              </div>
            </Card>
          )}
        </>
      )}

      {/* ─────────────── VIEW: MANUAL FORM ─────────────── */}
      {view === 'manual-form' && (
        <SubjectForm
          form={form}
          setForm={setForm}
          onSave={saveSubject}
          onCancel={cancelForm}
          saving={saving}
          title={editingSubjectId ? 'Edit Subject' : 'New Subject — Manual Setup'}
        />
      )}

      {/* ─────────────── VIEW: LP REVIEW ─────────────── */}
      {view === 'lp-review' && lpResult && (
        <>
          <div className="flex items-center gap-3 mb-6">
            <button className="btn btn-secondary btn-sm" onClick={() => setView('lp-upload')}>← Re-upload</button>
            <div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                Review Extracted Course Information
              </h2>
              <div className="text-sm text-muted">
                Qwen confidence: {Math.round(lpResult.confidence * 100)}% — review all fields before saving.
              </div>
            </div>
          </div>

          {lpResult.warnings.length > 0 && (
            <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {lpResult.warnings.map((w, i) => (
                <Alert key={i} variant="warning">{w}</Alert>
              ))}
            </div>
          )}

          <Alert variant="info">
            Fields marked with <strong>⚠ needs input</strong> could not be extracted from the LP.
            Please fill them in manually before saving.
          </Alert>

          <div style={{ marginTop: '1.25rem' }}>
            <SubjectForm
              form={form}
              setForm={setForm}
              onSave={saveSubject}
              onCancel={cancelForm}
              saving={saving}
              lpWarnings={lpResult.warnings}
              lpConfidence={lpResult.confidence}
              title="New Subject — Parsed from LP (Review & Edit)"
            />
          </div>
        </>
      )}
    </>
  )
}
