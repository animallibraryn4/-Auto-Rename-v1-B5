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

# ===== RESTORED FROM OLD FILE: ASS Subtitle Conversion =====
async def convert_ass_subtitles(input_path, output_path):
    """
    Convert ASS subtitles to mov_text format for MP4 compatibility
    (Restored from old file)
    """
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None:
        raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd,
        '-i', input_path,
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-c:s', 'mov_text',  # Convert subtitles to mov_text format
        '-map', '0',
        '-loglevel', 'error',
        '-y',  # Overwrite output file
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_message = stderr.decode()
        raise Exception(f"Subtitle conversion failed: {error_message}")

async def convert_to_mkv(input_path, output_path):
    """
    Convert any video file to MKV format without re-encoding, preserving all streams
    (Restored from old file)
    """
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None:
        raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd,
        '-i', input_path,
        '-map', '0',          # Map all streams from input
        '-c', 'copy',         # Copy all streams without re-encoding
        '-loglevel', 'error',
        '-y',  # Overwrite output file
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_message = stderr.decode()
        raise Exception(f"MKV conversion failed: {error_message}")

def extract_quality(filename):
    for pattern, quality in [(pattern5, lambda m: m.group(1) or m.group(2)), 
                            (pattern6, "4k"), 
                            (pattern7, "2k"), 
                            (pattern8, "HdRip"), 
                            (pattern9, "4kX264"), 
                            (pattern10, "4kx265")]:
        match = re.search(pattern, filename)
        if match: 
            return quality(match) if callable(quality) else quality
    return "Unknown"

def extract_episode_number(filename):
    for pattern in [pattern1, pattern2, pattern3, pattern3_2, pattern4, patternX]:
        match = re.search(pattern, filename)
        if match: 
            if pattern in [pattern1, pattern2, pattern4]:
                return match.group(2) 
            else:
                return match.group(1)
    return None

def extract_season_number(filename):
    for pattern in [pattern1, pattern4]:
        match = re.search(pattern, filename)
        if match: 
            return match.group(1)
    return None

