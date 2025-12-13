import asyncio
import time
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from aiohttp import web
from route import web_server
import pyrogram.utils
import pyromod
import os

asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
pyrogram.utils.MIN_CHANNEL_ID = -1001896877147

SUPPORT_CHAT = int(os.environ.get("SUPPORT_CHAT", "-1001896877147"))

class Bot(Client):

    def __init__(self):
        super().__init__(
            name="codeflixbots",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins={"root": "plugins"},
            workers=100
        )
        self.start_time = time.time()

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        print(f"{me.first_name} Is Started.....✨️")

        uptime = str(timedelta(seconds=int(time.time() - self.start_time)))

        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                await self.send_photo(
                    chat_id=chat_id,
                    photo=Config.START_PIC,
                    caption=f"Bot Restarted\nUptime: `{uptime}`",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Updates", url="https://t.me/animelibraryn4")]]
                    )
                )
            except:
                pass

Bot().run()
