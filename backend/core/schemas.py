from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    usernames: list[str] = Field(..., min_length=1, description="Instagram usernames to analyze")
    limit: int = Field(default=15, ge=1, le=50, description="Max reels to fetch per account")


class ReelMeta(BaseModel):
    username: str
    caption: str | None
    duration: float | None
    views: int
    likes: int | None = None
    comments: int | None = None
    hashtags: list[str] = []
    music: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None


class ReelAnalysis(BaseModel):
    """AI output for one reel."""

    topic: str = Field(..., description="Primary topic and niche")
    hook: str = Field(..., description="Opening hook in the first seconds")
    why_it_worked: str = Field(..., description="Key reasons this reel performed well")
    creator_script: str = Field(..., description="Actionable script template for creators")


class ReelAnalysisItem(BaseModel):
    reel_id: int
    reel: ReelMeta
    analysis: ReelAnalysis


class AnalysisResponse(BaseModel):
    run_id: int
    total_reels_fetched: int
    raw_items_count: int | None = None
    raw_preview: list[ReelMeta] = []
    average_views: float
    viral_reels_count: int
    viral_threshold: float
    niche_summary: str | None = None
    viral_reels: list[ReelMeta]
    reel_analyses: list[ReelAnalysisItem]


class AnalysisRunSummary(BaseModel):
    run_id: int
    usernames: list[str]
    total_reels_fetched: int
    average_views: float
    viral_reels_count: int
    created_at: datetime


class ReelDetail(BaseModel):
    id: int
    run_id: int
    username: str
    caption: str | None
    duration: float | None
    views: int


class RegenerateResponse(BaseModel):
    run_id: int
    viral_reels_count: int
    niche_summary: str | None = None
    reel_analyses: list[ReelAnalysisItem]
