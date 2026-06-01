import re
from src.agents.base import call_llm
from src.models import ContentStrategy, EvaluationResult

SYSTEM_PROMPT = """You are a world-class social media copywriter. You write posts that look and feel like they were written by a real person at the company — never like AI output.

## YOUR OUTPUT FORMAT

You must output the post in this EXACT format — nothing else before or after:

---POST---
[Your post content here — just the text that would actually appear on the platform]
---HASHTAGS---
[comma-separated hashtags without # symbols, e.g. startup, saas, growth]

## CRITICAL RULES

1. Output ONLY the post content between the markers. No preamble ("Here's your post:"), no explanation, no meta-commentary.
2. NEVER include <think>, </think>, or any reasoning tags.
3. NEVER start with "In today's...", "Let's dive into...", "Are you tired of...".
4. NEVER use: "revolutionary", "game-changer", "cutting-edge", "unlock potential", "transformative", "elevate", "leverage", "innovative", "seamless", "holistic", "paradigm".
5. Write like a real human at this company would. Use specific details from their website.
6. Use 0-2 emojis maximum. Never emoji-spam.
7. Every post MUST have a clear call-to-action at the end.

## PLATFORM-SPECIFIC STRUCTURES

### LinkedIn (1300-2000 characters)
- Open with a hook: a surprising stat, contrarian take, or specific question
- 2-3 short paragraphs with line breaks between them
- Use concrete specifics from the company (product names, features, metrics)
- End with a clear CTA (try free, visit site, comment your take)
- Hashtags go in the ---HASHTAGS--- section, not inline

### Twitter / X (under 280 characters)
- Punchy, single-thought post
- No filler words
- Optional: 1 emoji
- CTA in the last line

### Instagram (150-300 characters caption)
- Conversational, warm tone
- Tell a micro-story or share an insight
- End with a question or CTA to drive comments
- Hashtags go in ---HASHTAGS--- section (8-15 hashtags)

## EXAMPLES OF GREAT POSTS

### LinkedIn Example:
---POST---
We spent 6 months talking to 200+ D2C founders about one question: "What do you wish you knew about your customers?"

The #1 answer wasn't about demographics or purchase data.

It was: "Why do people stop coming back?"

That's why we built Compra's post-purchase surveys. Not another feedback form — a 2-minute setup that asks the right question at the right moment.

One brand found that 34% of churned customers left because of packaging, not product. They fixed it in a week.

Try it free at compra.com — no credit card needed.
---HASHTAGS---
D2Cbrands, customerfeedback, ecommerce, retention, shopify

### Twitter Example:
---POST---
Your customers already know why they're leaving. You're just not asking.

We built a tool that asks — right after purchase, right after returns.

Takes 2 min to set up. Free to try.
---HASHTAGS---
D2C, ecommerce

### Instagram Example:
---POST---
"Why did you almost not buy from us?"

That's the question that changed everything for one of our brands. The answer? Their checkout felt sketchy on mobile.

Fixed in 3 days. Conversion up 22%.

What's the one question you'd ask your customers? 👇
---HASHTAGS---
ecommerce, d2cbrands, customerfeedback, shopify, ecommercetips, brandgrowth, customerinsights, shopifystore"""


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
        platform_guidance = f"""Platform: {platform}
Post type: {plat.post_type}
Target length: {plat.length_guidance}
Hashtag strategy: {plat.hashtag_strategy}
Content angle: {plat.content_angle}
Hook style: {plat.hook_style}
CTA type: {plat.cta_type}
Example hook to riff on: {plat.example_hook}"""

    user = f"""Company: {company_name}
Campaign Goal: {strategy.campaign_goal}
Key Messages: {' | '.join(strategy.key_messages)}
Tone Guidelines: {strategy.tone_guidelines}

{platform_guidance}

Scraped Brand Content (use real details from this):
{scraped_text[:1800]}"""

    if feedback:
        fb_lines = []
        for criterion, score in feedback.scores.items():
            fb_lines.append(f"- {criterion}: {score}/10 — {feedback.feedback.get(criterion, '')}")
        user += f"""

PREVIOUS ATTEMPT FEEDBACK (fix these issues):
{chr(10).join(fb_lines)}

Approach: {trajectory.upper()}
{"Fix the specific issues above while keeping what works well." if trajectory == "refine" else "Take a completely different approach — new hook, new angle, new structure."}"""

    if previous_content:
        user += f"""

=== YOUR CURRENT POST DRAFT TO IMPROVE ===
{previous_content}
=========================================

You must take this current post draft and re-iterate directly over it to improve it based on the feedback and instructions. Do not rewrite from scratch unless trajectory is 'PIVOT'."""

    user += """

Remember: Output ONLY the ---POST--- and ---HASHTAGS--- format. No other text."""

    raw = await call_llm(SYSTEM_PROMPT, user, role="generator", temperature=0.75, max_tokens=1024)

    content, hashtags = _parse_post_output(raw)
    content = _sanitize_post(content)

    return content, hashtags


