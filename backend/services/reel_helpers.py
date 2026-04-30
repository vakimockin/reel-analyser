"""Build API schemas from persisted reel rows."""

import os

from core.schemas import ReelMeta
from db.models import ReelRecord


def _max_ai_reels() -> int:
    raw = os.getenv("AI_MAX_REELS", "10").strip()
    return int(raw) if raw else 10


def reel_meta_from_record(r: ReelRecord) -> ReelMeta:
    tags = r.hashtags
    if tags is None:
        tags = []
    elif not isinstance(tags, list):
        tags = list(tags)
    return ReelMeta(
        username=r.username,
        caption=r.caption,
        duration=r.duration,
        views=r.views,
        likes=r.likes_count,
        comments=r.comments_count,
        hashtags=[str(h).lstrip("#") for h in tags if h],
        music=r.music,
        video_url=r.video_url,
        thumbnail_url=r.thumbnail_url,
    )


def pairs_for_ai(records: list[ReelRecord]) -> list[tuple[int, ReelMeta]]:
    """Top reels by views for per-reel AI, capped by AI_MAX_REELS."""
    ordered = sorted(records, key=lambda r: r.views, reverse=True)
    cap = _max_ai_reels()
    return [(r.id, reel_meta_from_record(r)) for r in ordered[:cap]]
