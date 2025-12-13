from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from helper.database import codeflixbots
from helper.ban_filter import is_not_banned_filter # <-- NEW IMPORT

@Client.on_message(filters.private & filters.command("autorename") & is_not_banned_filter) # <-- MODIFIED
async def auto_rename_command(client, message: Message):
    user_id = message.from_user.id

    # Extract and validate the format from the command
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text(
            "**Please provide a new name after the command /autorename**\n\n"
            "Here's how to use it:\n"
            "**Example format:** ` /autorename S[SE.NUM]EP[EP.NUM] your video title [QUALITY]`"
        )
        return

    format_template = command_parts[1].strip()

    # Save the format template in the database
    await codeflixbots.set_format_template(user_id, format_template)

    # Send confirmation message with the template in monospaced font
    await message.reply_text(
        f"**🌟 Fantastic! You're ready to auto-rename your files.**\n\n"
        "📩 Simply send the file(s) you want to rename.\n\n"
        f"**Your saved template:** `{format_template}`\n\n"
        "Remember, it might take some time, but I'll ensure your files are renamed perfectly!✨"
    )

@Client.on_message(filters.private & filters.command("setmedia") & is_not_banned_filter) # <-- MODIFIED
async def set_media_command(client, message: Message):
    # Define inline keyboard buttons for media type selection
    current_pref = await codeflixbots.get_media_preference(message.from_user.id)
    
    doc_text = "📄 Document" + (" ✅" if current_pref == "document" else "")
    vid_text = "🎥 Video" + (" ✅" if current_pref == "video" else "")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(doc_text, callback_data="setmedia_document")],
        [InlineKeyboardButton(vid_text, callback_data="setmedia_video")]
    ])

    # Send a message with the inline buttons
    await message.reply_text(
        "**Please select the media type you want your files to be uploaded as:**",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex("^setmedia_"))
async def handle_media_selection(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    media_type = callback_query.data.split("_", 1)[1]  # Extract media type from callback data

    # Save the preferred media type in the database
    await codeflixbots.set_media_preference(user_id, media_type)

    # Re-generate buttons to show the checkmark
    current_pref = await codeflixbots.get_media_preference(user_id)
    doc_text = "📄 Document" + (" ✅" if current_pref == "document" else "")
    vid_text = "🎥 Video" + (" ✅" if current_pref == "video" else "")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(doc_text, callback_data="setmedia_document")],
        [InlineKeyboardButton(vid_text, callback_data="setmedia_video")]
    ])
    
    # Edit the message to reflect the change
    await callback_query.message.edit_text(
        "**Please select the media type you want your files to be uploaded as:**",
        reply_markup=keyboard
    )

    # Acknowledge the callback
    await callback_query.answer(f"Media preference set to: {media_type} ✅")
    
