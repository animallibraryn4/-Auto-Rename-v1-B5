from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from config import Config
import asyncio

# =============================
# Rename Queue
# =============================
rename_queue = asyncio.Queue()


# =============================
# Ban Check Before Queue
# =============================
async def check_ban_before_queue(client, message):
    """Check if user is banned before adding to rename queue"""
    user_id = message.from_user.id

    # Skip ban check for admins
    if user_id in Config.ADMIN:
        return False

    # Check ban status
    is_banned = await codeflixbots.is_banned(user_id)

    if is_banned:
        ban_info = await codeflixbots.get_ban_info(user_id)
        ban_reason = (
            ban_info.get("ban_reason", "No reason provided")
            if ban_info else "No reason provided"
        )

        await message.reply_text(
            "🚫 **You are banned and cannot use this bot.**\n\n"
            f"**Reason:** {ban_reason}\n\n"
            "If you want access, please contact @Anime_Library_N4 for permission."
        )
        return True  # User is banned

    return False  # User is not banned


# =============================
# Auto Rename Command
# =============================
@Client.on_message(filters.private & filters.command("autorename"))
async def auto_rename_command(client, message):
    user_id = message.from_user.id

    # Ban check
    if await check_ban_before_queue(client, message):
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text(
            "**Please provide a new name after /autorename**\n\n"
            "**Example:**\n"
            "`/autorename S[SE.NUM]EP[EP.NUM] Title [QUALITY]`"
        )
        return

    format_template = command_parts[1].strip()

    await codeflixbots.set_format_template(user_id, format_template)

    await message.reply_text(
        "✅ **Auto-Rename Enabled Successfully!**\n\n"
        "📂 Now send your file(s).\n\n"
        f"📝 **Saved Template:** `{format_template}`"
    )


# =============================
# Set Media Type Command
# =============================
@Client.on_message(filters.private & filters.command("setmedia"))
async def set_media_command(client, message):
    # Ban check
    if await check_ban_before_queue(client, message):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Document", callback_data="setmedia_document")],
        [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
    ])

    await message.reply_text(
        "**Select preferred media type:**",
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^setmedia_"))
async def handle_media_selection(client, callback_query):
    user_id = callback_query.from_user.id
    media_type = callback_query.data.split("_", 1)[1]

    await codeflixbots.set_media_preference(user_id, media_type)

    await callback_query.answer("Saved ✅")
    await callback_query.message.edit_text(
        f"**Media preference set to:** `{media_type}` ✅"
    )


# =============================
# Auto Rename File Handler
# =============================
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    # Ban check before queue
    is_banned = await check_ban_before_queue(client, message)
    if is_banned:
        return  # Do not add to queue

    # Add to rename queue
    await rename_queue.put((client, message))


# =============================
# Queue Processor (Example)
# =============================
async def rename_worker():
    while True:
        client, message = await rename_queue.get()
        try:
            # Your existing rename logic here
            pass
        except Exception as e:
            await message.reply_text(f"❌ Error: `{e}`")
        finally:
            rename_queue.task_done()
