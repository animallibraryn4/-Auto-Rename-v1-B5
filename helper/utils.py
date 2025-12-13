import math, time, asyncio, re, logging
from datetime import datetime
from pytz import timezone
from config import Config, Txt
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ================= PROGRESS =================

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if diff <= 0:
        return

    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff else 0
        elapsed_time = round(diff) * 1000
        eta = round((total - current) / speed) * 1000 if speed else 0

        progress = "■" * int(percentage / 5) + "□" * (20 - int(percentage / 5))
        text = (
            f"{ud_type}\n\n"
            f"{progress}\n"
            f"{round(percentage,2)}%\n"
            f"{humanbytes(current)} / {humanbytes(total)}\n"
            f"Speed: {humanbytes(speed)}/s\n"
            f"ETA: {TimeFormatter(eta)}"
        )

        try:
            await message.edit(
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("CANCEL", callback_data="close")]]
                )
            )
        except:
            pass

# ================= HELPERS =================

def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{round(size,2)} {units[n]}"

def TimeFormatter(ms):
    seconds, _ = divmod(int(ms), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    result = []
    if days: result.append(f"{days}d")
    if hours: result.append(f"{hours}h")
    if minutes: result.append(f"{minutes}m")
    if seconds: result.append(f"{seconds}s")

    return " ".join(result) if result else "0s"

# ================= SAFE LOG =================

async def send_log(bot, user):
    if not Config.LOG_CHANNEL:
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            bot.send_message(
                Config.LOG_CHANNEL,
                f"👤 New User\n"
                f"Name: {user.first_name}\n"
                f"ID: `{user.id}`"
            )
        )
    except Exception:
        logging.exception("send_log failed")

# ================= RENAME UTILS =================

def add_prefix_suffix(input_string, prefix='', suffix=''):
    pattern = r'(?P<filename>.*?)(\.\w+)?$'
    match = re.search(pattern, input_string)
    if not match:
        return input_string

    filename = match.group('filename')
    ext = match.group(2) or ''
    prefix = prefix or ''
    suffix = suffix or ''

    return f"{prefix}{filename}{suffix}{ext}"
