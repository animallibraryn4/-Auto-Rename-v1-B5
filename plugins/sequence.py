import asyncio
import re
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired, ChannelPrivate
from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message


# Global dictionaries for sequence management
user_sequences = {}  # user_id -> list of file data
user_notification_msg = {}  # user_id -> notification message info
update_tasks = {}  # user_id -> update task
user_settings = {}  # user_id -> sequence mode (per_ep or group)
processing_users = set()  # To prevent multiple "Processing" messages
user_ls_state = {}  # Store LS command state
user_mode = {}  # Store user mode (file or caption)
user_seq_mode = {}  # Store user sequence mode (per_ep or group)

# =====================================================
# SEQUENCE PARSING ENGINE
# =====================================================

def parse_file_info(text):
    """Parse file information from text (either filename or caption)"""
    if not text:
        return {"season": 1, "episode": 0, "quality": 0}
    
    quality_match = re.search(r'(\d{3,4})[pP]', text)
    quality = int(quality_match.group(1)) if quality_match else 0
    clean_name = re.sub(r'\d{3,4}[pP]', '', text)

    season_match = re.search(r'[sS](?:eason)?\s*(\d+)', clean_name)
    season = int(season_match.group(1)) if season_match else 1
    
    ep_match = re.search(r'[eE](?:p(?:isode)?)?\s*(\d+)', clean_name)
    if ep_match:
        episode = int(ep_match.group(1))
    else:
        nums = re.findall(r'\d+', clean_name)
        episode = int(nums[-1]) if nums else 0

    return {"season": season, "episode": episode, "quality": quality}

def extract_message_info(link):
    """
    Extract chat ID and message ID from Telegram message link
    Supports formats:
    - https://t.me/c/chat_id/message_id (private channels)
    - https://t.me/username/message_id (public channels/groups)
    """
    try:
        link = link.strip()
        
        if "/c/" in link:
            # Private channel link format: https://t.me/c/1234567890/123
            parts = link.split("/")
            
            # Get the chat_id part (it's 1234567890 in the example)
            chat_id_str = parts[4]
            
            # Check if it needs the -100 prefix
            if chat_id_str.startswith("-100"):
                chat_id = int(chat_id_str)
            elif chat_id_str.startswith("100"):
                # Some links might have 100xxxxxx format
                chat_id = int("-" + chat_id_str)
            else:
                # Regular negative ID for private channels
                chat_id = int("-100" + chat_id_str)
            
            message_id = int(parts[5])
            return chat_id, message_id
            
        elif "t.me/" in link:
            # Public channel/group link format: https://t.me/username/123
            parts = link.split("/")
            username = parts[3]
            message_id = int(parts[4])
            return username, message_id
            
    except Exception as e:
        print(f"Error parsing link {link}: {e}")
        
    return None, None

async def check_bot_admin(client, chat_id):
    """Check if bot is admin in the given chat/channel"""
    try:
        print(f"Checking admin status for chat_id: {chat_id}, type: {type(chat_id)}")
        
        # If chat_id is a username string, get the actual chat ID
        if isinstance(chat_id, str):
            try:
                chat = await client.get_chat(chat_id)
                chat_id = chat.id
            except Exception as e:
                print(f"Error getting chat from username {chat_id}: {e}")
                return False
        
        # Get bot's member status
        try:
            bot_member = await client.get_chat_member(chat_id, "me")
            status_str = str(bot_member.status).lower()
            
            # Check all possible admin status strings
            admin_statuses = [
                "administrator", 
                "creator",
                "Administrator",
                "Creator",
                "admin",
                "Admin",
                "chat_member_status_administrator",
                "chat_member_status_creator"
            ]
            
            is_admin = False
            for admin_status in admin_statuses:
                if admin_status.lower() in status_str:
                    is_admin = True
                    break
            
            print(f"Is admin: {is_admin}")
            return is_admin
            
        except (ChatAdminRequired, ChannelPrivate) as e:
            print(f"Admin check failed (ChatAdminRequired/ChannelPrivate): {e}")
            return False
        except Exception as e:
            print(f"Admin check error: {e}")
            return False
            
    except Exception as e:
        print(f"General error in check_bot_admin: {e}")
        return False

