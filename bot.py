import os
import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN


def _validate_config():
    missing=[]
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if missing:
        raise RuntimeError(
            "Missing required Render environment variable(s): " + ", ".join(missing) +
            ". Add them in Render → Environment, then redeploy. "
            "The bot will not open an interactive phone-number prompt on a server."
        )


_validate_config()


class Bot(Client):
    def __init__(self):
        super().__init__(
            "vj_join_request_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"},
            workers=50,
            sleep_threshold=10,
        )
        self.rich_callback_poller = None

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = "@" + (me.username or "")
        try:
            from plugins.rich_callback_poll import RichCallbackPoller
            self.rich_callback_poller = RichCallbackPoller(self)
            await self.rich_callback_poller.start()
        except Exception as exc:
            print(f"[Rich] callback poller could not start: {exc}")
        print(f"Bot Started: @{me.username or me.id}")

    async def stop(self, *args):
        if self.rich_callback_poller:
            try:
                await self.rich_callback_poller.stop()
            except Exception:
                pass
        await super().stop()
        print("Bot Stopped Bye")


Bot().run()
