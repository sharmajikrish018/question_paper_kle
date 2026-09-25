'use client'

import { useState, useEffect } from 'react'
import { api, type Question, type Completeness, type ImportResult } from '@/lib/api'
import { PageHeader, SectionLabel, Badge, FileDropzone, Alert, EmptyState, ProgressBar, Spinner } from '@/components/ui'

type Tab = 'overview' | 'browse' | 'import'

export default function QuestionsPage() {
  const [tab, setTab] = useState<Tab>('overview')
  const [completeness, setCompleteness] = useState<Completeness[]>([])
  const [questions, setQuestions] = useState<Question[]>([])
  const [filter, setFilter] = useState({ chapter: '', bloom: '' })
  const [loadingQ, setLoadingQ] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [importError, setImportError] = useState('')

  useEffect(() => {
    api.getCompleteness().then(setCompleteness).catch(() => {})
  }, [])

  async function loadQuestions() {
    setLoadingQ(true)
    try {
      const qs = await api.getQuestions({
        chapter: filter.chapter ? Number(filter.chapter) : undefined,
        bloom: filter.bloom || undefined,
        limit: 200,
      })
      setQuestions(qs)
    } finally { setLoadingQ(false) }
  }

  useEffect(() => { if (tab === 'browse') loadQuestions() }, [tab, filter.chapter, filter.bloom])

  async function handleImport(file: File) {
    setImporting(true)
    setImportResult(null)
    setImportError('')
    try {
      const result = await api.importQuestions(file)
      setImportResult(result)
      // Refresh completeness
      api.getCompleteness().then(setCompleteness)
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : 'Import failed')
    } finally { setImporting(false) }
  }

  const totalQ = completeness.reduce((s, c) => s + c.total, 0)
  const readyChapters = completeness.filter(c => c.complete).length

  function bloomBadge(bl: string) {
    return bl === 'L2'
      ? <Badge variant="green">L2</Badge>
      : <Badge variant="orange">L3</Badge>
  }

  function sourceBadge(src: string) {
    return src.includes('BANK')
      ? <Badge variant="blue">Bank</Badge>
      : <Badge variant="purple">AI</Badge>
  }

  return (
    <>
      <PageHeader title="Question Bank" subtitle="Manage and import exam questions" />

      {/* Tabs */}
      <div className="tabs">
        {(['overview', 'browse', 'import'] as Tab[]).map(t => (
          <button key={t} className={`tab${tab === t ? ' active' : ''}`}
            onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── Overview tab ─────────────────────────────────────────────── */}
      {tab === 'overview' && (
        <>
          <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <div className="stat-card">
              <div className="stat-icon">📋</div>
              <div className="stat-value">{totalQ}</div>
              <div className="stat-label">Total Questions</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">✅</div>
              <div className="stat-value">{readyChapters}/7</div>
              <div className="stat-label">Chapters Ready</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">📊</div>
              <div className="stat-value">{Math.min(100, Math.round(totalQ / 140 * 100))}%</div>
              <div className="stat-label">Bank Complete</div>
            </div>
          </div>

          <SectionLabel style={{ marginTop: '1.5rem' }}>Chapter Completeness</SectionLabel>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Chapter</th>
                  <th>L2 (Understand)</th>
                  <th>L3 (Apply)</th>
                  <th>Total</th>
                  <th>Progress</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {completeness.map(c => (
                  <tr key={c.chapter_number}>
                    <td className="font-medium">Chapter {c.chapter_number}</td>
                    <td>{c.l2_ok ? <span className="text-green">{c.l2_count}</span> : <span className="text-muted">{c.l2_count}/10</span>}</td>
                    <td>{c.l3_ok ? <span className="text-green">{c.l3_count}</span> : <span className="text-muted">{c.l3_count}/10</span>}</td>
                    <td>{c.total}/20</td>
                    <td style={{ width: 120 }}>
                      <ProgressBar value={c.total} max={20} />
                    </td>
                    <td>
                      {c.complete
                        ? <Badge variant="green">✅ Ready</Badge>
                        : <Badge variant="orange">⚠ Incomplete</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── Browse tab ────────────────────────────────────────────────── */}
      {tab === 'browse' && (
        <>
          <div className="flex gap-3 mb-6" style={{ flexWrap: 'wrap' }}>
            <select className="form-select" style={{ width: 180 }} value={filter.chapter}
              onChange={e => setFilter(f => ({ ...f, chapter: e.target.value }))}>
              <option value="">All Chapters</option>
              {[1,2,3,4,5,6,7].map(n => <option key={n} value={n}>Chapter {n}</option>)}
            </select>
            <select className="form-select" style={{ width: 160 }} value={filter.bloom}
              onChange={e => setFilter(f => ({ ...f, bloom: e.target.value }))}>
              <option value="">All Bloom Levels</option>
              <option value="L2">L2 — Understand</option>
              <option value="L3">L3 — Apply</option>
            </select>
          </div>

          {loadingQ ? (
            <div className="text-center" style={{ padding: '3rem' }}><Spinner size={28} /></div>
          ) : questions.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Chapter</th>
                    <th>Level</th>
                    <th>Source</th>
                    <th style={{ width: '50%' }}>Question</th>
                  </tr>
                </thead>
                <tbody>
                  {questions.map(q => (
                    <tr key={q.question_id}>
                      <td className="text-xs text-muted font-medium">{q.question_id}</td>
                      <td className="text-sm">Ch {q.chapter_number}</td>
                      <td>{bloomBadge(q.bloom_level)}</td>
                      <td>{sourceBadge(q.source)}</td>
                      <td className="text-sm" style={{ maxWidth: 500 }}>{q.question_text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon="🔍" title="No questions found" sub="Adjust filters or import a question bank" />
          )}
        </>
      )}

      {/* ── Import tab ────────────────────────────────────────────────── */}
      {tab === 'import' && (
        <div style={{ maxWidth: 640 }}>
          <p className="text-sm text-muted mb-6">
            Upload your question bank as PDF, Excel (.xlsx), CSV, JSON, or DOCX.
            The system will extract all questions and import them automatically.
          </p>

          <FileDropzone
            onFile={handleImport}
            accept=".pdf,.xlsx,.xls,.csv,.json,.docx"
            label="Drop question bank file here"
            sublabel="Supports PDF, XLSX, CSV, JSON, DOCX"
            disabled={importing}
          />

          {importing && (
            <div className="flex items-center gap-3 mt-6">
              <Spinner />
              <span className="text-sm text-muted">Extracting questions…</span>
            </div>
          )}

          {importError && <div className="mt-4"><Alert variant="error">{importError}</Alert></div>}

          {importResult && (
            <div className="card card-pad mt-6">
              <div className="font-semibold mb-4">Import Complete</div>
              <div className="grid-2">
                <div>
                  <div className="text-xs text-muted mb-1">Rows Parsed</div>
                  <div className="font-bold" style={{ fontSize: '1.5rem', color: 'var(--blue)' }}>{importResult.total_rows}</div>
                </div>
                <div>
                  <div className="text-xs text-muted mb-1">Questions Imported</div>
                  <div className="font-bold" style={{ fontSize: '1.5rem', color: 'var(--green-text)' }}>{importResult.imported}</div>
                </div>
              </div>
              {importResult.warnings.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs text-muted mb-2">Warnings ({importResult.warnings.length})</div>
                  {importResult.warnings.slice(0, 5).map((w, i) => (
                    <Alert key={i} variant="warning">{w}</Alert>
                  ))}
                </div>
              )}
              {importResult.errors.length > 0 && (
                <div className="mt-4">
                  {importResult.errors.slice(0, 3).map((e, i) => (
                    <Alert key={i} variant="error">{e}</Alert>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  )
}
