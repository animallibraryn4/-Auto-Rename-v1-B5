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
MAX_CONCURRENT_TASKS = 3  # server capacity ke hisaab se change kar sakte ho
global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
user_queues = {}

# Global dictionary to prevent duplicate renaming within a short time
renaming_operations = {}

# Dictionary to track verification status checks to prevent multiple verifications
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
            print(f"Error in user_worker for user {user_id}: {e}")
            if user_id in user_queues:
                try:
                    queue.task_done()
                except ValueError:
                    pass

def standardize_quality_name(quality):
    """Standardize quality names for consistent storage"""
    if not quality:
        return "Unknown"
    quality = quality.lower()
    if quality in ['4k', '2160p']:
        return '2160p'
    elif quality in ['hdrip', 'hd']:
        return 'HDrip'
    elif quality in ['2k']:
        return '2K'
    elif quality in ['4kx264']:
        return '4kX264'
    elif quality in ['4kx265']:
        return '4kx265'
    elif quality.endswith('p') and quality[:-1].isdigit():
        return quality.lower()
    return quality.capitalize()

async def convert_ass_subtitles(input_path, output_path):
    """Handle different subtitle types appropriately based on container."""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None:
        raise Exception("FFmpeg not found")
    
    if output_path.lower().endswith('.mp4'):
        command = [
            ffmpeg_cmd, '-y', '-nostdin',
            '-i', input_path,
            '-c:v', 'copy', '-c:a', 'copy',
            '-c:s', 'mov_text',
            '-map', '0',
            '-map', '-0:s:codec=hdmv_pgs_subtitle',
            '-map', '-0:s:codec=dvd_subtitle',
            '-loglevel', 'error',
            output_path
        ]
    else:
        command = [
            ffmpeg_cmd, '-y', '-nostdin',
            '-i', input_path,
            '-c', 'copy',
            '-loglevel', 'error',
            output_path
        ]
    
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        if output_path.lower().endswith('.mp4'):
            mkv_path = output_path.rsplit('.', 1)[0] + '.mkv'
            fallback_command = [ffmpeg_cmd, '-y', '-nostdin', '-i', input_path, '-c', 'copy', '-loglevel', 'error', mkv_path]
            fallback_process = await asyncio.create_subprocess_exec(*fallback_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await fallback_process.communicate()
            if fallback_process.returncode == 0:
                return mkv_path
        raise Exception(f"Subtitle conversion failed: {stderr.decode()}")
    return output_path

async def convert_to_mkv(input_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    command = [ffmpeg_cmd, '-y', '-nostdin', '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
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
    if match: return match.group(1), match.group(2)
    return None, None

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    if not Config.DUMP_CHANNEL: return
    try:
        dump_caption = (f"➜ **File Renamed**\n\n» **User:** {user_info['mention']}\n» **User ID:** `{user_info['id']}`\n"
                        f"➲ **Original Name:** `{file_name}`\n➲ **Renamed To:** `{renamed_file_name}`\n\n🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        send_func = getattr(client, f"send_{media_type}")
        await send_func(Config.DUMP_CHANNEL, **{media_type: path}, file_name=renamed_file_name, caption=dump_caption, thumb=ph_path if ph_path else None)
    except Exception as e:
        print(f"[DUMP ERROR] {e}")

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        if user_id in user_queues:
            while not user_queues[user_id]["queue"].empty():
                try: user_queues[user_id]["queue"].get_nowait(); user_queues[user_id]["queue"].task_done()
                except asyncio.QueueEmpty: break
        return

    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)
    if not format_template: return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    if message.document:
        file_id, file_name, file_size = message.document.file_id, message.document.file_name, message.document.file_size
        media_type, is_pdf = media_preference or "document", message.document.mime_type == "application/pdf"
    elif message.video:
        file_id, file_name, file_size = message.video.file_id, message.video.file_name or "video.mp4", message.video.file_size
        media_type, is_pdf = media_preference or "video", False
    elif message.audio:
        file_id, file_name, file_size = message.audio.file_id, message.audio.file_name or "audio.mp3", message.audio.file_size
        media_type, is_pdf = media_preference or "audio", False
    else: return await message.reply_text("Unsupported File Type")

    if await check_anti_nsfw(file_name, message): return
    if file_id in renaming_operations and (datetime.now() - renaming_operations[file_id]).seconds < 10: return
    renaming_operations[file_id] = datetime.now()

    episode_number, season_number = extract_episode_number(file_name), extract_season_number(file_name)
    volume_number, chapter_number = extract_volume_chapter(file_name)
    extracted_quality = extract_quality(file_name) if not is_pdf else None

    replacements = {"[EP.NUM]": str(episode_number or ""), "{episode}": str(episode_number or ""), "[SE.NUM]": str(season_number or ""), "{season}": str(season_number or ""), "[Vol{volume}]": f"Vol{volume_number}" if volume_number else "", "[Ch{chapter}]": f"Ch{chapter_number}" if chapter_number else "", "[QUALITY]": extracted_quality if extracted_quality != "Unknown" else "", "{quality}": extracted_quality if extracted_quality != "Unknown" else ""}
    for old, new in replacements.items(): format_template = format_template.replace(old, new)
    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    format_template = re.sub(r'\[\s*\]', '', format_template)

    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    download_path = f"downloads/{message.id}_{renamed_file_name}"
    metadata_file_path = f"Metadata/{message.id}_{renamed_file_name}"
    os.makedirs("downloads", exist_ok=True); os.makedirs("Metadata", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(message, file_name=download_path, progress=progress_for_pyrogram, progress_args=("Download Started...", download_msg, time.time()))
    except Exception as e:
        del renaming_operations[file_id]
        return await download_msg.edit(f"**Download Error:** {e}")

    await download_msg.edit("**__Processing File...__**")
    try:
        ffmpeg_cmd = shutil.which('ffmpeg')
        if (media_type in ["document", "video"]) and not path.lower().endswith('.mkv'):
            temp_mkv = f"{path}.mkv"
            await convert_to_mkv(path, temp_mkv)
            os.remove(path); path = temp_mkv
            renamed_file_name = f"{format_template}.mkv"
            metadata_file_path = f"Metadata/{message.id}_{renamed_file_name}"

        # Subtitle and Metadata logic
        has_subtitles = False
        try:
            ffprobe_cmd = shutil.which('ffprobe')
            proc = await asyncio.create_subprocess_exec(ffprobe_cmd, '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', path, stdout=asyncio.subprocess.PIPE)
            out, _ = await proc.communicate()
            if out.strip(): has_subtitles = True
        except: pass

        if has_subtitles:
            path = await convert_ass_subtitles(path, metadata_file_path)
        
        # FIXED: Explicit format handling to prevent "Unable to find suitable output format"
        temp_metadata_path = f"Metadata/temp_{message.id}{os.path.splitext(path)[1]}"
        output_format = "matroska" if path.lower().endswith('.mkv') else "mp4"

        metadata_command = [
            ffmpeg_cmd, '-y', '-nostdin', '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-metadata', f'author={await codeflixbots.get_author(user_id)}',
            '-metadata:s:v', f'title={await codeflixbots.get_video(user_id)}',
            '-metadata:s:a', f'title={await codeflixbots.get_audio(user_id)}',
            '-metadata:s:s', f'title={await codeflixbots.get_subtitle(user_id)}',
            '-map', '0', '-c', 'copy', '-f', output_format, '-loglevel', 'error', temp_metadata_path
        ]

        process = await asyncio.create_subprocess_exec(*metadata_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        
        if process.returncode == 0:
            if os.path.exists(metadata_file_path): os.remove(metadata_file_path)
            os.rename(temp_metadata_path, metadata_file_path)
            path = metadata_file_path
        
        # Uploading...
        upload_msg = await download_msg.edit("**__Uploading...__**")
        c_caption = await codeflixbots.get_caption(message.chat.id)
        
        # Thumbnail Handling
        ph_path = None
        c_thumb = await codeflixbots.get_global_thumb(user_id) if await codeflixbots.is_global_thumb_enabled(user_id) else await codeflixbots.get_thumbnail(user_id)
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
            if ph_path:
                with Image.open(ph_path) as img:
                    img.convert("RGB").save(ph_path, "JPEG")

        caption = c_caption.format(filename=renamed_file_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_file_name}**"
        user_info = {'mention': message.from_user.mention, 'id': message.from_user.id, 'username': message.from_user.username or "No Username"}
        
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info))
        
        send_func = getattr(client, f"send_{media_type}")
        await send_func(message.chat.id, **{media_type: path}, file_name=renamed_file_name, thumb=ph_path, caption=caption, progress=progress_for_pyrogram, progress_args=("Upload Started...", upload_msg, time.time()))
        await upload_msg.delete()

    finally:
        for p in [download_path, metadata_file_path, ph_path, f"downloads/{message.id}_{renamed_file_name}.mkv"]:
            if p and os.path.exists(p): os.remove(p)
        if 'temp_metadata_path' in locals() and os.path.exists(temp_metadata_path): os.remove(temp_metadata_path)
        del renaming_operations[file_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        if time.time() - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = time.time()
            await send_verification(client, message)
        return
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    await user_queues[user_id]["queue"].put(message)

