import os
import json
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import feedparser
from telethon import TelegramClient, events


SUBS_FILE = "subscribers.json"
SEEN_FILE = "seen_items.json"
NEWS_SEEN_FILE = "seen_news.json"

FEEDS = [
    "https://www.anekdot.ru/rss/export20.xml",
    "https://www.anekdot.ru/rss/export_j.xml",
    "https://www.anekdot.ru/rss/export_j_non_burning.xml",
]

NEWS_FEEDS = [
    "https://lenta.ru/rss/news",
    "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
    "https://tass.ru/rss/v2.xml",
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


def load_news_seen() -> set[str]:
    data = load_json(NEWS_SEEN_FILE, {"ids": []})
    return set(data.get("ids", []))


def save_news_seen(seen: set[str]) -> None:
    save_json(NEWS_SEEN_FILE, {"ids": sorted(seen)})


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


async def get_fresh_news() -> Dict | None:
    seen = load_news_seen()
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        tasks = [fetch_feed(client, url) for url in NEWS_FEEDS]
        buckets = await asyncio.gather(*tasks)
        items = [it for bucket in buckets for it in bucket]

    random.shuffle(items)

    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            save_news_seen(seen)
            text = f"{it['text']}\n\nИсточник: {it['link']}"
            return {"text": text}

    if items:
        it = random.choice(items)
        text = f"{it['text']}\n\nИсточник: {it['link']}"
        return {"text": text}

    return None


async def send_news_to_chat(client: TelegramClient, chat_id: int) -> None:
    news = await get_fresh_news()
    if not news:
        await client.send_message(chat_id, "Пока нет новостей — попробуйте позже.")
        return
    try:
        await client.send_message(chat_id, news["text"], link_preview=False)
    except Exception as e:
        print(f"Failed to send news to {chat_id}: {e}")


async def send_joke_to_chat(client: TelegramClient, chat_id: int) -> None:
    joke = await get_fresh_joke()
    if not joke:
        await client.send_message(chat_id, "Пока нет анекдотов — попробуйте позже.")
        return
    try:
        await client.send_message(chat_id, joke["text"], link_preview=False)
    except Exception as e:
        print(f"Failed to send to {chat_id}: {e}")


async def hourly_broadcast_loop(client: TelegramClient) -> None:
    while True:
        await asyncio.sleep(seconds_until_next_top_of_hour())
        subs = load_subscribers()
        if not subs:
            continue
        subs_list = list(subs)
        random.shuffle(subs_list)
        for chat_id in subs_list:
            await send_news_to_chat(client, chat_id)
            await send_joke_to_chat(client, chat_id)


def start_keepalive_server() -> None:
    """Start a tiny HTTP server so the platform detects an open port."""
    port = int(os.environ.get("PORT", 8000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    server = HTTPServer(("0.0.0.0", port), Handler)
    Thread(target=server.serve_forever, daemon=True).start()



async def main_async() -> None:
    api_id = 28972334
    api_hash = "d8e3e17284d08d122f17e64d8699c4c2"
=======

async def main_async() -> None:
    api_id = int(os.environ.get("TELEGRAM_API_ID", "0"))
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError(
            "Установите TELEGRAM_API_ID и TELEGRAM_API_HASH для MTProto клиента."
        )


    session = os.environ.get("TELEGRAM_SESSION", "jokebot")
    client = TelegramClient(session, api_id, api_hash)

    await client.start()

    @client.on(events.NewMessage(pattern="/start"))
    async def handler_start(event):
        subs = load_subscribers()
        subs.add(event.chat_id)
        save_subscribers(subs)
        await event.respond(
            "Привет! Шлю анекдот и новость каждый час из российских RSS.\n"
            "Команды: /joke — шутка сейчас, /news — новость сейчас, /stop — отписаться."
        )

    @client.on(events.NewMessage(pattern="/stop"))
    async def handler_stop(event):
        subs = load_subscribers()
        chat_id = event.chat_id
        if chat_id in subs:
            subs.remove(chat_id)
            save_subscribers(subs)
            await event.respond(
                "Готово! Больше не буду писать каждый час. Возвращайтесь с /start."
            )
        else:
            await event.respond(
                "Вас нет в списке подписок. Нажмите /start, чтобы подписаться."
            )

    @client.on(events.NewMessage(pattern="/joke"))
    async def handler_joke(event):
        joke = await get_fresh_joke()
        await event.respond(
            joke["text"] if joke else "Пока нет анекдотов — попробуйте позже.",
            link_preview=False,
        )

    @client.on(events.NewMessage(pattern="/news"))
    async def handler_news(event):
        news = await get_fresh_news()
        await event.respond(
            news["text"] if news else "Пока нет новостей — попробуйте позже.",
            link_preview=False,
        )

    asyncio.create_task(hourly_broadcast_loop(client))
    start_keepalive_server()
    print("Bot is running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()


def main() -> None:
    random.seed()
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

