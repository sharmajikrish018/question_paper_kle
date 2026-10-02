'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, type GenerateResponse, type ValidationReport, type SubjectDetail, type Completeness } from '@/lib/api'
import { PageHeader, ConfidentialBanner, SectionLabel, Alert, Spinner, ActiveSubjectBanner } from '@/components/ui'

type ExamType = 'ISA-I' | 'ISA-II' | 'ESA'

export default function GeneratePage() {
  const [activeSubject, setActiveSubjectDetail] = useState<SubjectDetail | null>(null)
  const [availableChapters, setAvailableChapters] = useState<number[]>([]) // empty until loaded
  const [completenessMap, setCompletenessMap] = useState<Record<number, Completeness>>({})
  const [loadingSubject, setLoadingSubject] = useState(true)
  const [examType, setExamType] = useState<ExamType>('ISA-I')
  const [numSets, setNumSets] = useState(1)
  const [l2Pct, setL2Pct] = useState(50)
  const [selectedChapters, setSelectedChapters] = useState<number[]>([])
  const [tolerance, setTolerance] = useState(5)
  const [academicYear, setAcademicYear] = useState('2026-27')
  const [department, setDepartment] = useState('Computer Science & Engineering')
  const [excludeUsed, setExcludeUsed] = useState(true)
  const [confirmed, setConfirmed] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const [error, setError] = useState('')

  const loadSubjectInfo = useCallback(async () => {
    setLoadingSubject(true)
    try {
      const { active_subject_id } = await api.getActiveSubjectId()
      let detail: SubjectDetail | null = null
      if (active_subject_id) {
        try { detail = await api.getSubject(active_subject_id) } catch { /* ignore */ }
      }
      if (!detail) {
        const list = await api.listSubjects()
        if (list.length > 0) {
          detail = await api.getSubject(list[0].subject_id)
        }
      }
      if (detail) {
        setActiveSubjectDetail(detail)
        if (detail.academic_year) setAcademicYear(detail.academic_year)
        if (detail.department) setDepartment(detail.department)

        // Collect chapter numbers from Course Setup — always subject-scoped
        const chList: number[] = []
        detail.units?.forEach(u => {
          u.chapters?.forEach(ch => {
            if (!chList.includes(ch.chapter_number)) chList.push(ch.chapter_number)
          })
        })
        chList.sort((a, b) => a - b)
        setAvailableChapters(chList)
        // Default selection: first 3 chapters (or all if fewer than 3)
        setSelectedChapters(chList.slice(0, Math.min(3, chList.length)))
      }

      // Load completeness map for tooltip hints
      try {
        const comp = await api.getCompleteness()
        const map: Record<number, Completeness> = {}
        for (const c of comp) { map[c.chapter_number] = c }
        setCompletenessMap(map)
      } catch { /* ignore */ }
    } catch { /* ignore */ } finally {
      setLoadingSubject(false)
    }
  }, [])

  useEffect(() => {
    loadSubjectInfo()

    const handleSubjectChange = () => {
      setResult(null)
      setError('')
      setConfirmed(false)
      setSelectedChapters([])
      setAvailableChapters([])
      setCompletenessMap({})
      loadSubjectInfo()
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('activeSubjectChanged', handleSubjectChange)
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('activeSubjectChanged', handleSubjectChange)
      }
    }
  }, [loadSubjectInfo])

  const l3Pct = 100 - l2Pct
  const isMinor = examType === 'ISA-I' || examType === 'ISA-II'

  // Retrieve saved marking scheme from active subject
  const savedSchemes = (activeSubject?.lp_metadata as { marking_schemes?: Record<string, any> })?.marking_schemes
  const activeScheme = examType === 'ISA-I' ? (savedSchemes?.isa1 || savedSchemes?.['ISA-I']) :
                       examType === 'ISA-II' ? (savedSchemes?.isa2 || savedSchemes?.['ISA-II']) :
                       (savedSchemes?.esa || savedSchemes?.['ESA'])

  const totalQ = activeScheme?.total_questions
    ? (activeScheme.total_questions * (activeScheme.sub_question_pattern?.length || 2))
    : (isMinor ? 6 : 16)

  function toggleChapter(ch: number) {
    setSelectedChapters(prev =>
      prev.includes(ch) ? prev.filter(x => x !== ch) : [...prev, ch].sort((a, b) => a - b)
    )
  }

  function handleExamTypeChange(t: ExamType) {
    setExamType(t)
    // Auto-select mapped chapters from minor_configuration if available
    if (t === 'ISA-I' && activeSubject?.minor_configuration?.minor1?.length) {
      const uNums = activeSubject.minor_configuration.minor1
      const mappedChapters: number[] = []
      activeSubject.units?.forEach(u => {
        if (uNums.includes(u.unit_number)) {
          u.chapters?.forEach(ch => mappedChapters.push(ch.chapter_number))
        }
      })
      if (mappedChapters.length > 0) setSelectedChapters(mappedChapters)
    } else if (t === 'ISA-II' && activeSubject?.minor_configuration?.minor2?.length) {
      const uNums = activeSubject.minor_configuration.minor2
      const mappedChapters: number[] = []
      activeSubject.units?.forEach(u => {
        if (uNums.includes(u.unit_number)) {
          u.chapters?.forEach(ch => mappedChapters.push(ch.chapter_number))
        }
      })
      if (mappedChapters.length > 0) setSelectedChapters(mappedChapters)
    }
  }

  /** Get tooltip for a chapter based on completeness */
  function chapterTooltip(ch: number): string {
    const c = completenessMap[ch]
    if (!c) return `Chapter ${ch} — no completeness data`
    if (c.complete) return `Chapter ${ch} — Ready (${c.total}/20 questions)`
    return `Chapter ${ch} — ${c.total}/20 questions (L2: ${c.l2_count}/10, L3: ${c.l3_count}/10)`
  }

  async function handleGenerate() {
    if (!confirmed) { setError('Please confirm the blueprint first.'); return }
    if (isMinor && selectedChapters.length === 0) { setError('Select at least one chapter.'); return }
    setError('')
    setGenerating(true)
    setResult(null)
    try {
      const res = await api.generatePapers({
        exam_type: examType,
        num_sets: numSets,
        l2_percent: l2Pct,
        l3_percent: l3Pct,
        selected_chapters: isMinor ? selectedChapters : availableChapters,
        tolerance_percent: tolerance,
        academic_year: academicYear,
        department,
        exclude_used_question_ids: excludeUsed,
      })
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally { setGenerating(false) }
  }

  function statusIcon(status: string) {
    return status === 'PASS' ? '✅' : status === 'PASS_WITH_WARNINGS' ? '⚠️' : '❌'
  }

  return (
    <>
      <PageHeader
        title={`Generate Paper — ${activeSubject?.course_name || 'Active Subject'}`}
        subtitle={`Configure and generate AI-powered question papers for ${activeSubject?.course_name || 'selected course'}`}
      />
      <ConfidentialBanner />

      {/* Active subject banner */}
      <ActiveSubjectBanner subject={activeSubject} showLink />

      <div style={{ maxWidth: 800 }}>

        {/* Exam type */}
        <SectionLabel>1 · Examination Type</SectionLabel>
        <div className="flex gap-3 mb-6">
          {(['ISA-I', 'ISA-II', 'ESA'] as ExamType[]).map(t => (
            <button key={t} onClick={() => handleExamTypeChange(t)}
              className={`btn ${examType === t ? 'btn-primary' : 'btn-secondary'}`}>
              {t === 'ISA-I' ? '📝 Minor 1 (ISA-I)' : t === 'ISA-II' ? '📝 Minor 2 (ISA-II)' : '📜 End-Semester (ESA)'}
            </button>
          ))}
        </div>

        {/* Sets */}
        <SectionLabel>2 · Number of Sets</SectionLabel>
        <div className="flex items-center gap-4 mb-6">
          <input type="range" className="slider" min={1} max={3} value={numSets}
            onChange={e => setNumSets(Number(e.target.value))} style={{ width: 200 }} />
          <span className="font-semibold" style={{ fontSize: '1.25rem', color: 'var(--blue)' }}>
            {numSets} set{numSets > 1 ? 's' : ''}
          </span>
        </div>

        {/* Chapters — only for MINOR */}
        {isMinor && (
          <>
            <SectionLabel>3 · Chapter Selection ({activeSubject?.course_name ?? 'Active Subject'})</SectionLabel>

            {loadingSubject ? (
              <div className="flex items-center gap-2 mb-6" style={{ color: 'var(--text-3)' }}>
                <Spinner size={16} />
                <span className="text-sm">Loading chapters from Course Setup…</span>
              </div>
            ) : availableChapters.length === 0 ? (
              <div className="card card-pad mb-6" style={{ textAlign: 'center', padding: '1.5rem' }}>
                <div className="text-sm text-muted" style={{ marginBottom: '1rem' }}>
                  No chapters found for this subject. Configure chapters in Course Setup first.
                </div>
                <a href="/course" className="btn btn-secondary btn-sm">→ Go to Course Setup</a>
              </div>
            ) : (
              <>
                {/* Legend */}
                <div className="flex gap-4 mb-3" style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>
                  <span>
                    <span style={{
                      display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                      background: 'var(--blue)', marginRight: 5, verticalAlign: 'middle',
                    }} />
                    Selected
                  </span>
                  <span>
                    <span style={{
                      display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                      background: 'rgba(0,0,0,0.12)', marginRight: 5, verticalAlign: 'middle',
                    }} />
                    Available (click to select)
                  </span>
                </div>

                <div className="flex gap-2 mb-2" style={{ flexWrap: 'wrap' }}>
                  {availableChapters.map(ch => {
                    const comp = completenessMap[ch]
                    const isSelected = selectedChapters.includes(ch)
                    const isReady = comp?.complete ?? false
                    return (
                      <div key={ch} style={{ position: 'relative' }}>
                        <button
                          onClick={() => toggleChapter(ch)}
                          className={`btn-chapter${isSelected ? ' selected' : ''}`}
                          title={chapterTooltip(ch)}
                        >
                          Ch {ch}
                          {/* Small completeness indicator */}
                          {comp && (
                            <span style={{
                              display: 'inline-block',
                              width: 6, height: 6,
                              borderRadius: '50%',
                              background: isReady ? 'var(--green)' : 'var(--orange)',
                              marginLeft: 4,
                              opacity: isSelected ? 0.9 : 0.6,
                              verticalAlign: 'middle',
                            }} />
                          )}
                        </button>
                      </div>
                    )
                  })}
                </div>

                {/* Completeness hint below buttons */}
                <div className="text-xs text-muted mb-6" style={{ marginTop: '0.5rem' }}>
                  ● = has enough questions &nbsp; ○ = insufficient questions &nbsp;
                  Hover a chapter button to see details.
                  {selectedChapters.length > 0 && (
                    <> &nbsp;| Selected: <strong>Ch {selectedChapters.join(', ')}</strong></>
                  )}
                </div>
              </>
            )}
          </>
        )}

        {/* Bloom distribution */}
        <SectionLabel>4 · Bloom Level Distribution</SectionLabel>
        <div className="card card-pad mb-6">
          <div className="flex items-center gap-4 mb-3">
            <div style={{ flex: 1 }}>
              <div className="form-label">L2 (Understand) — {l2Pct}%</div>
              <input type="range" className="slider" min={0} max={100} step={5} value={l2Pct}
                onChange={e => setL2Pct(Number(e.target.value))} />
            </div>
            <div style={{ textAlign: 'right', minWidth: 120 }}>
              <div className="form-label">L3 (Apply)</div>
              <div className="font-bold" style={{ fontSize: '1.5rem', color: 'var(--orange-text)' }}>{l3Pct}%</div>
            </div>
          </div>
          <div style={{ display: 'flex', height: 8, borderRadius: 'var(--radius-pill)', overflow: 'hidden' }}>
            <div style={{ width: `${l2Pct}%`, background: 'var(--green)', transition: 'width 0.2s' }} />
            <div style={{ width: `${l3Pct}%`, background: 'var(--orange)' }} />
          </div>
          <div className="flex justify-between mt-2 text-xs text-muted">
            <span>L2: {Math.round(totalQ * l2Pct / 100)} questions</span>
            <span>L3: {totalQ - Math.round(totalQ * l2Pct / 100)} questions</span>
          </div>
        </div>

        {/* Blueprint preview */}
        <SectionLabel>5 · Blueprint Preview</SectionLabel>
        <div className="table-wrap mb-6">
          <table>
            <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
            <tbody>
              <tr><td>Active Course</td><td><strong>{activeSubject?.course_name || 'N/A'}</strong> ({activeSubject?.course_code || 'N/A'})</td></tr>
              <tr><td>Exam Type</td><td>{examType === 'ISA-I' ? 'Minor 1 (ISA-I)' : examType === 'ISA-II' ? 'Minor 2 (ISA-II)' : 'End-Semester (ESA)'}</td></tr>
              <tr><td>Duration</td><td>{activeScheme?.duration || (isMinor ? '75 minutes' : '180 minutes')}</td></tr>
              <tr><td>Total Marks</td><td>{activeScheme?.total_marks ?? (isMinor ? 30 : 100)} marks</td></tr>
              <tr><td>Full Questions</td><td>{activeScheme?.total_questions ?? (isMinor ? 3 : 8)} full questions</td></tr>
              <tr><td>To Attempt</td><td>{activeScheme?.questions_to_attempt ?? (isMinor ? 2 : 5)} full questions</td></tr>
              {activeScheme?.sub_question_pattern?.length ? (
                <tr><td>Sub-question Pattern</td><td>[{activeScheme.sub_question_pattern.join(', ')}] marks</td></tr>
              ) : null}
              <tr><td>Total Sub-questions</td><td>{totalQ}</td></tr>
              <tr><td>From Question Bank</td><td>{Math.round(totalQ * 0.67)} (~67%)</td></tr>
              <tr><td>AI Generated</td><td>{totalQ - Math.round(totalQ * 0.67)} (~33%)</td></tr>
              <tr><td>L2 Questions</td><td>{Math.round(totalQ * l2Pct / 100)}</td></tr>
              <tr><td>L3 Questions</td><td>{totalQ - Math.round(totalQ * l2Pct / 100)}</td></tr>
              <tr><td>Sets</td><td>{numSets}</td></tr>
              {isMinor && selectedChapters.length > 0 && (
                <tr>
                  <td>Chapters</td>
                  <td>Ch {selectedChapters.join(', ')}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Advanced */}
        <details className="mb-6">
          <summary className="text-sm font-medium" style={{ cursor: 'pointer', marginBottom: '0.75rem' }}>
            ⚙️ Advanced Options
          </summary>
          <div className="card card-pad mt-3">
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Academic Year</label>
                <input className="form-input" value={academicYear}
                  onChange={e => setAcademicYear(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Bloom Tolerance (%)</label>
                <input className="form-input" type="number" min={1} max={20} value={tolerance}
                  onChange={e => setTolerance(Number(e.target.value))} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Department</label>
              <input className="form-input" value={department}
                onChange={e => setDepartment(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm" style={{ cursor: 'pointer' }}>
              <input type="checkbox" checked={excludeUsed}
                onChange={e => setExcludeUsed(e.target.checked)} />
              Exclude previously used questions
            </label>
          </div>
        </details>

        {/* Confirm + Generate */}
        <div className="card card-pad mb-6">
          <label className="flex items-center gap-3 text-sm font-medium" style={{ cursor: 'pointer', marginBottom: '1rem' }}>
            <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
            I confirm the blueprint above is correct for {activeSubject?.course_name || 'this subject'} and wish to generate the paper
          </label>
          {error && <Alert variant="error">{error}</Alert>}
          <button className="btn btn-primary btn-lg btn-full" onClick={handleGenerate}
            disabled={generating || !confirmed || loadingSubject}>
            {generating ? <><Spinner size={16} /> Generating…</> : `⚡ Generate Question Paper(s) for ${activeSubject?.course_name || 'Subject'}`}
          </button>
        </div>

        {/* Results */}
        {result && (
          <div className="card card-pad">
            {result.success ? (
              <>
                <Alert variant="success">
                  Successfully generated {result.paper_set_ids.length} paper set(s) for {activeSubject?.course_name}!
                </Alert>
                <div className="mt-4">
                  {result.validation_reports.map((vr: ValidationReport, i: number) => (
                    <div key={i} style={{ padding: '0.75rem 0', borderBottom: '1px solid var(--border-light)' }}>
                      <div className="flex items-center justify-between">
                        <span className="font-semibold">{statusIcon(vr.status)} {vr.set_id}</span>
                        <div className="flex gap-2">
                          <span className="badge badge-blue">Bank: {vr.source_bank_count}</span>
                          <span className="badge badge-purple">AI: {vr.source_ai_count}</span>
                          <span className="badge badge-green">L2: {vr.bloom_l2_count}</span>
                          <span className="badge badge-orange">L3: {vr.bloom_l3_count}</span>
                        </div>
                      </div>
                      {vr.findings.filter(f => f.severity === 'WARNING').map((f, fi) => (
                        <div key={fi} className="text-xs text-muted mt-1">⚠ {f.message}</div>
                      ))}
                    </div>
                  ))}
                </div>
                <div className="flex gap-3 mt-4">
                  <button className="btn btn-primary" onClick={() => { window.location.href = '/review' }}>👩‍🏫 Go to Faculty Review</button>
                  <button className="btn btn-secondary" onClick={() => setResult(null)}>Generate Another</button>
                </div>
              </>
            ) : (
              <>
                <Alert variant="error">Generation failed</Alert>
                {result.errors.map((e, i) => <div key={i} className="text-sm text-red mt-2">• {e}</div>)}
              </>
            )}
          </div>
        )}
      </div>
    </>
  )
}
