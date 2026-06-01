import json
from typing import Callable, Optional
from src.config import MAX_RETRIES_PER_POST
from src.storage import (
    update_company_scraped,
    update_job_status,
    update_job_strategy,
    save_post,
    get_company,
    get_job,
    get_posts_for_job,
)
from src.scraper import scrape_website
from src.agents.planner import plan_strategy
from src.agents.generator import generate_post
from src.agents.evaluator import evaluate_post


async def run_pipeline(
    company_id: int,
    job_id: int,
    company_name: str,
    company_url: str,
    company_desc: str,
    target_audience: str,
    platforms: list[str],
    on_status: Optional[Callable] = None,
    reiterate_from_job_id: Optional[int] = None,
):
    async def set_status(s: str):
        update_job_status(job_id, s)
        if on_status:
            on_status(s)

    try:
        scraped_text = ""
        strategy = None

        # Step 1: Scrape (or load if reiterating)
        await set_status("scraping")
        company = get_company(company_id)
        if reiterate_from_job_id and company and company.get("scraped_content"):
            scraped_data = json.loads(company["scraped_content"])
            from src.models import ScrapedContent
            scraped = ScrapedContent(**scraped_data)
        else:
            scraped = await scrape_website(company_url)
            update_company_scraped(company_id, scraped.model_dump())

        scraped_text = "\n\n".join(
            s for s in [
                scraped.tagline or "",
                scraped.about_summary or "",
                *(scraped.raw_snippets or []),
            ] if s
        )

        # Step 2: Plan (or load if reiterating)
        await set_status("planning")
        prev_job = get_job(reiterate_from_job_id) if reiterate_from_job_id else None
        if prev_job and prev_job.get("strategy"):
            strategy_data = json.loads(prev_job["strategy"])
            from src.models import ContentStrategy
            strategy = ContentStrategy(**strategy_data)
        else:
            strategy = await plan_strategy(
                scraped_text, company_name, company_desc, target_audience, platforms
            )
            update_job_strategy(job_id, strategy.model_dump())
        
        strategy_text = json.dumps(strategy.model_dump(), indent=2)

        # Step 3: Generate + Evaluate per platform
        for platform in platforms:
            await set_status(f"generating_{platform}")

            all_eval_history = []
            prev_scores: list[dict[str, float]] = []
            passed = False
            final_content = ""
            final_hashtags = ""
            final_score = 0.0
            iterations = 0

            # If reiterating, find the previous post for this platform
            previous_post = None
            if reiterate_from_job_id:
                prev_posts = get_posts_for_job(reiterate_from_job_id)
                for p in prev_posts:
                    if p["platform"] == platform:
                        previous_post = p
                        break

            for attempt in range(1, MAX_RETRIES_PER_POST + 1):
                last_eval = None
                current_prev_content = None

                # Seed the first attempt with the previous run's final draft & feedback if reiterating
                if attempt == 1 and previous_post:
                    current_prev_content = previous_post["content"]
                    prev_history = json.loads(previous_post["eval_history"]) if previous_post.get("eval_history") else []
                    if prev_history:
                        last_eval_data = prev_history[-1]
                        from src.models import EvaluationResult
                        last_eval = EvaluationResult(
                            scores=last_eval_data.get("scores", {}),
                            overall_score=last_eval_data.get("overall_score", 0.0),
                            passed=False,
                            feedback=last_eval_data.get("feedback", {}),
                            trajectory_signal=last_eval_data.get("trajectory", "refine"),
                        )
                elif all_eval_history:
                    # Normal refinement step: take last attempt's results
                    last_eval_data = all_eval_history[-1]
                    from src.models import EvaluationResult
                    last_eval = EvaluationResult(
                        scores=last_eval_data.get("scores", {}),
                        overall_score=last_eval_data.get("overall_score", 0.0),
                        passed=False,
                        feedback=last_eval_data.get("feedback", {}),
                        trajectory_signal=last_eval_data.get("trajectory", "refine"),
                    )
                    current_prev_content = last_eval_data.get("content", "")

                trajectory = last_eval.trajectory_signal if last_eval else "refine"

                content, hashtags = await generate_post(
                    strategy=strategy,
                    platform=platform,
                    scraped_text=scraped_text,
                    company_name=company_name,
                    feedback=last_eval,
                    trajectory=trajectory,
                    previous_content=current_prev_content,
                )

                # Save intermediate draft immediately so the frontend picks it up live!
                save_post(
                    company_id=company_id,
                    job_id=job_id,
                    platform=platform,
                    content=content,
                    hashtags=hashtags,
                    final_score=final_score,
                    iterations=attempt,
                    passed_eval=False,
                    eval_history=all_eval_history,
                )

                await set_status(f"evaluating_{platform}_attempt_{attempt}")

                eval_result = await evaluate_post(
                    content=content,
                    hashtags=hashtags,
                    platform=platform,
                    strategy_text=strategy_text,
                    scraped_text=scraped_text,
                    company_name=company_name,
                    prev_scores=prev_scores if prev_scores else None,
                )

                eval_entry = {
                    "attempt": attempt,
                    "scores": eval_result.scores,
                    "overall_score": eval_result.overall_score,
                    "passed": eval_result.passed,
                    "feedback": eval_result.feedback,
                    "trajectory": eval_result.trajectory_signal,
                    "content": content,
                    "hashtags": hashtags,
                }
                all_eval_history.append(eval_entry)
                prev_scores.append(eval_result.scores)
                iterations = attempt

                # Save evaluated intermediate post immediately so the frontend has active scores & feedback!
                save_post(
                    company_id=company_id,
                    job_id=job_id,
                    platform=platform,
                    content=content,
                    hashtags=hashtags,
                    final_score=eval_result.overall_score,
                    iterations=attempt,
                    passed_eval=eval_result.passed,
                    eval_history=all_eval_history,
                )

                if eval_result.passed:
                    passed = True
                    final_content = content
                    final_hashtags = hashtags
                    final_score = eval_result.overall_score
                    break

                final_content = content
                final_hashtags = hashtags
                final_score = eval_result.overall_score

            save_post(
                company_id=company_id,
                job_id=job_id,
                platform=platform,
                content=final_content,
                hashtags=final_hashtags,
                final_score=final_score,
                iterations=iterations,
                passed_eval=passed,
                eval_history=all_eval_history,
            )

        await set_status("completed")

    except Exception as e:
        await set_status("failed")
        update_job_status(job_id, "failed", str(e))
        raise
