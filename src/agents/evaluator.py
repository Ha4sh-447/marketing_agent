import json
import re
from src.agents.base import call_llm
from src.models import EvaluationResult

SYSTEM_PROMPT = """You are an extremely clinical, skeptical, and objective social media QA auditor. 
You evaluate marketing posts against an strict checklist to eliminate generic "AI self-bias". 
You must never hand out high scores easily. AI-generated posts naturally default to failing unless they exhibit genuine specificity.

## OBJECTIVE SCORING AUDIT SYSTEM
For each score, start at 10. Apply the deductions strictly:

1. **brand_voice_alignment** (threshold: 7) — Factual specificity & brand voice
   - Deduct 3 points if it uses generic claims that could fit any company in the space (must be uniquely grounded in company's scraped site).
   - Deduct 2 points if it fails to reference any actual, concrete features or product specifics from the scraped data.
   - Deduct 2 points if it quotes/imitates generic marketer-speak rather than the actual website copy.

2. **platform_fit** (threshold: 7) — Right conventions and lengths
   - Deduct 3 points if the post is unstructured or lacks clear paragraph dividers (LinkedIn needs spacing).
   - Deduct 2 points if length is inappropriate (LinkedIn: 1000-2000 chars; Twitter: <280 chars; Instagram: 150-300 chars).
   - Deduct 2 points if hashtags are embedded inline in the post body rather than separated inside the hashtags section.

3. **engagement_potential** (threshold: 6) — Hook and layout
   - Deduct 3 points if it starts with a cliché question ("What if you could...", "Are you tired of...", "Have you ever wondered...").
   - Deduct 2 points if the CTA is boring and lacks a motivating, company-specific hook.
   - Deduct 2 points if the sentences are long, dense, and not easily scannable.

4. **human_like_quality** (threshold: 7) — No AI-isms
   - Deduct 4 points for ANY banned word ("revolutionary", "game-changer", "cutting-edge", "unlock potential", "transformative", "elevate", "leverage", "in today's fast-paced world", "dive into", "seamless", "holistic").
   - Deduct 3 points if it uses vague corporate jargon or generic preambles.
   - Deduct 2 points if it uses more than 2 emojis (emoji spam is a massive AI tell).

5. **value_clarity** (threshold: 6) — Value proposition
   - Deduct 3 points if a first-time reader cannot easily explain what the product does and why it matters in one simple sentence.
   - Deduct 2 points if there's no clear proof point or specific outcome mentioned.

6. **cta_effectiveness** (threshold: 5) — Clear action
   - Deduct 3 points if there is no call-to-action, or if it is buried instead of being at the very end.

7. **format_compliance** (threshold: 8) — Text cleanliness
   - Deduct 5 points if any reasoning tags (<think>), preambles ("Here is your post:"), or markdown code blocks remain in the post text.

## ATTENTION: ATTEMPT 1 STRICT RULE
If this is Attempt 1 (first iteration), you MUST be extra critical. Even if the post is good, identify at least two highly specific, concrete areas of improvement (e.g., a stronger hook, more factual metrics, or unique CTA). Score at least one of 'human_like_quality', 'brand_voice_alignment' or 'engagement_potential' below their pass threshold (e.g., score 6/10) to force the generator to undergo a guided refinement cycle. This is required to leverage the multi-iteration self-improvement loop. On subsequent attempts, judge normally based on the checklist.

## OUTPUT FORMAT
You must respond ONLY with a single JSON block. Do not wrap in markdown blocks, do not write explanations before or after the JSON.
{
  "scores": {
    "brand_voice_alignment": 0,
    "platform_fit": 0,
    "engagement_potential": 0,
    "human_like_quality": 0,
    "value_clarity": 0,
    "cta_effectiveness": 0,
    "format_compliance": 0
  },
  "overall_score": 0.0,
  "passed": false,
  "feedback": {
    "brand_voice_alignment": "checklist deductions applied and reason",
    "platform_fit": "...",
    "engagement_potential": "...",
    "human_like_quality": "...",
    "value_clarity": "...",
    "cta_effectiveness": "...",
    "format_compliance": "..."
  },
  "trajectory_signal": "refine"
}
"""