def extract_volume_chapter(filename):
    match = re.search(pattern11, filename)
    if match:
        return match.group(1), match.group(2)
    return None, None

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    if not Config.DUMP_CHANNEL: 
        return
    try:
        dump_caption = (
            f"➜ **File Renamed**\n\n"
            f"» **User:** {user_info['mention']}\n"
            f"» **User ID:** `{user_info['id']}`\n"
            f"» **Username:** @{user_info['username']}\n\n"
            f"➲ **Original Name:** `{file_name}`\n"
            f"➲ **Renamed To:** `{renamed_file_name}`"
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
        logger.error(f"[DUMP ERROR] {e}")

async def process_rename(client: Client, message: Message):
    ph_path = None
    
    user_id = message.from_user.id
    if not await is_user_verified(user_id): 
        return

    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)
    
    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    # Determine file type and get basic info
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_size = message.document.file_size
        media_type = media_preference or "document"
        is_pdf = message.document.mime_type == "application/pdf"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_name}.mp4" if message.video.file_name else "video.mp4"
        file_size = message.video.file_size
        media_type = media_preference or "video"
        is_pdf = False
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_name}.mp3" if message.audio.file_name else "audio.mp3"
        file_size = message.audio.file_size
        media_type = media_preference or "audio"
        is_pdf = False
    else:
        return await message.reply_text("Unsupported File Type")

    if await check_anti_nsfw(file_name, message):
        return await message.reply_text("NSFW content detected. File upload rejected.")

    # Check for duplicate operations
    if file_id in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
        if elapsed_time < 10:
            return

    renaming_operations[file_id] = datetime.now()

    # ===== RESTORED FROM OLD FILE: Extract and process filename components =====
    # Extract episode number
    episode_number = extract_episode_number(file_name)
    if episode_number:
        format_template = format_template.replace("[EP.NUM]", str(episode_number)).replace("{episode}", str(episode_number))
    else:
        format_template = format_template.replace("[EP.NUM]", "").replace("{episode}", "")

    # Extract season number
    season_number = extract_season_number(file_name)
    if season_number:
        format_template = format_template.replace("[SE.NUM]", str(season_number)).replace("{season}", str(season_number))
    else:
        format_template = format_template.replace("[SE.NUM]", "").replace("{season}", "")

    # Extract volume and chapter
    volume_number, chapter_number = extract_volume_chapter(file_name)
    if volume_number and chapter_number:
        format_template = format_template.replace("[Vol{volume}]", f"Vol{volume_number}").replace("[Ch{chapter}]", f"Ch{chapter_number}")
    else:
        format_template = format_template.replace("[Vol{volume}]", "").replace("[Ch{chapter}]", "")

    # Extract quality (not for PDFs)
    if not is_pdf:
        extracted_quality = extract_quality(file_name)
        if extracted_quality != "Unknown":
            format_template = format_template.replace("[QUALITY]", extracted_quality).replace("{quality}", extracted_quality)
        else:
            format_template = format_template.replace("[QUALITY]", "").replace("{quality}", "")

    # Clean up the format template
    format_template = re.sub(r'\s+', ' ', format_template).strip()
    format_template = format_template.replace("_", " ")
    format_template = re.sub(r'\[\s*\]', '', format_template)

    # Create renamed file name
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    
    # Create paths
    download_path = f"downloads/{message.id}_{renamed_file_name}"
    metadata_path = f"Metadata/{message.id}_{renamed_file_name}"
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("Metadata", exist_ok=True)

    download_msg = await message.reply_text("**__Downloading...__**")
    
    try:
        path = await client.download_media(
            message,
            file_name=download_path,
            progress=progress_for_pyrogram,
            progress_args=("Download Started...", download_msg, time.time()),
        )
    except Exception as e:
        del renaming_operations[file_id]
        return await download_msg.edit(f"**Download Error:** {e}")

    await download_msg.edit("**__Processing File...__**")

    try:
        # ===== RESTORED FROM OLD FILE: MKV Conversion Logic =====
        need_mkv_conversion = False
        if media_type == "document":
            need_mkv_conversion = True
        elif media_type == "video" and path.lower().endswith('.mp4'):
            need_mkv_conversion = True

        # Convert to MKV if needed
        if need_mkv_conversion and not path.lower().endswith('.mkv'):
            temp_mkv_path = f"{path}.temp.mkv"
            try:
                await convert_to_mkv(path, temp_mkv_path)
                os.remove(path)
                os.rename(temp_mkv_path, path)
                renamed_file_name = f"{format_template}.mkv"
                metadata_path = f"Metadata/{message.id}_{renamed_file_name}"
            except Exception as e:
                await download_msg.edit(f"**MKV Conversion Error:** {e}")
                return

        # ===== RESTORED FROM OLD FILE: ASS Subtitle Detection and Conversion =====
        is_mp4_with_ass = False
        if path.lower().endswith('.mp4'):
            try:
                ffprobe_cmd = shutil.which('ffprobe')
                if ffprobe_cmd:
                    command = [
                        ffprobe_cmd,
                        '-v', 'error',
                        '-select_streams', 's',
                        '-show_entries', 'stream=codec_name',
                        '-of', 'csv=p=0',
                        path
                    ]
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        subtitle_codec = stdout.decode().strip().lower()
                        if 'ass' in subtitle_codec:
                            is_mp4_with_ass = True
            except Exception as e:
                logger.warning(f"Error checking subtitle codec: {e}")

        # ===== RESTORED FROM OLD FILE: Get Audio and Subtitle Metadata =====
        # Get all metadata from database (RESTORED CRITICAL PART)
        file_title = await codeflixbots.get_title(user_id)
        artist = await codeflixbots.get_artist(user_id)
        author = await codeflixbots.get_author(user_id)
        video_title = await codeflixbots.get_video(user_id)
        audio_title = await codeflixbots.get_audio(user_id)  # RESTORED
        subtitle_title = await codeflixbots.get_subtitle(user_id)  # RESTORED

        # Apply metadata based on subtitle type
        if is_mp4_with_ass:
            # Convert ASS subtitles first, then apply metadata
            temp_output = f"{metadata_path}.temp.mp4"
            final_output = f"{metadata_path}.final.mp4"
            
            await convert_ass_subtitles(path, temp_output)
            os.replace(temp_output, metadata_path)
            path = metadata_path
            
            # Now add metadata with subtitle and audio stream titles
            metadata_command = [
                'ffmpeg',
                '-i', path,
                '-metadata', f'title={file_title}',
                '-metadata', f'artist={artist}',
                '-metadata', f'author={author}',
                '-metadata:s:v', f'title={video_title}',
                '-metadata:s:a', f'title={audio_title}',  # RESTORED: Audio stream title
                '-metadata:s:s', f'title={subtitle_title}',  # RESTORED: Subtitle stream title
                '-map', '0',
                '-c', 'copy',
                '-loglevel', 'error',
                '-y',  # Overwrite
                final_output
            ]
        else:
            # Original metadata command with RESTORED audio and subtitle metadata
            metadata_command = [
                'ffmpeg',
                '-i', path,
                '-metadata', f'title={file_title}',
                '-metadata', f'artist={artist}',
                '-metadata', f'author={author}',
                '-metadata:s:v', f'title={video_title}',
                '-metadata:s:a', f'title={audio_title}',  # RESTORED: Audio stream title
                '-metadata:s:s', f'title={subtitle_title}',  # RESTORED: Subtitle stream title
                '-map', '0',
                '-c', 'copy',
                '-loglevel', 'error',
                '-y',  # Overwrite
                metadata_path
            ]

        process = await asyncio.create_subprocess_exec(
            *metadata_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode()
            await download_msg.edit(f"**Metadata Error:**\n{error_message}")
            return

        if is_mp4_with_ass:
            os.replace(final_output, metadata_path)
        path = metadata_path

        upload_msg = await download_msg.edit("**__Uploading...__**")

        # ===== RESTORED FROM OLD FILE: Quality-Based Thumbnail Selection =====
        c_caption = await codeflixbots.get_caption(message.chat.id)
        
        # Get quality from filename for thumbnail selection
        extracted_quality = extract_quality(file_name)
        standard_quality = standardize_quality_name(extracted_quality) if extracted_quality != "Unknown" else None
        
        # Try to get quality-specific thumbnail first
        c_thumb = None
        is_global_enabled = await codeflixbots.is_global_thumb_enabled(user_id)

        if is_global_enabled:
            c_thumb = await codeflixbots.get_global_thumb(user_id)
        else:
            if standard_quality:
                c_thumb = await codeflixbots.get_quality_thumbnail(user_id, standard_quality)
            
            # Fall back to default thumbnail if no quality-specific one exists
            if not c_thumb:
                c_thumb = await codeflixbots.get_thumbnail(user_id)
        
        # If still no thumbnail, check for video thumbnails
        if not c_thumb and media_type == "video" and message.video.thumbs:
            c_thumb = message.video.thumbs[0].file_id

        caption = (
            c_caption.format(
                filename=renamed_file_name,
                filesize=humanbytes(file_size),
                duration=convert(0),
            )
            if c_caption
            else f"**{renamed_file_name}**"
        )

        # Process thumbnail
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
            if ph_path and os.path.exists(ph_path):
                try:
                    img = Image.open(ph_path).convert("RGB")
                    
                    # Only crop to square if media preference is "document"
                    if media_type == "document":
                        # Square crop for documents (center crop)
                        width, height = img.size
                        min_dim = min(width, height)
                        left, top = (width - min_dim) // 2, (height - min_dim) // 2
                        right, bottom = (width + min_dim) // 2, (height + min_dim) // 2
                        img = img.crop((left, top, right, bottom)).resize((320, 320), Image.LANCZOS)
                    else:
                        # For videos/audio, just resize while maintaining aspect ratio
                        img.thumbnail((320, 320), Image.LANCZOS)
                    
                    img.save(ph_path, "JPEG", quality=95)
                except Exception as e:
                    logger.error(f"Thumbnail processing error: {e}")
                    ph_path = None

        # Background Forwarding to dump channel
        user_info = {
            'mention': message.from_user.mention, 
            'id': message.from_user.id, 
            'username': message.from_user.username or "No Username"
        }
        asyncio.create_task(forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info))

        # Final Upload
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
        except Exception as e:
            os.remove(path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            return await upload_msg.edit(f"Error: {e}")

        await upload_msg.delete()

    except Exception as e:
        logger.error(f"Process Error: {e}")
        await download_msg.edit(f"Error: {e}")
    finally:
        # Clean up files
        for file_path in [download_path, metadata_path, path, ph_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Error removing file {file_path}: {e}")
        
        # Clean up temporary files from subtitle conversion
        temp_files = [f"{download_path}.temp.mkv", 
                     f"{metadata_path}.temp.mp4", 
                     f"{metadata_path}.final.mp4"]
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        # Remove from operations tracking
        if file_id in renaming_operations:
            del renaming_operations[file_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    
    # Check verification
    if not await is_user_verified(user_id):
        curr = time.time()
        if curr - recent_verification_checks.get(user_id, 0) > 2:
            recent_verification_checks[user_id] = curr
            await send_verification(client, message)
        return
    
    # Queue management
    if user_id not in user_queues:
        user_queues[user_id] = {
            "queue": asyncio.Queue(), 
            "task": asyncio.create_task(user_worker(user_id, client))
        }
    
    await user_queues[user_id]["queue"].put(message)
