import aiohttp, asyncio, warnings, pytz
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client, __version__, filters, idle
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server
import pyrogram.utils
import pyromod
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import time

pyrogram.utils.MIN_CHANNEL_ID = -1001896877147

# Setting SUPPORT_CHAT directly here
SUPPORT_CHAT = int(os.environ.get("SUPPORT_CHAT", "-1001896877147"))

bot = Client(
    name="codeflixbots",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=200,
    plugins={"root": "plugins"},
    sleep_threshold=15,
)

# Initialize the bot's start time for uptime calculation
bot.start_time = time.time()

async def check_user_ban_status(user_id):
    """Check if a user is banned"""
    try:
        from helper.database import codeflixbots
        return await codeflixbots.is_banned(user_id)
    except ImportError:
        return False

@bot.on_message(filters.private & ~filters.user(Config.ADMIN))
async def check_banned_user(client, message):
    """Global ban check for all incoming messages"""
    user_id = message.from_user.id
    
    # Check if user is banned
    is_banned = await check_user_ban_status(user_id)
    
    if is_banned:
        # Get ban info to show reason
        try:
            from helper.database import codeflixbots
            ban_info = await codeflixbots.get_ban_info(user_id)
            ban_reason = ban_info.get('ban_reason', 'No reason provided') if ban_info else 'No reason provided'
            
            await message.reply_text(
                "🚫 **You are banned and cannot use this bot.**\n\n"
                f"**Reason:** {ban_reason}\n\n"
                "If you want access, please contact @Anime_Library_N4 for permission."
            )
        except:
            await message.reply_text(
                "🚫 **You are banned and cannot use this bot.**\n\n"
                "If you want access, please contact @Anime_Library_N4 for permission."
            )
        
        # Stop further processing
        raise StopPropagation

@bot.on_start()
async def on_start():
    me = await bot.get_me()
    bot.mention = me.mention
    bot.username = me.username  
    bot.uptime = Config.BOT_UPTIME     
    
    if Config.WEBHOOK:
        app = web.AppRunner(await web_server())
        await app.setup()       
        await web.TCPSite(app, "0.0.0.0", 9090).start()     
    
    print(f"{me.first_name} Is Started.....✨️")

    # Calculate uptime using timedelta
    uptime_seconds = int(time.time() - bot.start_time)
    uptime_string = str(timedelta(seconds=uptime_seconds))

    for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
        try:
            curr = datetime.now(timezone("Asia/Kolkata"))
            date = curr.strftime('%d %B, %Y')
            time_str = curr.strftime('%I:%M:%S %p')
            
            # Send the message with the photo
            await bot.send_photo(
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

        except Exception as e:
            print(f"Failed to send message in chat {chat_id}: {e}")

if __name__ == "__main__":
    bot.run()
