"""Per-reel vision analysis and optional niche summary.

Environment:
  OPENAI_API_KEY - required for AI routes.
  OPENAI_MODEL - vision model (default ``gpt-4o``).
  OPENAI_SUMMARY_MODEL - text-only niche digest (default ``gpt-4o-mini``).
  AI_MAX_REELS - cap reels sent to vision API per run (default ``10``).
  OPENAI_FRAMES_PER_REEL - JPEG samples per reel after thumbnail (default ``2``).
  AI_THUMBNAIL_ONLY - if ``true``, skip downloading video frames (default ``false``).
  AI_NICHE_SUMMARY_ENABLED - if ``true``, run extra text-only niche overview (default ``false``).
"""

import os

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from core.schemas import ReelAnalysis, ReelMeta
from services.video_service import get_reel_images

SYSTEM_PROMPT_REEL = """You are an expert in Instagram Reels and short-form video strategy.
You will receive reel metadata and a few visual frames (thumbnail plus sampled frames).
Analyze one reel and respond in concise English.

Required fields:
- topic: Main topic and niche in 1-2 sentences.
- hook: Attention trigger in the first 1-3 seconds, with concrete cues.
- why_it_worked: Why this reel performed well, grounded in available metadata and visuals.
- creator_script: Practical script template with structure, beat order, and CTA.

If visual context is limited, use only observed details and avoid fabricated claims."""

CAPTION_MAX = 150
HASHTAG_MAX = 5


class NicheSummaryOut(BaseModel):
    """Structured niche overview for a text-only follow-up."""

    summary: str = Field(..., description="Short niche overview in English (3-6 sentences)")


def _get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return AsyncOpenAI(api_key=api_key)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _reel_text(reel: ReelMeta) -> str:
    parts = [f"@{reel.username}"]
    parts.append(f"Views: {reel.views:,}")
    if reel.likes is not None:
        parts.append(f"Likes: {reel.likes:,}")
    if reel.comments is not None:
        parts.append(f"Comments: {reel.comments:,}")
    if reel.duration:
        parts.append(f"Duration: {reel.duration}s")
    if reel.music:
        parts.append(f"Music: {reel.music}")
    if reel.hashtags:
        tags = reel.hashtags[:HASHTAG_MAX]
        parts.append("Hashtags: " + " ".join("#" + str(h).lstrip("#") for h in tags))
    if reel.caption:
        caption = reel.caption.strip()
        if len(caption) > CAPTION_MAX:
            caption = caption[:CAPTION_MAX] + "..."
        parts.append(f"Caption: {caption}")
    return " | ".join(parts)


async def _build_user_content_single(reel: ReelMeta) -> list[dict]:
    content: list[dict] = [
        {"type": "text", "text": "Analyze this viral reel:\n" + _reel_text(reel)},
    ]
    images = await get_reel_images(reel.video_url, reel.thumbnail_url)
    for b64 in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "low",
                },
            }
        )
    return content


async def analyze_single_reel(reel: ReelMeta) -> ReelAnalysis:
    client = _get_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    user_content = await _build_user_content_single(reel)

    completion = await client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_REEL},
            {"role": "user", "content": user_content},
        ],
        response_format=ReelAnalysis,
        temperature=0.55,
    )
    message = completion.choices[0].message
    if message.refusal:
        raise RuntimeError(f"Model refusal: {message.refusal}")
    parsed = message.parsed
    if not parsed:
        raise RuntimeError("Empty model response")
    return parsed


async def generate_reel_analyses(pairs: list[tuple[int, ReelMeta]]) -> list[tuple[int, ReelAnalysis]]:
    """One vision call per reel. Input pairs are (reel_id, reel_meta)."""
    out: list[tuple[int, ReelAnalysis]] = []
    for reel_id, meta in pairs:
        analysis = await analyze_single_reel(meta)
        out.append((reel_id, analysis))
    return out


async def maybe_niche_summary(metas: list[ReelMeta]) -> str | None:
    if not _bool_env("AI_NICHE_SUMMARY_ENABLED", False) or not metas:
        return None

    client = _get_client()
    summary_model = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
    lines = [_reel_text(meta) for meta in metas]
    user_text = (
        "Here is compact metadata for selected viral reels (no images). "
        "Provide a concise niche summary: repeated themes, recurring hooks, and what is currently working. "
        "Return the answer in the summary field only.\n\n"
        + "\n\n".join(f"- {line}" for line in lines)
    )

    completion = await client.chat.completions.parse(
        model=summary_model,
        messages=[
            {"role": "system", "content": "You are a short-form content analyst. Keep the answer concise."},
            {"role": "user", "content": user_text},
        ],
        response_format=NicheSummaryOut,
        temperature=0.4,
    )
    message = completion.choices[0].message
    parsed = message.parsed
    if not parsed:
        return None
    return parsed.summary
