import re
from src.agents.base import call_llm
from src.models import ContentStrategy, EvaluationResult

SYSTEM_PROMPT = """You are a world-class social media copywriter. You write posts that look and feel like they were written by a real, senior person at the company — never like AI output.

## YOUR OUTPUT FORMAT

You must output the post in this EXACT format — nothing else before or after:

---POST---
[Your post content here — just the text that would actually appear on the platform]
---HASHTAGS---
[comma-separated hashtags without # symbols, e.g. startup, saas, growth]

## ABSOLUTE RULES — VIOLATIONS WILL CAUSE REJECTION

1. Output ONLY the ---POST--- / ---HASHTAGS--- block. Zero preamble. Zero meta-commentary. Zero explanation.
2. NEVER include <think>, </think>, <|thinking|>, or any internal reasoning tags in the output.
3. NEVER open with: "In today's...", "Let's dive into...", "Are you tired of...", "What if you could...", "Have you ever wondered...", "Imagine a world where..."
4. NEVER use these words or phrases — instant rejection: "revolutionary", "game-changer", "cutting-edge", "unlock potential", "transformative", "elevate", "leverage", "innovative", "seamless", "holistic", "paradigm", "empower", "robust", "scalable", "synergy", "disruptive", "next-generation", "state-of-the-art", "best-in-class", "world-class", "end-to-end", "out-of-the-box", "drill down", "move the needle", "circle back", "at the end of the day".
5. Use SPECIFIC details from the company's scraped content. Do not invent features.
6. Use 0–2 emojis maximum. Emoji spam = instant rejection.
7. Every post MUST end with a clear, specific call-to-action.
8. Hashtags go ONLY in the ---HASHTAGS--- section, never inline in the post body.

## PLATFORM-SPECIFIC RULES

### LinkedIn (1300–2000 characters)
- Hook: a surprising stat, a contrarian take, or a specific insight — NOT a generic question
- 3–5 short paragraphs with blank lines between them (LinkedIn rewards scannable structure)
- Each paragraph: 1–3 sentences max
- Include one concrete, specific detail from the company (a metric, a product name, a real feature, a customer outcome)
- CTA at the very end: visit the site, try free, comment a specific question

### Twitter / X (200–280 characters including CTA)
- Single punchy thought — cut everything that isn't load-bearing
- No filler, no em-dashes used decoratively, no "Here's the thing:"
- CTA must fit in the character count

### Instagram (150–300 characters caption)
- Warm, conversational tone — like a message from a person, not a brand
- Micro-story or specific insight
- End with a direct question or CTA to drive comments
- 8–15 hashtags in the ---HASHTAGS--- section

## WHAT GREAT LOOKS LIKE

### LinkedIn Example:
---POST---
We talked to 200+ D2C founders about their biggest blind spot.

Not acquisition. Not shipping. Not even returns.

It was: "Why do customers buy once and never come back?"

That's the question Compra's post-purchase surveys are built around. Two minutes to set up. One question at the right moment — right after delivery, right after a return.

One brand discovered 34% of their churn came from packaging, not the product. Fixed in a week.

If you're running a Shopify store and you don't know why customers leave, try it free at compra.com.
---HASHTAGS---
D2Cbrands, customerfeedback, ecommerce, retention, shopify

### Twitter Example:
---POST---
Your customers know exactly why they stopped buying from you.

You just haven't asked.

Compra does. Free to try: compra.com
---HASHTAGS---
D2C, ecommerce

### Instagram Example:
---POST---
One question changed everything for a brand we work with.

"Why did you almost not buy from us?"

The answer: their checkout felt sketchy on mobile. Fixed in 3 days. Conversion up 22%.

What question would you ask your customers? 👇
---HASHTAGS---
ecommerce, d2cbrands, customerfeedback, shopify, ecommercetips, brandgrowth, customerinsights, shopifystore"""


# Platform character limits for validation hint in prompt
_PLATFORM_LIMITS = {
    "linkedin":  (1300, 2000),
    "twitter":   (50,   280),
    "instagram": (150,  300),
}


