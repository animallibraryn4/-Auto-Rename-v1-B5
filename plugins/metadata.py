from helper.database import codeflixbots as db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from config import Txt
from helper.ban_filter import is_not_banned_filter # <-- NEW IMPORT


@Client.on_message(filters.command("metadata") & is_not_banned_filter) # <-- MODIFIED
async def metadata(client, message):
    user_id = message.from_user.id

    # Fetch user metadata from the database
    current = await db.get_metadata(user_id)
    title = await db.get_title(user_id)
    author = await db.get_author(user_id)
    artist = await db.get_artist(user_id)
    video = await db.get_video_title(user_id)
    audio = await db.get_audio(user_id)
    subtitle = await db.get_subtitle(user_id)
    metadata_code = await db.get_metadata_code(user_id)

    # Display the current metadata
    text = f"""
**㊋ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ: {'On ✅' if current else 'Off ❌'}**

**◈ Cᴏᴅᴇ ▹** `{metadata_code}`
**◈ Tɪᴛʟᴇ ▹** `{title if title else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Aᴜᴛʜᴏʀ ▹** `{author if author else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Aʀᴛɪꜱᴛ ▹** `{artist if artist else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Vɪᴅᴇᴏ Sᴛʀᴇᴀᴍ ▹** `{video if video else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Aᴜᴅɪᴏ Sᴛʀᴇᴀᴍ ▹** `{audio if audio else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Sᴜʙᴛɪᴛʟᴇ Sᴛʀᴇᴀᴍ ▹** `{subtitle if subtitle else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
"""

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Tᴜʀɴ Oғғ ❌" if current else "Tᴜʀɴ Oɴ ✅", callback_data="toggle_metadata")],
        [
            InlineKeyboardButton("Sᴇᴛ Cᴏᴅᴇ 🏷️", callback_data="set_meta_code"),
            InlineKeyboardButton("Cʟᴇᴀʀ Aʟʟ 🗑️", callback_data="clear_meta")
        ],
        [
            InlineKeyboardButton("Sᴇᴛ Tɪᴛʟᴇ 📜", callback_data="set_meta_title"),
            InlineKeyboardButton("Sᴇᴛ Aᴜᴛʜᴏʀ ✍️", callback_data="set_meta_author")
        ],
        [
            InlineKeyboardButton("Sᴇᴛ Aʀᴛɪꜱᴛ 🎨", callback_data="set_meta_artist"),
            InlineKeyboardButton("Sᴇᴛ Vɪᴅᴇᴏ 📹", callback_data="set_meta_video")
        ],
        [
            InlineKeyboardButton("Sᴇᴛ Aᴜᴅɪᴏ 🎵", callback_data="set_meta_audio"),
            InlineKeyboardButton("Sᴇᴛ Sᴜʙᴛɪᴛʟᴇ 💬", callback_data="set_meta_subtitle")
        ]
    ])

    await message.reply_text(
        text=text,
        reply_markup=buttons,
        disable_web_page_preview=True
    )


# --- Command Handlers ---

