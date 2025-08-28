import asyncio
import os
from aiohttp import web
from telethon import TelegramClient

# Read API credentials from environment or fallback to placeholders
API_ID = int(os.getenv("TELEGRAM_API_ID", "123456"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "abcd1234abcd1234abcd1234abcd1234")

# Futures used to wait for phone and code from the web form
loop = asyncio.get_event_loop()
phone_fut = loop.create_future()
code_fut = loop.create_future()

# Simple HTML form to request phone number and login code
HTML = """
<form method="post">
  Телефон: <input name="phone"><br>
  Код: <input name="code"><br>
  <button type="submit">Отправить</button>
</form>
"""


async def handler(request: web.Request) -> web.Response:
    """Serve the HTML form and capture submitted data."""
    if request.method == "POST":
        data = await request.post()
        if not phone_fut.done():
            phone_fut.set_result(data.get("phone", ""))
        if not code_fut.done():
            code_fut.set_result(data.get("code", ""))
        return web.Response(text="Данные получены, бот запускается…")
    return web.Response(text=HTML, content_type="text/html")


async def main_async() -> None:
    # Start the web server
    app = web.Application()
    app.router.add_get("/", handler)
    app.router.add_post("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

    # Wait for the user to submit the phone and code through the form
    phone = await phone_fut
    code = await code_fut

    # Authenticate with Telegram using the supplied credentials
    client = TelegramClient("session", API_ID, API_HASH)
    await client.start(phone=lambda: phone, code_callback=lambda: code)

    # Once logged in, shut down the web server and run the client
    await runner.cleanup()
    print("Бот запущен")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main_async())
