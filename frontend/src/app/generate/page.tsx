'use client'

import { useState, useEffect } from 'react'
import { api, type GenerateResponse, type ValidationReport } from '@/lib/api'
import { PageHeader, ConfidentialBanner, SectionLabel, Card, Alert, Spinner } from '@/components/ui'

type ExamType = 'MINOR' | 'END_SEM'

export default function GeneratePage() {
  const [examType, setExamType] = useState<ExamType>('MINOR')
  const [numSets, setNumSets] = useState(1)
  const [l2Pct, setL2Pct] = useState(50)
  const [selectedChapters, setSelectedChapters] = useState<number[]>([1, 2, 3])
  const [tolerance, setTolerance] = useState(5)
  const [academicYear, setAcademicYear] = useState('2024-25')
  const [department, setDepartment] = useState('Computer Science & Engineering')
  const [excludeUsed, setExcludeUsed] = useState(true)
  const [confirmed, setConfirmed] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const [error, setError] = useState('')

  const l3Pct = 100 - l2Pct
  const isMinor = examType === 'MINOR'
  const totalQ = isMinor ? 6 : 16

  function toggleChapter(ch: number) {
    setSelectedChapters(prev =>
      prev.includes(ch) ? prev.filter(x => x !== ch) : [...prev, ch].sort((a, b) => a - b)
    )
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
        selected_chapters: isMinor ? selectedChapters : [1,2,3,4,5,6,7],
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
      <PageHeader title="Generate Paper" subtitle="Configure and generate AI-powered question papers" />
      <ConfidentialBanner />

      <div style={{ maxWidth: 800 }}>

        {/* Exam type */}
        <SectionLabel>1 · Examination Type</SectionLabel>
        <div className="flex gap-3 mb-6">
          {(['MINOR', 'END_SEM'] as ExamType[]).map(t => (
            <button key={t} onClick={() => setExamType(t)}
              className={`btn ${examType === t ? 'btn-primary' : 'btn-secondary'}`}>
              {t === 'MINOR' ? '📝 Minor / Internal' : '📜 End-Semester'}
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

        {/* Chapters */}
        {isMinor && (
          <>
            <SectionLabel>3 · Chapter Selection</SectionLabel>
            <div className="flex gap-2 mb-6" style={{ flexWrap: 'wrap' }}>
              {[1,2,3,4,5,6,7].map(ch => (
                <button key={ch} onClick={() => toggleChapter(ch)}
                  className={`btn btn-sm ${selectedChapters.includes(ch) ? 'btn-primary' : 'btn-secondary'}`}>
                  Ch {ch}
                </button>
              ))}
            </div>
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
              <tr><td>Exam Type</td><td>{isMinor ? 'Minor / Internal' : 'End-Semester'}</td></tr>
              <tr><td>Duration</td><td>{isMinor ? '75 minutes' : '180 minutes'}</td></tr>
              <tr><td>Total Marks</td><td>{isMinor ? '40' : '100'}</td></tr>
              <tr><td>Total Questions</td><td>{totalQ}</td></tr>
              <tr><td>From Question Bank</td><td>{isMinor ? '4 (66.7%)' : '11 (68.75%)'}</td></tr>
              <tr><td>AI Generated</td><td>{isMinor ? '2 (33.3%)' : '5 (31.25%)'}</td></tr>
              <tr><td>L2 Questions</td><td>{Math.round(totalQ * l2Pct / 100)}</td></tr>
              <tr><td>L3 Questions</td><td>{totalQ - Math.round(totalQ * l2Pct / 100)}</td></tr>
              <tr><td>Sets</td><td>{numSets}</td></tr>
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
            I confirm the blueprint above is correct and wish to generate the paper
          </label>
          {error && <Alert variant="error">{error}</Alert>}
          <button className="btn btn-primary btn-lg btn-full" onClick={handleGenerate}
            disabled={generating || !confirmed}>
            {generating ? <><Spinner size={16} /> Generating…</> : '⚡ Generate Question Paper(s)'}
          </button>
        </div>

        {/* Results */}
        {result && (
          <div className="card card-pad">
            {result.success ? (
              <>
                <Alert variant="success">
                  Successfully generated {result.paper_set_ids.length} paper set(s)!
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
