import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function StatusBadge({ status }) {
  return (
    <span className={`status-badge status-${status.split('_')[0]}`}>
      {status}
    </span>
  )
}

export default function History() {
  const [jobs, setJobs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/history')
      .then(r => r.json())
      .then(d => setJobs(d.jobs))
      .catch(() => setError('Failed to load history'))
  }, [])

  return (
    <main>
      <div className="page-container" style={{ paddingTop: '2.5rem', paddingBottom: '4rem' }}>
        <div className="flex items-center justify-between mb-3">
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800 }}>Run History</h1>
          <Link to="/" className="btn btn-primary">+ New Run</Link>
        </div>

        {error && <div className="error-box mb-2">{error}</div>}

        {jobs === null && !error && (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <div className="spinner" style={{ margin: '0 auto', width: 28, height: 28 }} />
          </div>
        )}

        {jobs?.length === 0 && (
          <div className="empty-state card">
            <p style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✦</p>
            <p style={{ color: 'var(--text-muted)' }}>No runs yet.</p>
            <Link to="/" className="btn btn-primary" style={{ marginTop: '1rem', display: 'inline-flex' }}>
              Create your first run
            </Link>
          </div>
        )}

        {jobs?.length > 0 && (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="history-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Company</th>
                  <th>Platforms</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.id}>
                    <td style={{ color: 'var(--text-muted)', fontWeight: 600 }}>#{job.id}</td>
                    <td style={{ fontWeight: 500 }}>{job.company_name}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {Array.isArray(job.platforms)
                        ? job.platforms.join(', ')
                        : job.platforms}
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      {job.created_at ? job.created_at.slice(0, 10) : '—'}
                    </td>
                    <td>
                      <Link
                        to={`/run/${job.id}`}
                        className="btn btn-ghost"
                        style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }}
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  )
}
