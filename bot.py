import aiohttp, asyncio, warnings, pytz
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server
import pyrogram.utils
import pyromod
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import time
from helper.database import codeflixbots  # Import database

pyrogram.utils.MIN_CHANNEL_ID = -1001896877147

# Setting SUPPORT_CHAT directly here
SUPPORT_CHAT = int(os.environ.get("SUPPORT_CHAT", "-1001896877147"))

class Bot(Client):

    def __init__(self):
        super().__init__(
            name="codeflixbots",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )
        # Initialize the bot's start time for uptime calculation
        self.start_time = time.time()
        
    async def cleanup_expired_premium_periodically(self):
        """Periodically clean up expired premium users"""
        print("[PREMIUM] Cleanup task started")
        while True:
            try:
                expired_count = await codeflixbots.cleanup_expired_premium()
                if expired_count > 0:
                    print(f"[PREMIUM CLEANUP] Removed {expired_count} expired premium users")
            except Exception as e:
                print(f"[PREMIUM CLEANUP ERROR] {e}")
            
            # Run cleanup every 1 hour
            await asyncio.sleep(3600)

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username  
        self.uptime = Config.BOT_UPTIME     
        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()       
            await web.TCPSite(app, "0.0.0.0", 9090).start()     
        print(f"{me.first_name} Is Started.....вЬ®пЄП")

        # Start the cleanup task for expired premium users
        asyncio.create_task(self.cleanup_expired_premium_periodically())

        # Calculate uptime using timedelta
        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time_str = curr.strftime('%I:%M:%S %p')
                
                # Send the message with the photo
                await self.send_photo(
                    chat_id=chat_id,
                    photo=Config.START_PIC,
                    caption=(
                        "**біА…і ПбіА …™s  АбіЗsбіЫбіА АбіЫбіЗбіЕ біА…ҐбіА…™…і  !**\n\n"
                        f"…™ біЕ…™біЕ…і'біЫ s ЯбіЗбіШбіЫ s…™…ібіДбіЗ: `{uptime_string}`"
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton("біЬбіШбіЕбіАбіЫбіЗs", url="https://t.me/animelibraryn4")
                        ]]
                    )
                )

            except Exception as e:
                print(f"Failed to send message in chat {chat_id}: {e}")

Bot().run()
