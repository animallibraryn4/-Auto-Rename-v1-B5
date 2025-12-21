import os
import re
import time
import shutil
import asyncio
import logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config
from plugins import is_user_verified, send_verification

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== Global + Per-User Queue System =====
MAX_CONCURRENT_TASKS = 3  
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}

renaming_operations = {}
recent_verification_checks = {}

# Regex Patterns
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)]>}]?', re.IGNORECASE)
pattern11 = re.compile(r'Vol(\d+)\s*-\s*Ch(\d+)', re.IGNORECASE)

async def user_worker(user_id, client):
    queue = user_queues[user_id]["queue"]
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=300)
            async with global_semaphore:
                await process_rename(client, message)
            queue.task_done()
        except asyncio.TimeoutError:
            if user_id in user_queues: del user_queues[user_id]
            break
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            if user_id in user_queues:
                try: queue.task_done()
                except: pass

async def convert_subtitles_advanced(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: raise Exception("FFmpeg not found")
    
    # Convert all subtitle streams to mov_text for MP4 compatibility
    command = [
        ffmpeg_cmd, '-i', input_path,
        '-map', '0', '-c:v', 'copy', '-c:a', 'copy',
        '-c:s', 'mov_text', '-map_metadata', '0',
        '-movflags', 'faststart', '-loglevel', 'error', '-y', output_path
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

async def convert_to_mkv_advanced(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: raise Exception("FFmpeg not found")
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', '-y', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

def extract_quality(filename):
    for pattern, quality in [(pattern5, lambda m: m.group(1) or m.group(2)), (pattern6, "4k"), (pattern7, "2k"), (pattern8, "HdRip"), (pattern9, "4kX264"), (pattern10, "4kx265")]:
        match = re.search(pattern, filename)
        if match: return quality(match) if callable(quality) else quality
    return "Unknown"

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id): return

    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)
    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    media = message.document or message.video or message.audio
    if not media: return
    
    file_id = media.file_id
    file_name = getattr(media, 'file_name', 'file.mp4')
    file_size = media.file_size
    media_type = media_preference or ("video" if message.video else "audio" if message.audio else "document")

    # Rename Logic
    ep = extract_episode_number(file_name)
    se = extract_season_number(file_name)
    qual = extract_quality(file_name)
    
    renamed_name = format_template.replace("[EP.NUM]", str(ep or "")).replace("{episode}", str(ep or ""))
    renamed_name = renamed_name.replace("[QUALITY]", str(qual or "")).replace("{quality}", str(qual or ""))
    renamed_name = re.sub(r'\s+', ' ', renamed_name).strip()
    
    _, ext = os.path.splitext(file_name)
    final_name = f"{renamed_name}{ext}"
    
    dl_path = f"downloads/{message.id}_{final_name}"
    os.makedirs("downloads", exist_ok=True)

    msg = await message.reply_text("🚀 **Downloading...**")
    try:
        path = await client.download_media(message, file_name=dl_path, progress=progress_for_pyrogram, progress_args=("Downloading", msg, time.time()))
    except Exception as e:
        return await msg.edit(f"Download Error: {e}")

    await msg.edit("⚙️ **Processing Subtitles & Metadata...**")

    # --- Precise Thumbnail Logic ---
    c_thumb = await codeflixbots.get_thumbnail(user_id)
    ph_path = None
    if c_thumb:
        ph_path = await client.download_media(c_thumb)
        if ph_path:
            with Image.open(ph_path) as img:
                img = img.convert("RGB")
                width, height = img.size
                # Precise Center Crop to 320x320
                min_dim = min(width, height)
                left = (width - min_dim) / 2
                top = (height - min_dim) / 2
                right = (width + min_dim) / 2
                bottom = (height + min_dim) / 2
                img = img.crop((left, top, right, bottom))
                img = img.resize((320, 320), Image.LANCZOS)
                img.save(ph_path, "JPEG", quality=95)

    # Subtitle Conversion
    if path.endswith(".mp4"):
        temp_path = f"{path}_fixed.mp4"
        await convert_subtitles_advanced(path, temp_path)
        if os.path.exists(temp_path):
            os.replace(temp_path, path)

    await msg.edit("📤 **Uploading...**")
    try:
        caption = f"**{final_name}**"
        send_func = getattr(client, f"send_{media_type}")
        await send_func(
            message.chat.id,
            **{media_type: path},
            file_name=final_name,
            caption=caption,
            thumb=ph_path,
            progress=progress_for_pyrogram,
            progress_args=("Uploading", msg, time.time())
        )
    finally:
        if os.path.exists(path): os.remove(path)
        if ph_path and os.path.exists(ph_path): os.remove(ph_path)
        await msg.delete()

def extract_episode_number(f):
    m = re.search(r'(?:E|EP|Episode)\s*(\d+)', f, re.I) or re.search(r'-\s*(\d+)', f)
    return m.group(1) if m else None

def extract_season_number(f):
    m = re.search(r'S(\d+)', f, re.I)
    return m.group(1) if m else None

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        await send_verification(client, message)
        return
    
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    await user_queues[user_id]["queue"].put(message)
                                                                                                  
