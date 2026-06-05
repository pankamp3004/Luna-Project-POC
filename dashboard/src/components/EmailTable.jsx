import React, { useState } from 'react'
import { MoreHorizontal, ChevronLeft, ChevronRight } from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// Badge helpers
// ─────────────────────────────────────────────────────────────────────────────

const SCENARIO_COLORS = {
  new_lead:       { bg: '#1e3a5f', text: '#60a5fa', label: 'New Lead' },
  inquiry_reply:  { bg: '#1e2f4a', text: '#93c5fd', label: 'Inquiry Reply' },
  tour_confirm:   { bg: '#14362e', text: '#4ade80', label: 'Tour Confirm' },
  tour_reschedule:{ bg: '#2d2a14', text: '#facc15', label: 'Tour Reschedule' },
  post_tour:      { bg: '#1a2e1a', text: '#86efac', label: 'Post Tour' },
  objection:      { bg: '#3a1e0a', text: '#fb923c', label: 'Objection' },
  far_future:     { bg: '#2a1a3e', text: '#c084fc', label: 'Far Future' },
  re_engagement:  { bg: '#1a2a3a', text: '#67e8f9', label: 'Re-Engagement' },
  student_housing:{ bg: '#1e1a3a', text: '#a78bfa', label: 'Student Housing' },
  logistical_other:{ bg: '#2a2a2a', text: '#94a3b8', label: 'Logistical' },
  escalated:      { bg: '#3a1a1a', text: '#f87171', label: 'Escalated' },
  unknown:        { bg: '#2a2a2a', text: '#94a3b8', label: 'Unknown' },
}

const DECISION_COLORS = {
  SEND:     { bg: '#14362e', text: '#4ade80', label: 'SEND' },
  DRAFT:    { bg: '#2d2a14', text: '#facc15', label: 'DRAFT' },
  HOLD:     { bg: '#2d1f14', text: '#fb923c', label: 'HOLD' },
  SKIP:     { bg: '#2a2a2a', text: '#94a3b8', label: 'SKIP' },
  ESCALATE: { bg: '#3a1a1a', text: '#f87171', label: 'ESCALATE' },
}

function ScenarioBadge({ scenario }) {
  const cfg = SCENARIO_COLORS[scenario] || SCENARIO_COLORS.unknown
  return (
    <span
      className="badge text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap"
      style={{ backgroundColor: cfg.bg, color: cfg.text }}
    >
      {cfg.label}
    </span>
  )
}

function DecisionBadge({ decision }) {
  const cfg = DECISION_COLORS[decision] || DECISION_COLORS.SKIP
  return (
    <span
      className="badge text-xs font-semibold px-2 py-1 rounded-full whitespace-nowrap"
      style={{ backgroundColor: cfg.bg, color: cfg.text }}
    >
      {cfg.label}
    </span>
  )
}

