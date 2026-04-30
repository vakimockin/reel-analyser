import logging
import os

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("telegram_bot")

API_BASE = os.getenv("BACKEND_BASE_URL", "http://backend:8000")
BOT_TOKEN = (os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def _allowed_chat_ids() -> set[int]:
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return set()
    return {int(value.strip()) for value in raw.split(",") if value.strip()}


ALLOWED_CHAT_IDS = _allowed_chat_ids()


def _is_allowed(chat_id: int) -> bool:
    if not ALLOWED_CHAT_IDS:
        return True
    return chat_id in ALLOWED_CHAT_IDS


async def _get_json(path: str) -> dict | list:
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not _is_allowed(chat_id):
        await update.message.reply_text("This chat is not allowed to use this bot.")
        return

    text = (
        "Instagram Reels Analyzer Bot\n\n"
        "Commands:\n"
        "/latest - show latest runs\n"
        "/run <id> - show run details\n"
        "/help - show this help"
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_cmd(update, context)


async def latest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not _is_allowed(chat_id):
        await update.message.reply_text("This chat is not allowed to use this bot.")
        return

    try:
        runs = await _get_json("/api/v1/analyses?limit=10&offset=0")
    except Exception as exc:
        await update.message.reply_text(f"Failed to fetch runs: {exc}")
        return

    if not isinstance(runs, list) or not runs:
        await update.message.reply_text("No saved runs found.")
        return

    lines = ["Latest runs:"]
    for run in runs[:10]:
        run_id = run.get("run_id")
        fetched = run.get("total_reels_fetched")
        viral = run.get("viral_reels_count")
        avg = run.get("average_views")
        lines.append(f"#{run_id} | fetched={fetched}, viral={viral}, avg_views={avg}")
    await update.message.reply_text("\n".join(lines))


async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not _is_allowed(chat_id):
        await update.message.reply_text("This chat is not allowed to use this bot.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /run <id>")
        return

    try:
        run_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Run id must be an integer.")
        return

    try:
        data = await _get_json(f"/api/v1/analyses/{run_id}")
    except Exception as exc:
        await update.message.reply_text(f"Failed to fetch run #{run_id}: {exc}")
        return

    lines = [
        f"Run #{data.get('run_id')}",
        f"Fetched reels: {data.get('total_reels_fetched')}",
        f"Viral reels: {data.get('viral_reels_count')}",
        f"Average views: {data.get('average_views')}",
    ]
    if data.get("niche_summary"):
        lines.append("")
        lines.append(f"Niche summary: {data['niche_summary']}")

    analyses = data.get("reel_analyses") or []
    if analyses:
        lines.append("")
        lines.append("Top analyses:")
        for item in analyses[:3]:
            reel = item.get("reel", {})
            analysis = item.get("analysis", {})
            lines.append(
                f"@{reel.get('username')} ({reel.get('views')} views): "
                f"{analysis.get('topic')}"
            )

    await update.message.reply_text("\n".join(lines))


def _build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("latest", latest_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    return app


def main() -> None:
    app = _build_app()
    logger.info("Starting telegram bot polling")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
