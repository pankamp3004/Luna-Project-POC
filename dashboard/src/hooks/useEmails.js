/**
 * useEmails.js — Custom React hook for fetching and auto-refreshing email data.
 * Polls the API every 30 seconds for new data.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { getEmails, getStats } from '../services/api.js'

const REFRESH_INTERVAL_MS = 30_000 // 30 seconds

/**
 * Hook that fetches emails + stats and auto-refreshes every 30 seconds.
 *
 * @param {Object} options
 * @param {number}  options.page    - Current page (1-based)
 * @param {number}  options.limit   - Items per page
 * @param {string}  options.status  - Status filter
 * @param {string}  options.search  - Search string
 * @returns {{ emails, total, pages, stats, loading, error, refresh }}
 */
export function useEmails({ page = 1, limit = 10, status = 'all', search = '' } = {}) {
  const [emails, setEmails] = useState([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const timerRef = useRef(null)

  const fetchData = useCallback(async () => {
    try {
      setError(null)
      const [emailsRes, statsRes] = await Promise.all([
        getEmails(page, limit, status, search),
        getStats(),
      ])
      setEmails(emailsRes.emails || [])
      setTotal(emailsRes.total || 0)
      setPages(emailsRes.pages || 1)
      setStats(statsRes)
    } catch (err) {
      setError(err.message || 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [page, limit, status, search])

  // Fetch on mount and whenever params change
  useEffect(() => {
    setLoading(true)
    fetchData()
  }, [fetchData])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    timerRef.current = setInterval(() => {
      fetchData()
    }, REFRESH_INTERVAL_MS)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [fetchData])

  return {
    emails,
    total,
    pages,
    stats,
    loading,
    error,
    refresh: fetchData,
  }
}
