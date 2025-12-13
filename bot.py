import aiohttp
import asyncio
import warnings
import pytz
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
import sys
import nest_asyncio

# Apply nest_asyncio to fix event loop conflicts
nest_asyncio.apply()

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
            workers=50,  # Reduced from 200
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )
        self.start_time = time.time()

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username  
        self.uptime = Config.BOT_UPTIME     
        
        if Config.WEBHOOK:
            try:
                app = web.AppRunner(await web_server())
                await app.setup()       
                await web.TCPSite(app, "0.0.0.0", 9090).start()
                print("Webhook server started on port 9090")
            except Exception as e:
                print(f"Webhook server error: {e}")
        
        print(f"{me.first_name} Is Started.....✨️")

        # Calculate uptime
        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time_str = curr.strftime('%I:%M:%S %p')
                
                await self.send_photo(
                    chat_id=chat_id,
                    photo=Config.START_PIC,
                    caption=(
                        "**ᴀɴʏᴀ ɪs ʀᴇsᴛᴀʀᴛᴇᴅ ᴀɢᴀɪɴ  !**\n\n"
                        f"ɪ ᴅɪᴅɴ'ᴛ sʟᴇᴘᴛ sɪɴᴄᴇ: `{uptime_string}`"
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇs", url="https://t.me/animelibraryn4")
                        ]]
                    )
                )
                print(f"Restart message sent to chat {chat_id}")

            except Exception as e:
                print(f"Failed to send message in chat {chat_id}: {e}")
        
        print(f"Bot started successfully! Username: @{me.username}")
        return self

    async def stop(self):
        await super().stop()
        print("Bot stopped successfully!")

async def main():
    bot = None
    try:
        bot = Bot()
        await bot.start()
        print("Bot is running. Press Ctrl+C to stop.")
        
        # Keep bot running
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        print("\nReceived stop signal...")
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        if bot:
            await bot.stop()

if __name__ == "__main__":
    # Add nest_asyncio to requirements.txt
    # pip install nest_asyncio
    import nest_asyncio
    nest_asyncio.apply()
    
    asyncio.run(main())