async def get_messages_between(client, chat_id, start_msg_id, end_msg_id):
    """Fetch all messages between start_msg_id and end_msg_id (inclusive)"""
    messages = []
    
    # Ensure start is smaller than end
    if start_msg_id > end_msg_id:
        start_msg_id, end_msg_id = end_msg_id, start_msg_id
    
    try:
        # Fetch messages in batches
        for msg_id in range(start_msg_id, end_msg_id + 1):
            try:
                msg = await client.get_messages(chat_id, msg_id)
                if msg and (msg.document or msg.video or msg.audio):
                    messages.append(msg)
                # Small delay to avoid flood
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error fetching message {msg_id}: {e}")
                continue
    except Exception as e:
        print(f"Error in get_messages_between: {e}")
    
    return messages

async def sequence_messages(client, messages, mode="per_ep", user_id=None):
    """Convert messages to sequence format with File/Caption mode support"""
    files_data = []
    
    # Get user's current mode
    if user_id:
        current_mode = user_mode.get(user_id, "file")
    else:
        current_mode = "file"  # Default to file mode if no user_id provided
    
    for msg in messages:
        file_obj = msg.document or msg.video or msg.audio
        if file_obj:
            if current_mode == "caption":
                # Caption mode: Use caption text
                if msg.caption:
                    text_to_parse = msg.caption
                else:
                    # No caption found, skip this file
                    continue
            else:
                # File mode: Use filename
                file_name = file_obj.file_name if file_obj else "Unknown"
                text_to_parse = file_name
            
            info = parse_file_info(text_to_parse)
            
            files_data.append({
                "filename": text_to_parse,
                "msg_id": msg.id,
                "chat_id": msg.chat.id,
                "info": info
            })
    
    # Sort based on mode (per_ep or group)
    if mode == "per_ep":
        sorted_files = sorted(files_data, key=lambda x: (x["info"]["season"], x["info"]["episode"], x["info"]["quality"]))
    else:
        sorted_files = sorted(files_data, key=lambda x: (x["info"]["season"], x["info"]["quality"], x["info"]["episode"]))
    
    return sorted_files, current_mode

# =====================================================
# SEQUENCE COMMANDS
# =====================================================

@Client.on_message(filters.private & filters.command("sequence"))
async def start_sequence(client, message):
    """Start a new sequence session"""
    user_id = message.from_user.id
    
    # Check verification
    from plugins import is_user_verified, send_verification
    if not await is_user_verified(user_id):
        await send_verification(client, message)
        return
    
    user_sequences[user_id] = []
    if user_id in user_notification_msg:
        del user_notification_msg[user_id]
    
    # Get current mode
    current_mode = user_mode.get(user_id, "file")
    mode_text = "File mode (using filename)" if current_mode == "file" else "Caption mode (using file caption)"
    seq_mode = user_seq_mode.get(user_id, "per_ep")
    seq_text = "Episode Flow" if seq_mode == "per_ep" else "Quality Flow"
    
    await message.reply_text(
        f"<b>📂 File Sequence Mode Started!</b>\n\n"
        f"<blockquote>📝 <b>Current Mode:</b> {mode_text}\n"
        f"🔄 <b>Sequence Order:</b> {seq_text}\n\n"
        f"Send your files now. I'll sequence them in the configured order.</blockquote>"
    )

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio), group=-1)
async def store_file(client, message):
    """Store files for sequencing"""
    user_id = message.from_user.id
    
    # Check if we are currently in a sequence session
    if user_id in user_sequences:
        file_obj = message.document or message.video or message.audio
        current_mode = user_mode.get(user_id, "file")
        
        if current_mode == "caption":
            # Caption mode: Use caption text or ask to switch mode
            if message.caption:
                text_to_parse = message.caption
            else:
                # No caption found, ask user to switch mode
                await message.reply_text(
                    "<b>❌ No Caption Found!</b>\n\n"
                    "<blockquote>This file doesn't have a caption. Please:\n"
                    "1. Switch to File mode using /sf\n"
                    "2. Or add a caption to the file</blockquote>"
                )
                return
        else:
            # File mode: Use filename
            file_name = file_obj.file_name if file_obj else "Unknown"
            text_to_parse = file_name
        
        info = parse_file_info(text_to_parse)
        
        user_sequences[user_id].append({
            "filename": text_to_parse,
            "msg_id": message.id,
            "chat_id": message.chat.id,
            "info": info
        })
        
        # Get current count
        current_count = len(user_sequences[user_id])

        # Send "Processing" notification if 20+ files are added
        if user_id not in user_notification_msg and user_id not in processing_users and current_count >= 20:
            processing_users.add(user_id)  # Lock the user
            try:
                msg = await client.send_message(
                    message.chat.id,
                    "<blockquote>⏳ Processing files… Please wait</blockquote>"
                )
                user_notification_msg[user_id] = {
                    "msg_id": msg.id,
                    "chat_id": message.chat.id
                }
            finally:
                processing_users.remove(user_id)  # Release the lock
        
        # Cancel previous update task and start a new one (Debouncing)
        if user_id in update_tasks: 
            if update_tasks[user_id]:
                update_tasks[user_id].cancel()
        update_tasks[user_id] = asyncio.create_task(update_notification(client, user_id, message.chat.id))

