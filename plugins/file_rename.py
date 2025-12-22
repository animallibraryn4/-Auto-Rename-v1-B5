import os
import re
import time
import shutil
import asyncio
import logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
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

# Global dictionary to prevent duplicate operations
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

# Timeout configurations
DOWNLOAD_TIMEOUT = 300  # 5 minutes for download
UPLOAD_TIMEOUT = 600    # 10 minutes for upload
FFMPEG_TIMEOUT = 300    # 5 minutes for ffmpeg operations

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
    """Restored and Improved: Standardize quality names for consistent storage"""
    if not quality or quality == "Unknown":
        return "Unknown"
        
    q = quality.lower().strip()
    if any(x in q for x in ['4k', '2160', 'uhd']): return '2160p'
    if any(x in q for x in ['2k', '1440', 'qhd']): return '1440p'
    if '1080' in q: return '1080p'
    if '720' in q: return '720p'
    if '480' in q: return '480p'
    if '360' in q: return '360p'
    if any(x in q for x in ['hdrip', 'hd', 'web-dl']): return 'HDrip'
    if '4kx264' in q: return '4kX264'
    if '4kx265' in q: return '4kx265'
    
    match = re.search(r'(\d{3,4}p)', q)
    if match: return match.group(1)
    
    return quality.capitalize()

