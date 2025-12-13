from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from config import Config, Txt
from .user_limits import user_limits
import urllib.parse

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def check_limit_before_rename(client, message):
    """Check user limit before processing file"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if user_id in Config.ADMIN:
        return  # Allow admin to continue
    
    # Check user limit
    can_proceed, token_info = await user_limits.check_user_limit(user_id)
    
    if not can_proceed:
        # Send ad message
        await send_ad_message(client, message)
        return
    
    # Increment file count
    user_limits.increment_file_count(user_id)

async def send_ad_message(client, message):
    """Send ad message to user with token button"""
    user = message.from_user
    
    # Generate ad link with token
    token = user_limits.generate_token(user.id)
    ad_base_url = "https://your-ad-server.com"  # Replace with your actual ad server
    ad_params = {
        'user_id': user.id,
        'token': token,
        'ref': 'telegram_bot'
    }
    ad_link = f"{ad_base_url}?{urllib.parse.urlencode(ad_params)}"
    
    # Create message text
    message_text = f"Hey {user.first_name} 💌\n\n"
    message_text += "Temporary Token has expired. Kindly generate a new temp token to start using the bot again.\n\n"
    message_text += "Validity: 30 minutes"
    
    # Create buttons
    buttons = [
        [InlineKeyboardButton("Get Token", url=ad_link)],
        [InlineKeyboardButton("Tutorial", url="https://t.me/N4_Society/82")],
        [InlineKeyboardButton("ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ", callback_data="premiumx")]
    ]
    
    # Send message
    await message.reply_text(
        text=message_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("^verify_token_"))
async def verify_token_callback(client, callback_query: CallbackQuery):
    """Handle token verification from ad link"""
    user_id = callback_query.from_user.id
    token = callback_query.data.replace("verify_token_", "")
    
    if user_limits.verify_token(user_id, token):
        # Token is valid, reset file count
        user_limits.reset_file_count(user_id)
        
        await callback_query.answer("✅ Token verified! You can now use the bot for 30 minutes.", show_alert=True)
        
        # Edit message to show success
        await callback_query.message.edit_text(
            text=f"✅ Token Verified Successfully!\n\n"
                 f"You can now use the bot for the next 30 minutes.\n\n"
                 f"Files processed: 0/12",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Start Using Bot", callback_data="home")]
            ])
        )
    else:
        await callback_query.answer("❌ Invalid or expired token!", show_alert=True)

@Client.on_message(filters.private & filters.command("mystats"))
async def show_user_stats(client, message):
    """Show user's current stats and token status"""
    user_id = message.from_user.id
    
    if user_id in Config.ADMIN:
        await message.reply_text("👑 You are an admin - No limits apply!")
        return
    
    file_count = user_limits.user_file_counts.get(user_id, 0)
    token_status = user_limits.get_token_status(user_id)
    
    message_text = f"📊 **Your Usage Stats**\n\n"
    message_text += f"📁 Files processed: {file_count}/12\n\n"
    
    if token_status:
        if token_status['is_valid']:
            message_text += f"✅ **Active Token**\n"
            message_text += f"⏰ Expires in: {token_status['minutes_left']} minutes\n"
        else:
            message_text += f"❌ **Token Expired**\n"
            message_text += "You need to get a new token to continue.\n"
    else:
        message_text += "❌ **No Active Token**\n"
        
        if file_count >= 12:
            message_text += "You've reached the limit. Get a token to continue!\n"
    
    buttons = []
    if file_count >= 12 and (not token_status or not token_status['is_valid']):
        # Generate ad link
        token = user_limits.generate_token(user_id)
        ad_base_url = "https://your-ad-server.com"
        ad_params = {
            'user_id': user_id,
            'token': token,
            'ref': 'stats_command'
        }
        ad_link = f"{ad_base_url}?{urllib.parse.urlencode(ad_params)}"
        buttons.append([InlineKeyboardButton("Get Token", url=ad_link)])
    
    buttons.append([InlineKeyboardButton("Tutorial", url="https://t.me/N4_Society/82")])
    
    await message.reply_text(
        text=message_text,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )
