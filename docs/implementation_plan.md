# Marketing Post Generation Agent — Implementation Plan

## Architecture Overview

Planner–Generator–Evaluator three-agent pattern (GAN-inspired, from Anthropic's harness engineering), wrapped in a FastAPI web app with polling-based progress UI.

```
User Input (company URL, description, target audience, platforms)
    │
    ▼
┌─────────────┐    ┌───────────────────────────────────────────────┐
│  Scraper    │───►│  Scraped Artifact: brand voice, products,     │
│  Module     │    │  tone examples, blog themes, value props      │
└─────────────┘    └───────────────────────┬───────────────────────┘
                                           ▼
                              ┌─────────────────────────┐
                              │    Planner Agent         │
                              │  (content strategy spec) │
                              └───────────┬─────────────┘
                                           ▼
                              ┌─────────────────────────┐
                              │    Generator Agent       │
                              │  (draft posts per spec)  │
                              └───────────┬─────────────┘
                                           │
                              ┌───────────▼─────────────┐
                              │    Evaluator Agent        │
                              │  (LLM-as-Judge: score    │
                              │   per criterion, pass/   │
                              │   fail with feedback)    │
                              └───────────┬─────────────┘
                                           │
                              ┌───────────▼─────────────┐
                              │  All thresholds met?     │
                              └───────────┬─────────────┘
                      ┌───────────────────┼──────────────────┐
                      ▼                   ▼                   ▼
                   Yes ──► Save to    No, improving ──► Generator
                           SQLite +       (REFINE)      retries
                           output/                      with feedback
                      Draft posts        No, declining    │
                      for manual         (PIVOT) ────────┤
                      review             new approach     │
                                           (max 3 tries)──┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (async) |
| Frontend | Jinja2 templates + Pico CSS (no build step) |
| Storage | SQLite3 (stdlib) |
| LLM API | OpenRouter via `openai` SDK (OpenAI-compatible) |
| Scraper | `httpx` + `BeautifulSoup4` (no headless browser) |
| Data validation | Pydantic v2 |

## Project Structure

```
marketing_agent/
├── main.py                  # FastAPI app — entry point
├── pyproject.toml           # Dependencies
├── .env.example             # Template for secrets
├── src/
│   ├── __init__.py
│   ├── config.py            # Env-based config
│   ├── models.py            # All Pydantic models
│   ├── scraper.py           # httpx + bs4 website scraper
│   ├── storage.py           # SQLite CRUD layer
│   ├── pipeline.py          # Orchestrator (async background task)
│   └── agents/
│       ├── __init__.py
│       ├── base.py          # OpenRouter LLM wrapper
│       ├── planner.py       # Content strategist agent
│       ├── generator.py     # Copywriter agent
│       └── evaluator.py     # LLM-as-Judge agent
└── templates/
    ├── base.html            # Layout (Pico CSS)
    ├── index.html           # New run form
    ├── results.html         # Live polling results
    └── history.html         # Past runs
```

## Data Models

### `CompanyProfile`
- `name: str`
- `url: str`
- `description: str` — user-provided
- `target_audience: str` — user-provided
- `brand_voice_notes: str | None`
- `scraped_at: datetime | None`

### `ScrapedContent`
- `tagline: str | None`
- `about_summary: str | None`
- `products_services: list[str]`
- `blog_themes: list[str]`
- `tone_markers: list[str]` — e.g. "casual", "authoritative", "playful"
- `value_propositions: list[str]`

### `ContentStrategy`
- `campaign_goal: str`
- `key_messages: list[str]`
- `tone_guidelines: str`
- `platform_strategies: dict[str, PlatformStrategy]`

### `PlatformStrategy`
- `post_type: str` — e.g. "thought leadership", "product announcement"
- `length_guidance: str`
- `hashtag_strategy: str`

### `PostDraft`
- `platform: str`
- `content: str`
- `hashtags: list[str] | None`
- `iteration: int`

### `EvaluationResult`
- `scores: dict[str, float]` — per-criterion scores
- `overall_score: float`
- `passed: bool`
- `feedback: dict[str, str]` — per-criterion feedback
- `trajectory_signal: str` — "refine" or "pivot"

### `GeneratedPost`
- `id: int`
- `company_id: int`
- `platform: str`
- `content: str`
- `hashtags: str | None`
- `final_score: float`
- `iterations: int`
- `created_at: datetime`

## Evaluation Criteria (LLM-as-Judge)

Six criteria, scored 0–10, each with a hard threshold:

| Criterion | Threshold | Definition |
|-----------|-----------|------------|
| Brand Voice Alignment | 7 | Matches the scraped brand voice/tone |
| Platform Fit | 7 | Right format, length, conventions for the platform |
| Engagement Potential | 6 | Likely to get comments, shares, reactions |
| Human-Like Quality | 7 | No AI clichés, generic language, or artifacts |
| Value Clarity | 6 | Clearly communicates what the company offers |
| CTA Effectiveness | 5 | Call-to-action is clear and motivating |

**Overall pass**: all criteria ≥ their threshold.

**Hardcoded evaluator examples** (embedded in system prompt):

```
--- BAD (score 0-3) ---
"In today's fast-paced digital landscape, it's more important than ever to unlock your team's true potential! 🚀"
"Are you tired of [problem]? Look no further! Our cutting-edge solution revolutionizes the way you work."
"Let's dive into why our platform is a game-changer for businesses worldwide."

--- GOOD (score 8-10) ---
"We spent two years talking to 50 ops teams. Here's what they told us about incident response."
"Thread: 5 lessons from shipping our first mobile app. 1/ Ship before you're confident."
"One metric we track obsessively: time from idea to production. Here's ours over the last 6 quarters."
```

## Pipeline Flow (async background task)

```
POST /run → create job (status: "queued") → BackgroundTasks.add(pipeline.run)

pipeline.run():
  1. status = "scraping"
  2. scrape_website(url) → ScrapedContent (max 8 same-domain pages)
  3. status = "planning"
  4. plan_strategy(scraped, profile) → ContentStrategy
  5. For each requested platform:
     a. status = "generating {platform}"
     b. iteration = 0
     c. draft = generate(strategy, platform)
     d. Loop (max 3 iterations):
        - eval = evaluate(draft, strategy, scraped)
        - if eval.passed → break, save post
        - trajectory = "refine" if scores improving, else "pivot"
        - draft = generate(strategy, platform, eval.feedback, trajectory)
        - iteration++
     e. Save final (even if failed — human can review)
  6. status = "completed"
```

## Frontend Pages

| Route | Template | Purpose |
|-------|----------|---------|
| `GET /` | `index.html` | Form: URL, description, audience, platform checkboxes |
| `POST /run` | redirect | Creates job, redirects to results |
| `GET /run/{job_id}` | `results.html` | Polls status every 3s, shows live logs + posts when done |
| `GET /run/{job_id}/status` | JSON | Returns current status, posts, scores |
| `GET /history` | `history.html` | Lists all past runs with scores |
| `POST /run/{job_id}/rerun` | redirect | Re-runs a failed/completed job |

Polling: `results.html` uses `setInterval(fetch('/run/{id}/status'), 3000)` to update progress.

## OpenRouter Model Strategy

| Agent | Recommended Model | Rationale |
|-------|-------------------|-----------|
| Planner | `anthropic/claude-sonnet-4` | Strong at strategy, structured output |
| Generator | `anthropic/claude-sonnet-4` or `openai/gpt-4o` | Creative writing |
| Evaluator | `anthropic/claude-sonnet-4` | Critical reasoning, calibrated skepticism |

Configurable per-role via env vars: `PLANNER_MODEL`, `GENERATOR_MODEL`, `EVALUATOR_MODEL`.

## Deployment

- **Runtime**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Dependencies**: Minimal — `fastapi`, `uvicorn`, `httpx`, `beautifulsoup4`, `openai`, `pydantic`, `python-dotenv`, `jinja2`
- **Database**: SQLite file (`data/marketing.db`) — auto-created on first run
- **No external services needed**: Works on Railway, Render, Fly.io, or any VPS with Python 3.12+

## Things Explicitly Cut for v1

- User authentication
- Image/media generation
- WebSocket/SSE streaming (polling instead)
- Dockerfile/CI
- Automated tests
- Multi-variant post generation (1 post per platform, iterated for quality)
- Export to PDF/image

## Build Order (for implementation)

1. `pyproject.toml` + `.env.example` + `src/config.py` + `src/models.py`
2. `src/scraper.py` — httpx + bs4, max 8 linked pages
3. `src/storage.py` — SQLite schema + CRUD operations
4. `src/agents/base.py` — OpenRouter LLM wrapper
5. `src/agents/planner.py` — strategy generation
6. `src/agents/generator.py` — post drafting + refinement
7. `src/agents/evaluator.py` — LLM-as-Judge with hardcoded examples
8. `src/pipeline.py` — async orchestrator with retry loop
9. `templates/` — base.html, index.html, results.html, history.html
10. `main.py` — FastAPI routes, background tasks, run entrypoint
11. Test + fix bugs
