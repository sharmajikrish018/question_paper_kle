'use client'

import { useState, useEffect } from 'react'
import { api, type Chapter, type LessonPlanExtraction } from '@/lib/api'
import { PageHeader, Card, SectionLabel, Alert, FileDropzone, Spinner } from '@/components/ui'

export default function LessonPlanPage() {
  const [file, setFile] = useState<File | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [result, setResult] = useState<LessonPlanExtraction | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleFile(f: File) {
    setFile(f)
    setExtracting(true)
    setResult(null)
    setError('')
    setSaved(false)
    try {
      const res = await api.extractLessonPlan(f)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Extraction failed')
    } finally { setExtracting(false) }
  }

  async function handleSave() {
    if (!result) return
    setSaving(true)
    try {
      await api.saveCourseStructure(result.chapters)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } finally { setSaving(false) }
  }

  function updateChapter(idx: number, key: keyof Chapter, val: string | number) {
    if (!result) return
    const chapters = [...result.chapters]
    chapters[idx] = { ...chapters[idx], [key]: val }
    setResult({ ...result, chapters })
  }

  return (
    <>
      <PageHeader title="Lesson Plan" subtitle="Upload your lesson plan and extract chapter structure using AI" />

      {/* Upload zone */}
      <SectionLabel>Upload Lesson Plan</SectionLabel>
      <div style={{ maxWidth: 560, marginBottom: '2rem' }}>
        <FileDropzone
          onFile={handleFile}
          accept=".pdf,.docx,.txt,.md,.xlsx"
          label="Drop your lesson plan here"
          sublabel="Supports PDF, DOCX, TXT, Markdown, Excel"
          disabled={extracting}
        />
        {file && !extracting && (
          <div className="flex items-center gap-2 mt-3 text-sm text-muted">
            <span>📄</span> <span>{file.name}</span>
          </div>
        )}
        {extracting && (
          <div className="flex items-center gap-3 mt-4">
            <Spinner />
            <span className="text-sm text-muted">Extracting chapters with AI… this may take a moment</span>
          </div>
        )}
        {error && <Alert variant="error">{error}</Alert>}
      </div>

      {/* Results */}
      {result && (
        <>
          <div className="flex items-center justify-between mb-4">
            <SectionLabel style={{ margin: 0 }}>
              Extracted {result.chapters.length} chapters
              <span className="badge badge-{result.confidence > 0.7 ? 'green' : 'orange'} ml-2" style={{ marginLeft: '0.5rem' }}>
                {Math.round(result.confidence * 100)}% confidence
              </span>
            </SectionLabel>
            <div className="flex gap-3">
              <button className="btn btn-secondary btn-sm" onClick={() => setResult(null)}>
                Re-upload
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : saved ? '✅ Saved!' : 'Save Structure'}
              </button>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="mb-4">
              {result.warnings.map((w, i) => <Alert key={i} variant="warning">{w}</Alert>)}
            </div>
          )}

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Unit</th>
                  <th>Ch #</th>
                  <th>Title</th>
                  <th>Topics</th>
                </tr>
              </thead>
              <tbody>
                {result.chapters.map((ch, i) => (
                  <tr key={i}>
                    <td style={{ width: 70 }}>
                      <input className="form-input" type="number" value={ch.unit_number}
                        onChange={e => updateChapter(i, 'unit_number', Number(e.target.value))}
                        style={{ width: 55, padding: '0.3rem 0.5rem' }} />
                    </td>
                    <td style={{ width: 70 }}>
                      <input className="form-input" type="number" value={ch.chapter_number}
                        onChange={e => updateChapter(i, 'chapter_number', Number(e.target.value))}
                        style={{ width: 55, padding: '0.3rem 0.5rem' }} />
                    </td>
                    <td>
                      <input className="form-input" value={ch.title}
                        onChange={e => updateChapter(i, 'title', e.target.value)} />
                    </td>
                    <td className="text-sm text-muted">{ch.topics.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.raw_text_preview && (
            <details className="mt-6">
              <summary className="text-sm text-muted" style={{ cursor: 'pointer' }}>Raw text preview</summary>
              <pre style={{ fontSize: '0.78rem', color: 'var(--text-3)', marginTop: '0.5rem',
                background: 'var(--surface-2)', padding: '1rem', borderRadius: 'var(--radius-sm)',
                overflow: 'auto', maxHeight: 200 }}>
                {result.raw_text_preview}
              </pre>
            </details>
          )}
        </>
      )}
    </>
  )
}
