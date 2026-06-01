import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const STEPS = [
  { key: 'queued',      label: 'Queued' },
  { key: 'scraping',    label: 'Scraping' },
  { key: 'planning',    label: 'Planning' },
  { key: 'generating',  label: 'Generating' },
  { key: 'evaluating',  label: 'Evaluating' },
  { key: 'completed',   label: 'Done' },
]

const THRESHOLDS = {
  brand_voice_alignment: 7,
  platform_fit: 7,
  engagement_potential: 7,
  human_like_quality: 7,
  value_clarity: 7,
  cta_effectiveness: 7,
  format_compliance: 7,
}

const PLATFORM_META = {
  linkedin:  { abbr: 'in', cls: 'icon-linkedin',  label: 'LinkedIn' },
  twitter:   { abbr: 'X',  cls: 'icon-twitter',   label: 'Twitter / X' },
  instagram: { abbr: 'ig', cls: 'icon-instagram',  label: 'Instagram' },
}

function stepIndex(status) {
  if (!status) return 0
  if (status === 'completed') return 5
  if (status === 'failed')    return -1
  if (status.startsWith('evaluating')) return 4
  if (status.startsWith('generating')) return 3
  if (status === 'planning')   return 2
  if (status === 'scraping')   return 1
  return 0
}

function StatusBadge({ status }) {
  const base = status.split('_')[0]
  return (
    <span className={`status-badge status-${base}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function ProgressSteps({ status }) {
  const current = stepIndex(status)
  return (
    <div className="progress-steps">
      {STEPS.map((s, i) => {
        const isDone   = i < current
        const isActive = i === current
        return (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center' }}>
            <div className={`step${isDone ? ' done' : ''}${isActive ? ' active' : ''}`}>
              <div className="step-dot" />
              {s.label}
            </div>
            {i < STEPS.length - 1 && (
              <div className={`step-line${isDone ? ' done' : ''}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function CriteriaBar({ scores }) {
  return (
    <div className="criteria-grid" style={{ margin: '0.75rem 0' }}>
      {Object.entries(scores).map(([key, score]) => {
        const threshold = THRESHOLDS[key] || 6
        const pass = score >= threshold
        const pct = (score / 10) * 100
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        const displayScore = typeof score === 'number' ? score.toFixed(1).replace(/\.0$/, '') : score
        return (
          <div key={key} className="criterion-row">
            <div className="criterion-label">
              <span>{label}</span>
              <span className={pass ? 'score-pass' : 'score-fail'}>
                {displayScore}/10
              </span>
            </div>
            <div className="criterion-bar">
              <div
                className={`criterion-fill ${pass ? 'fill-pass' : 'fill-fail'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className={`copy-btn${copied ? ' copied' : ''}`} onClick={copy}>
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

function PostCard({ post, isJobRunning }) {
  const meta = PLATFORM_META[post.platform] || { abbr: '?', cls: '', label: post.platform }
  const passed = post.passed_eval

  const score = post.final_score || 0
  let ratingLabel = 'Needs Polish'
  let ratingClass = 'status-failed'
  if (score >= 8.5) {
    ratingLabel = 'Excellent'
    ratingClass = 'status-completed'
  } else if (score >= 7.5) {
    ratingLabel = 'Good'
    ratingClass = 'status-completed'
  }

  if (isJobRunning && !passed) {
    ratingLabel = 'Optimizing...'
    ratingClass = 'status-failed pulse-animation'
  }

  const hashtagStr = post.hashtags 
    ? post.hashtags.split(',').map(h => h.trim()).filter(Boolean).map(h => `#${h}`).join(' ')
    : ''
  const fullTextToCopy = post.content + (hashtagStr ? '\n\n' + hashtagStr : '')

  return (
    <div className="card post-card" style={{ marginBottom: '1.5rem', background: 'var(--bg-elevated)' }}>
      <div className="post-header">
        <div className="post-platform">
          <span className={`post-platform-icon ${meta.cls}`}>{meta.abbr}</span>
          {meta.label}
        </div>
        <div className="flex items-center gap-1">
          <span className={`score-value ${passed ? 'score-pass' : 'score-fail'}`}>
            {score.toFixed(1)}/10
          </span>
          <span className={`status-badge ${ratingClass}`}>
            {ratingLabel}
          </span>
          <span className="text-muted text-sm">
            {post.iterations} iter{post.iterations !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <div className="post-content-box" style={{ position: 'relative', background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
        <CopyButton text={fullTextToCopy} />
        <div style={{ whiteSpace: 'pre-wrap', paddingRight: '4.5rem', fontFamily: 'inherit' }}>
          {post.content}
          {hashtagStr && `\n\n${hashtagStr}`}
        </div>
      </div>

      {post.eval_history && post.eval_history.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '0.5rem', letterSpacing: '0.05em' }}>QA Auditor Scores</h4>
          <CriteriaBar scores={post.eval_history[post.eval_history.length - 1]?.scores || {}} />
        </div>
      )}
    </div>
  )
}

function TypingIndicator({ agentName, avatar, avatarStyle }) {
  return (
    <div className="agent-bubble typing-bubble" style={{
      display: 'flex',
      gap: '1rem',
      padding: '1.25rem',
      borderRadius: 'var(--radius-lg)',
      background: 'rgba(255, 255, 255, 0.02)',
      border: '1px dashed var(--border)',
      marginBottom: '1rem',
    }}>
      <div className="agent-avatar-wrap" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="agent-avatar" style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifycontent: 'center',
          fontSize: '1.2rem',
          ...avatarStyle
        }}>
          {avatar}
        </div>
      </div>
      <div className="agent-msg-content" style={{ flex: 1 }}>
        <div className="agent-meta" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
          <span className="agent-name" style={{ fontWeight: 700, fontSize: '0.9rem' }}>{agentName}</span>
          <span className="agent-tag" style={{
            fontSize: '0.65rem',
            padding: '0.1rem 0.4rem',
            borderRadius: '4px',
            background: 'var(--border)',
            color: 'var(--text-secondary)',
            fontWeight: 700
          }}>THINKING</span>
        </div>
        <div className="typing-stream" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', height: '20px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginRight: '0.25rem' }}>Analyzing parameters...</span>
          <div className="typing-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-light)', animation: 'pulse-dot 1s infinite' }} />
          <div className="typing-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-light)', animation: 'pulse-dot 1s infinite 0.2s' }} />
          <div className="typing-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-light)', animation: 'pulse-dot 1s infinite 0.4s' }} />
        </div>
      </div>
    </div>
  )
}

function ChatMessage({ msg }) {
  if (msg.type === 'separator') {
    return (
      <div className="chat-divider" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        margin: '2rem 0 1.5rem',
        position: 'relative'
      }}>
        <div style={{ position: 'absolute', left: 0, right: 0, height: '1px', background: 'var(--border)', zIndex: 1 }} />
        <span style={{
          position: 'relative',
          zIndex: 2,
          background: 'var(--bg-base)',
          padding: '0.25rem 1rem',
          fontSize: '0.75rem',
          fontWeight: 800,
          color: 'var(--accent-light)',
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          border: '1px solid var(--border)',
          borderRadius: '999px',
          boxShadow: 'var(--shadow-card)'
        }}>
          {msg.text}
        </span>
      </div>
    )
  }

  const isPlanner = msg.agent === 'planner'
  const isGenerator = msg.agent === 'generator'
  const isEvaluator = msg.agent === 'evaluator'
  const isSystem = msg.agent === 'system'

  let avatar = '🧠'
  let agentName = 'Planner Agent'
  let agentTag = 'STRATEGIST'
  let bubbleStyle = {
    background: 'rgba(124, 58, 237, 0.04)',
    border: '1px solid rgba(124, 58, 237, 0.15)',
  }
  let avatarStyle = {
    background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
    boxShadow: '0 0 12px rgba(124, 58, 237, 0.3)',
  }

  if (isGenerator) {
    avatar = '✍️'
    agentName = 'Generator Agent'
    agentTag = 'COPYWRITER'
    bubbleStyle = {
      background: 'rgba(245, 158, 11, 0.04)',
      border: '1px solid rgba(245, 158, 11, 0.15)',
    }
    avatarStyle = {
      background: 'linear-gradient(135deg, #d97706, #f59e0b)',
      boxShadow: '0 0 12px rgba(245, 158, 11, 0.3)',
    }
  } else if (isEvaluator) {
    avatar = '⚖️'
    agentName = 'Evaluator Agent'
    agentTag = 'QA AUDITOR'
    
    const passed = msg.passed
    bubbleStyle = {
      background: passed ? 'rgba(16, 185, 129, 0.04)' : 'rgba(239, 68, 68, 0.04)',
      border: passed ? '1px solid rgba(16, 185, 129, 0.18)' : '1px solid rgba(239, 68, 68, 0.18)',
    }
    avatarStyle = {
      background: passed 
        ? 'linear-gradient(135deg, #059669, #10b981)' 
        : 'linear-gradient(135deg, #dc2626, #ef4444)',
      boxShadow: passed 
        ? '0 0 12px rgba(16, 185, 129, 0.3)' 
        : '0 0 12px rgba(239, 68, 68, 0.3)',
    }
  } else if (isSystem) {
    avatar = '⚠️'
    agentName = 'System Dispatcher'
    agentTag = 'ERR'
    bubbleStyle = {
      background: 'rgba(239, 68, 68, 0.06)',
      border: '1px solid rgba(239, 68, 68, 0.3)',
    }
    avatarStyle = {
      background: '#ef4444',
      boxShadow: '0 0 12px rgba(239, 68, 68, 0.4)',
    }
  }

  return (
    <div className="agent-bubble" style={{
      display: 'flex',
      gap: '1rem',
      padding: '1.25rem',
      borderRadius: 'var(--radius-lg)',
      marginBottom: '1rem',
      position: 'relative',
      ...bubbleStyle
    }}>
      <div className="agent-avatar-wrap" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="agent-avatar" style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifycontent: 'center',
          fontSize: '1.2rem',
          color: '#fff',
          ...avatarStyle
        }}>
          {avatar}
        </div>
      </div>
      <div className="agent-msg-content" style={{ flex: 1, minWidth: 0 }}>
        <div className="agent-meta" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <span className="agent-name" style={{ fontWeight: 800, fontSize: '0.9rem' }}>{agentName}</span>
          <span className="agent-tag" style={{
            fontSize: '0.65rem',
            padding: '0.1rem 0.4rem',
            borderRadius: '4px',
            background: isEvaluator ? (msg.passed ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)') : 'rgba(255,255,255,0.06)',
            color: isEvaluator ? (msg.passed ? 'var(--green)' : 'var(--red)') : 'var(--text-secondary)',
            fontWeight: 800
          }}>{agentTag}</span>
          {msg.platform && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              · {PLATFORM_META[msg.platform]?.label || msg.platform}
            </span>
          )}
          {msg.attempt && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              · Attempt #{msg.attempt}
            </span>
          )}
        </div>

        <div className="agent-body" style={{ fontSize: '0.925rem', lineHeight: 1.6, color: 'var(--text-primary)' }}>
          <p style={{ whiteSpace: 'pre-wrap', marginBottom: msg.strategy || msg.content || msg.scores ? '0.75rem' : 0 }}>
            {msg.text}
          </p>

          {/* Strategy Brief inline */}
          {msg.strategy && (
            <div style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              marginTop: '0.75rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              <div>
                <h5 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--accent-light)', letterSpacing: '0.05em', marginBottom: '0.15rem' }}>Campaign Goal</h5>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{msg.strategy.campaign_goal}</p>
              </div>
              {msg.strategy.key_messages && msg.strategy.key_messages.length > 0 && (
                <div>
                  <h5 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--accent-light)', letterSpacing: '0.05em', marginBottom: '0.2rem' }}>Key Messages</h5>
                  <ul style={{ paddingLeft: '1.1rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {msg.strategy.key_messages.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                </div>
              )}
              {msg.strategy.tone_guidelines && (
                <div>
                  <h5 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--accent-light)', letterSpacing: '0.05em', marginBottom: '0.15rem' }}>Tone Voice Guidelines</h5>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{msg.strategy.tone_guidelines}</p>
                </div>
              )}
            </div>
          )}

          {/* Generated post content inline */}
          {msg.content && (
            <div style={{
              background: 'var(--bg-base)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              whiteSpace: 'pre-wrap',
              color: 'var(--text-primary)',
              marginTop: '0.5rem',
              borderLeft: '3px solid var(--yellow)',
              position: 'relative'
            }}>
              {msg.content}
              {msg.hashtags && `\n\n${msg.hashtags.split(',').map(h => `#${h.trim()}`).join(' ')}`}
            </div>
          )}

          {/* Evaluator metrics breakdown inline */}
          {msg.scores && (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--text-secondary)' }}>Audit Scoreboard:</span>
                <span className={`score-value ${msg.passed ? 'score-pass' : 'score-fail'}`} style={{ fontSize: '1.05rem', fontWeight: 800 }}>
                  {msg.score?.toFixed(1)}/10
                </span>
                <span className={`status-badge ${msg.passed ? 'status-completed' : 'status-failed'}`} style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}>
                  {msg.passed ? 'PASSED AUDIT' : 'FAILED AUDIT'}
                </span>
              </div>
              
              <CriteriaBar scores={msg.scores} />

              {/* Feedback text */}
              {msg.feedback && Object.keys(msg.feedback).length > 0 && (
                <div style={{
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.75rem',
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)'
                }}>
                  <h6 style={{ fontSize: '0.75rem', color: 'var(--text-primary)', fontWeight: 700, marginBottom: '0.25rem' }}>Auditor Critiques:</h6>
                  <ul style={{ paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                    {Object.entries(msg.feedback).map(([criterion, text]) => (
                      <li key={criterion}>
                        <strong>{criterion.replace(/_/g, ' ')}:</strong> {text}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Results() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('discussion')
  const pollRef = useRef(null)
  const rerunnning = useRef(false)
  const chatBottomRef = useRef(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`/api/run/${jobId}/status`)
      if (!res.ok) { setError('Job not found'); return }
      const json = await res.json()
      setData(json)
      return json.status
    } catch {
      setError('Network error')
    }
  }, [jobId])

  useEffect(() => {
    fetchStatus().then(status => {
      if (status !== 'completed' && status !== 'failed') {
        pollRef.current = setInterval(async () => {
          const s = await fetchStatus()
          if (s === 'completed' || s === 'failed') {
            clearInterval(pollRef.current)
          }
        }, 2000)
      }
    })
    return () => clearInterval(pollRef.current)
  }, [fetchStatus])

  // Scroll to bottom of chat logs automatically
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [data, activeTab])

  const handleReiterate = async () => {
    if (rerunnning.current) return
    rerunnning.current = true
    const res = await fetch(`/api/run/${jobId}/reiterate`, { method: 'POST' })
    const json = await res.json()
    rerunnning.current = false
    if (json.job_id) navigate(`/run/${json.job_id}`)
  }

  if (error) {
    return (
      <div className="page-container" style={{ paddingTop: '3rem' }}>
        <div className="error-box">{error}</div>
        <div className="mt-2">
          <Link to="/" className="btn btn-secondary">← New Run</Link>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="page-container" style={{ paddingTop: '3rem', textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '2rem auto', width: 28, height: 28 }} />
        <p className="text-muted">Loading Collaboration Canvas…</p>
      </div>
    )
  }

  const isRunning = data.status !== 'completed' && data.status !== 'failed'

  // Build the chronological conversation sequence
  const chatMessages = []

  // 1. Scraping Info
  if (data.status === 'scraping' || data.status === 'queued') {
    chatMessages.push({
      agent: 'planner',
      text: `Crawling site target parameters to build campaign blueprint...`,
      isThinking: data.status === 'scraping'
    })
  }

  // 2. Planning Info
  if (data.status === 'planning') {
    chatMessages.push({
      agent: 'planner',
      text: `Scrape success! Analyzing brand assets, taglines, and messaging framework. Developing campaign strategy and brief...`,
      isThinking: true
    })
  }

  // 3. Strategy briefing finalized
  if (data.strategy) {
    chatMessages.push({
      agent: 'planner',
      text: `Blueprint finalized! I have locked in the key brand messaging and campaign guidelines. Generator (Copywriter) and Evaluator (QA Auditor), align your work with this briefing:`,
      strategy: data.strategy
    })
  }

  // 4. Platforms threads
  if (data.posts && data.posts.length > 0) {
    data.posts.forEach(post => {
      const label = PLATFORM_META[post.platform]?.label || post.platform
      
      chatMessages.push({
        type: 'separator',
        text: `${label} Campaign Thread`
      })

      const history = post.eval_history || []
      
      history.forEach(entry => {
        // Generator Draft Message
        chatMessages.push({
          agent: 'generator',
          platform: post.platform,
          attempt: entry.attempt,
          content: entry.content,
          hashtags: entry.hashtags,
          text: entry.attempt === 1 
            ? `Drafting first creative copy option targeting our specified audience for ${label}:`
            : `Draft revision Attempt #${entry.attempt} completed. I have structured this draft to address the QA critiques by optimizing key sentences and integrating brand tags:`
        })

        // Evaluator Review Message
        chatMessages.push({
          agent: 'evaluator',
          platform: post.platform,
          attempt: entry.attempt,
          passed: entry.passed,
          score: entry.overall_score,
          scores: entry.scores,
          feedback: entry.feedback,
          text: entry.passed 
            ? `Audit Checklist completed! Copy passed all criteria checks with a final overall score of ${entry.overall_score?.toFixed(1)}/10. Ready for export!`
            : `Audit Checklist failed. The draft scored ${entry.overall_score?.toFixed(1)}/10 which is below the target quality threshold. Returning to Copywriter for guided corrections.`
        })
      })

      // If running & active on this platform
      if (isRunning) {
        if (data.status === `generating_${post.platform}`) {
          // Generator is typing
          chatMessages.push({
            agent: 'generator',
            platform: post.platform,
            attempt: history.length + 1,
            text: `Writing a creative draft for ${label} (Attempt #${history.length + 1}) based on the blueprint guidelines...`,
            isThinking: true
          })
        } else if (data.status.startsWith(`evaluating_${post.platform}`)) {
          const match = data.status.match(/attempt_(\d+)/)
          const currentAttempt = match ? parseInt(match[1]) : (history.length + 1)

          // Generator submitted
          chatMessages.push({
            agent: 'generator',
            platform: post.platform,
            attempt: currentAttempt,
            content: post.content,
            hashtags: post.hashtags,
            text: `Revised draft successfully completed! Submitting Attempt #${currentAttempt} copy to the QA Auditor:`
          })

          // Evaluator is typing
          chatMessages.push({
            agent: 'evaluator',
            platform: post.platform,
            attempt: currentAttempt,
            text: `Clinical QA Audit in progress for ${label} (Attempt #${currentAttempt}). Grading hook engagement, brand style, call-to-actions, and checking for passive AI patterns...`,
            isThinking: true
          })
        }
      }
    })
  } else if (isRunning && data.status.startsWith('generating')) {
    const activePlatform = data.status.split('_')[1]
    if (activePlatform) {
      const label = PLATFORM_META[activePlatform]?.label || activePlatform
      chatMessages.push({
        type: 'separator',
        text: `${label} Campaign Thread`
      })
      chatMessages.push({
        agent: 'generator',
        platform: activePlatform,
        attempt: 1,
        text: `Writing a creative draft for ${label} (Attempt #1) based on the blueprint guidelines...`,
        isThinking: true
      })
    }
  }

  // System failed state
  if (data.status === 'failed') {
    chatMessages.push({
      agent: 'system',
      text: `Critical Pipeline Error: ${data.error || 'All fallback options exhausted during generation.'}`
    })
  }

  // Identify which agent is currently "thinking" in the UI
  let activeThinkingAgent = null
  let activeThinkingPlatform = null
  if (isRunning) {
    if (data.status === 'scraping' || data.status === 'planning') {
      activeThinkingAgent = 'planner'
    } else {
      const activePlatform = data.platforms?.find(p => data.status.includes(p))
      if (activePlatform) {
        activeThinkingPlatform = activePlatform
        if (data.status.startsWith('generating')) {
          activeThinkingAgent = 'generator'
        } else if (data.status.startsWith('evaluating')) {
          activeThinkingAgent = 'evaluator'
        }
      }
    }
  }

  return (
    <main>
      <div className="page-container" style={{ paddingTop: '2.5rem', paddingBottom: '4rem' }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0 }}>
                Run #{jobId}
              </h1>
              {isRunning && <span className="spinner" style={{ color: 'var(--accent-light)' }} />}
            </div>
            <p className="text-muted" style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>
              {data.company_name}
              {data.platforms?.length > 0 && (
                <> · {data.platforms.join(', ')}</>
              )}
            </p>
          </div>
          <div className="flex gap-1">
            <Link to="/" className="btn btn-secondary">New Run</Link>
            <button className="btn btn-ghost" onClick={handleReiterate} disabled={isRunning || rerunnning.current}>
              ↺ Re-iterate
            </button>
          </div>
        </div>

        {/* Status Card */}
        <div className="card mb-3" style={{ padding: '1.25rem 1.75rem' }}>
          <div className="flex items-center gap-2 mb-2">
            <StatusBadge status={data.status} />
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {isRunning ? 'Collaborative Multi-Agent Session in Progress...' : 'Collaboration Finished'}
            </span>
          </div>
          <ProgressSteps status={data.status} />
          {data.error && <div className="error-box mt-2">{data.error}</div>}
        </div>

        {/* Dynamic Interactive Tabs */}
        <div className="tab-control-bar" style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          marginBottom: '1.5rem',
          gap: '1rem'
        }}>
          <button
            className={`tab-btn ${activeTab === 'discussion' ? 'active' : ''}`}
            onClick={() => setActiveTab('discussion')}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'discussion' ? '2px solid var(--accent-light)' : '2px solid transparent',
              color: activeTab === 'discussion' ? 'var(--text-primary)' : 'var(--text-secondary)',
              padding: '0.75rem 0.5rem',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              transition: 'all 0.15s'
            }}
          >
            💬 Agent Discussion Console
            {isRunning && <span className="status-badge status-generating pulse-animation" style={{ padding: '0.05rem 0.35rem', fontSize: '0.62rem' }}>LIVE</span>}
          </button>
          <button
            className={`tab-btn ${activeTab === 'deliverables' ? 'active' : ''}`}
            onClick={() => setActiveTab('deliverables')}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'deliverables' ? '2px solid var(--accent-light)' : '2px solid transparent',
              color: activeTab === 'deliverables' ? 'var(--text-primary)' : 'var(--text-secondary)',
              padding: '0.75rem 0.5rem',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              transition: 'all 0.15s'
            }}
          >
            📱 Approved Deliverables
            {!isRunning && data.posts?.length > 0 && (
              <span style={{
                background: 'var(--green-dim)',
                color: 'var(--green)',
                borderRadius: '50%',
                width: '18px',
                height: '18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.65rem',
                fontWeight: 800
              }}>
                {data.posts.filter(p => p.passed_eval).length}
              </span>
            )}
          </button>
        </div>

        {/* Tab 1: Agent Discussion Console */}
        {activeTab === 'discussion' && (
          <div className="agent-discussion-stream" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="chat-intro-note" style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
              marginBottom: '1.5rem',
              borderLeft: '3px solid var(--accent)'
            }}>
              💡 <strong>How it works:</strong> Below is a transcription of how the specialized agents collaborate in real-time. The <strong>Planner</strong> maps the branding, the <strong>Generator</strong> drafts the text, and the <strong>Evaluator</strong> performs audits to reject mediocre copy and force optimization loops.
            </div>

            {chatMessages.map((msg, i) => (
              <ChatMessage key={i} msg={msg} />
            ))}

            {/* Thinking / Typing Indicators */}
            {isRunning && activeThinkingAgent === 'planner' && (
              <TypingIndicator
                agentName="Planner Agent"
                avatar="🧠"
                avatarStyle={{ background: 'linear-gradient(135deg, #7c3aed, #a855f7)' }}
              />
            )}

            {isRunning && activeThinkingAgent === 'generator' && (
              <TypingIndicator
                agentName="Generator Agent"
                avatar="✍️"
                avatarStyle={{ background: 'linear-gradient(135deg, #d97706, #f59e0b)' }}
              />
            )}

            {isRunning && activeThinkingAgent === 'evaluator' && (
              <TypingIndicator
                agentName="Evaluator Agent"
                avatar="⚖️"
                avatarStyle={{ background: 'linear-gradient(135deg, #059669, #10b981)' }}
              />
            )}

            <div ref={chatBottomRef} />
          </div>
        )}

        {/* Tab 2: Approved Deliverables (Original Clean View) */}
        {activeTab === 'deliverables' && (
          <div className="deliverables-panel">
            {data.posts?.length > 0 ? (
              <div>
                <h2 style={{ fontSize: '1.15rem', marginBottom: '1rem', fontWeight: 800 }}>Approved Copy Options</h2>
                {data.posts.map((post, i) => (
                  <PostCard key={i} post={post} isJobRunning={isRunning} />
                ))}
              </div>
            ) : (
              <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📱</div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.25rem' }}>No Approved Deliverables Yet</h3>
                <p className="text-muted" style={{ fontSize: '0.85rem' }}>
                  {isRunning 
                    ? 'The copywriter and auditor agents are still debating and polishing. Approved posts will lock in here as soon as they pass audit.' 
                    : 'The pipeline finished but no posts reached the required quality thresholds.'}
                </p>
                {isRunning && <div className="spinner" style={{ margin: '1.5rem auto 0', width: 22, height: 22 }} />}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  )
}
