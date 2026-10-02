'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, type SubjectDetail } from '@/lib/api'
import { PageHeader, SectionLabel, Alert, Spinner, ActiveSubjectBanner } from '@/components/ui'

export default function LessonPlanPage() {
  const [subject, setSubject] = useState<SubjectDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadSubject = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { active_subject_id } = await api.getActiveSubjectId()
      let detail: SubjectDetail | null = null

      if (active_subject_id) {
        try { detail = await api.getSubject(active_subject_id) } catch { /* ignore */ }
      }

      // Fall back to first subject
      if (!detail) {
        const list = await api.listSubjects()
        if (list.length > 0) {
          detail = await api.getSubject(list[0].subject_id)
        }
      }

      setSubject(detail)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load subject')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSubject()
    const handler = () => loadSubject()
    window.addEventListener('activeSubjectChanged', handler)
    return () => window.removeEventListener('activeSubjectChanged', handler)
  }, [loadSubject])

  // ── Derived state ──────────────────────────────────────────────────
  const lpMeta = subject?.lp_metadata as Record<string, unknown> | undefined
  const hasLP = !!(lpMeta?.source_filename || (subject?.units && subject.units.length > 0))
  const totalChapters = subject?.units?.reduce((s, u) => s + u.chapters.length, 0) ?? 0

  // ── Loading state ─────────────────────────────────────────────────
  if (loading) {
    return (
      <>
        <PageHeader title="Lesson Plan" subtitle="Configured units, chapters and topics for the active subject" />
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '3rem 0', color: 'var(--text-3)' }}>
          <Spinner size={22} />
          <span className="text-sm">Loading lesson plan…</span>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Lesson Plan"
        subtitle="Configured units, chapters and topics for the active subject"
      />

      {/* Active subject banner */}
      <ActiveSubjectBanner subject={subject} showLink />

      {error && <Alert variant="error">{error}</Alert>}

      {/* No subject configured */}
      {!subject && !error && (
        <div className="card card-pad text-center" style={{ padding: '3rem 2rem' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📖</div>
          <div className="font-semibold" style={{ marginBottom: '0.5rem' }}>No Subject Configured</div>
          <div className="text-sm text-muted" style={{ marginBottom: '1.5rem' }}>
            Create a subject and upload a Lesson Plan in Course Setup first.
          </div>
          <a href="/course" className="btn btn-primary">+ Go to Course Setup</a>
        </div>
      )}

      {/* Subject exists but no LP */}
      {subject && !hasLP && (
        <div className="card card-pad" style={{ padding: '2.5rem 2rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📄</div>
          <div className="font-semibold" style={{ marginBottom: '0.5rem' }}>
            No Lesson Plan for {subject.course_name}
          </div>
          <div className="text-sm text-muted" style={{ marginBottom: '1.5rem', maxWidth: 440, margin: '0 auto 1.5rem' }}>
            No lesson plan has been uploaded for this subject yet.
            Go to Course Setup to upload an LP and configure units and chapters.
          </div>
          <a href="/course" className="btn btn-primary" style={{ display: 'inline-flex' }}>
            📤 Upload Lesson Plan in Course Setup
          </a>
        </div>
      )}

      {/* LP exists — show content */}
      {subject && hasLP && (
        <>
          {/* LP availability badge */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem',
          }}>
            <div className="flex items-center gap-3">
              <span className="badge badge-green" style={{ fontSize: '0.8rem', padding: '0.3rem 0.75rem' }}>
                ✓ Lesson Plan Available
              </span>
              <span className="text-sm text-muted">
                {subject.units.length} unit{subject.units.length !== 1 ? 's' : ''} ·{' '}
                {totalChapters} chapter{totalChapters !== 1 ? 's' : ''}
              </span>
              {lpMeta?.confidence !== undefined && (
                <span className="badge badge-blue" style={{ fontSize: '0.78rem' }}>
                  {Math.round((lpMeta.confidence as number) * 100)}% parse confidence
                </span>
              )}
            </div>
            <a href="/course" className="btn btn-secondary btn-sm">
              ✏ Edit in Course Setup
            </a>
          </div>

          {/* LP Metadata info */}
          {lpMeta?.source_filename && (
            <div style={{
              background: 'var(--surface-2)', borderRadius: 'var(--radius-sm)',
              padding: '0.625rem 1rem', marginBottom: '1.5rem',
              display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', color: 'var(--text-2)',
            }}>
              <span>📎</span>
              <span>Source: <strong>{String(lpMeta.source_filename)}</strong></span>
              {typeof lpMeta.raw_text_length === 'number' && lpMeta.raw_text_length > 0 && (
                <span className="text-muted">
                  · {Math.round(lpMeta.raw_text_length / 1000)}K chars parsed
                </span>
              )}
            </div>
          )}

          {/* Warnings from parse */}
          {Array.isArray(lpMeta?.warnings) && (lpMeta.warnings as string[]).length > 0 && (
            <div className="mb-6">
              {(lpMeta.warnings as string[]).slice(0, 3).map((w, i) => (
                <Alert key={i} variant="warning">{w}</Alert>
              ))}
            </div>
          )}

          {/* Units and Chapters */}
          {subject.units.map(unit => (
            <div key={unit.unit_number} style={{ marginBottom: '1.5rem' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem',
              }}>
                <div style={{
                  background: 'var(--blue)', color: 'white', borderRadius: '8px',
                  width: 32, height: 32, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: '0.8rem', fontWeight: 700, flexShrink: 0,
                }}>
                  {unit.unit_number}
                </div>
                <div>
                  <SectionLabel style={{ margin: 0, fontSize: '0.78rem' }}>
                    Unit {unit.unit_number}
                  </SectionLabel>
                  <div className="font-semibold" style={{ fontSize: '1rem', letterSpacing: '-0.01em' }}>
                    {unit.title}
                  </div>
                </div>
                <span className="badge badge-blue" style={{ marginLeft: 'auto' }}>
                  {unit.chapters.length} chapter{unit.chapters.length !== 1 ? 's' : ''}
                </span>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: 70 }}>Ch #</th>
                      <th>Chapter Title</th>
                      <th>Topics</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unit.chapters.map(ch => (
                      <tr key={ch.chapter_number}>
                        <td>
                          <span className="badge badge-gray">Ch {ch.chapter_number}</span>
                        </td>
                        <td className="font-medium">{ch.title || '(untitled)'}</td>
                        <td className="text-sm text-muted">
                          {ch.topics && ch.topics.length > 0
                            ? ch.topics.join(', ')
                            : <span style={{ fontStyle: 'italic', opacity: 0.6 }}>No topics listed</span>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </>
      )}
    </>
  )
}
