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
MAX_CONCURRENT_TASKS = 3
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}
renaming_operations = {}

# Patterns for extracting file information
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

# --- Helper Functions ---

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

async def convert_to_mkv(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None: raise Exception("FFmpeg not found")
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    """Silently forward renamed file to dump channel as a background task"""
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

    # Extracting file info
    if message.document:
        file_id, file_name, media_type, file_size = message.document.file_id, message.document.file_name, media_preference or "document", message.document.file_size
        is_pdf = message.document.mime_type == "application/pdf"
    elif message.video:
        file_id, file_name, media_type, file_size = message.video.file_id, f"{message.video.file_name}.mp4" if message.video.file_name else "video.mp4", media_preference or "video", message.video.file_size
        is_pdf = False
    elif message.audio:
        file_id, file_name, media_type, file_size = message.audio.file_id, f"{message.audio.file_name}.mp3" if message.audio.file_name else "audio.mp3", media_preference or "audio", message.audio.file_size
        is_pdf = False
    else: return

    if await check_anti_nsfw(file_name, message): return

    # Prepare user info for forwarding
    user_info = {
        'mention': message.from_user.mention,
        'id': message.from_user.id,
        'username': message.from_user.username or "No Username"
    }

    # Extract numbers for renaming
    episode_number = extract_episode_number(file_name)
    season_number = extract_season_number(file_name)
    volume_number, chapter_number = extract_volume_chapter(file_name)
    extracted_quality = extract_quality(file_name) if not is_pdf else None

    # Replace tags in template
    replacements = {"[EP.NUM]": str(episode_number or ""), "{episode}": str(episode_number or ""), "[SE.NUM]": str(season_number or ""), "{season}": str(season_number or ""), "[Vol{volume}]": f"Vol{volume_number}" if volume_number else "", "[Ch{chapter}]": f"Ch{chapter_number}" if chapter_number else "", "[QUALITY]": extracted_quality or "", "{quality}": extracted_quality or ""}
    for old, new in replacements.items(): format_template = format_template.replace(old, new)
    
    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    renamed_file_path = f"downloads/{renamed_file_name}"
    metadata_file_path = f"Metadata/{renamed_file_name}"

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(message, file_name=renamed_file_path, progress=progress_for_pyrogram, progress_args=("Download Started...", download_msg, time.time()))
    except Exception as e: return await download_msg.edit(f"**Download Error:** {e}")

    # --- Global Semaphore for FFmpeg/Metadata ---
    async with global_semaphore:
        await download_msg.edit("**__Processing Metadata...__**")
        if (media_type in ["document", "video"]) and not path.lower().endswith('.mkv'):
            temp_mkv = f"{path}.temp.mkv"
            await convert_to_mkv(path, temp_mkv)
            os.remove(path)
            os.rename(temp_mkv, path)
            renamed_file_name = f"{format_template}.mkv"
            metadata_file_path = f"Metadata/{renamed_file_name}"

        ffmpeg_cmd = shutil.which('ffmpeg')
        metadata_command = [ffmpeg_cmd, '-i', path, '-metadata', f'title={await codeflixbots.get_title(user_id)}', '-metadata', f'artist={await codeflixbots.get_artist(user_id)}', '-map', '0', '-c', 'copy', '-loglevel', 'error', metadata_file_path]
        process = await asyncio.create_subprocess_exec(*metadata_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        path = metadata_file_path

    # --- Upload Logic ---
    upload_msg = await download_msg.edit("**__Uploading...__**")
    c_caption = await codeflixbots.get_caption(message.chat.id)
    caption = c_caption.format(filename=renamed_file_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_file_name}**"

    ph_path = None
    c_thumb = await codeflixbots.get_thumbnail(user_id)
    if c_thumb: ph_path = await client.download_media(c_thumb)

    try:
        # Trigger background forward task
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info))
        
        # Main Upload to User
        if media_type == "document": 
            await client.send_document(message.chat.id, document=path, thumb=ph_path, caption=caption, progress=progress_for_pyrogram, progress_args=("Upload Started...", upload_msg, time.time()))
        elif media_type == "video": 
            await client.send_video(message.chat.id, video=path, caption=caption, thumb=ph_path, progress=progress_for_pyrogram, progress_args=("Upload Started...", upload_msg, time.time()))
        elif media_type == "audio":
            await client.send_audio(message.chat.id, audio=path, caption=caption, thumb=ph_path, progress=progress_for_pyrogram, progress_args=("Upload Started...", upload_msg, time.time()))
    finally:
        await upload_msg.delete()
        if os.path.exists(renamed_file_path): os.remove(renamed_file_path)
        # Note: we don't remove metadata_file_path/ph_path here because the background forward task might still be using them. 
        # For a production bot, you'd want a more robust cleanup or wait for the forward task to finish.

# --- Queue and Worker Logic ---

async def user_worker(user_id, client):
    queue = user_queues[user_id]["queue"]
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=300)
            await process_rename(client, message)
            queue.task_done()
        except asyncio.TimeoutError: break
        except Exception as e: print(f"Worker Error: {e}")
    if user_id in user_queues: del user_queues[user_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        await send_verification(client, message)
        return
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    await user_queues[user_id]["queue"].put(message)
