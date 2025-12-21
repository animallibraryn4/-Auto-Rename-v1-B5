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
# Format: {user_id: timestamp}
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
            # Wait for message from user's queue with timeout
            message = await asyncio.wait_for(queue.get(), timeout=300)
            
            # Acquire global semaphore to limit concurrent tasks
            async with global_semaphore:
                await process_rename(client, message)
                
            queue.task_done()
            
        except asyncio.TimeoutError:
            # Clean up inactive user queue
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
    
    # Determine output container based on input path
    if output_path.lower().endswith('.mp4'):
        # For MP4: only convert text-based subtitles, skip image-based ones
        command = [
            ffmpeg_cmd,
            '-i', input_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            # Convert only text subtitles to mov_text, copy or drop others
            '-c:s', 'mov_text',
            # Map all streams but skip unsupported subtitle codecs
            '-map', '0',
            '-map', '-0:s:codec=hdmv_pgs_subtitle',  # Skip PGS
            '-map', '-0:s:codec=dvd_subtitle',       # Skip DVD subtitles
            '-loglevel', 'error',
            output_path
        ]
    else:
        # For MKV: copy all streams as-is (MKV supports all codecs)
        command = [
            ffmpeg_cmd,
            '-i', input_path,
            '-c', 'copy',  # Copy everything
            '-loglevel', 'error',
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
        # If MP4 conversion fails, fall back to MKV
        if output_path.lower().endswith('.mp4'):
            print(f"[WARNING] MP4 subtitle conversion failed: {error_message}")
            print(f"[INFO] Falling back to MKV container")
            # Change to MKV and try again with copy-all
            mkv_path = output_path.rsplit('.', 1)[0] + '.mkv'
            fallback_command = [
                ffmpeg_cmd,
                '-i', input_path,
                '-c', 'copy',
                '-loglevel', 'error',
                mkv_path
            ]
            fallback_process = await asyncio.create_subprocess_exec(
                *fallback_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await fallback_process.communicate()
            if fallback_process.returncode == 0:
                return mkv_path
            else:
                raise Exception(f"Fallback MKV conversion also failed: {stderr.decode()}")
        else:
            raise Exception(f"Subtitle conversion failed: {error_message}")
    
    return output_path

async def convert_to_mkv(input_path, output_path):
    """Convert any video file to MKV format"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None:
        raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd,
        '-i', input_path,
        '-map', '0',
        '-c', 'copy',
        '-loglevel', 'error',
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
    """Extract quality from filename using patterns"""
    for pattern, quality in [
        (pattern5, lambda m: m.group(1) or m.group(2)),
        (pattern6, "4k"),
        (pattern7, "2k"),
        (pattern8, "HdRip"),
        (pattern9, "4kX264"),
        (pattern10, "4kx265")
    ]:
        match = re.search(pattern, filename)
        if match:
            return quality(match) if callable(quality) else quality
    return "Unknown"

def extract_episode_number(filename):
    """Extract episode number from filename"""
    for pattern in [pattern1, pattern2, pattern3, pattern3_2, pattern4, patternX]:
        match = re.search(pattern, filename)
        if match:
            return match.group(2) if pattern in [pattern1, pattern2, pattern4] else match.group(1)
    return None

def extract_season_number(filename):
    """Extract season number from filename"""
    for pattern in [pattern1, pattern4]:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return None

def extract_volume_chapter(filename):
    """Extract volume and chapter numbers"""
    match = re.search(pattern11, filename)
    if match:
        return match.group(1), match.group(2)
    return None, None

async def forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info):
    """Silently forward renamed file to dump channel (background task)"""
    if not Config.DUMP_CHANNEL:
        return
    
    try:
        # Get chat info first to ensure bot recognizes the channel
        try:
            dump_chat = await client.get_chat(Config.DUMP_CHANNEL)
            print(f"[DUMP] Preparing to forward to: {dump_chat.title}")
        except Exception as e:
            print(f"[DUMP ERROR] Cannot access channel: {e}")
            return
        
        dump_caption = (
            f"➜ **File Renamed**\n\n"
            f"» **User:** {user_info['mention']}\n"
            f"» **User ID:** `{user_info['id']}`\n"
            f"» **Username:** @{user_info['username']}\n\n"
            f"➲ **Original Name:** `{file_name}`\n"
            f"➲ **Renamed To:** `{renamed_file_name}`\n\n"
            f"🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if media_type == "document":
            await client.send_document(
                Config.DUMP_CHANNEL,
                document=path,
                file_name=renamed_file_name,  # ✅ FIXED: Added file_name parameter
                caption=dump_caption,
                thumb=ph_path if ph_path else None,
            )
        elif media_type == "video":
            await client.send_video(
                Config.DUMP_CHANNEL,
                video=path,
                file_name=renamed_file_name,  # ✅ FIXED: Added file_name parameter
                caption=dump_caption,
                thumb=ph_path if ph_path else None,
            )
        elif media_type == "audio":
            await client.send_audio(
                Config.DUMP_CHANNEL,
                audio=path,
                file_name=renamed_file_name,  # ✅ FIXED: Added file_name parameter
                caption=dump_caption,
                thumb=ph_path if ph_path else None,
            )
        print(f"[DUMP SUCCESS] File forwarded: {renamed_file_name}")
        
    except Exception as e:
        print(f"[DUMP ERROR] Failed to forward {renamed_file_name}: {e}")

async def process_rename(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Add verification check here too as a safety measure
    if not await is_user_verified(user_id):
        # Don't send verification here - let the main handler send only one
        # The queue will be cleared when user sends files while not verified
        if user_id in user_queues:
            # Clear the user's queue since they're not verified
            while not user_queues[user_id]["queue"].empty():
                try:
                    user_queues[user_id]["queue"].get_nowait()
                    user_queues[user_id]["queue"].task_done()
                except asyncio.QueueEmpty:
                    break
        return  # Just return without processing
        
    ph_path = None
    
    format_template = await codeflixbots.get_format_template(user_id)
    media_preference = await codeflixbots.get_media_preference(user_id)

    if not format_template:
        return await message.reply_text("Please Set An Auto Rename Format First Using /autorename")

    # Determine file type and properties
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        media_type = media_preference or "document"
        is_pdf = message.document.mime_type == "application/pdf"
        file_size = message.document.file_size
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_name}.mp4" if message.video.file_name else "video.mp4"
        media_type = media_preference or "video"
        is_pdf = False
        file_size = message.video.file_size
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_name}.mp3" if message.audio.file_name else "audio.mp3"
        media_type = media_preference or "audio"
        is_pdf = False
        file_size = message.audio.file_size
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

    # Process filename components
    episode_number = extract_episode_number(file_name)
    season_number = extract_season_number(file_name)
    volume_number, chapter_number = extract_volume_chapter(file_name)
    extracted_quality = extract_quality(file_name) if not is_pdf else None

    # Apply format template
    replacements = {
        "[EP.NUM]": str(episode_number) if episode_number else "",
        "{episode}": str(episode_number) if episode_number else "",
        "[SE.NUM]": str(season_number) if season_number else "",
        "{season}": str(season_number) if season_number else "",
        "[Vol{volume}]": f"Vol{volume_number}" if volume_number else "",
        "[Ch{chapter}]": f"Ch{chapter_number}" if chapter_number else "",
        "[QUALITY]": extracted_quality if extracted_quality != "Unknown" else "",
        "{quality}": extracted_quality if extracted_quality != "Unknown" else ""
    }

    for old, new in replacements.items():
        format_template = format_template.replace(old, new)

    format_template = re.sub(r'\s+', ' ', format_template).strip()
    format_template = format_template.replace("_", " ")
    format_template = re.sub(r'\[\s*\]', '', format_template)

    # Prepare file paths with message ID for uniqueness
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    msg_id = message.id
    download_path = f"downloads/{msg_id}_{renamed_file_name}"
    renamed_file_path = download_path
    metadata_file_path = f"Metadata/{msg_id}_{renamed_file_name}"
    os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

    # Download file
    download_msg = await message.reply_text("**__Downloading...__**")
    try:
        path = await client.download_media(
            message,
            file_name=renamed_file_path,
            progress=progress_for_pyrogram,
            progress_args=("Download Started...", download_msg, time.time()),
        )
    except Exception as e:
        del renaming_operations[file_id]
        return await download_msg.edit(f"**Download Error:** {e}")

    await download_msg.edit("**__Processing File...__**")

    try:
        os.rename(path, renamed_file_path)
        path = renamed_file_path

        # Handle file conversion if needed
        ffmpeg_cmd = shutil.which('ffmpeg')
        if ffmpeg_cmd is None:
            await download_msg.edit("**Error:** `ffmpeg` not found. Please install `ffmpeg` to use this feature.")
            return

        need_mkv_conversion = (media_type == "document") or (media_type == "video" and path.lower().endswith('.mp4'))
        if need_mkv_conversion and not path.lower().endswith('.mkv'):
            temp_mkv_path = f"{path}.temp.mkv"
            try:
                await convert_to_mkv(path, temp_mkv_path)
                os.remove(path)
                os.rename(temp_mkv_path, path)
                renamed_file_name = f"{format_template}.mkv"
                metadata_file_path = f"Metadata/{msg_id}_{renamed_file_name}"
            except Exception as e:
                await download_msg.edit(f"**MKV Conversion Error:** {e}")
                return

        # Check for any subtitles
        has_subtitles = False
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
                if process.returncode == 0 and stdout.strip():
                    has_subtitles = True
        except Exception:
            pass

        # Handle metadata
        if has_subtitles:
            # Use the fixed conversion function that handles all subtitle types
            converted_path = await convert_ass_subtitles(path, metadata_file_path)
            path = converted_path
            # Update file extension if it changed to .mkv
            if converted_path.lower().endswith('.mkv'):
                renamed_file_name = f"{format_template}.mkv"

        metadata_command = [
            ffmpeg_cmd,
            '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-metadata', f'author={await codeflixbots.get_author(user_id)}',
            '-metadata:s:v', f'title={await codeflixbots.get_video(user_id)}',
            '-metadata:s:a', f'title={await codeflixbots.get_audio(user_id)}',
            '-metadata:s:s', f'title={await codeflixbots.get_subtitle(user_id)}',
            '-map', '0',
            '-c', 'copy',
            '-loglevel', 'error',
            metadata_file_path
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

        path = metadata_file_path
        
        # Prepare for upload
        upload_msg = await download_msg.edit("**__Uploading...__**")
        c_caption = await codeflixbots.get_caption(message.chat.id)

        # Handle thumbnails
        c_thumb = None
        is_global_enabled = await codeflixbots.is_global_thumb_enabled(user_id)

        if is_global_enabled:
            c_thumb = await codeflixbots.get_global_thumb(user_id)
            if not c_thumb:
                await upload_msg.edit("⚠️ Global Mode is ON but no global thumbnail set!")
        else:
            standard_quality = standardize_quality_name(extract_quality(file_name)) if not is_pdf else None
            if standard_quality and standard_quality != "Unknown":
                c_thumb = await codeflixbots.get_quality_thumbnail(user_id, standard_quality)
            if not c_thumb:
                c_thumb = await codeflixbots.get_thumbnail(user_id)

        if not c_thumb and media_type == "video" and message.video.thumbs:
            c_thumb = message.video.thumbs[0].file_id

        ph_path = None
        if c_thumb:
            try:
                ph_path = await client.download_media(c_thumb)
                if ph_path and os.path.exists(ph_path):
                    try:
                        img = Image.open(ph_path)
                        # Convert to RGB if needed
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        width, height = img.size
                        target_size = 320
                        
                        # Check if already perfect size
                        if width == target_size and height == target_size:
                            # No processing needed for perfect thumbnails
                            img.save(ph_path, "JPEG", quality=95)
                        else:
                            # Only crop if one dimension matches and other is larger
                            if (width == target_size and height > target_size) or \
                               (height == target_size and width > target_size):
                                
                                # Calculate crop coordinates
                                if width > target_size:
                                    # Crop from sides (maintain height)
                                    left = (width - target_size) // 2
                                    top = 0
                                    right = left + target_size
                                    bottom = height
                                elif height > target_size:
                                    # Crop from top/bottom (maintain width)
                                    left = 0
                                    top = (height - target_size) // 2
                                    right = width
                                    bottom = top + target_size
                                
                                # Perform crop
                                img = img.crop((left, top, right, bottom))
                                img.save(ph_path, "JPEG", quality=95)
                            else:
                                # For all other cases (including smaller thumbnails), keep original
                                img.save(ph_path, "JPEG", quality=95)
                                
                    except Exception as e:
                        print(f"[THUMB ERROR] {e}")
                        ph_path = None
            except Exception as e:
                print(f"[THUMB DOWNLOAD ERROR] {e}")
                ph_path = None

        caption = (
            c_caption.format(
                filename=renamed_file_name,
                filesize=humanbytes(file_size),
                duration=convert(0),
            )
            if c_caption
            else f"**{renamed_file_name}**"
        )

        # Prepare user info for background forwarding
        user_info = {
            'mention': message.from_user.mention,
            'id': message.from_user.id,
            'username': message.from_user.username or "No Username"
        }
        
        # 🚀 START BACKGROUND FORWARDING TO DUMP CHANNEL (SILENT)
        # This runs in parallel without blocking or showing messages to the user
        forward_task = asyncio.create_task(
            forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info)
        )
        
        # Upload file to user (main task continues normally)
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=path,
                    file_name=renamed_file_name,
                    thumb=ph_path if ph_path else None,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=path,
                    file_name=renamed_file_name,
                    caption=caption,
                    thumb=ph_path if ph_path else None,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=path,
                    file_name=renamed_file_name,
                    caption=caption,
                    thumb=ph_path if ph_path else None,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
            elif is_pdf:
                await client.send_document(
                    message.chat.id,
                    document=path,
                    file_name=renamed_file_name,
                    thumb=ph_path if ph_path else None,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
        except Exception as e:
            if os.path.exists(renamed_file_path):
                os.remove(renamed_file_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            return await upload_msg.edit(f"Error: {e}")

        await upload_msg.delete()
        
        # Wait for the background dump task to complete
        try:
            await asyncio.wait_for(forward_task, timeout=30)  # Increased timeout for dump channel
        except asyncio.TimeoutError:
            print(f"[DUMP TIMEOUT] Forwarding task timed out for {renamed_file_name}")
        
        # File cleanup - Dump channel upload complete hone ke baad
        if os.path.exists(path):
            os.remove(path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)

    finally:
        # Final cleanup in case of any errors
        if os.path.exists(renamed_file_path):
            os.remove(renamed_file_path)
        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        del renaming_operations[file_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    
    # Check if user is verified before processing
    if not await is_user_verified(user_id):
        # Check cooldown to prevent multiple verification messages
        current_time = time.time()
        last_check = recent_verification_checks.get(user_id, 0)
        
        if current_time - last_check > 2:  # 2 seconds cooldown
            recent_verification_checks[user_id] = current_time
            await send_verification(client, message)
        
        # Clean up old verification checks
        cleanup_users = []
        for uid, check_time in recent_verification_checks.items():
            if current_time - check_time > 30:
                cleanup_users.append(uid)
        for uid in cleanup_users:
            del recent_verification_checks[uid]
        
        return  # Stop processing file
    
    # User is verified, proceed with adding to queue
    # Create per-user queue if it doesn't exist
    if user_id not in user_queues:
        user_queues[user_id] = {
            "queue": asyncio.Queue(),
            "task": asyncio.create_task(user_worker(user_id, client))
        }
    
    # Add message to user's queue
    await user_queues[user_id]["queue"].put(message)
