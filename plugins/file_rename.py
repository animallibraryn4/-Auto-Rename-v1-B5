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

# Global dictionary to prevent duplicate renaming within a short time
renaming_operations = {}
recent_verification_checks = {}

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
            logger.error(f"Error in user_worker for user {user_id}: {e}")
            if user_id in user_queues:
                try: queue.task_done()
                except: pass

def standardize_quality_name(quality):
    """Standardize quality names for consistent storage"""
    if not quality: return "Unknown"
    quality = quality.lower()
    mapping = {'4k': '2160p', '2160p': '2160p', 'hdrip': 'HDrip', 'hd': 'HDrip', '2k': '2K', '4kx264': '4kX264', '4kx265': '4kx265'}
    if quality in mapping: return mapping[quality]
    if quality.endswith('p') and quality[:-1].isdigit(): return quality
    return quality.capitalize()

async def convert_subtitles_advanced(input_path, output_path):
    """
    Advanced subtitle conversion: Detects subtitle types and converts 
    unsupported formats to mov_text for MP4 containers.
    """
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        raise Exception("FFmpeg not found")
    
    # Advanced Mapping: Copy video/audio, convert subtitles to mov_text (standard for MP4)
    # Use -map 0 to ensure all streams (including multiple audio/subs) are carried over
    command = [
        ffmpeg_cmd, '-i', input_path,
        '-map', '0',
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-c:s', 'mov_text',
        '-map_metadata', '0',
        '-movflags', 'faststart',
        '-loglevel', 'error',
        '-y', output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"Subtitle conversion failed: {stderr.decode()}")