def _parse_post_output(raw: str) -> tuple[str, str]:
    """
    Parse the ---POST--- / ---HASHTAGS--- delimited format.
    Falls back to heuristic splitting if delimiters are missing.
    """
    raw = raw.strip()

    # Try structured markers first
    if "---POST---" in raw:
        after_post = raw.split("---POST---", 1)[1]
        if "---HASHTAGS---" in after_post:
            content, hashtags = after_post.split("---HASHTAGS---", 1)
            return content.strip(), hashtags.strip()
        return after_post.strip(), ""

    # Fallback: look for a line that's clearly hashtags
    lines = raw.split("\n")
    hashtag_line_idx = None
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        # Detect lines that are mostly hashtags
        if line and (
            line.count("#") >= 3
            or line.lower().startswith("hashtags")
            or (line.count(",") >= 2 and all(w.strip().replace("#", "").isalnum() for w in line.split(",") if w.strip()))
        ):
            hashtag_line_idx = i
            break

    if hashtag_line_idx is not None:
        content = "\n".join(lines[:hashtag_line_idx]).strip()
        hashtags = lines[hashtag_line_idx].strip()
        # Clean up hashtag line
        if hashtags.lower().startswith("hashtags"):
            hashtags = hashtags.split(":", 1)[-1].strip() if ":" in hashtags else hashtags[8:].strip()
        hashtags = hashtags.replace("#", "").strip()
        return content, hashtags

    # Last resort: return everything as content
    return raw.strip(), ""


def _sanitize_post(content: str) -> str:
    """
    Clean up common LLM artifacts from post content:
    - "Here's your LinkedIn post:" preambles
    - Markdown formatting (bold markers, headers)
    - Stray code fences
    - Meta-commentary
    """
    # Remove common preambles (case-insensitive)
    preamble_patterns = [
        r"^(?:here(?:'s| is) (?:your|the|a) .{0,30}(?:post|content|draft)[:\s]*\n*)",
        r"^(?:(?:linkedin|twitter|instagram|x) post[:\s]*\n*)",
        r"^(?:post[:\s]*\n+)",
        r"^(?:caption[:\s]*\n+)",
    ]
    for pat in preamble_patterns:
        content = re.sub(pat, "", content, flags=re.IGNORECASE)

    # Remove markdown bold/italic markers but keep the text
    content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)
    content = re.sub(r"\*(.+?)\*", r"\1", content)

    # Remove markdown headers
    content = re.sub(r"^#{1,3}\s+", "", content, flags=re.MULTILINE)

    # Remove code fences
    content = re.sub(r"```\w*\n?", "", content)

    # Remove stray --- markers
    content = re.sub(r"^---+\s*$", "", content, flags=re.MULTILINE)

    # Clean up excessive blank lines (max 2 consecutive)
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()