async def update_notification(client, user_id, chat_id):
    """Update notification message with file count"""
    await asyncio.sleep(3)
    
    if user_id not in user_sequences:
        return
    
    count = len(user_sequences[user_id])
    
    # Get current modes for display
    current_mode = user_mode.get(user_id, "file")
    mode_text = "File" if current_mode == "file" else "Caption"
    seq_mode = user_seq_mode.get(user_id, "per_ep")
    seq_text = "Episode" if seq_mode == "per_ep" else "Quality"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Send Sequence", callback_data='send_sequence')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_sequence')]
    ])
    
    text = (
        f"<b>📊 Files Ready for Sequencing!</b>\n\n"
        f"<blockquote>📝 <b>Mode:</b> {mode_text} Mode\n"
        f"🔄 <b>Order:</b> {seq_text} Flow\n"
        f"📁 <b>Total Files:</b> {count}\n\n"
        f"Click below to send sequenced files:</blockquote>"
    )
    
    if user_id in user_notification_msg:
        try:
            await client.edit_message_text(
                chat_id=user_notification_msg[user_id]["chat_id"],
                message_id=user_notification_msg[user_id]["msg_id"],
                text=text,
                reply_markup=buttons
            )
        except:
            pass
    else:
        msg = await client.send_message(chat_id, text, reply_markup=buttons)
        user_notification_msg[user_id] = {
            "msg_id": msg.id,
            "chat_id": chat_id
        }

async def send_sequence_files(client, message, user_id):
    """Send sequenced files to user"""
    if user_id not in user_sequences or not user_sequences[user_id]:
        await message.edit_text("<blockquote>❌ No files in sequence!</blockquote>")
        return

    files_data = user_sequences[user_id]
    mode = user_seq_mode.get(user_id, "per_ep")
    
    await message.edit_text("<blockquote>📤 Sending files... Please wait.</blockquote>")

    if mode == "per_ep":
        sorted_files = sorted(files_data, key=lambda x: (x["info"]["season"], x["info"]["episode"], x["info"]["quality"]))
    else:
        sorted_files = sorted(files_data, key=lambda x: (x["info"]["season"], x["info"]["quality"], x["info"]["episode"]))

    for file in sorted_files:
        try:
            await client.copy_message(
                message.chat.id,
                from_chat_id=file["chat_id"],
                message_id=file["msg_id"]
            )
            await asyncio.sleep(0.8)
        except:
            continue

    try:
        await message.delete()
    except:
        pass
    
    # Clear user data
    user_sequences.pop(user_id, None)
    user_notification_msg.pop(user_id, None)
    update_tasks.pop(user_id, None)
    
    await client.send_message(
        message.chat.id,
        "<b>✅ All Files Sequenced Successfully!</b>\n\n"
        "<blockquote>Files have been sent in the configured sequence order.</blockquote>"
    )

# =====================================================
# /sf COMMAND - Switch between File and Caption Mode
# =====================================================

