from pyrogram import filters
from pyrogram.types import Message
from helper.database import codeflixbots
from config import Txt, Config

async def ban_check_filter(_, client, message: Message):
    """
    Custom Pyrogram filter to check for banned users on every message.
    Returns True if the message should be processed (user is not banned or is an admin).
    Returns False if the message should be ignored (user is banned).
    """
    
    if not message.from_user:
        return True # Allow messages without a user (e.g., channel posts/updates)

    user_id = message.from_user.id

    # 1. Admins are always allowed to use the bot, even if they somehow got banned.
    if user_id in Config.ADMIN:
        return True
            
    # 2. Check ban status from the database
    is_banned = await codeflixbots.is_banned(user_id)
    
    if is_banned:
        # Send the required ban message to the user
        try:
            await message.reply_text(Txt.BAN_MSG, quote=True)
        except Exception as e:
            # Ignore if the bot can't send a message (e.g., user blocked the bot)
            print(f"Error sending ban message to {user_id}: {e}")
            
        return False # Stop message propagation: the message will not be processed by any other handler
        
    return True # User is not banned, allow the message to proceed

# Instantiate the filter object for easy import
is_not_banned_filter = filters.create(ban_check_filter)

