'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { PageHeader, SectionLabel, Card, Alert, Spinner } from '@/components/ui'

export default function SettingsPage() {
  const [health, setHealth] = useState<{ status: string; message?: string; model?: string } | null>(null)
  const [checkingHealth, setCheckingHealth] = useState(false)
  const [msg, setMsg] = useState('')

  async function checkHealth() {
    setCheckingHealth(true)
    try {
      const res = await api.getLLMHealth()
      setHealth(res)
    } finally { setCheckingHealth(false) }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="LLM configuration, privacy controls, and paper rules" />

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
