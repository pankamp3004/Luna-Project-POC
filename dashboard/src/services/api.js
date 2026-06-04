/**
 * api.js — API client for the Luna Admin Panel.
 * All data comes from the FastAPI backend at http://localhost:8000.
 */

const BASE = 'http://127.0.0.1:8000'

/**
 * Fetch a paginated list of email log entries.
 *
 * @param {number} page - Page number (1-based)
 * @param {number} limit - Items per page
 * @param {string} status - Filter bucket: all | sent | draft | hold | escalated
 * @param {string} search - Search string
 * @returns {Promise<{emails: Array, total: number, page: number, pages: number}>}
 */
export async function getEmails(page = 1, limit = 10, status = 'all', search = '') {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
    status,
    search,
  })
  const res = await fetch(`${BASE}/api/emails?${params}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch emails: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

/**
 * Fetch a single email log entry by its UUID.
 *
 * @param {string} id - Email UUID
 * @returns {Promise<Object>}
 */
export async function getEmailById(id) {
  const res = await fetch(`${BASE}/api/emails/${encodeURIComponent(id)}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch email ${id}: ${res.status}`)
  }
  return res.json()
}

/**
 * Fetch the full reply text for an email.
 *
 * @param {string} id - Email UUID
 * @returns {Promise<{id: string, full_reply: string, reply_preview: string, status: string, decision: string}>}
 */
export async function getEmailReply(id) {
  const res = await fetch(`${BASE}/api/emails/${encodeURIComponent(id)}/reply`)
  if (!res.ok) {
    throw new Error(`Failed to fetch reply for ${id}: ${res.status}`)
  }
  return res.json()
}

/**
 * Fetch aggregate dashboard statistics.
 *
 * @returns {Promise<{total_emails: number, auto_sent: number, drafts: number, on_hold: number, escalations: number, total_cost_usd: number, llm_calls: number, template_calls: number}>}
 */
export async function getStats() {
  const res = await fetch(`${BASE}/api/stats`)
  if (!res.ok) {
    throw new Error(`Failed to fetch stats: ${res.status}`)
  }
  return res.json()
}

/**
 * Trigger the POC pipeline to process unread emails.
 *
 * @param {boolean} dryRun - If true, process but don't send
 * @param {number} maxEmails - Max emails to process
 * @returns {Promise<{success: boolean, returncode: number, stdout: string, stderr: string}>}
 */
export async function runPipeline(dryRun = false, maxEmails = 5) {
  const params = new URLSearchParams({
    dry_run: String(dryRun),
    max_emails: String(maxEmails),
  })
  const res = await fetch(`${BASE}/api/pipeline/run?${params}`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to run pipeline: ${res.status}`)
  }
  return res.json()
}
