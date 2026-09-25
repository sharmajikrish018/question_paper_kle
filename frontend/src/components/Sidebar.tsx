'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV = [
  { href: '/',            label: 'Dashboard' },
  { href: '/course',      label: 'Course Setup' },
  { href: '/questions',   label: 'Question Bank' },
  { href: '/lesson-plan', label: 'Lesson Plan' },
  { href: '/generate',    label: 'Generate Paper' },
  { href: '/review',      label: 'Faculty Review' },
  { href: '/validation',  label: 'Validation' },
  { href: '/history',     label: 'Usage History' },
  { href: '/settings',    label: 'Settings' },
]

export function Sidebar() {
  const path = usePathname()

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">Prashnopatra</div>
        <div className="sidebar-brand-sub">AI Question Paper Agent</div>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ href, label }) => {
          const active = href === '/' ? path === '/' : path.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-item${active ? ' active' : ''}`}
            >
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="status-pill">
          <div className="status-pill-label">Live API</div>
          <div className="status-pill-sub">Connected to backend</div>
        </div>
      </div>
    </aside>
  )
}
