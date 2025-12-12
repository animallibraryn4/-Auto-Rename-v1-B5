import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    UserNotParticipant, 
    ChatAdminRequired, 
    ChannelInvalid, 
    ChatIdInvalid
)
from config import Config
from helper.database import codeflixbots

# Store dynamic channels in database
async def set_dynamic_channel(user_id, channel_username):
    """Set dynamic force subscribe channel"""
    await codeflixbots.col.update_one(
        {"_id": user_id},
        {"$set": {"dynamic_channel": channel_username}},
        upsert=True
    )

async def get_dynamic_channel(user_id):
    """Get dynamic force subscribe channel"""
    user = await codeflixbots.col.find_one({"_id": user_id})
    return user.get("dynamic_channel") if user else None

async def remove_dynamic_channel(user_id):
    """Remove dynamic force subscribe channel"""
    await codeflixbots.col.update_one(
        {"_id": user_id},
        {"$unset": {"dynamic_channel": ""}}
    )

@Client.on_message(filters.private & filters.command("focus"))
async def focus_command(client, message: Message):
    """Setup dynamic force subscribe channel"""
    if message.from_user.id not in Config.ADMIN:
        return await message.reply_text("❌ This command is only for admins!")
    
    if len(message.command) < 2:
        await message.reply_text(
            "**📌 How to use /focus command:**\n\n"
            "1. **Add a channel:**\n"
            "   `/focus @channel_username`\n\n"
            "2. **Remove current channel:**\n"
            "   `/focus remove`\n\n"
            "3. **View current channel:**\n"
            "   `/focus view`\n\n"
            "**Note:** You must be admin in the channel!"
        )
        return
    
    action = message.command[1].lower()
    
    if action == "view":
        channel = await get_dynamic_channel(message.from_user.id)
        if channel:
            await message.reply_text(f"**Current Focus Channel:** @{channel}")
        else:
            await message.reply_text("❌ No focus channel set!")
        return
    
    if action == "remove":
        await remove_dynamic_channel(message.from_user.id)
        await message.reply_text("✅ Focus channel removed successfully!")
        return
    
    # Extract channel username
    channel_input = message.command[1]
    
    # Remove @ if present
    channel_username = channel_input.replace("@", "")
    
    # Validate channel username format
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,}$', channel_username):
        await message.reply_text(
            "❌ Invalid channel username format!\n"
            "Username should start with a letter and be at least 5 characters long."
        )
        return
    
    try:
        # Check if bot is admin in the channel
        chat = await client.get_chat(f"@{channel_username}")
        
        # Check if it's a channel
        if chat.type != "channel":
            await message.reply_text("❌ Please provide a channel username, not a group or private chat!")
            return
        
        # Try to get bot's status in channel
        try:
            member = await client.get_chat_member(chat.id, "me")
            if member.status not in ["administrator", "creator"]:
                await message.reply_text(
                    "❌ I'm not admin in this channel!\n"
                    "Please make me admin with:\n"
                    "1. Post Messages permission\n"
                    "2. Delete Messages permission\n"
                    "Then try again."
                )
                return
        except:
            await message.reply_text(
                "❌ I'm not a member of this channel!\n"
                "Please add me to the channel first as admin."
            )
            return
        
        # Ask for forward message
        await message.reply_text(
            f"**Forward a message from @{channel_username} to confirm:**\n\n"
            "Please forward any message from the channel to verify ownership.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data="cancel_focus")]
            ])
        )
        
        # Store temporary data
        await codeflixbots.col.update_one(
            {"_id": message.from_user.id},
            {"$set": {"temp_channel": channel_username}},
            upsert=True
        )
        
    except (ChannelInvalid, ChatIdInvalid):
        await message.reply_text(
            "❌ Channel not found!\n"
            "Please check:\n"
            "1. Channel username is correct\n"
            "2. Channel is public\n"
            "3. I have been added to the channel"
        )
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.forwarded)
async def handle_forwarded_message(client, message: Message):
    """Handle forwarded message for channel verification"""
    user_id = message.from_user.id
    
    # Check if user is in focus setup mode
    user_data = await codeflixbots.col.find_one({"_id": user_id})
    if not user_data or "temp_channel" not in user_data:
        return
    
    channel_username = user_data["temp_channel"]
    
    # Check if forwarded from the same channel
    if not message.forward_from_chat:
        await message.reply_text(
            "❌ Please forward a message from the channel, not from a user!"
        )
        return
    
    forwarded_channel = message.forward_from_chat.username
    if not forwarded_channel or forwarded_channel.lower() != channel_username.lower():
        await message.reply_text(
            f"❌ This message is not from @{channel_username}!\n"
            f"Forwarded from: @{forwarded_channel if forwarded_channel else 'private'}"
        )
        return
    
    # Verification successful
    await set_dynamic_channel(user_id, channel_username)
    
    # Clear temp data
    await codeflixbots.col.update_one(
        {"_id": user_id},
        {"$unset": {"temp_channel": ""}}
    )
    
    await message.reply_text(
        f"✅ **Focus Channel Set Successfully!**\n\n"
        f"**Channel:** @{channel_username}\n"
        f"**Status:** Active\n\n"
        f"All users will now need to join this channel to use the bot."
    )

@Client.on_callback_query(filters.regex("^cancel_focus$"))
async def cancel_focus_setup(client, callback):
    """Cancel focus channel setup"""
    user_id = callback.from_user.id
    
    await codeflixbots.col.update_one(
        {"_id": user_id},
        {"$unset": {"temp_channel": ""}}
    )
    
    await callback.message.edit_text("❌ Focus channel setup cancelled.")
    await callback.answer()

# Modified force subscription check to include dynamic channel
async def check_all_subscriptions(client, user_id):
    """Check all subscriptions (config + dynamic)"""
    channels_to_check = list(Config.FORCE_SUB_CHANNELS)
    
    # Add dynamic channel if set
    dynamic_channel = await get_dynamic_channel(Config.ADMIN[0])  # Get from first admin
    if dynamic_channel:
        channels_to_check.append(dynamic_channel)
    
    # Check all channels
    for channel in channels_to_check:
        try:
            user = await client.get_chat_member(channel, user_id)
            if user.status in {"kicked", "left"}:
                return False, channel
        except UserNotParticipant:
            return False, channel
    
    return True, None

# Update the force subscription handler
@Client.on_message(filters.private)
async def dynamic_force_sub(client, message: Message):
    """Check subscriptions before processing any message"""
    
    # Skip for commands that don't need subscription
    allowed_commands = ['start', 'focus', 'help', 'about']
    if message.text and message.text.startswith('/'):
        cmd = message.text.split()[0].replace('/', '')
        if cmd in allowed_commands:
            return
    
    # Check subscriptions
    is_subscribed, channel = await check_all_subscriptions(client, message.from_user.id)
    
    if not is_subscribed:
        channel_display = channel.replace("@", "") if channel else "channel"
        buttons = []
        
        # Add button for the missing channel
        buttons.append([
            InlineKeyboardButton(
                f"Join {channel_display.capitalize()}",
                url=f"https://t.me/{channel_display}"
            )
        ])
        
        buttons.append([
            InlineKeyboardButton(
                "✅ I've Joined",
                callback_data="check_subscription"
            )
        ])
        
        await message.reply_photo(
            photo="https://graph.org/file/a27d85469761da836337c.jpg",
            caption=(
                "**⚠️ Subscription Required!**\n\n"
                f"Please join @{channel_display} to use this bot.\n"
                "After joining, click 'I've Joined' button below."
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