@Client.on_message(filters.private & filters.command("sf"))
async def switch_rename_mode(client, message: Message):
    user_id = message.from_user.id
    
    # Toggle between file and caption mode
    new_mode = await codeflixbots.toggle_rename_mode(user_id)
    
    if new_mode == "file":
        mode_text = "📄 **File Mode**"
        description = "The bot will now extract information from **file names** for auto renaming."
        icon = "📄"
    else:
        mode_text = "📝 **Caption Mode**"
        description = "The bot will now extract information from **file captions** for auto renaming."
        icon = "📝"
    
    # Create response message
    response = f"""
{icon} **Rename Mode Changed**

**Current Mode:** {mode_text}

{description}

**How it works:**
- **File Mode:** Extracts episode, season, and quality info from file names
- **Caption Mode:** Extracts the same info from file captions

**Tip:** Make sure your captions contain the same pattern information as your file names.
"""
    
    # Create buttons for quick switching
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Switch Again", callback_data="toggle_rename_mode"),
            InlineKeyboardButton("❌ Close", callback_data="close_message")
        ]
    ])
    
    await message.reply_text(response, reply_markup=buttons)

@Client.on_callback_query(filters.regex("^toggle_rename_mode$"))
async def toggle_mode_callback(client, callback_query):
    user_id = callback_query.from_user.id
    
    # Toggle the mode
    new_mode = await codeflixbots.toggle_rename_mode(user_id)
    
    if new_mode == "file":
        mode_text = "📄 **File Mode**"
        description = "The bot will now extract information from **file names** for auto renaming."
        icon = "📄"
    else:
        mode_text = "📝 **Caption Mode**"
        description = "The bot will now extract information from **file captions** for auto renaming."
        icon = "📝"
    
    # Update the message
    response = f"""
{icon} **Rename Mode Changed**

**Current Mode:** {mode_text}

{description}

**How it works:**
- **File Mode:** Extracts episode, season, and quality info from file names
- **Caption Mode:** Extracts the same info from file captions

**Tip:** Make sure your captions contain the same pattern information as your file names.
"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Switch Again", callback_data="toggle_rename_mode"),
            InlineKeyboardButton("❌ Close", callback_data="close_message")
        ]
    ])
    
    await callback_query.message.edit_text(response, reply_markup=buttons)

@Client.on_message(filters.private & filters.command("mode"))
async def check_mode_command(client, message: Message):
    """Command to check current rename mode"""
    user_id = message.from_user.id
    current_mode = await codeflixbots.get_rename_mode(user_id)
    
    if current_mode == "file":
        mode_text = "📄 **File Mode**"
        description = "Currently extracting information from **file names**."
        icon = "📄"
    else:
        mode_text = "📝 **Caption Mode**"
        description = "Currently extracting information from **file captions**."
        icon = "📝"
    
    response = f"""
{icon} **Current Rename Mode**

**Mode:** {mode_text}

{description}

**To switch mode:** Use /sf command
**To check mode:** Use /mode command

**Note:** Make sure your source (filename or caption) contains episode numbers, season numbers, and quality information in a recognizable format.
"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Switch Mode", callback_data="toggle_rename_mode"),
            InlineKeyboardButton("❌ Close", callback_data="close_message")
        ]
    ])
    
    await message.reply_text(response, reply_markup=buttons)

# =====================================================
# /fileseq COMMAND - Choose Sequence Flow
# =====================================================

@Client.on_message(filters.private & filters.command("fileseq"))
async def quality_mode_cmd(client, message):
    """Handle /fileseq command to choose sequence flow"""
    text = (
        "<b>➲ Choose File Sequence Order</b>\n\n"
        "<blockquote>Select how your files will be sequenced:</blockquote>\n"
        
        "<b>📺 Episode Flow:</b>\n"
        "<blockquote>Files are sent episode by episode.\n"
        "Order: Season → Episode → Quality\n\n"
        "<i>Example:</i>\n"
        "S1E1 → All qualities\n"
        "S1E2 → All qualities\n</blockquote>"
        
        "<b>🎬 Quality Flow:</b>\n"
        "<blockquote>Files are sent quality by quality within each season.\n"
        "Order: Season → Quality → Episode\n\n"
        "<i>Example:</i>\n"
        "Season 1 → All 480p episodes\n"
        "Season 1 → All 720p episodes</blockquote>"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Episode Flow", callback_data='set_mode_per_ep')],
        [InlineKeyboardButton("🎬 Quality Flow", callback_data='set_mode_group')]
    ])
    
    await message.reply_text(text, reply_markup=buttons)

