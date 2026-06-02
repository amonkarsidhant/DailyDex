#!/usr/bin/env python3
"""Telegram bot for DailyDex — daily digest with friend voting.

Setup:
  1. Create a bot via @BotFather on Telegram, get the token.
  2. Set env var: export TELEGRAM_BOT_TOKEN="your_token_here"
  3. Run: python3 telegram_bot.py

Friends subscribe with /start, get daily digest, and can vote on items.
Votes appear as badges on the DailyDex dashboard.
"""

import hashlib
import json
import logging
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from data_models import IntelligenceDB

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DATA_SCORED_FILE = os.path.join(DATA_DIR, "data_scored.json")
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(DATA_DIR, "data.json"))
URL_MAP_FILE = os.path.join(DATA_DIR, "vote_url_map.json")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TOP_N = 5


# --- URL hash mapping (persisted so votes survive bot restarts) ---

def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _store_url(url: str) -> str:
    """Persist hash→url and return the hash key used in callback_data."""
    h = _url_hash(url)
    try:
        mapping = {}
        if os.path.exists(URL_MAP_FILE):
            with open(URL_MAP_FILE) as f:
                mapping = json.load(f)
        mapping[h] = url
        with open(URL_MAP_FILE, "w") as f:
            json.dump(mapping, f)
    except Exception as e:
        logger.warning(f"Could not persist url map: {e}")
    return h


def _resolve_url(hash_str: str) -> str:
    try:
        with open(URL_MAP_FILE) as f:
            return json.load(f).get(hash_str, "")
    except Exception:
        return ""


# --- Data loading ---

def get_top_items(limit: int = TOP_N) -> list:
    """Load top scored items for the digest."""
    for path in [DATA_SCORED_FILE, DATA_FILE]:
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            all_items = []
            for source in ["github", "youtube", "blogs", "papers", "huggingface", "hackernews"]:
                for item in data.get(source, []):
                    all_items.append({**item, "source_type": source})
            all_items.sort(key=lambda x: x.get("signal_score", 0), reverse=True)
            return all_items[:limit]
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
    return []


# --- Keyboard builder ---

def _item_keyboard(url: str, vote_count: int = 0) -> InlineKeyboardMarkup:
    h = _store_url(url)
    vote_label = f"👍 Vote ({vote_count})" if vote_count else "👍 Vote"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Read →", url=url),
        InlineKeyboardButton(vote_label, callback_data=f"v:{h}"),
        InlineKeyboardButton("Skip", callback_data="skip"),
    ]])


# --- Command handlers ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = IntelligenceDB()
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name or "friend"
    db.add_subscriber(chat_id, name)
    await update.message.reply_text(
        f"Hi {name}! You're subscribed to DailyDex.\n\n"
        "I'll send you the top AI signals each day.\n\n"
        "/digest — get today's picks now\n"
        "/stop — unsubscribe"
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = IntelligenceDB()
    db.remove_subscriber(update.effective_chat.id)
    await update.message.reply_text("Unsubscribed. Use /start to rejoin anytime.")


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = get_top_items()
    if not items:
        await update.message.reply_text(
            "No data yet — refresh the dashboard first, then try again."
        )
        return

    db = IntelligenceDB()
    date_str = datetime.now().strftime("%B %d, %Y")
    await update.message.reply_text(f"DailyDex — {date_str}\nTop {len(items)} AI signals today:")

    for item in items:
        url = item.get("url", "")
        title = item.get("title", "No title")[:100]
        source = item.get("source_type", "").upper()
        score = item.get("signal_score", 0)
        votes = db.get_vote_count(url) if url else 0

        filled = int(score / 10)
        bar = "█" * filled + "░" * (10 - filled)
        text = f"[{source}]\n{title}\n\n{bar} {score}/100"
        if votes:
            text += f"\n👍 {votes} friend{'s' if votes > 1 else ''} voted"

        await update.message.reply_text(
            text,
            reply_markup=_item_keyboard(url, votes) if url else None,
            disable_web_page_preview=True,
        )


# --- Callback handler ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "skip":
        await query.edit_message_reply_markup(None)
        return

    if not query.data.startswith("v:"):
        return

    h = query.data[2:]
    url = _resolve_url(h)
    if not url:
        await query.answer("Could not find this item — try /digest again.", show_alert=True)
        return

    db = IntelligenceDB()
    chat_id = query.from_user.id
    name = query.from_user.first_name or "friend"
    is_new = db.vote_item(url, chat_id, name)
    votes = db.get_vote_count(url)

    if is_new:
        label = f"✓ Voted! ({votes} total)"
    else:
        label = f"Already voted ({votes} total)"

    await query.edit_message_reply_markup(InlineKeyboardMarkup([[
        InlineKeyboardButton("Read →", url=url),
        InlineKeyboardButton(label, callback_data="skip"),
    ]]))


# --- Broadcast (called by dashboard API or cron) ---

async def broadcast_digest(application: Application) -> int:
    """Send the daily digest to all subscribers. Returns count of messages sent."""
    db = IntelligenceDB()
    subscribers = db.get_subscribers()
    items = get_top_items()

    if not items:
        logger.warning("broadcast_digest: no items to send")
        return 0
    if not subscribers:
        logger.info("broadcast_digest: no subscribers yet")
        return 0

    date_str = datetime.now().strftime("%B %d, %Y")
    sent = 0

    for sub in subscribers:
        chat_id = sub["chat_id"]
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=f"DailyDex — {date_str}\nTop {len(items)} AI signals today:",
            )
            for item in items:
                url = item.get("url", "")
                title = item.get("title", "No title")[:100]
                source = item.get("source_type", "").upper()
                score = item.get("signal_score", 0)
                votes = db.get_vote_count(url) if url else 0

                filled = int(score / 10)
                bar = "█" * filled + "░" * (10 - filled)
                text = f"[{source}]\n{title}\n\n{bar} {score}/100"
                if votes:
                    text += f"\n👍 {votes} vote{'s' if votes > 1 else ''}"

                await application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=_item_keyboard(url, votes) if url else None,
                    disable_web_page_preview=True,
                )
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send digest to {chat_id}: {e}")

    logger.info(f"Digest broadcast: {sent}/{len(subscribers)} subscribers reached")
    return sent


# --- App factory (used by main and by Flask API trigger) ---

def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Create a bot via @BotFather and export the token."
        )
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app


if __name__ == "__main__":
    build_application().run_polling()
