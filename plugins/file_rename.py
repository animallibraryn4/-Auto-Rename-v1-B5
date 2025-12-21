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

# All patterns from your original code preserved
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

def standardize_quality_name(quality):
    """Restored & Improved Quality Mapping from old code"""
    if not quality or quality == "Unknown": return "Unknown"
    q = quality.lower()
    if q in ['4k', '2160p']: return '2160p'
    if q in ['hdrip', 'hd']: return 'HDrip'
    if q == '2k': return '2K'
    if q == '4kx264': return '4kX264'
    if q == '4kx265': return '4kx265'
    if q.endswith('p') and q[:-1].isdigit(): return q
    return quality.capitalize()

async def convert_subtitles_advanced(input_path, output_path):
    """High-reliability subtitle conversion for MP4"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    command = [
        ffmpeg_cmd, '-i', input_path,
        '-map', '0', '-c:v', 'copy', '-c:a', 'copy',
        '-c:s', 'mov_text', '-map_metadata', '0',
        '-movflags', 'faststart', '-loglevel', 'error', '-y', output_path
    ]
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()

async def convert_to_mkv_advanced(input_path, output_path):
    """Reliable MKV Remuxing"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    command = [ffmpeg_cmd, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', '-y', output_path]
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()

# ... (extraction functions extract_quality, extract_episode_number, etc. same as above)

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
    file_name = getattr(media, 'file_name', 'video.mp4')
    file_size = media.file_size
    media_type = media_preference or ("video" if message.video else "audio" if message.audio else "document")
    is_pdf = getattr(media, 'mime_type', '') == "application/pdf"

    if await check_anti_nsfw(file_name, message): return 

    # Extraction Logic
    ep, se = extract_episode_number(file_name), extract_season_number(file_name)
    vol, ch = extract_volume_chapter(file_name)
    qual = extract_quality(file_name) if not is_pdf else "Unknown"

    # Restoration: Apply format template with your exact old code replacement logic
    replacements = {
        "[EP.NUM]": str(ep or ""), "{episode}": str(ep or ""),
        "[SE.NUM]": str(se or ""), "{season}": str(se or ""),
        "[Vol{volume}]": f"Vol{vol}" if vol else "",
        "[Ch{chapter}]": f"Ch{ch}" if ch else "",
        "[QUALITY]": qual if qual != "Unknown" else "",
        "{quality}": qual if qual != "Unknown" else ""
    }
    for old, new in replacements.items():
        format_template = format_template.replace(old, new)

    # Restoration: Your original cleanup regex
    format_template = re.sub(r'\s+', ' ', format_template).strip().replace("_", " ")
    format_template = re.sub(r'\[\s*\]', '', format_template)
    
    _, ext = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{ext}"
    
    msg_id = message.id
    download_path = f"downloads/{msg_id}_{renamed_file_name}"
    metadata_path = f"Metadata/{msg_id}_{renamed_file_name}"
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(message, file_name=download_path, progress=progress_for_pyrogram, progress_args=("Download Started...", download_msg, time.time()))
    except Exception as e:
        return await download_msg.edit(f"**Download Error:** {e}")

    await download_msg.edit("**__Processing File...__**")

    try:
        # MKV Conversion logic for Documents
        if (media_type == "document" or (media_type == "video" and path.lower().endswith('.mp4'))) and not path.lower().endswith('.mkv'):
            mkv_path = f"{path}.mkv"
            await convert_to_mkv_advanced(path, mkv_path)
            os.remove(path)
            path = mkv_path
            renamed_file_name = f"{format_template}.mkv"

        # Restoration: Full Metadata Tags (Author, Video Title, etc.)
        final_meta = f"Metadata/{msg_id}_final_{renamed_file_name}"
        meta_cmd = [
            shutil.which('ffmpeg'), '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-metadata', f'author={await codeflixbots.get_author(user_id)}',
            '-metadata:s:v', f'title={await codeflixbots.get_video(user_id)}',
            '-metadata:s:a', f'title={await codeflixbots.get_audio(user_id)}',
            '-metadata:s:s', f'title={await codeflixbots.get_subtitle(user_id)}',
            '-map', '0', '-c', 'copy', '-loglevel', 'error', '-y', final_meta
        ]
        proc = await asyncio.create_subprocess_exec(*meta_cmd)
        await proc.communicate()
        if os.path.exists(final_meta): path = final_meta

        # Restoration: Quality-Based Thumbnail Logic
        upload_msg = await download_msg.edit("**__Uploading...__**")
        is_global = await codeflixbots.is_global_thumb_enabled(user_id)
        c_thumb = await codeflixbots.get_global_thumb(user_id) if is_global else None
        
        if not c_thumb:
            std_qual = standardize_quality_name(qual)
            c_thumb = await codeflixbots.get_quality_thumbnail(user_id, std_qual) if std_qual != "Unknown" else None
        if not c_thumb:
            c_thumb = await codeflixbots.get_thumbnail(user_id)
        if not c_thumb and media_type == "video" and message.video and message.video.thumbs:
            c_thumb = message.video.thumbs[0].file_id

        # Thumbnail Processing (Smart Center-Crop)
        ph_path = None
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
            if ph_path:
                with Image.open(ph_path) as img:
                    img = img.convert("RGB")
                    w, h = img.size
                    if w != 320 or h != 320:
                        min_dim = min(w, h)
                        left, top = (w - min_dim) / 2, (h - min_dim) / 2
                        img = img.crop((left, top, left + min_dim, top + min_dim)).resize((320, 320), Image.LANCZOS)
                        img.save(ph_path, "JPEG", quality=95)

        c_caption = await codeflixbots.get_caption(message.chat.id)
        caption = c_caption.format(filename=renamed_file_name, filesize=humanbytes(file_size), duration=convert(0)) if c_caption else f"**{renamed_file_name}**"

        # Background Dump (Restored user_info)
        user_info = {'mention': message.from_user.mention, 'id': message.from_user.id, 'username': message.from_user.username or "N/A"}
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info))

        # Main Upload
        send_args = {"chat_id": message.chat.id, media_type: path, "file_name": renamed_file_name, "caption": caption, "thumb": ph_path, "progress": progress_for_pyrogram, "progress_args": ("Upload Started...", upload_msg, time.time())}
        if media_type == "video": await client.send_video(**send_args)
        elif media_type == "audio": await client.send_audio(**send_args)
        else: await client.send_document(**send_args)

        await upload_msg.delete()
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Final Cleanup
        for p in [download_path, metadata_path, path, ph_path, final_meta]:
            if p and os.path.exists(p): 
                try: os.remove(p)
                except: pass
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