# =====================================================
# /ls COMMAND - Link Sequence from Channel
# =====================================================

@Client.on_message(filters.private & filters.command("ls"))
async def ls_command(client, message):
    """Handle /ls command for channel file sequencing"""
    user_id = message.from_user.id
    
    # Get user's current mode
    current_mode = user_mode.get(user_id, "file")
    mode_text = "File Mode" if current_mode == "file" else "Caption Mode"
    seq_mode = user_seq_mode.get(user_id, "per_ep")
    seq_text = "Episode Flow" if seq_mode == "per_ep" else "Quality Flow"
    
    # Initialize LS state for user WITH mode information
    user_ls_state[user_id] = {
        "step": 1,  # 1: waiting for first link, 2: waiting for second link
        "first_link": None,
        "first_chat": None,
        "first_msg_id": None,
        "mode": seq_mode,
        "current_mode": current_mode
    }
    
    await message.reply_text(
        f"<b>📁 LS Mode Activated</b>\n\n"
        f"<blockquote><b>Current Mode:</b> {mode_text}\n"
        f"<b>Sequence Order:</b> {seq_text}</blockquote>\n\n"
        f"<blockquote>Please send the first file link from the channel/group.\n\n"
        f"ℹ️ Note: For private channels, the bot must be an admin.</blockquote>"
    )

@Client.on_message(filters.private & filters.text & filters.regex(r'https?://t\.me/'))
async def handle_ls_links(client, message):
    """Handle Telegram links for LS mode"""
    user_id = message.from_user.id
    
    if user_id not in user_ls_state:
        return  # Not in LS mode
    
    ls_data = user_ls_state[user_id]
    link = message.text.strip()
    
    try:
        if ls_data["step"] == 1:
            # First link
            chat_info, msg_id = extract_message_info(link)
            
            if not msg_id:
                await message.reply_text("<blockquote>❌ Invalid link format. Please send a valid Telegram message link.</blockquote>")
                return
            
            # Store first link data
            user_ls_state[user_id].update({
                "first_link": link,
                "first_chat": chat_info,
                "first_msg_id": msg_id,
                "step": 2
            })
            
            current_mode = ls_data.get("current_mode", "file")
            mode_text = "File Mode" if current_mode == "file" else "Caption Mode"
            
            await message.reply_text(
                f"<b>✅ First Link Received!</b>\n\n"
                f"<blockquote><b>Current Mode:</b> {mode_text}</blockquote>\n"
                f"<blockquote>Now please send the second file link from the same channel/group.</blockquote>"
            )
            
        elif ls_data["step"] == 2:
            # Second link
            second_chat, second_msg_id = extract_message_info(link)
            
            if not second_msg_id:
                await message.reply_text("<blockquote>❌ Invalid link format. Please send a valid Telegram message link.</blockquote>")
                return
            
            # Check if both links are from same chat
            first_chat = ls_data["first_chat"]
            if isinstance(first_chat, int) and isinstance(second_chat, str):
                # Try to resolve the string to ID for comparison
                try:
                    chat_obj = await client.get_chat(second_chat)
                    second_chat = chat_obj.id
                except:
                    pass
            elif isinstance(first_chat, str) and isinstance(second_chat, int):
                # Try to resolve the int to username for comparison
                try:
                    chat_obj = await client.get_chat(second_chat)
                    if chat_obj.username:
                        second_chat = chat_obj.username
                except:
                    pass
            
            if first_chat != second_chat:
                await message.reply_text("<blockquote>❌ Both links must be from the same channel/group.</blockquote>")
                # Reset LS state
                del user_ls_state[user_id]
                return
            
            # Store second link data
            user_ls_state[user_id].update({
                "second_link": link,
                "second_chat": second_chat,
                "second_msg_id": second_msg_id
            })
            
            current_mode = ls_data.get("current_mode", "file")
            mode_text = "File Mode" if current_mode == "file" else "Caption Mode"
            
            # Show buttons for Chat/Channel choice
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Send to Chat", callback_data=f"ls_chat_{user_id}")],
                [InlineKeyboardButton("📢 Send to Channel", callback_data=f"ls_channel_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data=f"ls_close_{user_id}")]
            ])
            
            await message.reply_text(
                f"<b>✅ Both Links Received!</b>\n\n"
                f"<blockquote><b>Current Mode:</b> {mode_text}</blockquote>\n"
                f"<blockquote>Choose where to send sequenced files:</blockquote>",
                reply_markup=buttons
            )
            
    except Exception as e:
        print(f"Error handling LS link: {e}")
        await message.reply_text("<blockquote>❌ An error occurred. Please try again with valid links.</blockquote>")
        if user_id in user_ls_state:
            del user_ls_state[user_id]

