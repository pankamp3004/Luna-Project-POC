import React, { useState, useEffect } from 'react'
import {
  X,
  Mail,
  User,
  Calendar,
  Tag,
  Cpu,
  DollarSign,
  Wrench,
  Send,
  FileEdit,
  ChevronRight,
  Hash,
  Copy,
  Check,
} from 'lucide-react'
import { getEmailReply } from '../services/api.js'

// ─────────────────────────────────────────────────────────────────────────────
// Badge helpers (same palette as EmailTable)
// ─────────────────────────────────────────────────────────────────────────────

const SCENARIO_COLORS = {
  new_lead:        { bg: '#1e3a5f', text: '#60a5fa', label: 'New Lead' },
  inquiry_reply:   { bg: '#1e2f4a', text: '#93c5fd', label: 'Inquiry Reply' },
  tour_confirm:    { bg: '#14362e', text: '#4ade80', label: 'Tour Confirm' },
  tour_reschedule: { bg: '#2d2a14', text: '#facc15', label: 'Tour Reschedule' },
  post_tour:       { bg: '#1a2e1a', text: '#86efac', label: 'Post Tour' },
  objection:       { bg: '#3a1e0a', text: '#fb923c', label: 'Objection' },
  far_future:      { bg: '#2a1a3e', text: '#c084fc', label: 'Far Future' },
  re_engagement:   { bg: '#1a2a3a', text: '#67e8f9', label: 'Re-Engagement' },
  student_housing: { bg: '#1e1a3a', text: '#a78bfa', label: 'Student Housing' },
  logistical_other:{ bg: '#2a2a2a', text: '#94a3b8', label: 'Logistical' },
  escalated:       { bg: '#3a1a1a', text: '#f87171', label: 'Escalated' },
  unknown:         { bg: '#2a2a2a', text: '#94a3b8', label: 'Unknown' },
}

const DECISION_COLORS = {
  SEND:     { bg: '#14362e', text: '#4ade80', label: 'SEND' },
  DRAFT:    { bg: '#2d2a14', text: '#facc15', label: 'DRAFT' },
  HOLD:     { bg: '#2d1f14', text: '#fb923c', label: 'HOLD' },
  SKIP:     { bg: '#2a2a2a', text: '#94a3b8', label: 'SKIP' },
  ESCALATE: { bg: '#3a1a1a', text: '#f87171', label: 'ESCALATE' },
}

function Badge({ label, bg, text }) {
  return (
    <span
      className="badge text-xs font-semibold px-2.5 py-1 rounded-full"
      style={{ backgroundColor: bg, color: text }}
    >
      {label}
    </span>
  )
}

function formatModelName(model) {
  if (!model || model === '—' || model === '— (No LLM)') return '— (No LLM)'
  // Combined format: "Sonnet 4.5 + Haiku 4.5" or "Sonnet 4.5 × 2" — already readable
  if (model.includes('+') || model.includes('×')) return model
  // Raw API model names (fallback for old log entries)
  if (model.includes('sonnet')) return 'Sonnet 4.5'
  if (model.includes('haiku')) return 'Haiku 4.5'
  if (model.includes('opus')) return 'Opus 4'
  return model
}

function formatCost(cost) {
  if (!cost || cost === 0) return '$0.0000'
  if (cost < 0.001) return `$${cost.toFixed(6)}`
  return `$${cost.toFixed(4)}`
}

