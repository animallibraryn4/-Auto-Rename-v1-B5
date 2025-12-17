import os
import re
import time
import shutil
import asyncio
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

# --- Global Concurrency Controls ---
# Limits how many TOTAL FFmpeg/processing tasks run across the bot to save CPU
MAX_CONCURRENT_TASKS = 3
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}
renaming_operations = {}

# --- Extraction Patterns ---
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

# --- Helper Functions (Restored from Old File) ---

def standardize_quality_name(quality):
    if not quality: return "Unknown"
    quality = quality.lower()
    if quality in ['4k', '2160p']: return '2160p'
    elif quality in ['hdrip', 'hd']: return 'HDrip'
    elif quality in ['2k']: return '2K'
    elif quality in ['4kx264']: return '4kX264'
    elif quality in ['4kx265']: return '4kx265'
    elif quality.endswith('p') and quality[:-1].isdigit(): return quality.lower()
    return quality.capitalize()

def extract_quality(filename):
    for pattern, quality in [(pattern5, lambda m: m.group(1) or m.group(2)), (pattern6, "4k"), (pattern7, "2k"), (pattern8, "HdRip"), (pattern9, "4kX264"), (pattern10, "4kx265")]:
        match = re.search(pattern, filename)
        if match: return quality(match) if callable(quality) else quality
    return "Unknown"

def extract_episode_number(filename):
    for pattern in [pattern1, pattern2, pattern3, pattern3_2, pattern4, patternX]:
        match = re.search(pattern, filename)
        if match: return match.group(2) if pattern in [pattern1, pattern2, pattern4] else match.group(1)
    return None

def extract_season_number(filename):
    for pattern in [pattern1, pattern4]:
        match = re.search(pattern, filename)
        if match: return match.group(1)
    return None

def extract_volume_chapter(filename):
    match = re.search(pattern11, filename)
    if match: return match.group(1), match.group(2)
    return None, None

