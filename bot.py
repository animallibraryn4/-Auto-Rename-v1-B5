# bot.py - CORRECTED VERSION
import asyncio
import os
import time
import sys
import nest_asyncio
from datetime import datetime, timedelta
from pytz import timezone

# Apply nest_asyncio first
nest_asyncio.apply()

# NOW import pyrogram
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import pyrogram.utils

# Set MIN_CHANNEL_ID AFTER importing pyrogram.utils
pyrogram.utils.MIN_CHANNEL_ID = -1001896877147

# Now import your config
from config import Config

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setting SUPPORT_CHAT
SUPPORT_CHAT = int(os.environ.get("SUPPORT_CHAT", "-1001896877147"))

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="codeflixbots",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )
        self.start_time = time.time()
        self.is_running = False

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username  
        self.uptime = Config.BOT_UPTIME
        
        print(f"{me.first_name} Is Started.....✨️")
        print(f"Bot started successfully! Username: @{me.username}")
        
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
                        "**ᴀɴʏᴀ ɪs ʀᴇsᴛᴀʀᴛᴇᴅ ᴀɴᴇᴡ !**\n\n"
                        f"ɪ ᴅɪᴅɴ'ᴛ sʟᴇᴘᴛ sɪɴᴄᴇ: `{uptime_string}`"
                    )
                )
                print(f"Restart message sent to chat {chat_id}")

            except Exception as e:
                print(f"Failed to send message in chat {chat_id}: {e}")
        
        self.is_running = True
        return self

    async def stop(self, *args):
        if self.is_running:
            await super().stop()
            self.is_running = False
            print("Bot stopped successfully!")

async def main():
    bot = None
    try:
        bot = Bot()
        await bot.start()
        print("Bot is running. Press Ctrl+C to stop.")
        
        # Keep bot running
        await asyncio.Event().wait()
            
    except KeyboardInterrupt:
        print("\nReceived stop signal...")
    except Exception as e:
        print(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if bot and bot.is_running:
            await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