async def generate_post(
    strategy: ContentStrategy,
    platform: str,
    scraped_text: str,
    company_name: str,
    feedback: EvaluationResult | None = None,
    trajectory: str = "refine",
    previous_content: str | None = None,
) -> tuple[str, str]:

    plat = strategy.platform_strategies.get(platform, None)
    platform_guidance = ""
    if plat:
        char_min, char_max = _PLATFORM_LIMITS.get(platform, (0, 99999))
        platform_guidance = f"""Platform: {platform}
Post type: {plat.post_type}
Target length: {plat.length_guidance} ({char_min}–{char_max} characters for the post body — count carefully)
Hashtag strategy: {plat.hashtag_strategy}
Content angle: {plat.content_angle}
Hook style: {plat.hook_style}
CTA type: {plat.cta_type}
Example hook (use this as a starting point, do NOT copy verbatim): {plat.example_hook}"""

    user = f"""Company: {company_name}
Campaign Goal: {strategy.campaign_goal}
Key Messages: {' | '.join(strategy.key_messages)}
Tone Guidelines: {strategy.tone_guidelines}

{platform_guidance}

Scraped Brand Content (ground the post in these real details):
{scraped_text[:1800]}"""

    # Attach evaluator feedback when refining
    if feedback and feedback.scores:
        fb_lines = []
        for criterion, score in sorted(
            feedback.scores.items(), key=lambda x: x[1]  # worst scores first
        ):
            fb_lines.append(
                f"- {criterion}: {score}/10 — {feedback.feedback.get(criterion, 'no detail')}"
            )
        approach_instruction = (
            "Surgically fix each issue listed below while keeping everything that already works. "
            "Do NOT rewrite sections that scored 8+."
            if trajectory == "refine"
            else
            "The previous approach is not working. Start from scratch with a completely different "
            "hook, angle, and structure. The only thing to keep is the brand/product specifics."
        )
        user += f"""

═══════════════════════════════════════
EVALUATOR FEEDBACK — ADDRESS EVERY POINT
═══════════════════════════════════════
Approach: {trajectory.upper()} — {approach_instruction}

Scores (worst first — focus here):
{chr(10).join(fb_lines)}"""

    if previous_content and trajectory == "refine":
        user += f"""

═══════════════════════════════════════
CURRENT DRAFT — IMPROVE THIS, DON'T REPLACE IT
═══════════════════════════════════════
{previous_content}
═══════════════════════════════════════"""

    user += "\n\nOutput ONLY the ---POST--- and ---HASHTAGS--- block. Nothing else."

    # Use higher temperature for pivot to force genuine novelty
    temperature = 0.95 if trajectory == "pivot" else 0.75

    raw = await call_llm(
        SYSTEM_PROMPT, user, role="generator", temperature=temperature, max_tokens=1024
    )

    content, hashtags = _parse_post_output(raw)
    content = _sanitize_post(content)

    return content, hashtags


def _parse_post_output(raw: str) -> tuple[str, str]:
    """
    Parse the ---POST--- / ---HASHTAGS--- delimited format.
    Falls back to heuristic splitting if delimiters are missing.
    """
    raw = raw.strip()

    # Primary: structured markers
    if "---POST---" in raw:
        after_post = raw.split("---POST---", 1)[1]
        if "---HASHTAGS---" in after_post:
            content, hashtags = after_post.split("---HASHTAGS---", 1)
            return content.strip(), hashtags.strip()
        return after_post.strip(), ""

    # Fallback: detect a hashtag line scanning from the bottom
    lines = raw.split("\n")
    hashtag_line_idx = None
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line and (
            line.count("#") >= 3
            or line.lower().startswith("hashtags")
            or (
                line.count(",") >= 2
                and all(
                    w.strip().replace("#", "").isalnum()
                    for w in line.split(",")
                    if w.strip()
                )
            )
        ):
            hashtag_line_idx = i
            break

    if hashtag_line_idx is not None:
        content = "\n".join(lines[:hashtag_line_idx]).strip()
        hashtags = lines[hashtag_line_idx].strip()
        if hashtags.lower().startswith("hashtags"):
            hashtags = (
                hashtags.split(":", 1)[-1].strip()
                if ":" in hashtags
                else hashtags[8:].strip()
            )
        hashtags = hashtags.replace("#", "").strip()
        return content, hashtags

    return raw.strip(), ""


def _sanitize_post(content: str) -> str:
    """
    Strip common LLM artifacts from post content:
    - Reasoning tags from various model families
    - Preamble lines
    - Markdown formatting artefacts
    - Stray delimiters
    """
    # Remove reasoning tags — covers DeepSeek, GLM, GPT-OSS, Qwen styles
    reasoning_patterns = [
        r"<think>.*?</think>",
        r"<think>.*",               # unclosed
        r"<\|thinking\|>.*?<\|/thinking\|>",
        r"<\|thinking\|>.*",        # unclosed
        r"\[thinking\].*?\[/thinking\]",
        r"<reasoning>.*?</reasoning>",
        r"<reasoning>.*",           # unclosed
    ]
    for pat in reasoning_patterns:
        content = re.sub(pat, "", content, flags=re.DOTALL)

    # Remove preamble lines (case-insensitive)
    preamble_patterns = [
        r"^(?:here(?:'s| is) (?:your|the|a|an) .{0,40}(?:post|content|draft|caption)[:\s]*\n*)",
        r"^(?:(?:linkedin|twitter|instagram|x|social media) (?:post|caption)[:\s]*\n*)",
        r"^(?:post[:\s]*\n+)",
        r"^(?:caption[:\s]*\n+)",
        r"^(?:sure[!,.]?\s+here(?:'s| is).*?\n)",
        r"^(?:of course[!,.]?\s+here(?:'s| is).*?\n)",
    ]
    for pat in preamble_patterns:
        content = re.sub(pat, "", content, flags=re.IGNORECASE)

    # Strip markdown bold/italic but keep text
    content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)
    content = re.sub(r"\*(.+?)\*", r"\1", content)

    # Strip markdown headers
    content = re.sub(r"^#{1,3}\s+", "", content, flags=re.MULTILINE)

    # Strip code fences
    content = re.sub(r"```\w*\n?", "", content)

    # Strip stray --- delimiters
    content = re.sub(r"^---+\s*$", "", content, flags=re.MULTILINE)

    # Collapse 3+ blank lines to 2
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()