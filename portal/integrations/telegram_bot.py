"""
Telegram Bot Integration
────────────────────────
Entry point: users send messages to the Telegram bot,
the bot forwards them to the Orchestrator and replies with the result.

Supported commands:
  /start    — greeting
  /status   — show last N tasks for this chat
  /help     — list capabilities

Usage:
    python -m portal.integrations.telegram_bot
    # or
    from portal.integrations.telegram_bot import run_bot
    run_bot()

Requires:
    TELEGRAM_BOT_TOKEN in .env
    pip install python-telegram-bot
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from portal.orchestrator import Orchestrator  # noqa: E402
from portal.storage import list_tasks  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent.parent / ".env")

try:
    from telegram import Update
    from telegram.constants import ParseMode
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError as exc:
    raise ImportError("Install python-telegram-bot: uv add python-telegram-bot") from exc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_orch: Orchestrator | None = None


def _get_orchestrator() -> Orchestrator:
    global _orch
    if _orch is None:
        _orch = Orchestrator()
    return _orch


# ── Handlers ──────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *AI Portal bot*\n\n"
        "Send me any request and I'll route it to the right AI agent:\n"
        "• Write documents, reports, ad copy\n"
        "• Create leads in CRM\n"
        "• Research markets and competitors\n"
        "• Publish pages to Tilda / Google Docs\n\n"
        "Use /status to see your recent tasks.\n"
        "Use /help for more info.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Available commands:*\n"
        "/start — welcome message\n"
        "/status — recent tasks\n"
        "/help — this message\n\n"
        "*Example requests:*\n"
        "• _Write a Facebook ad for a yoga studio in Kyiv_\n"
        "• _Create a lead: Olena Kovalenko, phone +380501234567_\n"
        "• _Analyse competitors of an online English school_\n"
        "• _Make a Google Doc with a marketing plan for Q2_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    tasks = list_tasks(source_id=chat_id, limit=5)
    if not tasks:
        await update.message.reply_text("No tasks yet. Send me a request!")
        return

    lines = ["*Your recent tasks:*"]
    for t in tasks:
        status_emoji = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(
            t["status"], "❓"
        )
        lines.append(
            f"{status_emoji} `{t['id'][:8]}` — {t.get('agent') or 'pending'} — "
            f"{t['input'][:60]}{'…' if len(t['input']) > 60 else ''}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    text = update.message.text or ""
    if not text.strip():
        return

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Send to orchestrator (blocking — runs in thread pool by python-telegram-bot)
    orch = _get_orchestrator()
    result = orch.handle(source="telegram", source_id=chat_id, text=text)

    # Telegram message limit is 4096 chars
    if len(result) > 4000:
        chunks = [result[i : i + 4000] for i in range(0, len(result), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(result)


# ── Entry point ───────────────────────────────────────────────────────────────


def run_bot(token: str | None = None) -> None:
    """Start the Telegram bot (blocking)."""
    bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise OSError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting Telegram bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()