async def evaluate_post(
    content: str,
    hashtags: str,
    platform: str,
    strategy_text: str,
    scraped_text: str,
    company_name: str,
    prev_scores: list[dict[str, float]] | None = None,
) -> EvaluationResult:
    # Determine the current iteration number
    attempt_num = len(prev_scores) + 1 if prev_scores else 1

    user = f"""Company: {company_name}
Platform: {platform}
Current Iteration: Attempt {attempt_num}

Content Strategy Brief:
{strategy_text[:2000]}

Brand Reference (from company's actual website):
{scraped_text[:1200]}

=== POST TO EVALUATE ===
{content}

=== HASHTAGS ===
{hashtags}
========================

Perform a clinical audit using the checklist. 
If this is Attempt 1, apply the strict rule to identify specific issues and score at least one parameter below threshold to trigger a refinement loop.
Be highly specific in feedback and cite exact text where applicable."""

    raw = await call_llm(SYSTEM_PROMPT, user, role="evaluator", temperature=0.1, max_tokens=1024)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                return EvaluationResult(
                    scores={},
                    overall_score=0.0,
                    passed=False,
                    feedback={"error": "Failed to parse evaluator response"},
                    trajectory_signal="refine",
                )
        else:
            return EvaluationResult(
                scores={},
                overall_score=0.0,
                passed=False,
                feedback={"error": "Failed to parse evaluator response"},
                trajectory_signal="refine",
            )

    scores = data.get("scores", {})
    feedback = data.get("feedback", {})

    # Hardcoded thresholds — the LLM cannot self-report a pass if any score falls short
    THRESHOLDS = {
        "brand_voice_alignment": 7,
        "platform_fit": 7,
        "engagement_potential": 7,
        "human_like_quality": 7,
        "value_clarity": 7,
        "cta_effectiveness": 7,
        "format_compliance": 7,
    }
    overall_score = data.get("overall_score", sum(scores.values()) / max(len(scores), 1))
    computed_passed = (
        overall_score >= 7.5
        and all(
            scores.get(criterion, 0) >= threshold
            for criterion, threshold in THRESHOLDS.items()
        )
    )

    # Intelligently trigger refinement on Attempt 1
    if attempt_num == 1:
        # If the post is exceptionally good (average score >= 8.5), let it pass immediately!
        avg_score = sum(scores.values()) / max(len(scores), 1)
        if avg_score < 8.5:
            # Lower at least one score if all are passing to guarantee iteration 2 is triggered
            for criterion, threshold in THRESHOLDS.items():
                if scores.get(criterion, 10) >= threshold:
                    # Lower human_like_quality or brand_voice_alignment slightly below threshold
                    if criterion in ["human_like_quality", "brand_voice_alignment", "engagement_potential"]:
                        scores[criterion] = threshold - 1.0
                        feedback[criterion] = f"[Attempt 1 Polishing Loop] {feedback.get(criterion, '')} Post needs a slight refinement to optimize hooks and specific brand phrasing."
                        break
            computed_passed = False

    # Determine trajectory from score trend
    trajectory = data.get("trajectory_signal", "refine")
    if prev_scores and len(prev_scores) >= 2:
        current_avg = sum(scores.values()) / max(len(scores), 1)
        prev_avg = sum(
            sum(p.values()) / max(len(p), 1) for p in prev_scores[-2:]
        ) / max(len(prev_scores[-2:]), 1)
        if current_avg < prev_avg:
            trajectory = "pivot"

    return EvaluationResult(
        scores=scores,
        overall_score=data.get("overall_score", sum(scores.values()) / max(len(scores), 1)),
        passed=computed_passed,
        feedback=feedback,
        trajectory_signal=trajectory,
    )
