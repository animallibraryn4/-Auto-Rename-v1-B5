from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from helper.database import codeflixbots
from config import Txt

# Dictionary to track user states
user_states = {}

@Client.on_message(filters.private & filters.command("sub"))
async def subtitle_command(client, message: Message):
    user_id = message.from_user.id
    current_status = await codeflixbots.get_subtitle_status(user_id)
    current_text = await codeflixbots.get_subtitle_text(user_id) or "Not set"
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {'ON ✅' if current_status else 'OFF ❌'}", 
                               callback_data=f"sub_toggle_{user_id}")
        ],
        [
            InlineKeyboardButton("Set Subtitle Text", callback_data=f"sub_settext_{user_id}"),
            InlineKeyboardButton("Delete Subtitle", callback_data=f"sub_delete_{user_id}")
        ],
        [
            InlineKeyboardButton("Close", callback_data=f"sub_close_{user_id}")
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
    
    msg = await message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
    user_states[user_id] = msg.id

@Client.on_callback_query(filters.regex(r"^sub_toggle_(\d+)$"))
async def toggle_sub_status(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    current_status = await codeflixbots.get_subtitle_status(user_id)
    new_status = not current_status
    await codeflixbots.set_subtitle_status(user_id, new_status)
    
    current_text = await codeflixbots.get_subtitle_text(user_id) or "Not set"
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {'ON ✅' if new_status else 'OFF ❌'}", 
                               callback_data=f"sub_toggle_{user_id}")
        ],
        [
            InlineKeyboardButton("Set Subtitle Text", callback_data=f"sub_settext_{user_id}"),
            InlineKeyboardButton("Delete Subtitle", callback_data=f"sub_delete_{user_id}")
        ],
        [
            InlineKeyboardButton("Close", callback_data=f"sub_close_{user_id}")
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
    
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error editing message: {e}")
    
    await query.answer(f"Subtitle {'enabled' if new_status else 'disabled'}")

@Client.on_callback_query(filters.regex(r"^sub_settext_(\d+)$"))
async def set_sub_text(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    try:
        await query.message.edit_text(
            "**Please send the subtitle text you want to add to your videos.**\n\n"
            "Example: `Your Channel: @Animelibraryn4`\n\n"
            "This text will appear at the start of videos and every 8 minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data=f"sub_cancel_{user_id}")]
            ])
        )
        user_states[user_id] = "awaiting_subtitle_text"
    except Exception as e:
        print(f"Error in set_sub_text: {e}")
    await query.answer()

@Client.on_message(filters.private & filters.reply & filters.text & ~filters.command(['start', 'help', 'sub']))
async def save_sub_text(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id] != "awaiting_subtitle_text":
        return
    
    replied = message.reply_to_message
    if replied and "subtitle text you want to add" in replied.text:
        sub_text = message.text
        await codeflixbots.set_subtitle_text(user_id, sub_text)
        await codeflixbots.set_subtitle_status(user_id, True)
        
        buttons = [
            [InlineKeyboardButton("View Settings", callback_data=f"sub_back_{user_id}")]
        ]
        
        await message.reply_text(
            f"✅ Subtitle text saved successfully!\n\n`{sub_text}`",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        user_states[user_id] = None

@Client.on_callback_query(filters.regex(r"^sub_delete_(\d+)$"))
async def delete_sub_text(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    await codeflixbots.set_subtitle_text(user_id, None)
    await codeflixbots.set_subtitle_status(user_id, False)
    
    await query.message.edit_text(
        "🗑 Subtitle text deleted and disabled successfully!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Back", callback_data=f"sub_back_{user_id}")]
        ])
    )
    await query.answer("Subtitle deleted")

@Client.on_callback_query(filters.regex(r"^sub_back_(\d+)$"))
async def sub_back(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    await subtitle_command(client, query.message)

@Client.on_callback_query(filters.regex(r"^sub_cancel_(\d+)$"))
async def sub_cancel(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    await subtitle_command(client, query.message)

@Client.on_callback_query(filters.regex(r"^sub_close_(\d+)$"))
async def close_sub(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("This is not for you!", show_alert=True)
        return
    
    try:
        if user_id in user_states:
            del user_states[user_id]
        await query.message.delete()
    except Exception as e:
        print(f"Error deleting message: {e}")
    await query.answer()
