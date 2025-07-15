from pyrogram import Client, filters, types
from pyrogram.errors import RPCError
from config import Config
from typing import Dict, Optional
import re

# User-wise memory for storing links
user_links: Dict[int, Dict[str, str]] = {}

@Client.on_message(filters.command("postlink") & filters.user(Config.ADMIN))
async def post_link_command(client: Client, message: types.Message):
    """
    Command to initialize link posting process.
    Usage: /postlink [message with inline buttons]
    """
    if not message.reply_to_message or not message.reply_to_message.reply_markup:
        return await message.reply("Please reply to a message with inline buttons using this command.")
    
    # Store the message ID for later reference
    user_id = message.from_user.id
    if user_id not in user_links:
        user_links[user_id] = {}
    
    user_links[user_id]["message_to_edit"] = message.reply_to_message
    
    await message.reply("Message registered. Now use /oldlink and /newlink to specify the URLs to replace.")

@Client.on_message(filters.command("oldlink") & filters.user(Config.ADMIN))
async def old_link_command(client: Client, message: types.Message):
    """
    Command to set the old link pattern to replace.
    Usage: /oldlink [URL pattern]
    """
    if len(message.command) < 2:
        return await message.reply("Please provide the old link pattern.\nExample: /oldlink t.me/c/123456789/123")
    
    user_id = message.from_user.id
    if user_id not in user_links:
        return await message.reply("Please use /postlink first to register a message.")
    
    old_link = message.text.split(maxsplit=1)[1].strip()
    user_links[user_id]["old_link"] = old_link
    
    await message.reply(f"Old link pattern set to: {old_link}\nNow use /newlink to specify the replacement URL.")

@Client.on_message(filters.command("newlink") & filters.user(Config.ADMIN))
async def new_link_command(client: Client, message: types.Message):
    """
    Command to set the new replacement link and perform the replacement.
    Usage: /newlink [new URL]
    """
    if len(message.command) < 2:
        return await message.reply("Please provide the new link.\nExample: /newlink t.me/c/987654321/456")
    
    user_id = message.from_user.id
    if user_id not in user_links:
        return await message.reply("Please use /postlink first to register a message.")
    
    if "old_link" not in user_links[user_id]:
        return await message.reply("Please set the old link pattern first with /oldlink.")
    
    new_link = message.text.split(maxsplit=1)[1].strip()
    user_links[user_id]["new_link"] = new_link
    
    # Get the stored message
    msg_to_edit = user_links[user_id]["message_to_edit"]
    old_link_pattern = user_links[user_id]["old_link"]
    
    # Process the inline keyboard to replace URLs
    try:
        if not msg_to_edit.reply_markup:
            return await message.reply("The registered message has no inline buttons.")
        
        new_keyboard = []
        for row in msg_to_edit.reply_markup.inline_keyboard:
            new_row = []
            for button in row:
                # Replace URL if it matches the old link pattern
                if hasattr(button, "url") and old_link_pattern in button.url:
                    new_url = button.url.replace(old_link_pattern, new_link)
                    new_button = types.InlineKeyboardButton(
                        text=button.text,
                        url=new_url
                    )
                    new_row.append(new_button)
                else:
                    new_row.append(button)
            new_keyboard.append(new_row)
        
        # Edit the message with the new keyboard
        await client.edit_message_reply_markup(
            chat_id=msg_to_edit.chat.id,
            message_id=msg_to_edit.id,
            reply_markup=types.InlineKeyboardMarkup(new_keyboard)
        )
        
        await message.reply("✅ Links replaced successfully!")
        
        # Clear the user's stored data
        user_links.pop(user_id, None)
        
    except RPCError as e:
        await message.reply(f"Failed to edit message: {e}")
    except Exception as e:
        await message.reply(f"An error occurred: {e}")

def is_private_channel_link(link: str) -> bool:
    """Check if the link is a private Telegram channel link"""
    return bool(re.match(r'^t\.me/c/\d+/\d+$', link))

def is_public_channel_link(link: str) -> bool:
    """Check if the link is a public Telegram channel link"""
    return bool(re.match(r'^t\.me/[a-zA-Z0-9_]+/\d+$', link))
