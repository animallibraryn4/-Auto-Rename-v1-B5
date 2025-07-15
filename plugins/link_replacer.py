from pyrogram import Client, filters, types
from pyrogram.errors import RPCError, MessageIdInvalid, MessageNotModified
from config import Config
from typing import Dict
import re

# User-wise memory for storing links
user_links: Dict[int, Dict[str, str]] = {}

def is_valid_telegram_link(link: str) -> bool:
    """Check if the link is a valid Telegram link (channel post or invite)"""
    patterns = [
        r'^t\.me/(?:c/\d+|[\w]+)/\d+$',  # Standard channel links
        r'^t\.me/\+[\w-]+$',             # Invite links
        r'^https?://t\.me/\+[\w-]+$',    # HTTPS invite links
        r'^https?://t\.me/(?:c/\d+|[\w]+)/\d+$'  # HTTPS standard links
    ]
    return any(re.match(pattern, link.strip()) for pattern in patterns)

def normalize_link(link: str) -> str:
    """Normalize links to t.me format"""
    link = link.strip()
    if link.startswith(('http://', 'https://')):
        link = link.split('//')[1]  # Remove protocol
    return link.replace('www.', '').lower()

@Client.on_message(filters.command("postlink") & filters.user(Config.ADMIN))
async def post_link_command(client: Client, message: types.Message):
    """Initialize link replacement process"""
    if not message.reply_to_message:
        return await message.reply("⚠️ Please reply to the target message with buttons.")
    
    if not message.reply_to_message.reply_markup:
        return await message.reply("⚠️ The replied message has no inline buttons.")
    
    user_id = message.from_user.id
    user_links[user_id] = {
        "chat_id": message.reply_to_message.chat.id,
        "message_id": message.reply_to_message.id,
        "buttons": message.reply_to_message.reply_markup.inline_keyboard
    }
    
    await message.reply("✅ Message registered. Now use:\n"
                       "/oldlink [current_url]\n"
                       "/newlink [replacement_url]")

@Client.on_message(filters.command("oldlink") & filters.user(Config.ADMIN))
async def old_link_command(client: Client, message: types.Message):
    """Set the URL pattern to be replaced"""
    if len(message.command) < 2:
        return await message.reply("⚠️ Please provide the URL to replace.\n"
                                 "Examples:\n"
                                 "/oldlink t.me/c/123456789/123\n"
                                 "/oldlink t.me/+invite123\n"
                                 "/oldlink https://t.me/+invite123")
    
    user_id = message.from_user.id
    if user_id not in user_links:
        return await message.reply("⚠️ Please use /postlink first.")
    
    old_link = message.text.split(maxsplit=1)[1]
    if not is_valid_telegram_link(old_link):
        return await message.reply("⚠️ Invalid Telegram link format. Supported formats:\n"
                                 "- t.me/c/123456789/123\n"
                                 "- t.me/channelname/123\n"
                                 "- t.me/+invite_code\n"
                                 "- https:// versions of above")
    
    user_links[user_id]["old_link"] = normalize_link(old_link)
    await message.reply(f"🔗 Old link set: {user_links[user_id]['old_link']}\n"
                       "Now use /newlink [replacement_url]")

@Client.on_message(filters.command("newlink") & filters.user(Config.ADMIN))
async def new_link_command(client: Client, message: types.Message):
    """Set the new URL and perform the replacement"""
    if len(message.command) < 2:
        return await message.reply("⚠️ Please provide the new URL.\n"
                                 "Examples:\n"
                                 "/newlink t.me/c/987654321/456\n"
                                 "/newlink t.me/+newinvite456\n"
                                 "/newlink https://t.me/+newinvite456")
    
    user_id = message.from_user.id
    if user_id not in user_links:
        return await message.reply("⚠️ Please use /postlink first.")
    
    if "old_link" not in user_links[user_id]:
        return await message.reply("⚠️ Please set the old link with /oldlink first.")
    
    new_link = message.text.split(maxsplit=1)[1]
    if not is_valid_telegram_link(new_link):
        return await message.reply("⚠️ Invalid Telegram link format.")
    
    normalized_new = normalize_link(new_link)
    normalized_old = user_links[user_id]["old_link"]
    
    # Create new keyboard with replaced URLs
    new_keyboard = []
    replacements = 0
    
    for row in user_links[user_id]["buttons"]:
        new_row = []
        for button in row:
            if hasattr(button, "url"):
                normalized_button_url = normalize_link(button.url)
                if normalized_old in normalized_button_url:
                    # Preserve original URL structure (http/https/www)
                    if button.url.startswith('http'):
                        new_url = button.url.replace(
                            normalize_link(button.url),
                            normalized_new
                        )
                    else:
                        new_url = normalized_new
                    
                    new_row.append(button.__class__(text=button.text, url=new_url))
                    replacements += 1
                    continue
            new_row.append(button)
        new_keyboard.append(new_row)
    
    if replacements == 0:
        return await message.reply("⚠️ No matching links found in the buttons.")
    
    # Attempt to edit the message
    try:
        await client.edit_message_reply_markup(
            chat_id=user_links[user_id]["chat_id"],
            message_id=user_links[user_id]["message_id"],
            reply_markup=types.InlineKeyboardMarkup(new_keyboard)
        )
        await message.reply(f"✅ Successfully replaced {replacements} link(s)!")
    except MessageIdInvalid:
        await message.reply("⚠️ Failed to edit: Invalid message (maybe deleted or I don't have permission)")
    except MessageNotModified:
        await message.reply("⚠️ The buttons already have this URL.")
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
