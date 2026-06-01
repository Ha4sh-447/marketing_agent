import json
from src.agents.base import call_llm
from src.models import ContentStrategy, PlatformStrategy

SYSTEM_PROMPT = """You are a senior content strategist at a top marketing agency.

Given a company's website data, produce a detailed content strategy brief that a
copywriter can use to write platform-specific social media posts.

Your brief must be SPECIFIC to this company — no generic advice. Ground every
recommendation in what you actually see in the scraped content.

Output ONLY valid JSON with this exact structure (no markdown, no commentary):
{
  "campaign_goal": "One sentence: what outcome should these posts drive?",
  "key_messages": [
    "Specific message 1 grounded in company data",
    "Specific message 2",
    "Specific message 3"
  ],
  "tone_guidelines": "2-3 sentences describing the brand's actual voice based on their website copy. Quote real phrases from the scraped content.",
  "platform_strategies": {
    "linkedin": {
      "post_type": "thought leadership / product launch / case study / culture",
      "length_guidance": "1300-2000 characters",
      "hashtag_strategy": "3-5 industry hashtags",
      "content_angle": "The specific angle to take — e.g. 'customer pain point → product solution'",
      "hook_style": "question / bold statistic / surprising insight / contrarian take",
      "cta_type": "try free / learn more / share opinion / visit site",
      "example_hook": "Write one concrete opening sentence a copywriter could actually use"
    },
    "twitter": {
      "post_type": "hook-driven / thread / announcement / hot take",
      "length_guidance": "under 280 characters",
      "hashtag_strategy": "1-2 hashtags max",
      "content_angle": "...",
      "hook_style": "...",
      "cta_type": "...",
      "example_hook": "..."
    },
    "instagram": {
      "post_type": "storytelling / educational carousel / behind-scenes / product showcase",
      "length_guidance": "150-300 character caption",
      "hashtag_strategy": "8-15 niche + broad hashtags",
      "content_angle": "...",
      "hook_style": "...",
      "cta_type": "...",
      "example_hook": "..."
    }
  }
}

Only include platforms that were requested. Be ambitious but realistic."""


async def plan_strategy(scraped_text: str, company_name: str, company_desc: str,
                        target_audience: str, platforms: list[str]) -> ContentStrategy:
    user = f"""Company: {company_name}
Description: {company_desc}
Target Audience: {target_audience}
Platforms to create strategies for: {', '.join(platforms)}

Scraped Website Content:
{scraped_text[:6000]}"""

    raw = await call_llm(SYSTEM_PROMPT, user, role="planner", temperature=0.5, max_tokens=2048)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ContentStrategy(campaign_goal="Error parsing strategy")

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
