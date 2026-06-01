import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const PLATFORMS = [
  { id: 'linkedin',  label: 'LinkedIn',    abbr: 'in',  cls: 'icon-linkedin' },
  { id: 'twitter',   label: 'Twitter / X', abbr: 'X',   cls: 'icon-twitter' },
  { id: 'instagram', label: 'Instagram',   abbr: 'ig',  cls: 'icon-instagram' },
]

export default function NewRun() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    company_name: '',
    company_url: '',
    description: '',
    target_audience: '',
  })
  const [selectedPlatforms, setSelectedPlatforms] = useState(['linkedin'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const togglePlatform = (id) => {
    setSelectedPlatforms(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (selectedPlatforms.length === 0) {
      setError('Please select at least one platform.')
      return
    }
    setError('')
    setLoading(true)

    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => fd.append(k, v))
    selectedPlatforms.forEach(p => fd.append('platforms', p))

    try {
      const res = await fetch('/api/run', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to start run')
      navigate(`/run/${data.job_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <main>
      <div className="page-container">
        {/* Hero */}
        <div className="hero">
          <div className="hero-eyebrow">
            <span>✦</span> AI-Powered Marketing
          </div>
          <h1>Generate posts that<br />actually sound human</h1>
          <p>
            Enter your company details. The agent scrapes your site, plans a strategy,
            drafts posts, and iterates until they pass a strict quality bar.
          </p>
        </div>

        {/* Form card */}
        <div className="card" style={{ maxWidth: 680, margin: '0 auto 4rem' }}>
          <form onSubmit={handleSubmit}>
            <div className="flex-col gap-3">
              {/* Row 1 */}
              <div className="form-grid">
                <div className="form-group">
                  <label htmlFor="company_name">Company Name</label>
                  <input
                    id="company_name"
                    type="text"
                    placeholder="Acme Corp"
                    required
                    value={form.company_name}
                    onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="company_url">Website URL</label>
                  <input
                    id="company_url"
                    type="url"
                    placeholder="https://example.com"
                    required
                    value={form.company_url}
                    onChange={e => setForm(f => ({ ...f, company_url: e.target.value }))}
                  />
                </div>
              </div>

              {/* Description */}
              <div className="form-group">
                <label htmlFor="description">Company Description</label>
                <textarea
                  id="description"
                  placeholder="What does the company do? What problem do they solve?"
                  required
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                />
              </div>

              {/* Target audience */}
              <div className="form-group">
                <label htmlFor="target_audience">Target Audience</label>
                <input
                  id="target_audience"
                  type="text"
                  placeholder="e.g. B2B SaaS founders, developers, marketers"
                  required
                  value={form.target_audience}
                  onChange={e => setForm(f => ({ ...f, target_audience: e.target.value }))}
                />
              </div>

              {/* Platform selector */}
              <div className="form-group">
                <label>Platforms</label>
                <div className="platform-chips">
                  {PLATFORMS.map(p => (
                    <button
                      key={p.id}
                      type="button"
                      className={`platform-chip${selectedPlatforms.includes(p.id) ? ' active' : ''}`}
                      onClick={() => togglePlatform(p.id)}
                    >
                      <span
                        className={`post-platform-icon ${p.cls}`}
                        style={{ width: 20, height: 20, fontSize: '0.6rem', borderRadius: 5 }}
                      >
                        {p.abbr}
                      </span>
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {error && <div className="error-box">{error}</div>}

              <button
                type="submit"
                className="btn btn-primary w-full"
                disabled={loading}
                style={{ justifyContent: 'center', marginTop: '0.5rem' }}
              >
                {loading ? (
                  <>
                    <span className="spinner" />
                    Starting…
                  </>
                ) : (
                  <>✦ Generate Posts</>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
  )
}
