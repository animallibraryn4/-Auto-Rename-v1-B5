import aiohttp, asyncio, warnings, pytz
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server
import pyrogram.utils
import pyromod
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

pyrogram.utils.MIN_CHANNEL_ID = -1001896877147

# Setting SUPPORT_CHAT directly here
SUPPORT_CHAT = int(os.environ.get("SUPPORT_CHAT", "-1001896877147"))

def fix_database_permissions():
    """Fix SQLite database permission issues"""
    try:
        # Create sessions directory with proper permissions
        session_dir = Path("sessions")
        session_dir.mkdir(exist_ok=True)
        
        # Fix permissions
        os.system("chmod 755 sessions")
        
        # Create a test database to check permissions
        test_db = session_dir / "test.db"
        try:
            conn = sqlite3.connect(str(test_db))
            conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")
            conn.commit()
            conn.close()
            print("✓ Database permissions are working")
            # Clean up test file
            if test_db.exists():
                test_db.unlink()
        except Exception as e:
            print(f"⚠ Database test failed: {e}")
            # Try alternative permissions
            os.system("chmod 777 sessions")
            
    except Exception as e:
        print(f"⚠ Error fixing permissions: {e}")

# Fix permissions before starting
fix_database_permissions()

class Bot(Client):

    def __init__(self):
        # Ensure sessions directory exists
        os.makedirs("sessions", exist_ok=True)
        
        super().__init__(
            name="codeflixbots",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
            workdir="sessions"  # ADD THIS LINE - MOST IMPORTANT
        )
        # Initialize the bot's start time for uptime calculation
        self.start_time = time.time()

    async def start(self):
        try:
            await super().start()
            me = await self.get_me()
            self.mention = me.mention
            self.username = me.username  
            self.uptime = Config.BOT_UPTIME     
            
            if Config.WEBHOOK:
                app = web.AppRunner(await web_server())
                await app.setup()       
                await web.TCPSite(app, "0.0.0.0", 9090).start()     
            
            print(f"✅ {me.first_name} Is Started Successfully! ✓✓✓")
            print(f"📁 Session stored in: {os.path.abspath('sessions')}")

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
                            "**🎉 Bot Started Successfully!**\n\n"
                            f"**Bot Name:** {me.first_name}\n"
                            f"**Username:** @{me.username}\n"
                            f"**ID:** `{me.id}`\n"
                            f"**Version:** {__version__}\n"
                            f"**Uptime:** `{uptime_string}`\n\n"
                            f"📅 **Date:** {date}\n"
                            f"🕒 **Time:** {time_str}"
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [[
                                InlineKeyboardButton("📢 Channel", url="https://t.me/animelibraryn4")
                            ]]
                        )
                    )
                    print(f"✅ Startup message sent to chat {chat_id}")

                except Exception as e:
                    print(f"⚠ Failed to send message in chat {chat_id}: {e}")
                    
        except sqlite3.OperationalError as e:
            print(f"❌ Database Error: {e}")
            print("Trying alternative solution...")
            await self.fix_database_error()
        except Exception as e:
            print(f"❌ Startup Error: {e}")

    async def fix_database_error(self):
        """Alternative method to fix database issues"""
        try:
            print("🔄 Attempting to fix database...")
            
            # Remove old session file if exists
            session_file = Path("sessions/codeflixbots.session")
            if session_file.exists():
                backup_file = Path("sessions/codeflixbots.session.backup")
                session_file.rename(backup_file)
                print("⚠ Old session file backed up")
            
            # Try with new session name
            temp_client = Client(
                name="temp_session",
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                bot_token=Config.BOT_TOKEN,
                workdir="sessions"
            )
            
            await temp_client.start()
            me = await temp_client.get_me()
            print(f"✅ Connected as {me.first_name}")
            await temp_client.stop()
            
            # Now try original client
            print("🔄 Retrying original client...")
            await super().start()
            
        except Exception as e:
            print(f"❌ Could not fix database: {e}")
            print("Please check file permissions or run: chmod 755 sessions")

# Run the bot
if __name__ == "__main__":
    try:
        print("🚀 Starting Bot...")
        print("📂 Creating sessions directory...")
        
        # Ensure directory exists
        if not os.path.exists("sessions"):
            os.makedirs("sessions", mode=0o755)
            print("✅ Created sessions directory")
        
        # Run the bot
        Bot().run()
        
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        print("\n💡 **Troubleshooting Steps:**")
        print("1. Run: mkdir sessions")
        print("2. Run: chmod 755 sessions")
        print("3. Run: chmod 755 *.py")
        print("4. Check if you have write permissions")
