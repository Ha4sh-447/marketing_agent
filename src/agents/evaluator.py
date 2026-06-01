import json
import re
from src.agents.base import call_llm
from src.models import EvaluationResult

SYSTEM_PROMPT = """You are an extremely clinical, skeptical, and objective social media QA auditor with a zero-tolerance policy for AI-generated filler.

Your job is to catch every way this post could fail in the real world — not just on paper. A post that sounds polished but says nothing specific is a failing post.

## SCORING SYSTEM
Start each criterion at 10. Apply ALL applicable deductions. Scores can go below zero if multiple deductions stack.

─────────────────────────────────────────────────────────────────
1. brand_voice_alignment — Factual specificity & authentic brand voice
   -3  Generic claims that could describe any company in the space (not grounded in this company's specific product/features)
   -2  No reference to any concrete product name, feature, metric, or outcome from the scraped site data
   -2  Uses marketer-speak instead of the brand's actual voice/phrasing from their website
   -1  Tone is inconsistent with the brand voice described in the strategy brief

2. platform_fit — Correct conventions and length
   -3  Unstructured wall of text (LinkedIn requires clear paragraph breaks)
   -2  Length is out of range (LinkedIn: 1300–2000 chars; Twitter: <280 chars; Instagram: 150–300 chars)
   -2  Hashtags embedded inline in post body instead of in the hashtags section
   -1  Uses platform conventions incorrectly (e.g. thread-style formatting on Instagram)

3. engagement_potential — Hook quality and scannability
   -3  Opens with a banned cliché: "What if you could...", "Are you tired of...", "Have you ever wondered...", "Imagine a world where...", "In today's fast-paced..."
   -2  CTA is generic ("Learn more", "Check it out") instead of specific and motivating
   -2  Dense, long sentences that kill scannability — no one will read past line 3
   -1  Hook does not create immediate curiosity, tension, or a "so what" moment

4. human_like_quality — No AI-isms or corporate filler
   -4  ANY banned word present: "revolutionary", "game-changer", "cutting-edge", "unlock potential", "transformative", "elevate", "leverage", "innovative", "seamless", "holistic", "paradigm", "empower", "robust", "scalable", "synergy", "disruptive", "next-generation", "state-of-the-art", "best-in-class", "world-class", "end-to-end"
   -3  Vague corporate jargon or generic preambles that add zero information
   -2  More than 2 emojis (emoji spam is a strong AI tell)
   -1  Reads like it was written by a marketing department, not a real person at the company

5. value_clarity — Is the value proposition immediately obvious?
   -3  A first-time reader cannot explain in one sentence what this product does and why it matters
   -2  No specific proof point, metric, outcome, or customer result mentioned
   -1  The benefit is stated but buried — not front-loaded or scannable

6. cta_effectiveness — Call to action quality
   -3  No CTA, or CTA is not at the end of the post
   -2  CTA is vague or generic ("visit our site", "learn more") with no specific hook
   -1  CTA does not match the platform convention or the campaign goal

7. format_compliance — Output cleanliness
   -5  Reasoning tags present (<think>, </think>, <|thinking|>, etc.)
   -5  Preamble present ("Here is your post:", "Sure! Here's a LinkedIn post:", etc.)
   -3  Markdown formatting artefacts (**, ##, ``` etc.) present in the post body
   -2  Post contains content that belongs in the hashtags section (inline hashtags)
─────────────────────────────────────────────────────────────────

## PASS THRESHOLDS (all must be met simultaneously)
brand_voice_alignment  ≥ 7
platform_fit           ≥ 7
engagement_potential   ≥ 6
human_like_quality     ≥ 7
value_clarity          ≥ 6
cta_effectiveness      ≥ 6
format_compliance      ≥ 8
overall_score          ≥ 7.0

## ATTEMPT 1 STRICT RULE
On Attempt 1, you MUST force a refinement loop unless the post is genuinely exceptional (avg ≥ 8.5/10 across all criteria):
- Identify at least two highly specific, concrete issues with exact text citations
- Score at least one of [human_like_quality, brand_voice_alignment, engagement_potential] below its threshold
- Set passed: false

This is not optional — the multi-iteration loop only adds value if Attempt 1 triggers it.

## TRAJECTORY SIGNAL RULES
- "refine"  → scores are improving or stable; targeted fixes will get this over the line
- "pivot"   → scores are declining across iterations, OR the post is fundamentally broken in approach (wrong hook style, wrong angle entirely); requires a full rewrite

## OUTPUT FORMAT
Respond ONLY with a single valid JSON object. No markdown fences. No text before or after.
{
  "scores": {
    "brand_voice_alignment": <integer 0-10>,
    "platform_fit": <integer 0-10>,
    "engagement_potential": <integer 0-10>,
    "human_like_quality": <integer 0-10>,
    "value_clarity": <integer 0-10>,
    "cta_effectiveness": <integer 0-10>,
    "format_compliance": <integer 0-10>
  },
  "overall_score": <float, computed as average of scores above>,
  "passed": <boolean>,
  "feedback": {
    "brand_voice_alignment": "List every deduction applied with the exact text that triggered it",
    "platform_fit": "...",
    "engagement_potential": "...",
    "human_like_quality": "...",
    "value_clarity": "...",
    "cta_effectiveness": "...",
    "format_compliance": "..."
  },
  "trajectory_signal": "refine" | "pivot",
  "top_priority_fix": "One sentence naming the single highest-impact change the generator should make next"
}"""