# =====================================================
# CALLBACK QUERY HANDLERS
# =====================================================

@Client.on_callback_query(filters.regex(r'^mode_(file|caption)$|^close_mode$'))
async def mode_callback_handler(client, query):
    """Handle mode switching callbacks"""
    data = query.data
    user_id = query.from_user.id
    
    if data == "mode_file":
        user_mode[user_id] = "file"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ File Mode", callback_data="mode_file")],
            [InlineKeyboardButton("Caption Mode", callback_data="mode_caption")],
            [InlineKeyboardButton("❌ Close", callback_data="close_mode")]
        ])
        text = (
            "<b>🔄 Sequence Mode Settings</b>\n\n"
            "<blockquote><b>Current Mode:</b> File Mode\n\n"
            "<b>📝 File Mode:</b> Sequence files using filename\n"
            "<b>🏷️ Caption Mode:</b> Sequence files using file caption\n\n"
            "✅ <i>Mode switched to File Mode!</i></blockquote>"
        )
        
        await query.message.edit_text(text, reply_markup=buttons)
        await query.answer("Switched to File Mode!", show_alert=True)
        
    elif data == "mode_caption":
        user_mode[user_id] = "caption"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("File Mode", callback_data="mode_file")],
            [InlineKeyboardButton("✅ Caption Mode", callback_data="mode_caption")],
            [InlineKeyboardButton("❌ Close", callback_data="close_mode")]
        ])
        text = (
            "<b>🔄 Sequence Mode Settings</b>\n\n"
            "<blockquote><b>Current Mode:</b> Caption Mode\n\n"
            "<b>📝 File Mode:</b> Sequence files using filename\n"
            "<b>🏷️ Caption Mode:</b> Sequence files using file caption\n\n"
            "✅ <i>Mode switched to Caption Mode!</i></blockquote>"
        )
        
        await query.message.edit_text(text, reply_markup=buttons)
        await query.answer("Switched to Caption Mode!", show_alert=True)
        
    elif data == "close_mode":
        await query.message.delete()
        await query.answer("Closed mode settings", show_alert=False)

@Client.on_callback_query(filters.regex(r'^set_mode_(group|per_ep)$'))
async def set_mode_callback(client, query):
    """Handle sequence mode callbacks"""
    data = query.data
    user_id = query.from_user.id
    
    if data == "set_mode_group":
        user_seq_mode[user_id] = "group"
        await query.message.edit_text(
            "<b>✅ Mode Set: Quality Flow</b>\n\n"
            "<blockquote>Files will be sequenced by quality within each season.</blockquote>"
        )
        await query.answer("Quality Flow selected", show_alert=True)
    elif data == "set_mode_per_ep":
        user_seq_mode[user_id] = "per_ep"
        await query.message.edit_text(
            "<b>✅ Mode Set: Episode Flow</b>\n\n"
            "<blockquote>Files will be sequenced episode by episode.</blockquote>"
        )
        await query.answer("Episode Flow selected", show_alert=True)

@Client.on_callback_query(filters.regex(r'^(send_sequence|cancel_sequence)$'))
async def sequence_control_callback(client, query):
    """Handle sequence control callbacks"""
    data = query.data
    user_id = query.from_user.id
    
    if data == "send_sequence":
        if user_id in user_sequences:
            await send_sequence_files(client, query.message, user_id)
    elif data == "cancel_sequence":
        user_sequences.pop(user_id, None)
        user_notification_msg.pop(user_id, None)
        update_tasks.pop(user_id, None)
        await query.message.edit_text("<blockquote>❌ Sequence cancelled.</blockquote>")

