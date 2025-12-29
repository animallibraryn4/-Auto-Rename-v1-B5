import os
import re
import time
import shutil
import asyncio
import logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from plugins.antinsfw import check_anti_nsfw
from plugins import is_user_verified, send_verification
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_CONCURRENT_TASKS = 3
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}
renaming_operations = {}
recent_verification_checks = {}

# ---------------- REGEX ----------------
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'(\d{3,4}p)', re.IGNORECASE)

# ---------------- HELPERS ----------------
def extract_episode_number(name):
    for p in [pattern1, pattern2, patternX]:
        m = p.search(name)
        if m:
            return m.group(2) if p != patternX else m.group(1)
    return ""

def extract_quality(name):
    m = pattern5.search(name)
    return m.group(1) if m else ""

def standardize_quality_name(q):
    if not q:
        return "Unknown"
    q = q.lower()
    if "2160" in q or "4k" in q:
        return "2160p"
    if "1080" in q:
        return "1080p"
    if "720" in q:
        return "720p"
    if "480" in q:
        return "480p"
    return q

async def convert_to_mkv_video_only(inp, out):
    cmd = shutil.which("ffmpeg")
    if not cmd:
        return False
    p = await asyncio.create_subprocess_exec(
        cmd, "-i", inp, "-map", "0", "-c", "copy", "-y", out,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await p.communicate()
    return os.path.exists(out)

# ---------------- WORKER ----------------
async def user_worker(user_id, client):
    queue = user_queues[user_id]["queue"]
    while True:
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=300)
            async with global_semaphore:
                await process_rename(client, msg)
            queue.task_done()
        except asyncio.TimeoutError:
            user_queues.pop(user_id, None)
            break

# ---------------- MAIN LOGIC ----------------
async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        return

    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        return await message.reply_text("Set rename format first using /autorename")

    media = message.audio or message.video or message.document
    if not media:
        return

    # ✅ FIXED MEDIA TYPE LOGIC
    if message.audio:
        media_type = "audio"
    elif message.video:
        media_type = "video"
    else:
        media_type = "document"

    file_name = media.file_name or "file"
    file_size = media.file_size
    file_id = media.file_id

    if await check_anti_nsfw(file_name, message):
        return

    if file_id in renaming_operations:
        return
    renaming_operations[file_id] = True

    ep = extract_episode_number(file_name)
    quality = extract_quality(file_name)

    renamed = (
        format_template
        .replace("{episode}", ep)
        .replace("{quality}", quality)
        .strip()
    )

    _, ext = os.path.splitext(file_name)
    renamed_file_name = f"{renamed}{ext}"

    os.makedirs("downloads", exist_ok=True)
    download_path = f"downloads/{message.id}_{renamed_file_name}"

    msg = await message.reply_text("⬇️ Downloading...")
    path = await client.download_media(
        message,
        file_name=download_path,
        progress=progress_for_pyrogram,
        progress_args=("Downloading", msg, time.time())
    )

    # ✅ VIDEO ONLY → MKV
    if media_type == "video" and not path.endswith(".mkv"):
        mkv_path = f"{path}.mkv"
        if await convert_to_mkv_video_only(path, mkv_path):
            os.remove(path)
            path = mkv_path
            renamed_file_name = renamed_file_name.replace(ext, ".mkv")

    # ---------------- THUMBNAIL ----------------
    thumb = None
    c_thumb = await codeflixbots.get_thumbnail(user_id)
    if c_thumb:
        thumb = await client.download_media(c_thumb)

    caption = f"**{renamed_file_name}**"

    send = {
        "video": client.send_video,
        "audio": client.send_audio,
        "document": client.send_document
    }[media_type]

    await msg.edit("⬆️ Uploading...")
    await send(
        message.chat.id,
        path,
        file_name=renamed_file_name,
        caption=caption,
        thumb=thumb,
        progress=progress_for_pyrogram,
        progress_args=("Uploading", msg, time.time())
    )

    await msg.delete()

    for p in [path, thumb]:
        if p and os.path.exists(p):
            os.remove(p)

    renaming_operations.pop(file_id, None)

# ---------------- HANDLER ----------------
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        now = time.time()
        if now - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = now
            await send_verification(client, message)
        return

    if user_id not in user_queues:
        user_queues[user_id] = {
            "queue": asyncio.Queue(),
            "task": asyncio.create_task(user_worker(user_id, client))
        }

    await user_queues[user_id]["queue"].put(message)
