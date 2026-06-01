import json
import re
from src.agents.base import call_llm
from src.models import ContentStrategy, PlatformStrategy

SYSTEM_PROMPT = """You are a senior content strategist at a top marketing agency with 15 years of B2B and B2C experience.

Given a company's scraped website content, produce a razor-sharp content strategy brief that a copywriter can use immediately. Every recommendation must be grounded in the actual scraped content — if you can't find evidence for a claim in the scraped data, don't make it.

## QUALITY STANDARDS
- Every key message must cite or paraphrase something specific from the scraped content (a product name, a stated benefit, a real number, a quoted phrase).
- tone_guidelines must quote at least one real phrase verbatim from the scraped content to anchor the voice.
- example_hook must be a fully written, copy-paste-ready opening sentence — not a description of what it should be.
- content_angle must name the specific customer problem this company solves, not a generic marketing angle.

## FAILURE MODES TO AVOID
- Do NOT write "leverage cutting-edge technology" or any generic SaaS/marketing filler.
- Do NOT invent product features not mentioned in the scraped content.
- Do NOT write example hooks like "Did you know that X?" — write the actual hook.
- Do NOT write platform strategies for platforms not in the requested list.

Output ONLY valid JSON with this exact structure — no markdown fences, no commentary, no trailing commas:
{
  "campaign_goal": "One specific sentence grounded in the company's actual product/service and a concrete outcome (e.g. 'Drive trial signups for WeSeeGPT's AI vision analysis tool by showing e-commerce teams how it cuts manual QA time').",
  "key_messages": [
    "Message 1: specific claim from scraped content with supporting evidence",
    "Message 2: specific differentiator mentioned on the site",
    "Message 3: specific customer outcome or use case from the site"
  ],
  "tone_guidelines": "2-3 sentences. Describe the brand voice with evidence. Must include at least one verbatim phrase from the scraped content in quotes to anchor the tone.",
  "platform_strategies": {
    "PLATFORM_NAME": {
      "post_type": "one of: thought leadership / product launch / case study / how-to / contrarian take / behind-the-scenes",
      "length_guidance": "exact character range for this platform",
      "hashtag_strategy": "exact count and type (e.g. '3-5 hashtags: 2 niche industry tags + 1 brand tag')",
      "content_angle": "Name the specific problem this company solves for this platform's audience. E.g. 'E-commerce teams waste 4+ hours/week on manual product image QA — WeSeeGPT automates it'",
      "hook_style": "one of: bold statistic / contrarian take / specific question / micro-story / surprising insight",
      "cta_type": "exact CTA text or template, e.g. 'Try free at [url] — no credit card' or 'Comment your take below'",
      "example_hook": "A fully written, ready-to-use opening sentence that a copywriter could paste directly into the post. Must be specific to this company."
    }
  }
}"""


def _build_platform_schema(platforms: list[str]) -> str:
    """Return a filled-in platform_strategies skeleton for the requested platforms only."""
    length_map = {
        "linkedin":  "1300–2000 characters",
        "twitter":   "under 280 characters",
        "instagram": "150–300 characters",
    }
    schemas = {}
    for p in platforms:
        schemas[p] = {
            "post_type": "...",
            "length_guidance": length_map.get(p, "platform-appropriate length"),
            "hashtag_strategy": "...",
            "content_angle": "...",
            "hook_style": "...",
            "cta_type": "...",
            "example_hook": "...",
        }
    return json.dumps({"platform_strategies": schemas}, indent=2)


async def plan_strategy(
    scraped_text: str,
    company_name: str,
    company_desc: str,
    target_audience: str,
    platforms: list[str],
) -> ContentStrategy:

    platform_list = ", ".join(platforms)
    platform_schema_hint = _build_platform_schema(platforms)

    user = f"""Company: {company_name}
Description: {company_desc}
Target Audience: {target_audience}
Platforms requested (include ONLY these in platform_strategies): {platform_list}

Scraped Website Content:
{scraped_text[:6000]}

---
Your platform_strategies block must contain ONLY these keys: {platform_list}
Use this skeleton as a reference for the expected structure:
{platform_schema_hint}

Remember: every field must be grounded in the scraped content above. No generic advice."""

    raw = await call_llm(
        SYSTEM_PROMPT, user, role="planner", temperature=0.4, max_tokens=3000
    )
    raw = raw.strip()

    # Strip markdown fences if model wrapped output
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # Attempt 1: direct parse
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt 2: extract the outermost JSON object
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    # Attempt 3: ask LLM to repair the JSON
    if data is None:
        repair_prompt = (
            "The following text should be valid JSON but has syntax errors. "
            "Return ONLY the corrected JSON with no commentary:\n\n" + raw[:4000]
        )
        repaired = await call_llm(
            "You are a JSON repair tool. Output only valid JSON, nothing else.",
            repair_prompt,
            role="planner",
            temperature=0.0,
            max_tokens=3000,
        )
        repaired = repaired.strip()
        if repaired.startswith("```"):
            repaired = re.sub(r"^```(?:json)?\s*", "", repaired)
            repaired = re.sub(r"\s*```$", "", repaired)
        try:
            data = json.loads(repaired.strip())
        except json.JSONDecodeError:
            return ContentStrategy(
                campaign_goal="Error: planner could not produce valid JSON strategy.",
                key_messages=[],
                tone_guidelines="",
                platform_strategies={},
            )

    ps = data.get("platform_strategies", {})
    platform_strategies = {}
    for plat in platforms:
        p = ps.get(plat, {})
        platform_strategies[plat] = PlatformStrategy(
            post_type=p.get("post_type", ""),
            length_guidance=p.get("length_guidance", ""),
            hashtag_strategy=p.get("hashtag_strategy", ""),
            content_angle=p.get("content_angle", ""),
            hook_style=p.get("hook_style", ""),
            cta_type=p.get("cta_type", ""),
            example_hook=p.get("example_hook", ""),
        )

    return ContentStrategy(
        campaign_goal=data.get("campaign_goal", ""),
        key_messages=data.get("key_messages", []),
        tone_guidelines=data.get("tone_guidelines", ""),
        platform_strategies=platform_strategies,
    )