async def convert_to_mkv_advanced(input_path, output_path):
    """Convert any video file to MKV format preserving all metadata/streams"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd, '-i', input_path,
        '-map', '0',
        '-c', 'copy',
        '-loglevel', 'error',
        '-y', output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"MKV conversion failed: {stderr.decode()}")

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
    return (match.group(1), match.group(2)) if match else (None, None)

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    if not Config.DUMP_CHANNEL: return
    try:
        dump_caption = (
            f"➜ **File Renamed**\n\n"
            f"» **User:** {user_info['mention']}\n"
            f"» **User ID:** `{user_info['id']}`\n\n"
            f"➲ **Original:** `{file_name}`\n"
            f"➲ **Renamed:** `{renamed_file_name}`"
        )
        
        send_func = {
            "document": client.send_document,
            "video": client.send_video,
            "audio": client.send_audio
        }.get(media_type, client.send_document)

        await send_func(
            Config.DUMP_CHANNEL,
            **{media_type: path},
            file_name=renamed_file_name,
            caption=dump_caption,
            thumb=ph_path if ph_path else None,
        )
    except Exception as e:
        logger.error(f"Dump Error: {e}")

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        if user_id in user_queues:
            while not user_queues[user_id]["queue"].empty():
                try: 
                    user_queues[user_id]["queue"].get_nowait()
                    user_queues[user_id]["queue"].task_done()
                except: break
        return

    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)
    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    # Property extraction
    media = message.document or message.video or message.audio
    if not media: return await message.reply_text("Unsupported File Type")
    
    file_id = media.file_id
    file_name = getattr(media, 'file_name', 'file')
    file_size = media.file_size
    media_type = media_preference or ("video" if message.video else "audio" if message.audio else "document")
    is_pdf = getattr(media, 'mime_type', '') == "application/pdf"

    if await check_anti_nsfw(file_name, message): return 

    if file_id in renaming_operations:
        if (datetime.now() - renaming_operations[file_id]).seconds < 10: return
    renaming_operations[file_id] = datetime.now()

    # Template replacement logic
    ep, se = extract_episode_number(file_name), extract_season_number(file_name)
    vol, ch = extract_volume_chapter(file_name)
    qual = extract_quality(file_name) if not is_pdf else "Unknown"

    replacements = {"[EP.NUM]": ep, "{episode}": ep, "[SE.NUM]": se, "{season}": se, "[Vol{volume}]": f"Vol{vol}" if vol else "", "[Ch{chapter}]": f"Ch{ch}" if ch else "", "[QUALITY]": qual, "{quality}": qual}
    for old, new in replacements.items():
        format_template = format_template.replace(old, str(new or ""))

    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    
    download_path = f"downloads/{message.id}_{renamed_file_name}"
    metadata_path = f"Metadata/{message.id}_{renamed_file_name}"
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(message, file_name=download_path, progress=progress_for_pyrogram, progress_args=("Download Started...", download_msg, time.time()))
    except Exception as e:
        del renaming_operations[file_id]
        return await download_msg.edit(f"**Download Error:** {e}")

    await download_msg.edit("**__Processing Media...__**")

    try:
        ffmpeg_cmd = shutil.which('ffmpeg')
        if not ffmpeg_cmd:
            return await download_msg.edit("FFmpeg not installed on server.")

        # --- Advanced Conversion Logic ---
        # 1. Force MKV if it's a document/video and not already MKV
        if (media_type in ["document", "video"]) and not path.lower().endswith('.mkv'):
            mkv_path = f"{path}.mkv"
            try:
                await convert_to_mkv_advanced(path, mkv_path)
                os.remove(path)
                path = mkv_path
                renamed_file_name = f"{format_template}.mkv"
            except Exception as e:
                logger.warning(f"MKV conversion failed, using original: {e}")

        # 2. Check for incompatible subtitles (ASS/SSA) in MP4 containers
        if path.lower().endswith('.mp4'):
            ffprobe_cmd = shutil.which('ffprobe')
            if ffprobe_cmd:
                cmd = [ffprobe_cmd, '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', path]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
                stdout, _ = await proc.communicate()
                if any(x in stdout.decode().lower() for x in ['ass', 'ssa', 'subrip']):
                    sub_path = f"{path}_sub.mp4"
                    try:
                        await convert_subtitles_advanced(path, sub_path)
                        os.replace(sub_path, path)
                    except Exception as e:
                        logger.error(f"Subtitle conversion error: {e}")

        # 3. Apply Metadata
        final_meta_path = f"{metadata_path}.mkv" if path.lower().endswith('.mkv') else f"{metadata_path}.mp4"
        meta_cmd = [
            ffmpeg_cmd, '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-map', '0', '-c', 'copy', '-loglevel', 'error', '-y', final_meta_path
        ]
        
        proc = await asyncio.create_subprocess_exec(*meta_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        if os.path.exists(final_meta_path):
            path = final_meta_path

        # Thumbnails & Upload
        upload_msg = await download_msg.edit("**__Uploading...__**")
        c_caption = await codeflixbots.get_caption(message.chat.id)
        
        # Thumbnail logic
        c_thumb = await codeflixbots.get_thumbnail(user_id) # Simplified for brevity
        ph_path = await client.download_media(c_thumb) if c_thumb else None
        
        caption = c_caption.format(filename=renamed_file_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_file_name}**"

        # Background Dump
        user_info = {'mention': message.from_user.mention, 'id': message.from_user.id, 'username': message.from_user.username or "N/A"}
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info))

        # Main Upload
        send_args = {
            "chat_id": message.chat.id,
            media_type: path,
            "file_name": renamed_file_name,
            "caption": caption,
            "thumb": ph_path,
            "progress": progress_for_pyrogram,
            "progress_args": ("Upload Started...", upload_msg, time.time())
        }
        
        if media_type == "video": await client.send_video(**send_args)
        elif media_type == "audio": await client.send_audio(**send_args)
        else: await client.send_document(**send_args)

        await upload_msg.delete()

    except Exception as e:
        logger.error(f"Process Error: {e}")
        await download_msg.edit(f"Error: {e}")
    finally:
        for p in [download_path, metadata_path, path, ph_path]:
            if p and os.path.exists(p): 
                try: os.remove(p)
                except: pass
        del renaming_operations[file_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        current_time = time.time()
        if current_time - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = current_time
            await send_verification(client, message)
        return
    
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    await user_queues[user_id]["queue"].put(message)