@Client.on_callback_query(filters.regex(r'^ls_(chat|channel|close)_'))
async def ls_callback_handlers(client, query):
    """Handle LS callback handlers"""
    data = query.data
    user_id = query.from_user.id
    
    # Extract target_user_id from callback data
    try:
        parts = data.split("_")
        action = parts[1]  # chat, channel, or close
        target_user_id = int(parts[2])
    except (IndexError, ValueError):
        await query.answer("Invalid callback data.", show_alert=True)
        return
    
    if user_id != target_user_id:
        await query.answer("This button is not for you!", show_alert=True)
        return
    
    if target_user_id not in user_ls_state:
        await query.answer("Session expired. Please start again with /ls", show_alert=True)
        await query.message.delete()
        return
    
    ls_data = user_ls_state[target_user_id]
    current_mode = ls_data.get("current_mode", "file")
    
    if action == "chat":
        await query.message.edit_text("<blockquote>⏳ Fetching files from channel... Please wait.</blockquote>")
        
        try:
            # Get messages between the two links
            chat_id = ls_data["first_chat"]
            start_msg_id = ls_data["first_msg_id"]
            end_msg_id = ls_data["second_msg_id"]
            
            # Fetch messages
            messages = await get_messages_between(client, chat_id, start_msg_id, end_msg_id)
            
            if not messages:
                await query.message.edit_text("<blockquote>❌ No files found between the specified links.</blockquote>")
                return
            
            # Process and sequence files WITH user mode
            sorted_files, used_mode = await sequence_messages(client, messages, ls_data["mode"], target_user_id)
            
            if not sorted_files:
                if used_mode == "caption":
                    await query.message.edit_text(
                        "<blockquote>❌ No files with captions found in the specified range.</blockquote>\n"
                        "<blockquote>Switch to File mode using /sf or ensure files have captions.</blockquote>"
                    )
                else:
                    await query.message.edit_text("<blockquote>❌ No valid files found to sequence.</blockquote>")
                return
            
            mode_text = "File Mode" if used_mode == "file" else "Caption Mode"
            skipped_count = len(messages) - len(sorted_files) if used_mode == "caption" else 0
            
            # Send files to user's chat
            if skipped_count > 0:
                await query.message.edit_text(
                    f"<blockquote>📤 Sending {len(sorted_files)} files to chat... (Skipped {skipped_count} files without captions)</blockquote>"
                )
            else:
                await query.message.edit_text(f"<blockquote>📤 Sending {len(sorted_files)} files to chat... Please wait.</blockquote>")
            
            for file in sorted_files:
                try:
                    await client.copy_message(user_id, from_chat_id=file["chat_id"], message_id=file["msg_id"])
                    await asyncio.sleep(0.8)
                except Exception as e:
                    print(f"Error sending file: {e}")
                    continue
            
            if skipped_count > 0:
                await query.message.edit_text(
                    f"<b>✅ Successfully sent {len(sorted_files)} files to your chat!</b>\n\n"
                    f"<blockquote>Mode: {mode_text}\n"
                    f"Note: {skipped_count} files skipped (no captions found)</blockquote>"
                )
            else:
                await query.message.edit_text(
                    f"<b>✅ Successfully sent {len(sorted_files)} files to your chat!</b>\n\n"
                    f"<blockquote>Mode: {mode_text}</blockquote>"
                )
            
        except Exception as e:
            print(f"LS Chat error: {e}")
            await query.message.edit_text("<blockquote>❌ An error occurred while processing files. Please try again.</blockquote>")
        
        # Clean up
        if target_user_id in user_ls_state:
            del user_ls_state[target_user_id]
    
    elif action == "channel":
        await query.message.edit_text("<blockquote>⏳ Checking bot permissions in channel... Please wait.</blockquote>")
        
        try:
            # Check if bot is admin in the channel
            chat_id = ls_data["first_chat"]
            
            is_admin = await check_bot_admin(client, chat_id)
            
            if not is_admin:
                await query.message.edit_text(
                    "<b>❌ Bot is not admin in this channel!</b>\n\n"
                    "<blockquote>To send files back to the channel, the bot must be added as an administrator "
                    "with permission to post messages.</blockquote>"
                )
                return
            
            await query.message.edit_text("<blockquote>✅ Bot is admin! Fetching files from channel... Please wait.</blockquote>")
            
            # Get messages between the two links
            start_msg_id = ls_data["first_msg_id"]
            end_msg_id = ls_data["second_msg_id"]
            
            # Fetch messages
            messages = await get_messages_between(client, chat_id, start_msg_id, end_msg_id)
            
            if not messages:
                await query.message.edit_text("<blockquote>❌ No files found between the specified links.</blockquote>")
                return
            
            # Process and sequence files WITH user mode
            sorted_files, used_mode = await sequence_messages(client, messages, ls_data["mode"], target_user_id)
            
            if not sorted_files:
                if used_mode == "caption":
                    await query.message.edit_text(
                        "<blockquote>❌ No files with captions found in the specified range.</blockquote>\n"
                        "<blockquote>Switch to File mode using /sf or ensure files have captions.</blockquote>"
                    )
                else:
                    await query.message.edit_text("<blockquote>❌ No valid files found to sequence.</blockquote>")
                return
            
            mode_text = "File Mode" if used_mode == "file" else "Caption Mode"
            skipped_count = len(messages) - len(sorted_files) if used_mode == "caption" else 0
            
            # Send files back to channel
            if skipped_count > 0:
                await query.message.edit_text(
                    f"<blockquote>📤 Sending {len(sorted_files)} files to channel... (Skipped {skipped_count} files without captions)</blockquote>"
                )
            else:
                await query.message.edit_text(f"<blockquote>📤 Sending {len(sorted_files)} files to channel... Please wait.</blockquote>")
            
            success_count = 0
            for file in sorted_files:
                try:
                    await client.copy_message(chat_id, from_chat_id=file["chat_id"], message_id=file["msg_id"])
                    await asyncio.sleep(2)  # Wait 2 seconds between sending files
                    success_count += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Error sending file to channel: {e}")
                    continue
            
            if skipped_count > 0:
                await query.message.edit_text(
                    f"<b>✅ Successfully sent {success_count} files back to the channel!</b>\n\n"
                    f"<blockquote>Mode: {mode_text}\n"
                    f"Total files found: {len(messages)}\n"
                    f"Files with captions: {len(sorted_files)}\n"
                    f"Successfully sent: {success_count}\n"
                    f"Skipped (no captions): {skipped_count}</blockquote>"
                )
            else:
                await query.message.edit_text(
                    f"<b>✅ Successfully sent {success_count} files back to the channel!</b>\n\n"
                    f"<blockquote>Mode: {mode_text}\n"
                    f"Total files found: {len(sorted_files)}\n"
                    f"Successfully sent: {success_count}</blockquote>"
                )
            
        except Exception as e:
            print(f"LS Channel error: {e}")
            await query.message.edit_text(f"<blockquote>❌ An error occurred: {str(e)[:200]}...</blockquote>")
        
        # Clean up
        if target_user_id in user_ls_state:
            del user_ls_state[target_user_id]
            
    elif action == "close":
        # Handle Close button for LS
        await query.message.delete()
        
        # Clean up
        if target_user_id in user_ls_state:
            del user_ls_state[target_user_id]