# Ground-truth thresholds — the LLM score is ignored for pass/fail;
# only these hardcoded values determine whether the post passes.
THRESHOLDS: dict[str, float] = {
    "brand_voice_alignment": 7,
    "platform_fit":          7,
    "engagement_potential":  6,
    "human_like_quality":    7,
    "value_clarity":         6,
    "cta_effectiveness":     6,
    "format_compliance":     8,
}
OVERALL_PASS_THRESHOLD = 7.0


async def evaluate_post(
    content: str,
    hashtags: str,
    platform: str,
    strategy_text: str,
    scraped_text: str,
    company_name: str,
    prev_scores: list[dict[str, float]] | None = None,
) -> EvaluationResult:

    attempt_num = len(prev_scores) + 1 if prev_scores else 1

    # Build a score trend summary to give the evaluator context
    trend_summary = ""
    if prev_scores and len(prev_scores) >= 1:
        trend_lines = []
        for i, ps in enumerate(prev_scores, 1):
            avg = sum(ps.values()) / max(len(ps), 1)
            trend_lines.append(f"  Attempt {i}: avg {avg:.1f}/10 — {', '.join(f'{k}={v}' for k, v in ps.items())}")
        trend_summary = f"\nScore history (for trajectory context):\n" + "\n".join(trend_lines)

    user = f"""Company: {company_name}
Platform: {platform}
Current Iteration: Attempt {attempt_num}{trend_summary}

Content Strategy Brief:
{strategy_text[:2000]}

Brand Reference (from company's actual website — use this to judge specificity):
{scraped_text[:1500]}

=== POST TO EVALUATE ===
{content}

=== HASHTAGS ===
{hashtags}
========================

Apply the full scoring checklist. Cite the exact text from the post that triggers each deduction.
{"ATTEMPT 1: Apply the strict rule. Force refinement unless avg score is genuinely ≥ 8.5." if attempt_num == 1 else f"Attempt {attempt_num}: Judge normally. Be accurate — don't artificially inflate or deflate scores."}"""

    raw = await call_llm(
        SYSTEM_PROMPT, user, role="evaluator", temperature=0.1, max_tokens=1200
    )
    raw = raw.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # Parse JSON
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    if data is None:
        return EvaluationResult(
            scores={},
            overall_score=0.0,
            passed=False,
            feedback={"error": f"Evaluator returned unparseable response: {raw[:200]}"},
            trajectory_signal="refine",
        )

    scores: dict[str, float] = {
        k: float(v) for k, v in data.get("scores", {}).items()
    }
    feedback: dict[str, str] = data.get("feedback", {})

    # ── Compute overall score ourselves — never trust the LLM's self-reported value ──
    overall_score = (
        sum(scores.values()) / len(scores)
        if scores
        else 0.0
    )

    # ── Compute pass/fail ourselves using hardcoded thresholds ──
    computed_passed = (
        overall_score >= OVERALL_PASS_THRESHOLD
        and all(
            scores.get(criterion, 0) >= threshold
            for criterion, threshold in THRESHOLDS.items()
        )
    )

    # ── Attempt 1 forced refinement loop ──
    if attempt_num == 1:
        avg_score = overall_score
        if avg_score < 8.5:
            # Find the first eligible criterion that's currently passing and nudge it below threshold
            priority_order = [
                "human_like_quality",
                "brand_voice_alignment",
                "engagement_potential",
            ]
            nudged = False
            for criterion in priority_order:
                threshold = THRESHOLDS[criterion]
                if scores.get(criterion, 10) >= threshold:
                    scores[criterion] = threshold - 1.0
                    existing_fb = feedback.get(criterion, "")
                    feedback[criterion] = (
                        f"[Attempt 1 — Polishing Loop Triggered] {existing_fb} "
                        f"Refine the {criterion.replace('_', ' ')} further before this passes."
                    )
                    nudged = True
                    break
            # If all priority criteria are already failing, no nudge needed
            computed_passed = False
            # Recompute overall after nudge
            overall_score = sum(scores.values()) / max(len(scores), 1)

    # ── Trajectory: override to "pivot" if scores are declining ──
    trajectory = data.get("trajectory_signal", "refine")
    if prev_scores and len(prev_scores) >= 2:
        current_avg = overall_score
        # Compare against the average of the last 2 attempts
        recent_avgs = [
            sum(p.values()) / max(len(p), 1)
            for p in prev_scores[-2:]
        ]
        prev_avg = sum(recent_avgs) / len(recent_avgs)
        if current_avg < prev_avg - 0.3:   # meaningful decline, not just noise
            trajectory = "pivot"

    # Surface the top_priority_fix if the evaluator provided it
    top_fix = data.get("top_priority_fix", "")

    return EvaluationResult(
        scores=scores,
        overall_score=round(overall_score, 2),
        passed=computed_passed,
        feedback=feedback,
        trajectory_signal=trajectory,
    )