function ClassificationBadge({ method }) {
  const isLLM = method === 'LLM'
  return (
    <span
      className="badge text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap"
      style={{
        backgroundColor: isLLM ? '#1e1a3a' : '#1f2937',
        color: isLLM ? '#a78bfa' : '#94a3b8',
      }}
    >
      {isLLM ? 'LLM + Tools' : 'Policy Match'}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Avatar with initials
// ─────────────────────────────────────────────────────────────────────────────

const AVATAR_COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f59e0b',
  '#10b981', '#3b82f6', '#ef4444', '#14b8a6',
]

function getAvatarColor(str) {
  if (!str) return AVATAR_COLORS[0]
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function getInitials(name, email) {
  if (name && name.trim()) {
    const parts = name.trim().split(' ')
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
    return parts[0].slice(0, 2).toUpperCase()
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return '??'
}

function Avatar({ name, email }) {
  const initials = getInitials(name, email)
  const color = getAvatarColor(email || name)
  return (
    <div
      className="flex items-center justify-center rounded-full flex-shrink-0 text-white text-xs font-bold"
      style={{ width: '32px', height: '32px', backgroundColor: color }}
    >
      {initials}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatModelName(model) {
  if (!model || model === '—' || model === '— (No LLM)') return '— (No LLM)'
  if (model.includes('sonnet')) return 'Claude Sonnet 4.5'
  if (model.includes('haiku')) return 'Claude Haiku 4.5'
  return model
}

function formatCost(cost) {
  if (!cost || cost === 0) return '—'
  if (cost < 0.001) return `$${cost.toFixed(6)}`
  return `$${cost.toFixed(4)}`
}

function formatTime(isoStr) {
  if (!isoStr) return '—'
  try {
    // Handle both "2026-06-03T10:45:53.927320+00:00" and "2026-06-03T09:43:09.423653" (no tz)
    const normalized = isoStr.includes('+') || isoStr.endsWith('Z') ? isoStr : isoStr + 'Z'
    const d = new Date(normalized)
    const now = new Date()
    const diff = (now - d) / 1000

    if (diff < 60) return 'just now'
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`

    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    })
  } catch {
    return isoStr.slice(0, 10)
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Main EmailTable
// ─────────────────────────────────────────────────────────────────────────────

export default function EmailTable({
  emails = [],
  total = 0,
  page = 1,
  pages = 1,
  onPageChange,
  selectedId,
  onSelectEmail,
  loading = false,
}) {
  const [checkedIds, setCheckedIds] = useState(new Set())

  const toggleCheck = (id, e) => {
    e.stopPropagation()
    setCheckedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (checkedIds.size === emails.length) {
      setCheckedIds(new Set())
    } else {
      setCheckedIds(new Set(emails.map(e => e.id)))
    }
  }

  if (loading) {
    return (
      <div
        className="rounded-lg p-8 text-center"
        style={{ backgroundColor: '#1e2130', border: '1px solid #2a2d3e' }}
      >
        <div className="text-text-muted animate-pulse">Loading emails...</div>
      </div>
    )
  }

  if (emails.length === 0) {
    return (
      <div
        className="rounded-lg p-12 text-center"
        style={{ backgroundColor: '#1e2130', border: '1px solid #2a2d3e' }}
      >
        <div style={{ color: '#64748b', fontSize: '14px' }}>
          No emails found. Run the pipeline to process emails.
        </div>
      </div>
    )
  }

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ backgroundColor: '#1e2130', border: '1px solid #2a2d3e' }}
    >
      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
          {/* Header */}
          <thead>
            <tr style={{ borderBottom: '1px solid #2a2d3e', backgroundColor: '#181b28' }}>
              <th className="px-4 py-3 text-left w-10">
                <input
                  type="checkbox"
                  checked={checkedIds.size === emails.length && emails.length > 0}
                  onChange={toggleAll}
                  className="rounded"
                />
              </th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '180px' }}>From</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '200px' }}>Subject / Preview</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '130px' }}>Intent</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '130px' }}>Classification</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '90px' }}>Decision</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '150px' }}>Model Used</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '80px' }}>AI Cost</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: '#64748b', minWidth: '100px' }}>Received</th>
              <th className="px-4 py-3 text-center font-medium w-10" style={{ color: '#64748b' }}>•••</th>
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {emails.map((email) => {
              const isSelected = email.id === selectedId
              const isChecked = checkedIds.has(email.id)

              return (
                <tr
                  key={email.id}
                  onClick={() => onSelectEmail && onSelectEmail(email)}
                  className={`email-row cursor-pointer transition-colors ${isSelected ? 'email-row-selected' : ''}`}
                  style={{
                    borderBottom: '1px solid #2a2d3e',
                    backgroundColor: isSelected ? '#1e2340' : undefined,
                    borderLeft: isSelected ? '3px solid #6366f1' : '3px solid transparent',
                  }}
                >
                  {/* Checkbox */}
                  <td className="px-4 py-3" onClick={e => toggleCheck(email.id, e)}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {}}
                      className="rounded"
                    />
                  </td>

                  {/* From */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Avatar name={email.from_name} email={email.from_addr} />
                      <div className="min-w-0">
                        <div
                          className="font-medium truncate-text text-sm"
                          style={{ color: '#e2e8f0', maxWidth: '120px' }}
                        >
                          {email.from_name || email.from_addr.split('@')[0]}
                        </div>
                        <div
                          className="text-xs truncate-text"
                          style={{ color: '#64748b', maxWidth: '120px' }}
                        >
                          {email.from_addr}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Subject / Preview */}
                  <td className="px-4 py-3">
                    <div style={{ maxWidth: '240px' }}>
                      <div
                        className="font-semibold text-sm truncate-text"
                        style={{ color: '#e2e8f0' }}
                      >
                        {email.subject || '(no subject)'}
                      </div>
                      <div
                        className="text-xs mt-0.5 truncate-text"
                        style={{ color: '#64748b' }}
                      >
                        {email.body_preview || '—'}
                      </div>
                    </div>
                  </td>

                  {/* Intent / Scenario */}
                  <td className="px-4 py-3">
                    <ScenarioBadge scenario={email.scenario} />
                  </td>

                  {/* Classification Method */}
                  <td className="px-4 py-3">
                    <ClassificationBadge method={email.classification_method} />
                  </td>

                  {/* Decision */}
                  <td className="px-4 py-3">
                    <DecisionBadge decision={email.decision} />
                  </td>

                  {/* Model Used */}
                  <td className="px-4 py-3">
                    <span style={{ color: '#94a3b8', fontSize: '12px' }}>
                      {formatModelName(email.model_used)}
                    </span>
                  </td>

                  {/* AI Cost */}
                  <td className="px-4 py-3">
                    <span
                      style={{
                        color: email.ai_cost_usd > 0 ? '#4ade80' : '#64748b',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                      }}
                    >
                      {formatCost(email.ai_cost_usd)}
                    </span>
                  </td>

                  {/* Received */}
                  <td className="px-4 py-3">
                    <span style={{ color: '#64748b', fontSize: '12px' }}>
                      {formatTime(email.received_at)}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={e => e.stopPropagation()}
                      className="p-1 rounded hover:bg-white/10 transition-colors"
                      style={{ color: '#64748b' }}
                    >
                      <MoreHorizontal size={16} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderTop: '1px solid #2a2d3e' }}
      >
        <div style={{ color: '#64748b', fontSize: '13px' }}>
          Showing {Math.min((page - 1) * 10 + 1, total)}–{Math.min(page * 10, total)} of {total}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange && onPageChange(page - 1)}
            className="flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors disabled:opacity-40"
            style={{
              backgroundColor: '#2a2d3e',
              color: '#e2e8f0',
              border: '1px solid #3a3d4e',
              cursor: page <= 1 ? 'not-allowed' : 'pointer',
            }}
          >
            <ChevronLeft size={14} />
            Prev
          </button>

          {/* Page numbers */}
          {Array.from({ length: Math.min(pages, 5) }, (_, i) => {
            // show pages around current
            let pageNum
            if (pages <= 5) {
              pageNum = i + 1
            } else if (page <= 3) {
              pageNum = i + 1
            } else if (page >= pages - 2) {
              pageNum = pages - 4 + i
            } else {
              pageNum = page - 2 + i
            }
            return (
              <button
                key={pageNum}
                onClick={() => onPageChange && onPageChange(pageNum)}
                className="w-8 h-8 rounded text-sm font-medium transition-colors"
                style={{
                  backgroundColor: pageNum === page ? '#6366f1' : '#2a2d3e',
                  color: pageNum === page ? '#ffffff' : '#e2e8f0',
                  border: `1px solid ${pageNum === page ? '#6366f1' : '#3a3d4e'}`,
                  cursor: 'pointer',
                }}
              >
                {pageNum}
              </button>
            )
          })}

          <button
            disabled={page >= pages}
            onClick={() => onPageChange && onPageChange(page + 1)}
            className="flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors disabled:opacity-40"
            style={{
              backgroundColor: '#2a2d3e',
              color: '#e2e8f0',
              border: '1px solid #3a3d4e',
              cursor: page >= pages ? 'not-allowed' : 'pointer',
            }}
          >
            Next
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