async def convert_subtitles_advanced(input_path, output_path):
    """Robust conversion of ASS/SSA subtitles to mov_text for MP4 containers"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd, '-i', input_path,
        '-map', '0', '-c:v', 'copy', '-c:a', 'copy',
        '-c:s', 'mov_text', '-map_metadata', '0',
        '-movflags', 'faststart', '-loglevel', 'error', '-y', output_path
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=FFMPEG_TIMEOUT)
        if process.returncode != 0:
            logger.error(f"Subtitle Conversion Fail: {stderr.decode()}")
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise Exception("Subtitle conversion timed out")

async def convert_to_mkv_advanced(input_path, output_path):
    """Reliable remuxing of any video to MKV container"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: raise Exception("FFmpeg not found")
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', '-y', output_path]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        await asyncio.wait_for(process.communicate(), timeout=FFMPEG_TIMEOUT)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise Exception("MKV conversion timed out")

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
            f"» **User ID:** `{user_info['id']}`\n"
            f"» **Username:** @{user_info['username']}\n\n"
            f"➲ **Original Name:** `{file_name}`\n"
            f"➲ **Renamed To:** `{renamed_file_name}`"
        )
        send_func = {"document": client.send_document, "video": client.send_video, "audio": client.send_audio}.get(media_type, client.send_document)
        await asyncio.wait_for(
            send_func(
                Config.DUMP_CHANNEL,
                **{media_type: path},
                file_name=renamed_file_name,
                caption=dump_caption,
                thumb=ph_path if ph_path else None,
            ),
            timeout=UPLOAD_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[DUMP ERROR] Forwarding to dump channel timed out")
    except Exception as e:
        logger.error(f"[DUMP ERROR] {e}")

async def download_with_retry(client, message, download_path, download_msg, max_retries=3):
    """Download with retry logic for timeout handling"""
    for attempt in range(max_retries):
        try:
            path = await asyncio.wait_for(
                client.download_media(
                    message, 
                    file_name=download_path, 
                    progress=progress_for_pyrogram, 
                    progress_args=("Download Started...", download_msg, time.time())
                ),
                timeout=DOWNLOAD_TIMEOUT
            )
            return path
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await download_msg.edit(f"**Download timeout, retrying... (Attempt {attempt + 1}/{max_retries})**")
                await asyncio.sleep(5)
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                await download_msg.edit(f"**Download error: {str(e)[:100]}, retrying...**")
                await asyncio.sleep(5)
            else:
                raise
    return None

async def upload_with_retry(client, media_type, send_args, upload_msg, max_retries=3):
    """Upload with retry logic for timeout handling"""
    for attempt in range(max_retries):
        try:
            if media_type == "video":
                return await asyncio.wait_for(
                    client.send_video(**send_args),
                    timeout=UPLOAD_TIMEOUT
                )
            elif media_type == "audio":
                return await asyncio.wait_for(
                    client.send_audio(**send_args),
                    timeout=UPLOAD_TIMEOUT
                )
            else:
                return await asyncio.wait_for(
                    client.send_document(**send_args),
                    timeout=UPLOAD_TIMEOUT
                )
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await upload_msg.edit(f"**Upload timeout, retrying... (Attempt {attempt + 1}/{max_retries})**")
                await asyncio.sleep(5)
            else:
                raise
        except FloodWait as e:
            await asyncio.sleep(e.value)
            if attempt < max_retries - 1:
                continue
            else:
                raise
    return None

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id): return

    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)
    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    media = message.document or message.video or message.audio
    if not media: return await message.reply_text("Unsupported File Type")
    
    file_id = media.file_id
    file_name = getattr(media, 'file_name', 'video.mp4')
    file_size = media.file_size
    media_type = media_preference or ("video" if message.video else "audio" if message.audio else "document")
    is_pdf = getattr(media, 'mime_type', '') == "application/pdf"

    if await check_anti_nsfw(file_name, message): return 

    if file_id in renaming_operations:
        if (datetime.now() - renaming_operations[file_id]).seconds < 10: return
    renaming_operations[file_id] = datetime.now()

    # Extraction
    episode_number = extract_episode_number(file_name)
    season_number = extract_season_number(file_name)
    volume_number, chapter_number = extract_volume_chapter(file_name)
    extracted_quality = extract_quality(file_name) if not is_pdf else "Unknown"

    # Replacement logic
    replacements = {
        "[EP.NUM]": str(episode_number or ""), "{episode}": str(episode_number or ""),
        "[SE.NUM]": str(season_number or ""), "{season}": str(season_number or ""),
        "[Vol{volume}]": f"Vol{volume_number}" if volume_number else "",
        "[Ch{chapter}]": f"Ch{chapter_number}" if chapter_number else "",
        "[QUALITY]": extracted_quality if extracted_quality != "Unknown" else "",
        "{quality}": extracted_quality if extracted_quality != "Unknown" else ""
    }
    for old, new in replacements.items():
        format_template = format_template.replace(old, new)

    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    
    download_path = f"downloads/{message.id}_{renamed_file_name}"
    metadata_path = f"Metadata/{message.id}_{renamed_file_name}"
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await download_with_retry(client, message, download_path, download_msg)
        if not path:
            del renaming_operations[file_id]
            return await download_msg.edit("**Download failed after multiple retries**")
    except Exception as e:
        del renaming_operations[file_id]
        return await download_msg.edit(f"**Download Error:** {str(e)[:200]}")

    await download_msg.edit("**__Processing File...__**")

    try:
        # Advanced MKV Remuxing
        if (media_type in ["document", "video"]) and not path.lower().endswith('.mkv'):
            mkv_path = f"{path}.mkv"
            try:
                await convert_to_mkv_advanced(path, mkv_path)
                if os.path.exists(mkv_path):
                    os.remove(path)
                    path = mkv_path
                    renamed_file_name = f"{format_template}.mkv"
            except Exception as e:
                logger.warning(f"MKV conversion skipped: {e}")

        # Advanced Subtitle Fixing for MP4
        if path.lower().endswith('.mp4'):
            ffprobe_cmd = shutil.which('ffprobe')
            if ffprobe_cmd:
                cmd = [ffprobe_cmd, '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', path]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                try:
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=FFMPEG_TIMEOUT)
                    if any(x in stdout.decode().lower() for x in ['ass', 'ssa', 'subrip']):
                        fixed_path = f"{path}_fixed.mp4"
                        await convert_subtitles_advanced(path, fixed_path)
                        if os.path.exists(fixed_path): 
                            os.replace(fixed_path, path)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    logger.warning("Subtitle detection timed out")

        # Apply Metadata
        final_meta = f"{metadata_path}.mkv" if path.endswith('.mkv') else f"{metadata_path}.mp4"
        meta_cmd = [
            shutil.which('ffmpeg'), '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-map', '0', '-c', 'copy', '-loglevel', 'error', '-y', final_meta
        ]
        proc = await asyncio.create_subprocess_exec(*meta_cmd)
        try:
            await asyncio.wait_for(proc.communicate(), timeout=FFMPEG_TIMEOUT)
            if os.path.exists(final_meta): 
                path = final_meta
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("Metadata application timed out")

        # RESTORED: Improved Quality-Based Thumbnail Selection
        upload_msg = await download_msg.edit("**__Uploading...__**")
        c_thumb = None
        is_global_enabled = await codeflixbots.is_global_thumb_enabled(user_id)

        if is_global_enabled:
            c_thumb = await codeflixbots.get_global_thumb(user_id)
        else:
            std_quality = standardize_quality_name(extracted_quality) if not is_pdf else None
            if std_quality and std_quality != "Unknown":
                c_thumb = await codeflixbots.get_quality_thumbnail(user_id, std_quality)
            if not c_thumb:
                c_thumb = await codeflixbots.get_thumbnail(user_id)

        # Fallback to video thumb if no user thumb is set
        if not c_thumb and media_type == "video" and message.video and message.video.thumbs:
            c_thumb = message.video.thumbs[0].file_id

        # Precise Center-Crop Processing
        ph_path = None
        if c_thumb:
            try:
                ph_path = await asyncio.wait_for(
                    client.download_media(c_thumb),
                    timeout=DOWNLOAD_TIMEOUT
                )
                if ph_path:
                    with Image.open(ph_path) as img:
                        img = img.convert("RGB")
                        width, height = img.size
                        min_dim = min(width, height)
                        left, top = (width - min_dim) / 2, (height - min_dim) / 2
                        right, bottom = (width + min_dim) / 2, (height + min_dim) / 2
                        img = img.crop((left, top, right, bottom)).resize((320, 320), Image.LANCZOS)
                        img.save(ph_path, "JPEG", quality=95)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Thumbnail processing failed: {e}")
                ph_path = None

        c_caption = await codeflixbots.get_caption(message.chat.id)
        caption = c_caption.format(filename=renamed_file_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_file_name}**"

        # Background Forwarding
        user_info = {'mention': message.from_user.mention, 'id': message.from_user.id, 'username': message.from_user.username or "No Username"}
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info))

        # Final Upload with retry
        send_args = {
            "chat_id": message.chat.id, 
            media_type: path, 
            "file_name": renamed_file_name, 
            "caption": caption, 
            "thumb": ph_path, 
            "progress": progress_for_pyrogram, 
            "progress_args": ("Upload Started...", upload_msg, time.time())
        }
        
        await upload_with_retry(client, media_type, send_args, upload_msg)
        await upload_msg.delete()

    except asyncio.TimeoutError:
        logger.error(f"Process timeout for user {user_id}")
        await download_msg.edit("**Process timed out. Please try again.**")
    except Exception as e:
        logger.error(f"Process Error for user {user_id}: {e}")
        await download_msg.edit(f"**Error:** {str(e)[:200]}")
    finally:
        # Cleanup files
        for p in [download_path, metadata_path, path, ph_path]:
            if p and os.path.exists(p): 
                try: 
                    os.remove(p)
                except Exception as e:
                    logger.warning(f"Failed to remove {p}: {e}")
        
        # Cleanup temporary files
        for root, dirs, files in os.walk("downloads"):
            for file in files:
                if file.endswith(('.mkv', '.mp4', '.jpg', '.jpeg', '.png')):
                    try:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path) and os.path.getctime(file_path) < time.time() - 3600:
                            os.remove(file_path)
                    except:
                        pass
        
        # Remove from operations tracking
        if file_id in renaming_operations:
            del renaming_operations[file_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        curr = time.time()
        if curr - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = curr
            await send_verification(client, message)
        return
    
    if user_id not in user_queues:
        user_queues[user_id] = {"queue": asyncio.Queue(), "task": asyncio.create_task(user_worker(user_id, client))}
    await user_queues[user_id]["queue"].put(message)
