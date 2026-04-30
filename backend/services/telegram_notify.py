import os

import httpx

from core.schemas import AnalysisResponse


def _bot_token() -> str:
    return (os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def _chat_id() -> str:
    return (os.getenv("TG_CHAT_ID") or "").strip()


def _is_enabled() -> bool:
    return bool(_bot_token() and _chat_id())


def _build_message(result: AnalysisResponse) -> str:
    lines = [
        "Reels analysis completed",
        f"Run ID: {result.run_id}",
        f"Fetched reels: {result.total_reels_fetched}",
        f"Viral reels: {result.viral_reels_count}",
        f"Average views: {result.average_views}",
        f"Viral threshold: {result.viral_threshold}",
    ]
    if result.niche_summary:
        lines.append("")
        lines.append("Niche summary:")
        lines.append(result.niche_summary)

    analyses = result.reel_analyses[:3]
    if analyses:
        lines.append("")
        lines.append("Top insights:")
        for item in analyses:
            lines.append(f"@{item.reel.username}: {item.analysis.topic}")

    return "\n".join(lines)


async def send_run_notification(result: AnalysisResponse) -> None:
    """Send a non-blocking-safe Telegram notification for a completed run."""
    if not _is_enabled():
        return

    url = f"https://api.telegram.org/bot{_bot_token()}/sendMessage"
    payload = {
        "chat_id": _chat_id(),
        "text": _build_message(result),
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
