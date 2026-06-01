import json
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import SITE_NAME
from src.storage import (
    init_db,
    get_job,
    get_posts_for_job,
    get_all_jobs,
    create_job,
    save_company,
    get_company,
    update_job_status,
)
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=SITE_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_running_tasks: dict[int, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.post("/api/run")
async def start_run(
    company_name: str = Form(..., max_length=200),
    company_url: str = Form(..., max_length=500),
    description: str = Form(..., max_length=3000),
    target_audience: str = Form(..., max_length=1000),
    platforms: list[str] = Form(...),
):
    import re
    # Basic input sanitization to catch blatant injection attempts
    suspicious_patterns = r"(?i)(ignore previous instructions|system prompt|bypass|forget all|you are now)"
    for field in [company_name, description, target_audience]:
        if re.search(suspicious_patterns, field):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid input detected.")

    company_id = save_company(company_name, company_url, description, target_audience)
    job_id = create_job(company_id, platforms)

    task = asyncio.create_task(
        run_pipeline(
            company_id=company_id,
            job_id=job_id,
            company_name=company_name,
            company_url=company_url,
            company_desc=description,
            target_audience=target_audience,
            platforms=platforms,
        )
    )
    _running_tasks[job_id] = task

    return JSONResponse({"job_id": job_id})


@app.get("/api/run/{job_id}/status")
async def run_status(job_id: int):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"status": "not_found"}, status_code=404)

    company = get_company(job["company_id"])
    posts = get_posts_for_job(job_id)

    post_list = []
    for p in posts:
        eval_history = p.get("eval_history", "[]")
        if isinstance(eval_history, str):
            try:
                eval_history = json.loads(eval_history)
            except (json.JSONDecodeError, TypeError):
                eval_history = []

        post_list.append({
            "platform": p["platform"],
            "content": p["content"],
            "hashtags": p.get("hashtags", ""),
            "final_score": p["final_score"],
            "iterations": p["iterations"],
            "passed_eval": bool(p["passed_eval"]),
            "eval_history": eval_history,
        })

    return JSONResponse({
        "job_id": job_id,
        "status": job["status"],
        "error": job.get("error", ""),
        "company_name": company["name"] if company else "Unknown",
        "platforms": json.loads(job.get("platforms", "[]")),
        "strategy": json.loads(job["strategy"]) if job.get("strategy") else None,
        "posts": post_list,
    })


@app.post("/api/run/{job_id}/rerun")
async def rerun_run(job_id: int):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    company = get_company(job["company_id"])
    if not company:
        return JSONResponse({"error": "Company not found"}, status_code=404)

    platforms = json.loads(job.get("platforms", "[]"))

    new_job_id = create_job(job["company_id"], platforms)

    task = asyncio.create_task(
        run_pipeline(
            company_id=job["company_id"],
            job_id=new_job_id,
            company_name=company["name"],
            company_url=company["url"],
            company_desc=company["description"],
            target_audience=company["target_audience"],
            platforms=platforms,
        )
    )
    _running_tasks[new_job_id] = task

    return JSONResponse({"job_id": new_job_id})


@app.post("/api/run/{job_id}/reiterate")
async def reiterate_run(job_id: int):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    company = get_company(job["company_id"])
    if not company:
        return JSONResponse({"error": "Company not found"}, status_code=404)

    platforms = json.loads(job.get("platforms", "[]"))

    new_job_id = create_job(job["company_id"], platforms)

    task = asyncio.create_task(
        run_pipeline(
            company_id=job["company_id"],
            job_id=new_job_id,
            company_name=company["name"],
            company_url=company["url"],
            company_desc=company["description"],
            target_audience=company["target_audience"],
            platforms=platforms,
            reiterate_from_job_id=job_id,
        )
    )
    _running_tasks[new_job_id] = task

    return JSONResponse({"job_id": new_job_id})


@app.get("/api/history")
async def history():
    jobs = get_all_jobs()
    result = []
    for j in jobs:
        result.append({
            "id": j["id"],
            "company_name": j.get("company_name", ""),
            "status": j["status"],
            "platforms": json.loads(j.get("platforms", "[]")),
            "created_at": j.get("created_at", ""),
            "error": j.get("error", ""),
        })
    return JSONResponse(jsonable_encoder({"jobs": result}))


@app.post("/api/run/{job_id}/cancel")
async def cancel_run(job_id: int):
    """Cancel a running pipeline."""
    task = _running_tasks.get(job_id)
    if task is None:
        # No in-memory task — might still be a stale running status in DB
        job = get_job(job_id)
        if job and job["status"] not in ("completed", "failed", "cancelled"):
            update_job_status(job_id, "cancelled")
            return JSONResponse({"status": "cancelled", "detail": "Marked as cancelled (no active task)"})
        return JSONResponse({"error": "No running task found for this job"}, status_code=404)

    if task.done():
        _running_tasks.pop(job_id, None)
        return JSONResponse({"error": "Task already finished"}, status_code=409)

    task.cancel()
    # Wait briefly so CancelledError propagates and the pipeline's except block runs
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
        pass

    update_job_status(job_id, "cancelled")
    _running_tasks.pop(job_id, None)
    logger.info("Pipeline job_id=%d cancelled by user", job_id)
    return JSONResponse({"status": "cancelled"})


# ---------------------------------------------------------------------------
# SPA Catch-all — serve React frontend
# ---------------------------------------------------------------------------

if FRONTEND_DIST.exists():
    # Mount static assets (JS, CSS, images from Vite build)
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Return index.html for all non-API routes so React Router can handle them."""
        index = FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
else:
    @app.get("/")
    async def dev_root():
        return JSONResponse({
            "message": "Backend running. Build the frontend with: cd frontend && npm run build",
            "api_docs": "/docs",
        })
