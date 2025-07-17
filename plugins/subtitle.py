from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from helper.database import codeflixbots
from config import Txt
import asyncio

# Global dictionary to track user states
user_state = {}

@Client.on_message(filters.private & filters.command("sub"))
async def subtitle_command(client, message: Message):
    user_id = message.from_user.id
    current_status = await codeflixbots.get_subtitle_status(user_id)
    current_text = await codeflixbots.get_subtitle_text(user_id) or "Not set"
    
    buttons = [
        [InlineKeyboardButton(f"🔄 Toggle Status ({'ON ✅' if current_status else 'OFF ❌'})", callback_data=f"subtoggle_{user_id}")],
        [InlineKeyboardButton("✏️ Set Subtitle Text", callback_data=f"subsettext_{user_id}")],
        [InlineKeyboardButton("🗑 Delete Subtitle", callback_data=f"subdelete_{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data=f"subclose_{user_id}")]
    ]
    
    text = f"""
<b>🎬 Subtitle Settings</b>

<b>• Current Status:</b> {'Enabled ✅' if current_status else 'Disabled ❌'}
<b>• Current Text:</b> <code>{current_text}</code>

The subtitle will appear:
- At the start of the video (for 10 seconds)
- Every 8 minutes during playback
"""
    
    try:
        # Delete previous message if exists
        if user_id in user_state:
            try:
                await client.delete_messages(message.chat.id, user_state[user_id])
            except:
                pass
        
        msg = await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        user_state[user_id] = msg.id
    except Exception as e:
        print(f"Error in subtitle_command: {str(e)}")
        await message.reply_text("⚠️ An error occurred. Please try again.")

async def update_subtitle_menu(client, query, user_id):
    current_status = await codeflixbots.get_subtitle_status(user_id)
    current_text = await codeflixbots.get_subtitle_text(user_id) or "Not set"
    
    buttons = [
        [InlineKeyboardButton(f"🔄 Toggle Status ({'ON ✅' if current_status else 'OFF ❌'})", callback_data=f"subtoggle_{user_id}")],
        [InlineKeyboardButton("✏️ Set Subtitle Text", callback_data=f"subsettext_{user_id}")],
        [InlineKeyboardButton("🗑 Delete Subtitle", callback_data=f"subdelete_{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data=f"subclose_{user_id}")]
    ]
    
    text = f"""
<b>🎬 Subtitle Settings</b>

<b>• Current Status:</b> {'Enabled ✅' if current_status else 'Disabled ❌'}
<b>• Current Text:</b> <code>{current_text}</code>

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
        print(f"Error updating menu: {str(e)}")
        await query.answer("Failed to update menu. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^subtoggle_(\d+)$"))
async def toggle_subtitle_status(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("🚫 This menu isn't for you!", show_alert=True)
        return
    
    try:
        current_status = await codeflixbots.get_subtitle_status(user_id)
        new_status = not current_status
        await codeflixbots.set_subtitle_status(user_id, new_status)
        await update_subtitle_menu(client, query, user_id)
        await query.answer(f"Subtitle {'enabled' if new_status else 'disabled'}")
    except Exception as e:
        print(f"Error in toggle_subtitle_status: {str(e)}")
        await query.answer("⚠️ Failed to toggle status. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^subsettext_(\d+)$"))
async def set_subtitle_text_handler(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("🚫 This menu isn't for you!", show_alert=True)
        return
    
    try:
        await query.message.edit_text(
            "📝 <b>Please send the subtitle text you want to add:</b>\n\n"
            "Example: <code>Your Channel: @Animelibraryn4</code>\n\n"
            "This text will appear:\n"
            "- At video start (10 seconds)\n"
            "- Every 8 minutes during playback",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Back", callback_data=f"subback_{user_id}")]
            ])
        )
        user_state[user_id] = "awaiting_text"
        await query.answer()
    except Exception as e:
        print(f"Error in set_subtitle_text_handler: {str(e)}")
        await query.answer("⚠️ Failed to open text input. Please try again.", show_alert=True)

@Client.on_message(filters.private & filters.text & ~filters.command(['start', 'help', 'sub']))
async def save_subtitle_text(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_state or user_state[user_id] != "awaiting_text":
        return
    
    if not message.reply_to_message:
        return
    
    try:
        sub_text = message.text
        await codeflixbots.set_subtitle_text(user_id, sub_text)
        await codeflixbots.set_subtitle_status(user_id, True)
        
        # Clear the state
        user_state[user_id] = None
        
        # Send confirmation
        await message.reply_text(
            f"✅ <b>Subtitle text saved successfully!</b>\n\n"
            f"<code>{sub_text}</code>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Back to Settings", callback_data=f"subback_{user_id}")]
            ])
        )
    except Exception as e:
        print(f"Error saving subtitle text: {str(e)}")
        await message.reply_text("⚠️ Failed to save subtitle text. Please try again.")

@Client.on_callback_query(filters.regex(r"^subdelete_(\d+)$"))
async def delete_subtitle_text(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("🚫 This menu isn't for you!", show_alert=True)
        return
    
    try:
        await codeflixbots.set_subtitle_text(user_id, None)
        await codeflixbots.set_subtitle_status(user_id, False)
        await update_subtitle_menu(client, query, user_id)
        await query.answer("🗑 Subtitle text deleted and disabled")
    except Exception as e:
        print(f"Error deleting subtitle: {str(e)}")
        await query.answer("⚠️ Failed to delete subtitle. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^subback_(\d+)$"))
async def back_to_subtitle_menu(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("🚫 This menu isn't for you!", show_alert=True)
        return
    
    try:
        await update_subtitle_menu(client, query, user_id)
        await query.answer()
    except Exception as e:
        print(f"Error going back to menu: {str(e)}")
        await query.answer("⚠️ Failed to return to menu. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^subclose_(\d+)$"))
async def close_subtitle_menu(client, query: CallbackQuery):
    user_id = int(query.matches[0].group(1))
    if query.from_user.id != user_id:
        await query.answer("🚫 This menu isn't for you!", show_alert=True)
        return
    
    try:
        if user_id in user_state:
            try:
                await client.delete_messages(query.message.chat.id, query.message.id)
            except:
                pass
            del user_state[user_id]
        await query.answer("Menu closed")
    except Exception as e:
        print(f"Error closing menu: {str(e)}")
        await query.answer("⚠️ Failed to close menu. Please try again.", show_alert=True)
