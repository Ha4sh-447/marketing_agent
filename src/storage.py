import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional

# Load PostgreSQL connection URL if provided
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Fallback SQLite path
from src.config import DB_PATH

_is_postgres = bool(
    DATABASE_URL.startswith("postgres://") or 
    DATABASE_URL.startswith("postgresql://") or
    DATABASE_URL.startswith("postgresql+asyncpg://")
)

if _is_postgres:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    # Standardize the database protocol format for compatibility
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    elif DATABASE_URL.startswith("postgresql+asyncpg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


# ── Database connection helpers ───────────────────────────────────────────

def _get_db():
    global _is_postgres
    if _is_postgres:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except Exception as e:
            print(f"\n⚠️ DATABASE WARNING: Failed to connect to PostgreSQL ({e}).")
            print("💡 Falling back to local SQLite database (data/marketing.db) for safety!\n")
            _is_postgres = False
            
            # Establish SQLite connection
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def _execute(query: str, params: tuple = ()) -> list[dict]:
    """Execute a query and return all rows as a list of dicts."""
    with _get_db() as conn:
        if _is_postgres:
            query = query.replace("?", "%s")
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if cur.description:
                    return [dict(r) for r in cur.fetchall()]
                return []
        else:
            cur = conn.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def _execute_one(query: str, params: tuple = ()) -> Optional[dict]:
    """Execute a query and return the first row as a dict, or None."""
    rows = _execute(query, params)
    return rows[0] if rows else None


def _execute_write(query: str, params: tuple = ()):
    """Execute a write query (UPDATE, DELETE)."""
    with _get_db() as conn:
        if _is_postgres:
            query = query.replace("?", "%s")
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()
        else:
            conn.execute(query, params)
            conn.commit()


def _execute_insert(query: str, params: tuple = ()) -> int:
    """Execute an INSERT query and return the generated primary key ID."""
    with _get_db() as conn:
        if _is_postgres:
            query = query.replace("?", "%s")
            # Append RETURNING id to get the generated primary key in Postgres
            query_with_returning = query + " RETURNING id"
            with conn.cursor() as cur:
                cur.execute(query_with_returning, params)
                generated_id = cur.fetchone()[0]
            conn.commit()
            return generated_id
        else:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.lastrowid


# ---------------------------------------------------------------------------
# Public Database API
# ---------------------------------------------------------------------------

def init_db():
    conn = _get_db()
    try:
        if _is_postgres:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS companies (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        target_audience TEXT DEFAULT '',
                        brand_voice_notes TEXT DEFAULT '',
                        scraped_content TEXT DEFAULT '',
                        scraped_at TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS jobs (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                        status TEXT DEFAULT 'queued',
                        platforms TEXT DEFAULT '[]',
                        strategy TEXT DEFAULT '',
                        error TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS posts (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                        platform TEXT NOT NULL,
                        content TEXT NOT NULL,
                        hashtags TEXT DEFAULT '',
                        final_score REAL DEFAULT 0.0,
                        iterations INTEGER DEFAULT 0,
                        passed_eval INTEGER DEFAULT 0,
                        eval_history TEXT DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.commit()
        else:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    target_audience TEXT DEFAULT '',
                    brand_voice_notes TEXT DEFAULT '',
                    scraped_content TEXT DEFAULT '',
                    scraped_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'queued',
                    platforms TEXT DEFAULT '[]',
                    strategy TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    job_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    content TEXT NOT NULL,
                    hashtags TEXT DEFAULT '',
                    final_score REAL DEFAULT 0.0,
                    iterations INTEGER DEFAULT 0,
                    passed_eval INTEGER DEFAULT 0,
                    eval_history TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (company_id) REFERENCES companies(id),
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                );
            """)
            conn.commit()
    finally:
        conn.close()


def save_company(name: str, url: str, description: str, target_audience: str) -> int:
    existing = _execute_one("SELECT id FROM companies WHERE url=?", (url,))
    if existing:
        _execute_write(
            "UPDATE companies SET name=?, description=?, target_audience=? WHERE id=?",
            (name, description, target_audience, existing["id"])
        )
        return existing["id"]
    return _execute_insert(
        "INSERT INTO companies (name, url, description, target_audience) VALUES (?, ?, ?, ?)",
        (name, url, description, target_audience),
    )


def update_company_scraped(company_id: int, scraped: dict):
    _execute_write(
        "UPDATE companies SET scraped_content=?, scraped_at=? WHERE id=?",
        (json.dumps(scraped), datetime.now(timezone.utc).isoformat(), company_id),
    )


def get_company(company_id: int) -> Optional[dict]:
    return _execute_one("SELECT * FROM companies WHERE id=?", (company_id,))


def create_job(company_id: int, platforms: list[str]) -> int:
    return _execute_insert(
        "INSERT INTO jobs (company_id, status, platforms) VALUES (?, ?, ?)",
        (company_id, "queued", json.dumps(platforms)),
    )


def update_job_status(job_id: int, status: str, error: str = ""):
    _execute_write(
        "UPDATE jobs SET status=?, updated_at=?, error=? WHERE id=?",
        (status, datetime.now(timezone.utc).isoformat(), error, job_id),
    )


def update_job_strategy(job_id: int, strategy: dict):
    _execute_write(
        "UPDATE jobs SET strategy=?, updated_at=? WHERE id=?",
        (json.dumps(strategy), datetime.now(timezone.utc).isoformat(), job_id),
    )


def get_job(job_id: int) -> Optional[dict]:
    return _execute_one("SELECT * FROM jobs WHERE id=?", (job_id,))


def save_post(
    company_id: int,
    job_id: int,
    platform: str,
    content: str,
    hashtags: str,
    final_score: float,
    iterations: int,
    passed_eval: bool,
    eval_history: list,
) -> int:
    row = _execute_one(
        "SELECT id FROM posts WHERE job_id=? AND platform=?", (job_id, platform)
    )
    if row:
        post_id = row["id"]
        _execute_write(
            """UPDATE posts
               SET content=?, hashtags=?, final_score=?, iterations=?, passed_eval=?, eval_history=?
               WHERE id=?""",
            (content, hashtags, final_score, iterations, int(passed_eval), json.dumps(eval_history), post_id)
        )
        return post_id
    else:
        return _execute_insert(
            """INSERT INTO posts
               (company_id, job_id, platform, content, hashtags, final_score, iterations, passed_eval, eval_history)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company_id, job_id, platform, content, hashtags, final_score, iterations,
             int(passed_eval), json.dumps(eval_history)),
        )


def get_posts_for_job(job_id: int) -> list[dict]:
    return _execute(
        "SELECT * FROM posts WHERE job_id=? ORDER BY platform", (job_id,)
    )


def get_all_jobs() -> list[dict]:
    return _execute(
        """SELECT j.*, c.name as company_name
           FROM jobs j JOIN companies c ON j.company_id = c.id
           ORDER BY j.created_at DESC"""
    )
