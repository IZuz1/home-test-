import os
import json
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict

import httpx
import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

SUBS_FILE = "subscribers.json"
SEEN_FILE = "seen_items.json"

FEEDS = [
    "https://www.anekdot.ru/rss/export20.xml",
    "https://www.anekdot.ru/rss/export_j.xml",
    "https://www.anekdot.ru/rss/export_j_non_burning.xml",
]

USER_AGENT = "TelegramJokeBot/1.0 (+https://www.anekdot.ru/)"

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_subscribers() -> set[int]:
    data = load_json(SUBS_FILE, {"chat_ids": []})
    return set(map(int, data.get("chat_ids", [])))

def save_subscribers(subs: set[int]) -> None:
    save_json(SUBS_FILE, {"chat_ids": sorted(subs)})

def load_seen() -> set[str]:
    data = load_json(SEEN_FILE, {"ids": []})
    return set(data.get("ids", []))

def save_seen(seen: set[str]) -> None:
    save_json(SEEN_FILE, {"ids": sorted(seen)})

def seconds_until_next_top_of_hour() -> float:
    now = datetime.now(timezone.utc)
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return (next_hour - now).total_seconds()

async def fetch_feed(client: httpx.AsyncClient, url: str) -> List[Dict]:
    try:
        resp = await client.get(url, timeout=20)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        items = []
        for e in parsed.entries:
            uid = getattr(e, "id", None) or f"{getattr(e, 'link', '')}::{getattr(e,'title','')}"
            text = getattr(e, "summary", None) or getattr(e, "description", None) or getattr(e, "title", "")
            link = getattr(e, "link", "")
            if text:
                items.append({"id": uid, "text": text.strip(), "link": link})
        return items
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return []

async def get_fresh_joke() -> Dict | None:
    seen = load_seen()
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        tasks = [fetch_feed(client, url) for url in FEEDS]
        buckets = await asyncio.gather(*tasks)
        items = [it for bucket in buckets for it in bucket]

    random.shuffle(items)

    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            save_seen(seen)
            text = f"{it['text']}\n\nИсточник: {it['link'] or 'https://www.anekdot.ru/'}"
            return {"text": text}

    if items:
        it = random.choice(items)
        text = f"{it['text']}\n\nИсточник: {it['link'] or 'https://www.anekdot.ru/'}"
        return {"text": text}

    return None

async def send_joke_to_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    joke = await get_fresh_joke()
    if not joke:
        await context.bot.send_message(chat_id=chat_id, text="Пока нет анекдотов — попробуйте позже.")
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=joke["text"], disable_web_page_preview=True)
    except Exception as e:
        print(f"Failed to send to {chat_id}: {e}")

async def hourly_broadcast(context: ContextTypes.DEFAULT_TYPE) -> None:
    subs = load_subscribers()
    if not subs:
        return
    subs_list = list(subs)
    random.shuffle(subs_list)
    for chat_id in subs_list:
        await send_joke_to_chat(context, chat_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subs = load_subscribers()
    subs.add(update.effective_chat.id)
    save_subscribers(subs)
    await update.message.reply_text(
        "Привет! Шлю короткий анекдот каждый час из RSS Anekdot.ru.\n"
        "Команды: /joke — шутка сейчас, /stop — отписаться."
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subs = load_subscribers()
    chat_id = update.effective_chat.id
    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
        await update.message.reply_text("Готово! Больше не буду писать каждый час. Возвращайтесь с /start.")
    else:
        await update.message.reply_text("Вас нет в списке подписок. Нажмите /start, чтобы подписаться.")

async def joke_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    joke = await get_fresh_joke()
    await update.message.reply_text(joke["text"] if joke else "Пока нет анекдотов — попробуйте позже.", disable_web_page_preview=True)

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("Установите переменную окружения TELEGRAM_TOKEN с токеном от BotFather.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("joke", joke_now))

    first_run = seconds_until_next_top_of_hour()
    app.job_queue.run_repeating(
        hourly_broadcast,
        interval=3600,
        first=first_run,
        name="hourly_jokes"
    )

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    random.seed()
    main()