function formatDateTime(isoStr) {
  if (!isoStr) return '—'
  try {
    // Handle both "+00:00" timezone and naive UTC timestamps
    const normalized = isoStr.includes('+') || isoStr.endsWith('Z') ? isoStr : isoStr + 'Z'
    const d = new Date(normalized)
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return isoStr
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab components
// ─────────────────────────────────────────────────────────────────────────────

function OverviewTab({ email }) {
  const scenarioCfg = SCENARIO_COLORS[email.scenario] || SCENARIO_COLORS.unknown
  const decisionCfg = DECISION_COLORS[email.decision] || DECISION_COLORS.SKIP

  return (
    <div className="space-y-4">
      {/* Classification */}
      <Section title="Classification" icon={Tag}>
        <Row label="Intent">
          <Badge label={scenarioCfg.label} bg={scenarioCfg.bg} text={scenarioCfg.text} />
        </Row>
        <Row label="Method">
          <span style={{ color: '#94a3b8', fontSize: '13px' }}>
            {email.classification_method === 'LLM' ? 'LLM + Tools (Claude)' : 'Policy Match (No LLM)'}
          </span>
        </Row>
        {email.template_used && (
          <Row label="Template">
            <span style={{ color: '#94a3b8', fontSize: '13px' }}>
              {email.template_used}
            </span>
          </Row>
        )}
      </Section>

      {/* Decision */}
      <Section title="Decision" icon={ChevronRight}>
        <Row label="Action">
          <Badge label={decisionCfg.label} bg={decisionCfg.bg} text={decisionCfg.text} />
        </Row>
        <Row label="Status">
          <span
            style={{
              color: email.status === 'sent' ? '#4ade80'
                : email.status === 'escalated' ? '#f87171'
                : email.status === 'error' ? '#ef4444'
                : '#94a3b8',
              fontSize: '13px',
              textTransform: 'capitalize',
            }}
          >
            {email.status || '—'}
          </span>
        </Row>
        {email.error && (
          <Row label="Error">
            <span style={{ color: '#ef4444', fontSize: '12px', fontFamily: 'monospace' }}>
              {email.error}
            </span>
          </Row>
        )}
      </Section>

      {/* AI / Cost */}
      <Section title="AI & Cost" icon={Cpu}>
        <Row label="Model">
          <span style={{ color: '#94a3b8', fontSize: '13px' }}>
            {formatModelName(email.model_used)}
          </span>
        </Row>
        <Row label="Input tokens">
          <span style={{ color: '#94a3b8', fontSize: '13px', fontFamily: 'monospace' }}>
            {(email.input_tokens || 0).toLocaleString()}
          </span>
        </Row>
        <Row label="Output tokens">
          <span style={{ color: '#94a3b8', fontSize: '13px', fontFamily: 'monospace' }}>
            {(email.output_tokens || 0).toLocaleString()}
          </span>
        </Row>
        <Row label="Total cost">
          <span style={{ color: '#4ade80', fontSize: '13px', fontFamily: 'monospace' }}>
            {formatCost(email.ai_cost_usd)}
          </span>
        </Row>
      </Section>
    </div>
  )
}

// Strip markdown formatting for clean email display
function stripMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')   // **bold** -> bold
    .replace(/\*(.+?)\*/g, '$1')        // *italic* -> italic
    .replace(/`(.+?)`/g, '$1')          // `code` -> code
    .replace(/^#{1,6}\s+/gm, '')        // # headers -> plain
    .replace(/^\s*[-*+]\s+/gm, '- ')    // list items
    .trim()
}

function ReplyPreviewTab({ email }) {
  const [fullReply, setFullReply] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editedReply, setEditedReply] = useState('')
  const [sending, setSending] = useState(false)
  const [sendStatus, setSendStatus] = useState(null) // 'success' | 'error' | null

  useEffect(() => {
    if (!email?.id) return
    setLoading(true)
    setIsEditing(false)
    setSendStatus(null)
    getEmailReply(email.id)
      .then(data => {
        const reply = data.full_reply || ''
        setFullReply(reply)
        setEditedReply(stripMarkdown(reply))
      })
      .catch(() => {
        const fallback = email.full_reply || email.reply_preview || ''
        setFullReply(fallback)
        setEditedReply(stripMarkdown(fallback))
      })
      .finally(() => setLoading(false))
  }, [email?.id])

  const displayText = stripMarkdown(fullReply ?? email.reply_preview ?? '')
  const isEmpty = !displayText || displayText.trim() === '' || displayText.trim() === 'SKIP'

  const copyToClipboard = () => {
    const textToCopy = isEditing ? editedReply : displayText
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const handleEditToggle = () => {
    if (!isEditing) {
      setEditedReply(displayText)
    }
    setIsEditing(!isEditing)
    setSendStatus(null)
  }

  const handleSendNow = async () => {
    const textToSend = isEditing ? editedReply : displayText
    if (!textToSend || !email?.from_addr) return

    const confirmed = window.confirm(
      `Send this reply to ${email.from_addr}?\n\nSubject: Re: ${email.subject}`
    )
    if (!confirmed) return

    setSending(true)
    setSendStatus(null)
    try {
      // const res = await fetch(`http://127.0.0.1:8000/api/emails/${email.id}/send`, {
      const res = await fetch(`http://52.45.229.96:8000/api/emails/${email.id}/send`, {

        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: textToSend }),
      })
      if (res.ok) {
        setSendStatus('success')
        setIsEditing(false)
      } else {
        const err = await res.json().catch(() => ({}))
        setSendStatus('error:' + (err.detail || res.statusText))
      }
    } catch (e) {
      setSendStatus('error:' + e.message)
    } finally {
      setSending(false)
    }
  }

  if (loading) {
    return (
      <div className="text-center py-8" style={{ color: '#64748b' }}>
        Loading reply...
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div
        className="rounded-lg p-6 text-center"
        style={{ backgroundColor: '#181b28', border: '1px solid #2a2d3e' }}
      >
        <span style={{ color: '#64748b', fontSize: '13px' }}>
          No reply generated for this email.
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Status banner */}
      {sendStatus === 'success' && (
        <div className="rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: '#14362e', color: '#4ade80', border: '1px solid #1a4a3a' }}>
          Reply sent successfully!
        </div>
      )}
      {sendStatus && sendStatus.startsWith('error:') && (
        <div className="rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: '#3a1a1a', color: '#f87171', border: '1px solid #5a2020' }}>
          Failed: {sendStatus.replace('error:', '')}
        </div>
      )}

      {/* Reply box — either display or editable */}
      {isEditing ? (
        <textarea
          value={editedReply}
          onChange={e => setEditedReply(e.target.value)}
          className="w-full rounded-lg p-4 text-sm leading-relaxed"
          style={{
            backgroundColor: '#181b28',
            border: '1px solid #6366f1',
            color: '#e2e8f0',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            minHeight: '200px',
            resize: 'vertical',
            outline: 'none',
          }}
        />
      ) : (
        <div
          className="rounded-lg p-4"
          style={{ backgroundColor: '#181b28', border: '1px solid #2a2d3e' }}
        >
          <pre
            className="text-sm leading-relaxed whitespace-pre-wrap"
            style={{
              color: '#e2e8f0',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
              margin: 0,
            }}
          >
            {displayText}
          </pre>
        </div>
      )}

      {/* To field hint */}
      <div className="text-xs px-1" style={{ color: '#64748b' }}>
        To: <span style={{ color: '#94a3b8' }}>{email.from_addr}</span>
        <span style={{ marginLeft: '8px' }}>
          Subject: <span style={{ color: '#94a3b8' }}>Re: {email.subject}</span>
        </span>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
          style={{
            backgroundColor: '#2a2d3e',
            color: '#e2e8f0',
            border: '1px solid #3a3d4e',
            cursor: 'pointer',
          }}
        >
          {copied ? <Check size={14} color="#4ade80" /> : <Copy size={14} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
        <button
          onClick={handleEditToggle}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
          style={{
            backgroundColor: isEditing ? '#1e3a5f' : '#2a2d3e',
            color: isEditing ? '#60a5fa' : '#e2e8f0',
            border: `1px solid ${isEditing ? '#3a6abf' : '#3a3d4e'}`,
            cursor: 'pointer',
          }}
        >
          <FileEdit size={14} />
          {isEditing ? 'Cancel Edit' : 'Edit Draft'}
        </button>
        <button
          onClick={handleSendNow}
          disabled={sending || sendStatus === 'success'}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
          style={{
            backgroundColor: sendStatus === 'success' ? '#14362e' : '#6366f1',
            color: sendStatus === 'success' ? '#4ade80' : '#ffffff',
            cursor: (sending || sendStatus === 'success') ? 'not-allowed' : 'pointer',
            opacity: sending ? 0.7 : 1,
            border: 'none',
          }}
        >
          <Send size={14} />
          {sending ? 'Sending...' : sendStatus === 'success' ? 'Sent!' : 'Send Now'}
        </button>
      </div>
    </div>
  )
}

function DetailsTab({ email }) {
  const tools = email.tools_called || []

  return (
    <div className="space-y-4">
      {/* Tools called */}
      <Section title="Tools Called" icon={Wrench}>
        {tools.length === 0 ? (
          <p style={{ color: '#64748b', fontSize: '13px' }}>No tools called</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {tools.map(tool => (
              <span
                key={tool}
                className="text-xs px-2.5 py-1 rounded-full"
                style={{ backgroundColor: '#1e1a3a', color: '#a78bfa', fontFamily: 'monospace' }}
              >
                {tool}
              </span>
            ))}
          </div>
        )}
      </Section>

      {/* Token breakdown */}
      <Section title="Token Breakdown" icon={Hash}>
        <Row label="Input tokens">
          <span style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: '13px' }}>
            {(email.input_tokens || 0).toLocaleString()}
          </span>
        </Row>
        <Row label="Output tokens">
          <span style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: '13px' }}>
            {(email.output_tokens || 0).toLocaleString()}
          </span>
        </Row>
        <Row label="Total tokens">
          <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '13px', fontWeight: '600' }}>
            {((email.input_tokens || 0) + (email.output_tokens || 0)).toLocaleString()}
          </span>
        </Row>
      </Section>

      {/* Email metadata */}
      <Section title="Email Metadata" icon={Mail}>
        <Row label="ID">
          <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '11px', wordBreak: 'break-all' }}>
            {email.id}
          </span>
        </Row>
        <Row label="Received">
          <span style={{ color: '#94a3b8', fontSize: '13px' }}>
            {formatDateTime(email.received_at)}
          </span>
        </Row>
        {email.template_used && (
          <Row label="Template">
            <span style={{ color: '#94a3b8', fontSize: '13px' }}>
              {email.template_used}
            </span>
          </Row>
        )}
      </Section>

      {/* Body preview */}
      <Section title="Email Body Preview" icon={Mail}>
        <div
          className="text-xs leading-relaxed overflow-y-auto"
          style={{ 
            color: '#94a3b8', 
            fontFamily: 'monospace', 
            whiteSpace: 'pre-wrap',
            maxHeight: '300px',
            overflowY: 'auto'
          }}
        >
          {email.full_body || email.body_preview || '—'}
        </div>
      </Section>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Small helpers