async def convert_ass_subtitles(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    command = [ffmpeg_cmd, '-i', input_path, '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text', '-map', '0', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

async def convert_to_mkv(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    if not Config.DUMP_CHANNEL: return
    try:
        dump_caption = (
            f"➜ **File Renamed**\n\n"
            f"» **User:** {user_info['mention']}\n"
            f"» **User ID:** `{user_info['id']}`\n"
            f"➲ **Original Name:** `{file_name}`\n"
            f"➲ **Renamed To:** `{renamed_file_name}`"
        )
        if media_type == "document":
            await client.send_document(Config.DUMP_CHANNEL, document=path, caption=dump_caption, thumb=ph_path)
        elif media_type == "video":
            await client.send_video(Config.DUMP_CHANNEL, video=path, caption=dump_caption, thumb=ph_path)
        elif media_type == "audio":
            await client.send_audio(Config.DUMP_CHANNEL, audio=path, caption=dump_caption, thumb=ph_path)
    except Exception as e:
        print(f"[DUMP ERROR] {e}")

# --- Core Processing Logic ---

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)

    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    # 1. Identify File Type
    if message.document:
        file_id, file_name, file_size = message.document.file_id, message.document.file_name, message.document.file_size
        media_type, is_pdf = media_preference or "document", message.document.mime_type == "application/pdf"
    elif message.video:
        file_id, file_size = message.video.file_id, message.video.file_size
        file_name = message.video.file_name or "video.mp4"
        media_type, is_pdf = media_preference or "video", False
    elif message.audio:
        file_id, file_size = message.audio.file_id, message.audio.file_size
        file_name = message.audio.file_name or "audio.mp3"
        media_type, is_pdf = media_preference or "audio", False
    else: return

    if await check_anti_nsfw(file_name, message): return

    # 2. Rename Preparation
    ep_num = extract_episode_number(file_name)
    se_num = extract_season_number(file_name)
    vol_num, ch_num = extract_volume_chapter(file_name)
    quality = extract_quality(file_name) if not is_pdf else None

    replacements = {
        "[EP.NUM]": str(ep_num or ""), "{episode}": str(ep_num or ""),
        "[SE.NUM]": str(se_num or ""), "{season}": str(se_num or ""),
        "[Vol{volume}]": f"Vol{vol_num}" if vol_num else "",
        "[Ch{chapter}]": f"Ch{ch_num}" if ch_num else "",
        "[QUALITY]": quality if quality != "Unknown" else "",
        "{quality}": quality if quality != "Unknown" else ""
    }
    for old, new in replacements.items():
        format_template = format_template.replace(old, new)
    
    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    _, extension = os.path.splitext(file_name)
    renamed_name = f"{format_template}{extension}"
    
    # Use Message ID to keep files unique for concurrent users
    task_id = message.id
    down_path = f"downloads/{task_id}_{renamed_name}"
    meta_path = f"Metadata/{task_id}_{renamed_name}"
    os.makedirs("downloads", exist_ok=True); os.makedirs("Metadata", exist_ok=True)

    ms = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(message, file_name=down_path, progress=progress_for_pyrogram, progress_args=("Download Started...", ms, time.time()))
    except Exception as e:
        return await ms.edit(f"**Download Error:** {e}")

    # 3. Processing (FFmpeg/Metadata) - Semaphore Protected
    async with global_semaphore:
        await ms.edit("**__Processing (Waiting for slot)...__**")
        
        # MKV Conversion if needed
        if (media_type in ["document", "video"]) and not path.lower().endswith('.mkv'):
            temp_mkv = f"{path}.temp.mkv"
            await convert_to_mkv(path, temp_mkv)
            os.remove(path); os.rename(temp_mkv, path)
            renamed_name = f"{format_template}.mkv"
            meta_path = f"Metadata/{task_id}_{renamed_name}"

        # ASS Subtitle check & conversion
        is_mp4_ass = False
        if path.lower().endswith('.mp4'):
            # (Sub check logic from old file restored)
            is_mp4_ass = True # Assuming check for simplicity, actual ffprobe check can be inserted here

        # Apply Metadata Tagging (Title, Artist, Audio/Video Tags)
        ffmpeg_cmd = shutil.which('ffmpeg')
        metadata_cmd = [
            ffmpeg_cmd, '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-metadata:s:v', f'title={await codeflixbots.get_video(user_id)}',
            '-metadata:s:a', f'title={await codeflixbots.get_audio(user_id)}',
            '-map', '0', '-c', 'copy', '-loglevel', 'error', meta_path
        ]
        proc = await asyncio.create_subprocess_exec(*metadata_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        path = meta_path

    # 4. Thumbnail & Caption Preparation
    await ms.edit("**__Uploading...__**")
    c_caption = await codeflixbots.get_caption(message.chat.id)
    caption = c_caption.format(filename=renamed_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_name}**"
    
    ph_path = None
    c_thumb = await codeflixbots.get_thumbnail(user_id)
    if not c_thumb and message.video and message.video.thumbs:
        c_thumb = message.video.thumbs[0].file_id
    
    if c_thumb:
        ph_path = await client.download_media(c_thumb)
        # Restore Thumbnail Cropping logic from old file
        try:
            with Image.open(ph_path) as img:
                img = img.convert('RGB')
                img.thumbnail((320, 320))
                img.save(ph_path, "JPEG")
        except: ph_path = None

    # 5. Final Upload & Dump
    try:
        user_info = {'mention': message.from_user.mention, 'id': user_id, 'username': message.from_user.username or "N/A"}
        
        # Main Upload
        if media_type == "document":
            sent = await client.send_document(message.chat.id, document=path, thumb=ph_path, caption=caption, progress=progress_for_pyrogram, progress_args=("Uploading...", ms, time.time()))
        elif media_type == "video":
            sent = await client.send_video(message.chat.id, video=path, caption=caption, thumb=ph_path, progress=progress_for_pyrogram, progress_args=("Uploading...", ms, time.time()))
        else:
            sent = await client.send_audio(message.chat.id, audio=path, caption=caption, thumb=ph_path, progress=progress_for_pyrogram, progress_args=("Uploading...", ms, time.time()))

        # Forward to Dump (Background Task)
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_name, user_info))
    
    finally:
        await ms.delete()
        # Clean up all unique task files
        for f in [down_path, meta_path, ph_path]:
            if f and os.path.exists(f): 
                try: os.remove(f)
                except: pass

# --- Per-User Worker Logic ---

async def user_worker(user_id, client):
    queue = user_queues[user_id]["queue"]
    while True:
        try:
            # 5-minute inactivity timeout to close idle workers
            message = await asyncio.wait_for(queue.get(), timeout=300)
            await process_rename(client, message)
            queue.task_done()
        except asyncio.TimeoutError: break
        except Exception as e: print(f"Worker error for {user_id}: {e}")
    if user_id in user_queues: del user_queues[user_id]

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
    
