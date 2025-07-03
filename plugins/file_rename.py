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

# Global dictionary to prevent duplicate renaming within a short time
renaming_operations = {}

# Asyncio Queue to manage file renaming tasks
rename_queue = asyncio.Queue()

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
    """Convert ASS subtitles to mov_text format"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if ffmpeg_cmd is None:
        raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd,
        '-i', input_path,
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-c:s', 'mov_text',
        '-map', '0',
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
        raise Exception(f"Subtitle conversion failed: {error_message}")

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

async def process_rename(client: Client, message: Message):
    ph_path = None
    
    user_id = message.from_user.id
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
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_name}.mp4" if message.video.file_name else "video.mp4"
        media_type = media_preference or "video"
        is_pdf = False
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_name}.mp3" if message.audio.file_name else "audio.mp3"
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

    # Prepare file paths
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = f"{format_template}{file_extension}"
    renamed_file_path = f"downloads/{renamed_file_name}"
    metadata_file_path = f"Metadata/{renamed_file_name}"
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
                metadata_file_path = f"Metadata/{renamed_file_name}"
            except Exception as e:
                await download_msg.edit(f"**MKV Conversion Error:** {e}")
                return

        # Check for ASS subtitles
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
            except Exception:
                pass

        # Handle metadata
        if is_mp4_with_ass:
            temp_output = f"{metadata_file_path}.temp.mp4"
            final_output = f"{metadata_file_path}.final.mp4"
            await convert_ass_subtitles(path, temp_output)
            os.replace(temp_output, metadata_file_path)
            path = metadata_file_path

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
            metadata_file_path if not is_mp4_with_ass else final_output
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
            os.replace(final_output, metadata_file_path)
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
                        await upload_msg.edit(f"⚠️ Thumbnail Process Error: {e}")
                        ph_path = None
            except Exception as e:
                await upload_msg.edit(f"⚠️ Thumbnail Download Error: {e}")
                ph_path = None

        caption = (
            c_caption.format(
                filename=renamed_file_name,
                filesize=humanbytes(message.document.file_size),
                duration=convert(0),
            )
            if c_caption
            else f"**{renamed_file_name}**"
        )

        # Upload file
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=path,
                    thumb=ph_path if ph_path else None,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=path,
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
                    thumb=ph_path if ph_path else None,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload Started...", upload_msg, time.time()),
                )
        except Exception as e:
            os.remove(renamed_file_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            return await upload_msg.edit(f"Error: {e}")

        await download_msg.delete() 
        if os.path.exists(path):
            os.remove(path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)

    finally:
        if os.path.exists(renamed_file_path):
            os.remove(renamed_file_path)
        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        del renaming_operations[file_id]
        
async def rename_worker():
    while True:
        client, message = await rename_queue.get()
        try:
            await process_rename(client, message)
        except Exception as e:
            print(f"Error processing rename task: {e}")
        finally:
            rename_queue.task_done()

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    await rename_queue.put((client, message))

asyncio.create_task(rename_worker())