// ─────────────────────────────────────────────────────────────────────────────

function Section({ title, icon: Icon, children }) {
  return (
    <div
      className="rounded-lg p-4"
      style={{ backgroundColor: '#181b28', border: '1px solid #2a2d3e' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} style={{ color: '#64748b' }} />
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#64748b' }}>
          {title}
        </span>
      </div>
      <div className="space-y-2.5">
        {children}
      </div>
    </div>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-xs flex-shrink-0" style={{ color: '#64748b', minWidth: '90px', paddingTop: '2px' }}>
        {label}
      </span>
      <div className="flex-1 min-w-0 text-right">
        {children}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main panel
// ─────────────────────────────────────────────────────────────────────────────

const TABS = ['Overview', 'Reply Preview', 'Details']

export default function EmailDetailPanel({ email, onClose }) {
  const [activeTab, setActiveTab] = useState('Overview')

  // Reset tab when email changes
  useEffect(() => {
    setActiveTab('Overview')
  }, [email?.id])

  if (!email) return null

  return (
    <div
      className="flex flex-col h-full slide-in-right flex-shrink-0"
      style={{
        width: '380px',
        backgroundColor: '#1a1d27',
        borderLeft: '1px solid #2a2d3e',
        overflowY: 'auto',
      }}
    >
      {/* Header */}
      <div
        className="flex items-start justify-between px-4 py-4 flex-shrink-0"
        style={{ borderBottom: '1px solid #2a2d3e' }}
      >
        <div className="flex-1 min-w-0 pr-2">
          {/* From */}
          <div className="flex items-center gap-2 mb-1">
            <User size={13} style={{ color: '#64748b', flexShrink: 0 }} />
            <span
              className="text-sm font-medium truncate"
              style={{ color: '#e2e8f0' }}
            >
              {email.from_name || email.from_addr}
            </span>
          </div>
          <div
            className="text-xs mb-2"
            style={{ color: '#64748b' }}
          >
            {email.from_addr}
          </div>

          {/* Subject */}
          <div
            className="text-sm font-semibold leading-snug mb-2"
            style={{ color: '#e2e8f0' }}
          >
            {email.subject || '(no subject)'}
          </div>

          {/* Date */}
          <div className="flex items-center gap-1.5">
            <Calendar size={12} style={{ color: '#64748b' }} />
            <span style={{ color: '#64748b', fontSize: '12px' }}>
              {formatDateTime(email.received_at)}
            </span>
          </div>
        </div>

        {/* Close button */}
        <button
          onClick={onClose}
          className="flex items-center justify-center rounded-lg p-1.5 hover:bg-white/10 transition-colors flex-shrink-0"
          style={{ color: '#64748b', cursor: 'pointer', backgroundColor: 'transparent', border: 'none' }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Tabs */}
      <div
        className="flex px-4 flex-shrink-0"
        style={{ borderBottom: '1px solid #2a2d3e' }}
      >
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-3 py-3 text-sm font-medium transition-colors relative"
            style={{
              color: activeTab === tab ? '#6366f1' : '#64748b',
              backgroundColor: 'transparent',
              border: 'none',
              cursor: 'pointer',
              borderBottom: activeTab === tab ? '2px solid #6366f1' : '2px solid transparent',
              marginBottom: '-1px',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 p-4 overflow-y-auto">
        {activeTab === 'Overview' && <OverviewTab email={email} />}
        {activeTab === 'Reply Preview' && <ReplyPreviewTab email={email} />}
        {activeTab === 'Details' && <DetailsTab email={email} />}
      </div>
    </div>
  )
}
