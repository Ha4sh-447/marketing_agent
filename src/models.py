from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CompanyProfile(BaseModel):
    name: str
    url: str
    description: str
    target_audience: str
    brand_voice_notes: Optional[str] = None
    scraped_at: Optional[datetime] = None


class ScrapedContent(BaseModel):
    tagline: Optional[str] = None
    about_summary: Optional[str] = None
    products_services: list[str] = Field(default_factory=list)
    blog_themes: list[str] = Field(default_factory=list)
    tone_markers: list[str] = Field(default_factory=list)
    value_propositions: list[str] = Field(default_factory=list)
    raw_snippets: list[str] = Field(default_factory=list)


class PlatformStrategy(BaseModel):
    post_type: str = ""
    length_guidance: str = ""
    hashtag_strategy: str = ""
    content_angle: str = ""       # e.g. "customer pain point → solution"
    hook_style: str = ""          # e.g. "question", "bold stat", "personal story"
    cta_type: str = ""            # e.g. "try free", "read more", "comment below"
    example_hook: str = ""        # a concrete example opening line


class ContentStrategy(BaseModel):
    campaign_goal: str = ""
    key_messages: list[str] = Field(default_factory=list)
    tone_guidelines: str = ""
    platform_strategies: dict[str, PlatformStrategy] = Field(default_factory=dict)


class PostDraft(BaseModel):
    platform: str
    content: str
    hashtags: Optional[str] = None
    iteration: int = 0


class EvaluationResult(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = False
    feedback: dict[str, str] = Field(default_factory=dict)
    trajectory_signal: str = "refine"


class GeneratedPost(BaseModel):
    id: Optional[int] = None
    company_id: int
    job_id: int
    platform: str
    content: str
    hashtags: Optional[str] = None
    final_score: float = 0.0
    iterations: int = 0
    passed_eval: bool = False
    created_at: Optional[datetime] = None