@Client.on_message(filters.private & filters.command('settitle') & is_not_banned_filter) # <-- MODIFIED
async def title(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Tɪᴛʟᴇ\\n\\nExᴀᴍᴩʟᴇ:- /settitle Encoded by @Animelibraryn4**")
    title = message.text.split(" ", 1)[1]
    await db.set_title(message.from_user.id, title=title)
    await message.reply_text("**✅ Tɪᴛʟᴇ Sᴀᴠᴇᴅ**")

@Client.on_message(filters.private & filters.command('setauthor') & is_not_banned_filter) # <-- MODIFIED
async def author(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Aᴜᴛʜᴏʀ\\n\\nExᴀᴍᴩʟᴇ:- /setauthor @Animelibraryn4**")
    author = message.text.split(" ", 1)[1]
    await db.set_author(message.from_user.id, author=author)
    await message.reply_text("**✅ Aᴜᴛʜᴏʀ Sᴀᴠᴇᴅ**")

@Client.on_message(filters.private & filters.command('setartist') & is_not_banned_filter) # <-- MODIFIED
async def artist(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Aʀᴛɪꜱᴛ\\n\\nExᴀᴍᴩʟᴇ:- /setartist @Animelibraryn4**")
    artist = message.text.split(" ", 1)[1]
    await db.set_artist(message.from_user.id, artist=artist)
    await message.reply_text("**✅ Aʀᴛɪꜱᴛ Sᴀᴠᴇᴅ**")

@Client.on_message(filters.private & filters.command('setaudio') & is_not_banned_filter) # <-- MODIFIED
async def audio(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Aᴜᴅɪᴏ Tɪᴛʟᴇ\\n\\nExᴀᴍᴩʟᴇ:- /setaudio @Animelibraryn4**")
    audio = message.text.split(" ", 1)[1]
    await db.set_audio(message.from_user.id, audio=audio)
    await message.reply_text("**✅ Aᴜᴅɪᴏ Sᴀᴠᴇᴅ**")

@Client.on_message(filters.private & filters.command('setsubtitle') & is_not_banned_filter) # <-- MODIFIED
async def subtitle(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Sᴜʙᴛɪᴛʟᴇ Tɪᴛʟᴇ\\n\\nExᴀᴍᴩʟᴇ:- /setsubtitle @Animelibraryn4**")
    subtitle = message.text.split(" ", 1)[1]
    await db.set_subtitle(message.from_user.id, subtitle=subtitle)
    await message.reply_text("**✅ Sᴜʙᴛɪᴛʟᴇ Sᴀᴠᴇᴅ**")

@Client.on_message(filters.private & filters.command('setvideo') & is_not_banned_filter) # <-- MODIFIED
async def video_title(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Vɪᴅᴇᴏ Sᴛʀᴇᴀᴍ Tɪᴛʟᴇ\\n\\nExᴀᴍᴩʟᴇ:- /setvideo @Animelibraryn4**")
    video = message.text.split(" ", 1)[1]
    await db.set_video_title(message.from_user.id, video_title=video)
    await message.reply_text("**✅ Vɪᴅᴇᴏ Sᴛʀᴇᴀᴍ Tɪᴛʟᴇ Sᴀᴠᴇᴅ**")


# --- Callback Handlers ---

@Client.on_callback_query(filters.regex("toggle_metadata"))
async def toggle_metadata_cb(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    current_status = await db.get_metadata(user_id)
    new_status = not current_status
    await db.set_metadata(user_id, new_status)
    await callback.answer(f"Metadata is now {'On ✅' if new_status else 'Off ❌'}")
    
    # Re-fetch and edit the message
    await metadata(client, callback.message)


@Client.on_callback_query(filters.regex("set_meta_code"))
async def set_metadata_code_cb(client, callback: CallbackQuery):
    await callback.message.edit_text(
        "**Sᴇɴᴅ ʏᴏᴜʀ ɴᴇᴡ Mᴇᴛᴀᴅᴀᴛᴀ Cᴏᴅᴇ:**\n(E.g., `Telegram : @Animelibraryn4`)"
    )
    # The next message from the user will be handled by a listener or prompt logic if you have one.
    # For simplicity here, we assume the user follows up with a command /setcode <new_code>
    await callback.answer("Ready to set new code.")
    
@Client.on_message(filters.private & filters.command('setcode') & is_not_banned_filter) # <-- NEW COMMAND FOR SIMPLICITY
async def set_metadata_code_cmd(client, message: Message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Mᴇᴛᴀᴅᴀᴛᴀ Cᴏᴅᴇ\\n\\nExᴀᴍᴩʟᴇ:- /setcode Telegram : @Animelibraryn4**")
    code = message.text.split(" ", 1)[1]
    await db.set_metadata_code(message.from_user.id, code=code)
    await message.reply_text("**✅ Mᴇᴛᴀᴅᴀᴛᴀ Cᴏᴅᴇ Sᴀᴠᴇᴅ**")
    await metadata(client, message) # Show the updated menu

@Client.on_callback_query(filters.regex("clear_meta"))
async def clear_metadata_cb(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    # Reset all metadata fields to their defaults
    await db.set_metadata_code(user_id, "Telegram : @Animelibraryn4")
    await db.set_title(user_id, 'Encoded by @Animelibraryn4')
    await db.set_author(user_id, '@Animelibraryn4')
    await db.set_artist(user_id, '@Animelibraryn4')
    await db.set_audio(user_id, 'By @Animelibraryn4')
    await db.set_subtitle(user_id, 'By @Animelibraryn4')
    await db.set_video_title(user_id, 'By @Animelibraryn4')
    await callback.answer("All metadata fields cleared to default.")
    
    # Re-fetch and edit the message
    await metadata(client, callback.message)


@Client.on_callback_query(filters.regex("^set_meta_(title|author|artist|audio|subtitle|video)"))
async def set_single_metadata_cb(client, callback: CallbackQuery):
    field = callback.data.split("_")[-1]
    
    await callback.message.edit_text(
        f"**Sᴇɴᴅ ʏᴏᴜʀ ɴᴇᴡ {field.upper()} (use the command /set{field} <value>):**\n"
        f"E.g., `/set{field} New {field} Value`"
    )
    await callback.answer(f"Ready to set {field}.")
            
