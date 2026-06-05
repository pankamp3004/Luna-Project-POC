import React, { useState, useCallback } from 'react'
import {
  Mail,
  CheckCircle,
  FileEdit,
  Clock,
  AlertTriangle,
  DollarSign,
  Search,
  RefreshCw,
  Play,
  XCircle,
} from 'lucide-react'
import StatsCard from '../components/StatsCard.jsx'
import EmailTable from '../components/EmailTable.jsx'
import EmailDetailPanel from '../components/EmailDetailPanel.jsx'
import { useEmails } from '../hooks/useEmails.js'
import { runPipeline } from '../services/api.js'

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatCostDisplay(cost) {
  if (!cost || cost === 0) return '$0.00'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

const STATUS_OPTIONS = [
  { value: 'all',       label: 'All Status' },
  { value: 'sent',      label: 'Sent' },
  { value: 'draft',     label: 'Drafts' },
  { value: 'hold',      label: 'On Hold' },
  { value: 'escalated', label: 'Escalated' },
  { value: 'skipped',   label: 'Skipped' },
]

const INTENT_OPTIONS = [
  { value: 'all',             label: 'All Intents' },
  { value: 'new_lead',        label: 'New Lead' },
  { value: 'inquiry_reply',   label: 'Inquiry Reply' },
  { value: 'tour_confirm',    label: 'Tour Confirm' },
  { value: 'tour_reschedule', label: 'Tour Reschedule' },
  { value: 'post_tour',       label: 'Post Tour' },
  { value: 'objection',       label: 'Objection' },
  { value: 'far_future',      label: 'Far Future' },
  { value: 're_engagement',   label: 'Re-Engagement' },
  { value: 'student_housing', label: 'Student Housing' },
  { value: 'logistical_other','label': 'Logistical' },
]

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard page
// ─────────────────────────────────────────────────────────────────────────────

export default function Dashboard({ filter: initialFilter = 'all', title = 'Dashboard' }) {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState(initialFilter)
  const [intentFilter, setIntentFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [pipelineMsg, setPipelineMsg] = useState('')

  // Build the combined search/filter string
  // For intent filter, we pass it as part of the search (backend searches scenario field)
  const effectiveSearch = [
    search,
    intentFilter !== 'all' ? intentFilter : '',
  ].filter(Boolean).join(' ')

  const { emails, total, pages, stats, loading, error, refresh } = useEmails({
    page,
    limit: 10,
    status: statusFilter,
    search: effectiveSearch,
  })

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const handleSelectEmail = useCallback((email) => {
    setSelectedEmail(prev => prev?.id === email.id ? null : email)
  }, [])

  const handleClosePanel = useCallback(() => {
    setSelectedEmail(null)
  }, [])

  const handleRunPipeline = async () => {
    setPipelineRunning(true)
    setPipelineMsg('Running pipeline...')
    try {
      const result = await runPipeline(false, 1)
      if (result.success) {
        setPipelineMsg('Pipeline completed successfully. Refreshing...')
        // Small delay to ensure log file is fully written before reading
        await new Promise(resolve => setTimeout(resolve, 500))
        await refresh()
        setPage(1)
        setPipelineMsg('Pipeline completed. Table updated.')
      } else {
        setPipelineMsg(`Pipeline failed (code ${result.returncode}). Check terminal for details.`)
      }
    } catch (err) {
      setPipelineMsg(`Error: ${err.message}`)
    } finally {
      setPipelineRunning(false)
      setTimeout(() => setPipelineMsg(''), 6000)
    }
  }

  return (
    <div className="flex h-full">
      {/* Main panel */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <div
          className="flex items-center justify-between px-6 py-4 flex-shrink-0"
          style={{ borderBottom: '1px solid #2a2d3e' }}
        >
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#e2e8f0' }}>
              {title}
            </h1>
            <p style={{ color: '#64748b', fontSize: '13px', marginTop: '2px' }}>
              Luna leasing email automation — real-time overview
            </p>
          </div>
          <div className="flex items-center gap-3">
            {pipelineMsg && (
              <span style={{ color: '#64748b', fontSize: '12px' }}>{pipelineMsg}</span>
            )}
            <button
              onClick={refresh}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors"
              style={{
                backgroundColor: '#1e2130',
                color: '#94a3b8',
                border: '1px solid #2a2d3e',
                cursor: 'pointer',
              }}
              title="Refresh data"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              onClick={handleRunPipeline}
              disabled={pipelineRunning}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
              style={{
                backgroundColor: '#6366f1',
                color: '#ffffff',
                cursor: pipelineRunning ? 'not-allowed' : 'pointer',
                border: 'none',
              }}
            >
              <Play size={14} fill={pipelineRunning ? 'none' : 'currentColor'} />
              {pipelineRunning ? 'Running...' : 'Run Pipeline'}
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* Error banner */}
          {error && (
            <div
              className="rounded-lg px-4 py-3 text-sm"
              style={{ backgroundColor: '#3a1a1a', color: '#f87171', border: '1px solid #5a2020' }}
            >
              ⚠️ {error} — Make sure the API server is running on port 8000.
            </div>
          )}

          {/* Stats row */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-7">
            <StatsCard
              icon={Mail}
              title="Total Emails"
              value={stats?.total_emails ?? '—'}
              color="#6366f1"
            />
            <StatsCard
              icon={CheckCircle}
              title="Auto-Sent"
              value={stats?.auto_sent ?? '—'}
              color="#22c55e"
            />
            <StatsCard
              icon={FileEdit}
              title="Drafts"
              value={stats?.drafts ?? '—'}
              color="#eab308"
            />
            <StatsCard
              icon={Clock}
              title="On Hold"
              value={stats?.on_hold ?? '—'}
              color="#f97316"
            />
            <StatsCard
              icon={AlertTriangle}
              title="Escalations"
              value={stats?.escalations ?? '—'}
              color="#ef4444"
            />
            <StatsCard
              icon={XCircle}
              title="Skipped"
              value={stats?.skipped ?? '—'}
              color="#64748b"
            />
            <StatsCard
              icon={DollarSign}
              title="AI Cost Total"
              value={stats ? formatCostDisplay(stats.total_cost_usd) : '—'}
              color="#a855f7"
            />
          </div>

          {/* Search + Filters row */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 min-w-[200px]">
              <div className="relative flex-1">
                <Search
                  size={16}
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: '#64748b',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  type="text"
                  value={searchInput}
                  onChange={e => setSearchInput(e.target.value)}
                  placeholder="Search by from, subject, intent..."
                  className="w-full pl-9 pr-4 py-2 rounded-lg text-sm outline-none"
                  style={{
                    backgroundColor: '#1e2130',
                    border: '1px solid #2a2d3e',
                    color: '#e2e8f0',
                  }}
                  onBlur={() => {
                    if (!searchInput) { setSearch(''); setPage(1) }
                  }}
                />
              </div>
              <button
                type="submit"
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{
                  backgroundColor: '#6366f1',
                  color: '#fff',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Search
              </button>
              {search && (
                <button
                  type="button"
                  onClick={() => { setSearch(''); setSearchInput(''); setPage(1) }}
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{
                    backgroundColor: '#2a2d3e',
                    color: '#94a3b8',
                    border: '1px solid #3a3d4e',
                    cursor: 'pointer',
                  }}
                >
                  Clear
                </button>
              )}
            </form>

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              className="px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                backgroundColor: '#1e2130',
                border: '1px solid #2a2d3e',
                color: '#e2e8f0',
                cursor: 'pointer',
              }}
            >
              {STATUS_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>

            {/* Intent filter */}
            <select
              value={intentFilter}
              onChange={e => { setIntentFilter(e.target.value); setPage(1) }}
              className="px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                backgroundColor: '#1e2130',
                border: '1px solid #2a2d3e',
                color: '#e2e8f0',
                cursor: 'pointer',
              }}
            >
              {INTENT_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Email table */}
          <EmailTable
            emails={emails}
            total={total}
            page={page}
            pages={pages}
            onPageChange={setPage}
            selectedId={selectedEmail?.id}
            onSelectEmail={handleSelectEmail}
            loading={loading}
          />

          {/* LLM / Template call split */}
          {stats && (stats.llm_calls > 0 || stats.template_calls > 0) && (
            <div
              className="rounded-lg p-4"
              style={{ backgroundColor: '#1e2130', border: '1px solid #2a2d3e' }}
            >
              <div className="text-sm font-semibold mb-3" style={{ color: '#e2e8f0' }}>
                Classification Method Breakdown
              </div>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span style={{ color: '#a78bfa', fontSize: '12px' }}>LLM + Tools</span>
                    <span style={{ color: '#a78bfa', fontSize: '12px', fontWeight: '600' }}>
                      {stats.llm_calls}
                    </span>
                  </div>
                  <div
                    className="rounded-full overflow-hidden"
                    style={{ height: '6px', backgroundColor: '#2a2d3e' }}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${total > 0 ? (stats.llm_calls / total) * 100 : 0}%`,
                        backgroundColor: '#6366f1',
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span style={{ color: '#94a3b8', fontSize: '12px' }}>Policy Match</span>
                    <span style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600' }}>
                      {stats.template_calls}
                    </span>
                  </div>
                  <div
                    className="rounded-full overflow-hidden"
                    style={{ height: '6px', backgroundColor: '#2a2d3e' }}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${total > 0 ? (stats.template_calls / total) * 100 : 0}%`,
                        backgroundColor: '#475569',
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detail panel — slides in when an email is selected */}
      {selectedEmail && (
        <EmailDetailPanel
          email={selectedEmail}
          onClose={handleClosePanel}
        />
      )}
    </div>
  )
}
