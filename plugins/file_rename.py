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

# ===== Global + Per-User Queue System =====
MAX_CONCURRENT_TASKS = 3  
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}

# Global dictionary to prevent duplicate renaming within a short time
renaming_operations = {}
# Cooldown for verification messages to prevent flooding on batch uploads
verification_cooldown = {}

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

async def user_worker(user_id, client):
    """Worker to process files for a specific user"""
    queue = user_queues[user_id]["queue"]
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=300)
            async with global_semaphore:
                await process_rename(client, message)
            queue.task_done()
        except asyncio.TimeoutError:
            if user_id in user_queues:
                del user_queues[user_id]
            break
        except Exception as e:
            print(f"Error in user_worker for user {user_id}: {e}")
            if user_id in user_queues:
                try:
                    queue.task_done()
                except ValueError:
                    pass

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

async def convert_ass_subtitles(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None: raise Exception("FFmpeg not found")
    command = [ffmpeg_cmd, '-i', input_path, '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text', '-map', '0', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    if process.returncode != 0: raise Exception("Subtitle conversion failed")

async def convert_to_mkv(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None: raise Exception("FFmpeg not found")
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await process.communicate()
    if process.returncode != 0: raise Exception("MKV conversion failed")

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

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    if not Config.DUMP_CHANNEL: return
    try:
        dump_caption = (f"➜ **File Renamed**\n\n» **User:** {user_info['mention']}\n» **User ID:** `{user_info['id']}`\n➲ **Original Name:** `{file_name}`\n➲ **Renamed To:** `{renamed_file_name}`")
        if media_type == "document":
            await client.send_document(Config.DUMP_CHANNEL, document=path, file_name=renamed_file_name, caption=dump_caption, thumb=ph_path)
        elif media_type == "video":
            await client.send_video(Config.DUMP_CHANNEL, video=path, file_name=renamed_file_name, caption=dump_caption, thumb=ph_path)
        elif media_type == "audio":
            await client.send_audio(Config.DUMP_CHANNEL, audio=path, file_name=renamed_file_name, caption=dump_caption, thumb=ph_path)
    except Exception as e:
        print(f"[DUMP ERROR] {e}")

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    ph_path = None
    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)

    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    if message.document:
        file_id, file_name, file_size = message.document.file_id, message.document.file_name, message.document.file_size
        media_type, is_pdf = media_preference or "document", message.document.mime_type == "application/pdf"
    elif message.video:
        file_id, file_name, file_size = message.video.file_id, f"{message.video.file_name}.mp4" if message.video.file_name else "video.mp4", message.video.file_size
        media_type, is_pdf = media_preference or "video", False
    elif message.audio:
        file_id, file_name, file_size = message.audio.file_id, f"{message.audio.file_name}.mp3" if message.audio.file_name else "audio.mp3", message.audio.file_size
        media_type, is_pdf = media_preference or "audio", False
    else: return

    if await check_anti_nsfw(file_name, message): return

    episode_number, season_number = extract_episode_number(file_name), extract_season_number(file_name)
    vol, ch = extract_volume_chapter(file_name)
    quality = extract_quality(file_name) if not is_pdf else None

    replacements = {"[EP.NUM]": str(episode_number or ""), "{episode}": str(episode_number or ""), "[SE.NUM]": str(season_number or ""), "{season}": str(season_number or ""), "[Vol{volume}]": f"Vol{vol}" if vol else "", "[Ch{chapter}]": f"Ch{ch}" if ch else "", "[QUALITY]": quality if quality != "Unknown" else "", "{quality}": quality if quality != "Unknown" else ""}
    for old, new in replacements.items(): format_template = format_template.replace(old, new)
    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")

    _, ext = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{ext}"
    download_path = f"downloads/{message.id}_{renamed_file_name}"
    os.makedirs("downloads", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(message, file_name=download_path, progress=progress_for_pyrogram, progress_args=("Download Started...", download_msg, time.time()))
    except Exception as e: return await download_msg.edit(f"**Download Error:** {e}")

    await download_msg.edit("**__Uploading...__**")
    c_caption = await codeflixbots.get_caption(message.chat.id)
    caption = c_caption.format(filename=renamed_file_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_file_name}**"

    try:
        if media_type == "video":
            await client.send_video(message.chat.id, video=path, caption=caption, file_name=renamed_file_name)
        else:
            await client.send_document(message.chat.id, document=path, caption=caption, file_name=renamed_file_name)
    except Exception as e: await upload_msg.edit(f"Error: {e}")
    finally:
        if os.path.exists(download_path): os.remove(download_path)
        await download_msg.delete()

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    
    # 1. Verification Check with Cooldown
    if not await is_user_verified(user_id):
        current_time = time.time()
        # If we sent a link in the last 30 seconds, don't send another one to this user
        last_sent = verification_cooldown.get(user_id, 0)
        if current_time - last_sent < 30:
            return 
        
        verification_cooldown[user_id] = current_time
        await send_verification(client, message)
        return
    
    # 2. Add to Queue if Verified
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    await user_queues[user_id]["queue"].put(message)
    
