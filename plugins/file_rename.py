import os
import re
import time
import shutil
import asyncio
from datetime import datetime
from PIL import Image

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config
from plugins import is_user_verified, send_verification

# =========================================================
# GLOBAL + PER-USER QUEUE SYSTEM (IMPORTANT PART)
# =========================================================

MAX_CONCURRENT_TASKS = 3
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

user_queues = {}   # { user_id: { "queue": Queue, "task": Task } }

# =========================================================
# REGEX PATTERNS
# =========================================================

pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'\b(\d{3,4}p)\b', re.IGNORECASE)

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def extract_episode(filename):
    for p in [pattern1, pattern2, pattern3, pattern3_2, pattern4, patternX]:
        m = p.search(filename)
        if m:
            return m.group(len(m.groups()))
    return ""

def extract_season(filename):
    m = pattern1.search(filename)
    return m.group(1) if m else ""

def extract_quality(filename):
    m = pattern5.search(filename)
    return m.group(1) if m else ""

async def convert_to_mkv(input_path, output_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise Exception("ffmpeg not found")

    cmd = [ffmpeg, "-i", input_path, "-map", "0", "-c", "copy", output_path]
    p = await asyncio.create_subprocess_exec(*cmd)
    await p.communicate()

# =========================================================
# CORE RENAME FUNCTION (UNCHANGED LOGIC + SAFE)
# =========================================================

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id

    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        await message.reply_text("Please set rename format using /autorename")
        return

    if message.document:
        file_name = message.document.file_name
        file_size = message.document.file_size
        media_type = "document"
    elif message.video:
        file_name = message.video.file_name or "video.mp4"
        file_size = message.video.file_size
        media_type = "video"
    elif message.audio:
        file_name = message.audio.file_name or "audio.mp3"
        file_size = message.audio.file_size
        media_type = "audio"
    else:
        return

    if await check_anti_nsfw(file_name, message):
        return

    ep = extract_episode(file_name)
    se = extract_season(file_name)
    quality = extract_quality(file_name)

    format_template = (
        format_template
        .replace("{episode}", ep)
        .replace("{season}", se)
        .replace("{quality}", quality)
    )

    format_template = re.sub(r"\s+", " ", format_template).strip()

    _, ext = os.path.splitext(file_name)
    new_name = f"{format_template}{ext}"

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    download_path = f"downloads/{message.id}_{new_name}"
    final_path = f"Metadata/{message.id}_{new_name}"

    msg = await message.reply_text("Downloading...")

    path = await client.download_media(
        message,
        file_name=download_path,
        progress=progress_for_pyrogram,
        progress_args=("Downloading", msg, time.time())
    )

    # ================= GLOBAL LIMIT HERE =================
    async with global_semaphore:

        await msg.edit("Processing...")

        if media_type in ["video", "document"] and not path.endswith(".mkv"):
            mkv = path + ".mkv"
            await convert_to_mkv(path, mkv)
            os.remove(path)
            path = mkv
            final_path = final_path.replace(ext, ".mkv")
            new_name = new_name.replace(ext, ".mkv")

        ffmpeg = shutil.which("ffmpeg")
        cmd = [
            ffmpeg, "-i", path,
            "-metadata", f"title={await codeflixbots.get_title(user_id)}",
            "-map", "0", "-c", "copy",
            final_path
        ]

        p = await asyncio.create_subprocess_exec(*cmd)
        await p.communicate()

    await msg.edit("Uploading...")

    caption = f"**{new_name}**\nSize: {humanbytes(file_size)}"

    if media_type == "document":
        await client.send_document(message.chat.id, final_path, caption=caption)
    elif media_type == "video":
        await client.send_video(message.chat.id, final_path, caption=caption)
    else:
        await client.send_audio(message.chat.id, final_path, caption=caption)

    await msg.delete()

    for f in [path, final_path]:
        if f and os.path.exists(f):
            os.remove(f)

# =========================================================
# PER-USER WORKER
# =========================================================

async def user_worker(user_id, client):
    queue = user_queues[user_id]["queue"]

    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=300)
            await process_rename(client, message)
            queue.task_done()
        except asyncio.TimeoutError:
            break
        except Exception as e:
            print("Worker error:", e)

    user_queues.pop(user_id, None)

# =========================================================
# MESSAGE HANDLER
# =========================================================

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id

    if not await is_user_verified(user_id):
        await send_verification(client, message)
        return

    if user_id not in user_queues:
        user_queues[user_id] = {
            "queue": asyncio.Queue(),
            "task": asyncio.create_task(user_worker(user_id, client))
        }

    await user_queues[user_id]["queue"].put(message)
