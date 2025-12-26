import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from helper.database import codeflixbots
from config import Config

@Client.on_message(filters.private & filters.command("merging"))
async def merge_mode_command(client, message: Message):
    user_id = message.from_user.id
    
    # Get current merge mode status
    current_mode = await codeflixbots.get_merge_mode(user_id)
    
    # Create toggle buttons
    buttons = [
        [
            InlineKeyboardButton(
                "✅ ON" if current_mode else "ON",
                callback_data="merge_on"
            ),
            InlineKeyboardButton(
                "OFF" if current_mode else "✅ OFF",
                callback_data="merge_off"
            )
        ],
        [
            InlineKeyboardButton("❓ How to Use", callback_data="merge_help")
        ]
    ]
    
    status_text = "🟢 **ACTIVE**" if current_mode else "🔴 **INACTIVE**"
    
    text = f"""
🔧 **Auto File Merging System**

**Current Status:** {status_text}

**Mode Rules:**
• **Merge Mode ON:** Auto rename is disabled, merging is enabled
• **Merge Mode OFF:** Auto rename works normally (default)

**Workflow:**
1️⃣ Send `/mergeformat` to set output format
2️⃣ Send Batch 1 files (source for audio/subtitles)
3️⃣ Send Batch 2 files (target videos to merge into)
4️⃣ Bot will process files one by one

**Note:** Only one mode can be active at a time.
"""
    
    await message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r'^merge_(on|off|help)$'))
async def merge_callback_handler(client, query):
    user_id = query.from_user.id
    action = query.data.split('_')[1]
    
    if action == "on":
        # Enable merge mode
        await codeflixbots.set_merge_mode(user_id, True)
        await codeflixbots.clear_merge_data(user_id)  # Clear any old data
        
        # Send instructions
        await query.message.edit_text(
            text="✅ **Merge Mode ENABLED**\n\n"
                 "Auto renaming is now disabled.\n\n"
                 "**Next Steps:**\n"
                 "1. Use `/mergeformat` to set output naming\n"
                 "2. Send Batch 1 files (source for audio/subtitles)\n"
                 "3. Then send Batch 2 files (target videos)\n\n"
                 "Use `/merging` to turn merge mode OFF.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_merge")]
            ])
        )
        
    elif action == "off":
        # Disable merge mode
        await codeflixbots.set_merge_mode(user_id, False)
        await codeflixbots.clear_merge_data(user_id)
        
        await query.message.edit_text(
            text="✅ **Merge Mode DISABLED**\n\n"
                 "Auto renaming is now active again.\n\n"
                 "Send files normally for auto renaming.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_merge")]
            ])
        )
        
    elif action == "help":
        await query.message.edit_text(
            text="📖 **Merge Mode Help**\n\n"
                 "**Batch 1 (Source Files):**\n"
                 "• Send multiple video files\n"
                 "• Bot extracts audio & subtitle tracks\n"
                 "• Video quality is ignored\n\n"
                 "**Batch 2 (Target Files):**\n"
                 "• Send videos to merge tracks into\n"
                 "• Original video stream is kept\n"
                 "• Matching audio/subtitles are added\n\n"
                 "**Output:**\n"
                 "• Uses `/mergeformat` for naming\n"
                 "• Quality from Batch 2\n"
                 "• [Dual] added if audio was merged\n\n"
                 "**Commands:**\n"
                 "• `/merging` - Toggle mode\n"
                 "• `/mergeformat` - Set output format\n"
                 "• `/mergeclear` - Clear current session",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_merge")]
            ])
        )

@Client.on_callback_query(filters.regex(r'^back_to_merge$'))
async def back_to_merge(client, query):
    # Re-show the merge mode menu
    await merge_mode_command(client, query.message)