# =====================================================
# CLEANUP FUNCTION
# =====================================================

async def cleanup_user_data(user_id):
    """Clean up user data to prevent memory leaks"""
    user_sequences.pop(user_id, None)
    user_notification_msg.pop(user_id, None)
    user_ls_state.pop(user_id, None)
    user_mode.pop(user_id, None)
    user_seq_mode.pop(user_id, None)
    
    if user_id in update_tasks:
        task = update_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

# =====================================================
# SEQUENCE HELP TEXT
# =====================================================

SEQUENCE_HELP_TEXT = """
<b>📁 File Sequence Commands</b>

<blockquote><b>/sequence</b> - Start a new sequence session
<b>/sf</b> - Switch between File Mode and Caption Mode
<b>/fileseq</b> - Choose sequence flow (Episode or Quality)
<b>/ls</b> - Sequence files from channel links

<b>📝 Modes:</b>
• <b>File Mode</b> - Sequence using filenames
• <b>Caption Mode</b> - Sequence using file captions

<b>🔄 Sequence Flows:</b>
• <b>Episode Flow</b> - Season → Episode → Quality
• <b>Quality Flow</b> - Season → Quality → Episode

<b>🔗 LS Mode:</b>
Send two Telegram message links from the same channel to sequence files between them.</blockquote>
"""
