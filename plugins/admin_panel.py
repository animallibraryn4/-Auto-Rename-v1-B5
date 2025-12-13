from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os, sys, time, asyncio, logging, datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
ADMIN_USER_ID = Config.ADMIN

# ================= RESTART =================

@Client.on_message(filters.private & filters.command("restart") & filters.user(ADMIN_USER_ID))
async def restart_bot(b, m):
    await m.reply_text("Restarting...")
    await b.stop()
    time.sleep(2)
    os.execl(sys.executable, sys.executable, *sys.argv)

# ================= TUTORIAL =================

@Client.on_message(filters.private & filters.command("tutorial"))
async def tutorial(bot: Client, message: Message):
    try:
        format_template = await codeflixbots.get_format_template(message.from_user.id)
        await message.reply_text(
            Txt.FILE_NAME_TXT.format(format_template=format_template),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("OWNER", url="https://t.me/Anime_library_n4")]
            ])
        )
    except Exception:
        logger.exception("Tutorial error")

# ================= STATS =================

@Client.on_message(filters.command(["stats", "status"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    try:
        total_users = await codeflixbots.total_users_count()
        uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - bot.uptime))
        await message.reply_text(
            f"Uptime: {uptime}\nUsers: {total_users}"
        )
    except Exception:
        logger.exception("Stats error")

# ================= BAN =================

@Client.on_message(filters.private & filters.command("ban") & filters.user(Config.ADMIN))
async def ban_user_command(bot: Client, message: Message):
    try:
        user_id = int(message.command[1])
        reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason"

        await codeflixbots.ban_user(user_id, reason)

        await message.reply_text(f"User `{user_id}` banned\nReason: {reason}")

        asyncio.create_task(
            bot.send_message(
                Config.LOG_CHANNEL,
                f"User {user_id} banned by {message.from_user.id}"
            )
        )

    except Exception:
        logger.exception("Ban command error")

# ================= UNBAN =================

@Client.on_message(filters.private & filters.command("unban") & filters.user(Config.ADMIN))
async def unban_user_command(bot: Client, message: Message):
    try:
        user_id = int(message.command[1])
        await codeflixbots.unban_user(user_id)
        await message.reply_text(f"User `{user_id}` unbanned")
    except Exception:
        logger.exception("Unban error")
