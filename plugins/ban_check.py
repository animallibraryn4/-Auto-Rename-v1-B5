# ban_check.py
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import codeflixbots
from config import Config

async def check_ban(user_id: int) -> bool:
    """Check if user is banned - SIMPLIFIED version"""
    try:
        return await codeflixbots.is_user_banned(user_id)
    except:
        return False

async def ban_check_middleware(client: Client, message: Message):
    """Middleware to check if user is banned before processing any message"""
    
    # Skip if user is admin
    if message.from_user.id in Config.ADMIN:
        return
    
    # Skip /start command (handled separately)
    if message.text and message.text.startswith("/start"):
        return
    
    # Check if user is banned
    try:
        if await check_ban(message.from_user.id):
            await message.reply_text(
                "🚫 **You are banned and cannot use this bot.**\n\n"
                "If you want access, request permission from @Anime_Library_N4."
            )
            return True  # Stop further processing
    except:
        pass  # If there's an error checking ban, continue normally
    
    return False

# Register the middleware
@Client.on_message(filters.private & ~filters.command("start"))
async def global_ban_check(client: Client, message: Message):
    """Global ban check for all private messages except /start"""
    return await ban_check_middleware(client, message)
