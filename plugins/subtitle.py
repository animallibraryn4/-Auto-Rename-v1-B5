from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from helper.database import codeflixbots
from config import Txt

@Client.on_message(filters.private & filters.command("sub"))
async def subtitle_command(client, message: Message):
    user_id = message.from_user.id
    current_status = await codeflixbots.get_subtitle_status(user_id)
    current_text = await codeflixbots.get_subtitle_text(user_id) or "Not set"
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {'ON ✅' if current_status else 'OFF ❌'}", 
                               callback_data="toggle_sub_status")
        ],
        [
            InlineKeyboardButton("Set Subtitle Text", callback_data="set_sub_text"),
            InlineKeyboardButton("Delete Subtitle", callback_data="delete_sub_text")
        ],
        [
            InlineKeyboardButton("Close", callback_data="close_sub")
        ]
    ]
    
    text = f"""
**🎬 Subtitle Settings**

**Current Status:** {'Enabled ✅' if current_status else 'Disabled ❌'}
**Current Text:** `{current_text}`

The subtitle will appear:
- At the start of the video (for 10 seconds)
- Every 8 minutes during playback
"""
    
    await message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r"^toggle_sub_status$"))
async def toggle_sub_status(client, query: CallbackQuery):
    user_id = query.from_user.id
    current_status = await codeflixbots.get_subtitle_status(user_id)
    new_status = not current_status
    await codeflixbots.set_subtitle_status(user_id, new_status)
    
    # Update the message
    current_text = await codeflixbots.get_subtitle_text(user_id) or "Not set"
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {'ON ✅' if new_status else 'OFF ❌'}", 
                               callback_data="toggle_sub_status")
        ],
        [
            InlineKeyboardButton("Set Subtitle Text", callback_data="set_sub_text"),
            InlineKeyboardButton("Delete Subtitle", callback_data="delete_sub_text")
        ],
        [
            InlineKeyboardButton("Close", callback_data="close_sub")
        ]
    ]
    
    text = f"""
**🎬 Subtitle Settings**

**Current Status:** {'Enabled ✅' if new_status else 'Disabled ❌'}
**Current Text:** `{current_text}`

The subtitle will appear:
- At the start of the video (for 10 seconds)
- Every 8 minutes during playback
"""
    
    await query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
    await query.answer(f"Subtitle {'enabled' if new_status else 'disabled'}")

@Client.on_callback_query(filters.regex(r"^set_sub_text$"))
async def set_sub_text(client, query: CallbackQuery):
    await query.message.edit_text(
        "**Please send the subtitle text you want to add to your videos.**\n\n"
        "Example: `Your Channel: @Animelibraryn4`\n\n"
        "This text will appear at the start of videos and every 8 minutes.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Cancel", callback_data="sub_cancel")]
        ])
    )
    await query.answer()

@Client.on_message(filters.private & filters.reply & filters.text & ~filters.command(['start', 'help', 'sub']))
async def save_sub_text(client, message: Message):
    # Check if this is a reply to the "set subtitle text" message
    replied = message.reply_to_message
    if replied and "subtitle text you want to add" in replied.text:
        user_id = message.from_user.id
        sub_text = message.text
        
        # Save the text
        await codeflixbots.set_subtitle_text(user_id, sub_text)
        
        # Show success message
        buttons = [
            [InlineKeyboardButton("View Settings", callback_data="sub_back")]
        ]
        
        await message.reply_text(
            f"✅ Subtitle text saved successfully!\n\n`{sub_text}`",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

@Client.on_callback_query(filters.regex(r"^delete_sub_text$"))
async def delete_sub_text(client, query: CallbackQuery):
    user_id = query.from_user.id
    await codeflixbots.set_subtitle_text(user_id, None)
    await codeflixbots.set_subtitle_status(user_id, False)
    
    await query.message.edit_text(
        "🗑 Subtitle text deleted and disabled successfully!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Back", callback_data="sub_back")]
        ])
    )
    await query.answer("Subtitle deleted")

@Client.on_callback_query(filters.regex(r"^sub_back$"))
async def sub_back(client, query: CallbackQuery):
    # Return to main subtitle menu
    await subtitle_command(client, query.message)

@Client.on_callback_query(filters.regex(r"^sub_cancel$"))
async def sub_cancel(client, query: CallbackQuery):
    # Return to main subtitle menu
    await subtitle_command(client, query.message)

@Client.on_callback_query(filters.regex(r"^close_sub$"))
async def close_sub(client, query: CallbackQuery):
    await query.message.delete()
    await query.answer()
