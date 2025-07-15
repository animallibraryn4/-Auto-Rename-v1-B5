from pyrogram import Client, filters, types
from pyrogram.errors import RPCError, MessageIdInvalid, MessageNotModified
from config import Config
from typing import Dict, Optional
import re
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-wise memory for storing links
user_links: Dict[int, Dict[str, str]] = {}

def is_valid_telegram_link(link: str) -> bool:
    """Check if the link is a valid Telegram link"""
    patterns = [
        r'^(?:https?://)?(?:www\.)?t\.me/(?:c/\d+|[\w]+)(?:/\d+)?$',
        r'^(?:https?://)?(?:www\.)?t\.me/\+[\w-]+$',
        r'^(?:https?://)?(?:www\.)?t\.me/joinchat/[\w-]+$',
        r'^(?:https?://)?(?:www\.)?t\.me/\w+$'
    ]
    link = link.strip().lower()
    return any(re.match(pattern, link) for pattern in patterns)

def normalize_link(link: str) -> str:
    """Normalize links to consistent format"""
    link = link.strip().lower()
    if link.startswith(('http://', 'https://')):
        link = link.split('//')[1]
    if link.startswith('www.'):
        link = link[4:]
    return link.replace('joinchat/', '+')

async def can_edit_message(client: Client, chat_id: int, message_id: int) -> bool:
    """Check if we can edit this message"""
    try:
        # First check if message exists
        msg = await client.get_messages(chat_id, message_ids=message_id)
        if not msg:
            return False
            
        # Check message age
        message_age = time.time() - msg.date.timestamp()
        if message_age > 172800:  # 48 hours
            return False
            
        # Try a dummy edit
        await client.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=msg.reply_markup
        )
        return True
    except Exception as e:
        logger.error(f"Can't edit message: {e}")
        return False

@Client.on_message(filters.command("postlink") & filters.user(Config.ADMIN))
async def post_link_command(client: Client, message: types.Message):
    """Initialize link replacement process"""
    if not message.reply_to_message:
        return await message.reply("⚠️ Please reply to the target message with buttons.")
    
    target_msg = message.reply_to_message
    
    if not target_msg.reply_markup:
        return await message.reply("⚠️ The replied message has no inline buttons.")
    
    # Verify edit permissions
    if not await can_edit_message(client, target_msg.chat.id, target_msg.id):
        return await message.reply("""⚠️ Cannot edit this message. Possible reasons:
1. Message doesn't exist
2. I don't have edit permissions
3. Message is too old (>48 hours)
4. Message is in a private chat where I'm not admin""")
    
    user_id = message.from_user.id
    user_links[user_id] = {
        "chat_id": target_msg.chat.id,
        "message_id": target_msg.id,
        "buttons": target_msg.reply_markup.inline_keyboard,
        "original_markup": target_msg.reply_markup  # Store original markup
    }
    
    await message.reply("✅ Message registered. Now use:\n"
                       "/oldlink [current_url]\n"
                       "/newlink [replacement_url]")

@Client.on_message(filters.command("oldlink") & filters.user(Config.ADMIN))
async def old_link_command(client: Client, message: types.Message):
    """Set the URL pattern to be replaced"""
    if len(message.command) < 2:
        return await message.reply("⚠️ Please provide the URL to replace.")
    
    user_id = message.from_user.id
    if user_id not in user_links:
        return await message.reply("⚠️ Please use /postlink first.")
    
    old_link = message.text.split(maxsplit=1)[1]
    if not is_valid_telegram_link(old_link):
        return await message.reply("⚠️ Invalid Telegram link format.")
    
    user_links[user_id]["old_link"] = normalize_link(old_link)
    await message.reply(f"🔗 Old link set: {user_links[user_id]['old_link']}\n"
                       "Now use /newlink [replacement_url]")

@Client.on_message(filters.command("newlink") & filters.user(Config.ADMIN))
async def new_link_command(client: Client, message: types.Message):
    """Set the new URL and perform the replacement"""
    if len(message.command) < 2:
        return await message.reply("⚠️ Please provide the new URL.")
    
    user_id = message.from_user.id
    if user_id not in user_links:
        return await message.reply("⚠️ Please use /postlink first.")
    
    if "old_link" not in user_links[user_id]:
        return await message.reply("⚠️ Please set the old link with /oldlink first.")
    
    new_link = message.text.split(maxsplit=1)[1]
    if not is_valid_telegram_link(new_link):
        return await message.reply("⚠️ Invalid Telegram link format.")
    
    # Get stored data
    data = user_links[user_id]
    normalized_old = data["old_link"]
    normalized_new = normalize_link(new_link)
    
    # Create new keyboard with replaced URLs
    new_keyboard = []
    replacements = 0
    
    for row in data["buttons"]:
        new_row = []
        for button in row:
            if hasattr(button, "url"):
                normalized_button_url = normalize_link(button.url)
                if normalized_old in normalized_button_url:
                    # Preserve original URL structure
                    if button.url.startswith('http'):
                        new_url = button.url.replace(
                            normalized_old,
                            normalized_new
                        )
                    else:
                        prefix = "https://t.me/"
                        if '+' in normalized_new:  # For invite links
                            new_url = f"{prefix}{normalized_new}"
                        else:
                            new_url = f"{prefix}{normalized_new}"
                    
                    new_row.append(types.InlineKeyboardButton(
                        text=button.text,
                        url=new_url
                    ))
                    replacements += 1
                    continue
            new_row.append(button)
        new_keyboard.append(new_row)
    
    if replacements == 0:
        return await message.reply("⚠️ No matching links found in the buttons.")
    
    # Attempt to edit the message
    try:
        # First try with the new keyboard
        await client.edit_message_reply_markup(
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            reply_markup=types.InlineKeyboardMarkup(new_keyboard)
        )
        await message.reply(f"✅ Successfully replaced {replacements} link(s)!")
    except MessageNotModified:
        await message.reply("⚠️ The buttons already have this URL.")
    except MessageIdInvalid:
        # Fallback: Try to send as new message if edit fails
        try:
            original_msg = await client.get_messages(
                chat_id=data["chat_id"],
                message_ids=data["message_id"]
            )
            if original_msg:
                await client.send_message(
                    chat_id=data["chat_id"],
                    text=f"Updated version of message ({original_msg.text or original_msg.caption or ''})",
                    reply_markup=types.InlineKeyboardMarkup(new_keyboard)
                )
                await message.reply("⚠️ Couldn't edit original message. Sent as new message instead.")
        except Exception as e:
            await message.reply(f"⚠️ Failed completely: {str(e)}")
    except RPCError as e:
        await message.reply(f"⚠️ Error: {str(e)}")
    finally:
        user_links.pop(user_id, None)

@Client.on_message(filters.command("clearlinks") & filters.user(Config.ADMIN))
async def clear_links_command(client: Client, message: types.Message):
    """Clear any stored link data for the user"""
    user_id = message.from_user.id
    if user_id in user_links:
        user_links.pop(user_id)
        await message.reply("✅ Cleared your stored link data.")
    else:
        await message.reply("ℹ️ No link data to clear.")
