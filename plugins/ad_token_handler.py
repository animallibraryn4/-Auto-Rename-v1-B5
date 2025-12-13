# plugins/token_handler.py - Complete token system

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from config import Config, Txt
from .user_limits import user_limits
import asyncio

class TokenSystem:
    def __init__(self):
        self.pending_verifications = {}
    
    async def check_and_process(self, client, message):
        """Check limit and process or show token message"""
        user_id = message.from_user.id
        
        # Skip for admins
        if str(user_id) in map(str, Config.ADMIN) or user_id in Config.ADMIN:
            return True
        
        # Check limit
        can_proceed, token_info = await user_limits.check_user_limit(user_id)
        
        if not can_proceed:
            await self.send_token_message(client, message)
            return False
        return True
    
    async def send_token_message(self, client, message):
        """Send token request message"""
        user = message.from_user
        
        # Generate token
        token = user_limits.generate_token(user.id)
        
        # Create message text
        message_text = f"Hey {user.first_name or user.id} 💌\n\n"
        message_text += "**Temporary Token has expired!**\n\n"
        message_text += "You've processed 12 files. Generate a new temp token to continue using the bot.\n\n"
        message_text += "**Validity:** 30 minutes\n\n"
        message_text += f"**Your Token:** `{token}`"
        
        # Create buttons
        buttons = [
            [InlineKeyboardButton("✅ Verify Token", callback_data=f"verify_token_{token}")],
            [InlineKeyboardButton("📖 Tutorial", url="https://t.me/N4_Society/82")],
            [InlineKeyboardButton("ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ", callback_data="premiumx")]
        ]
        
        # Send message
        await message.reply_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    
    async def verify_token(self, client, callback_query, token):
        """Verify token from callback"""
        user_id = callback_query.from_user.id
        
        if user_limits.verify_token(user_id, token):
            # Token is valid, reset file count
            user_limits.reset_file_count(user_id)
            
            await callback_query.answer("✅ Token verified! You can now use the bot for 30 minutes.", show_alert=True)
            
            # Edit message to show success
            await callback_query.message.edit_text(
                text=f"**✅ Token Verified Successfully!**\n\n"
                     f"Hey {callback_query.from_user.first_name or callback_query.from_user.id},\n\n"
                     f"You can now use the bot for the next **30 minutes**.\n\n"
                     f"**Files processed:** 0/12\n\n"
                     f"Start sending files to rename!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Start Using Bot", callback_data="home")]
                ])
            )
            return True
        else:
            await callback_query.answer("❌ Invalid or expired token! Generate a new one.", show_alert=True)
            
            # Show new token
            new_token = user_limits.generate_token(user_id)
            await callback_query.message.edit_text(
                text=f"**❌ Token Expired!**\n\n"
                     f"Your token was invalid or expired. Here's a new one:\n\n"
                     f"**New Token:** `{new_token}`\n\n"
                     f"Click below to verify:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Verify New Token", callback_data=f"verify_token_{new_token}")],
                    [InlineKeyboardButton("📖 Tutorial", url="https://t.me/N4_Society/82")],
                ])
            )
            return False

# Create global instance
token_system = TokenSystem()

# Handler for checking limits on file messages
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def check_limit_handler(client, message):
    """Check limit before processing files"""
    can_proceed = await token_system.check_and_process(client, message)
    
    # If user can proceed, the file will be processed by auto_rename_files
    # If not, token message is sent and processing stops
    return can_proceed

# Handler for token verification callback
@Client.on_callback_query(filters.regex(r"^verify_token_"))
async def token_callback_handler(client, callback_query: CallbackQuery):
    """Handle token verification callbacks"""
    token = callback_query.data.replace("verify_token_", "")
    await token_system.verify_token(client, callback_query, token)

# Command to show user stats
@Client.on_message(filters.private & filters.command("mystats"))
async def show_stats_command(client, message):
    """Show user's current stats"""
    user_id = message.from_user.id
    
    if str(user_id) in map(str, Config.ADMIN) or user_id in Config.ADMIN:
        await message.reply_text("👑 **You are an admin** - No limits apply!")
        return
    
    file_count = user_limits.user_file_counts.get(user_id, 0)
    token_status = user_limits.get_token_status(user_id)
    
    message_text = f"📊 **Your Usage Stats**\n\n"
    message_text += f"📁 **Files processed:** `{file_count}/12`\n\n"
    
    if token_status:
        if token_status['is_valid']:
            message_text += f"✅ **Active Token**\n"
            message_text += f"⏰ **Expires in:** {token_status['minutes_left']}m {token_status['seconds_left']}s\n"
            message_text += f"🔄 **Reset count:** {file_count}/12 → 0/12\n"
        else:
            message_text += f"❌ **Token Expired**\n"
            message_text += "You need to generate a new token to continue.\n"
    else:
        message_text += "❌ **No Active Token**\n"
        
        if file_count >= 12:
            message_text += "**You've reached the limit!** Generate a token to continue.\n"
        else:
            message_text += f"**{12 - file_count} files remaining** before token required.\n"
    
    # Add buttons based on status
    buttons = []
    
    if file_count >= 12 and (not token_status or not token_status['is_valid']):
        # Generate token button
        token = user_limits.generate_token(user_id)
        buttons.append([InlineKeyboardButton("🔑 Get New Token", callback_data=f"verify_token_{token}")])
    
    buttons.append([InlineKeyboardButton("📖 Tutorial", url="https://t.me/N4_Society/82")])
    
    if buttons:
        await message.reply_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await message.reply_text(text=message_text)

# Command to manually get token
@Client.on_message(filters.private & filters.command("gettoken"))
async def get_token_command(client, message):
    """Command to get a token"""
    user_id = message.from_user.id
    
    if str(user_id) in map(str, Config.ADMIN) or user_id in Config.ADMIN:
        await message.reply_text("👑 Admins don't need tokens!")
        return
    
    file_count = user_limits.user_file_counts.get(user_id, 0)
    
    if file_count < 12:
        await message.reply_text(
            f"**You don't need a token yet!**\n\n"
            f"Files processed: `{file_count}/12`\n"
            f"You can still process **{12 - file_count} files** without a token."
        )
        return
    
    # Generate and send token
    token = user_limits.generate_token(user_id)
    
    await message.reply_text(
        f"**🔑 Your Token**\n\n"
        f"**Token:** `{token}`\n\n"
        f"**Validity:** 30 minutes\n\n"
        f"Click the button below to verify:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Verify Token", callback_data=f"verify_token_{token}")],
            [InlineKeyboardButton("📖 Tutorial", url="https://t.me/N4_Society/82")]
        ])
    )
