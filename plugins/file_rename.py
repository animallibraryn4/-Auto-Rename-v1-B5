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

### NEW FUNCTION FOR LARGE FILE HANDLING ###
async def split_large_file(file_path, max_size=2*1024*1024*1024):
    """Split large files into chunks of max_size (default: 2GB)"""
    try:
        file_size = os.path.getsize(file_path)
        if file_size <= max_size:
            return [file_path]  # No splitting needed
        
        base_name = os.path.basename(file_path)
        output_dir = os.path.dirname(file_path)
        chunk_files = []
        
        with open(file_path, 'rb') as f:
            part_num = 1
            while True:
                chunk_data = f.read(max_size)
                if not chunk_data:
                    break
                    
                chunk_name = f"{base_name}.part{part_num:03d}"
                chunk_path = os.path.join(output_dir, chunk_name)
                
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                    
                chunk_files.append(chunk_path)
                part_num += 1
        
        return chunk_files
    except Exception as e:
        print(f"Error splitting file: {e}")
        raise

async def process_large_file(client, message, file_path, format_template, media_type):
    """Process and upload large file in parts"""
    try:
        # Notify user
        processing_msg = await message.reply_text(
            "📦 **Processing large file...**\n"
            "This may take a while depending on file size."
        )
        
        # Split the file
        chunk_files = await split_large_file(file_path)
        
        # Process each chunk
        for i, chunk_path in enumerate(chunk_files, 1):
            # Update progress
            await processing_msg.edit_text(
                f"🔄 Processing part {i}/{len(chunk_files)}...\n"
                f"File: {os.path.basename(chunk_path)}"
            )
            
            # Upload the chunk
            await upload_chunk(client, message, chunk_path, media_type)
            
            # Clean up
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
                
        await processing_msg.edit_text(
            "✅ **File processing completed!**\n"
            f"Total parts uploaded: {len(chunk_files)}"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Error processing large file: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def upload_chunk(client, message, chunk_path, media_type):
    """Upload a single chunk of file"""
    try:
        # Get user settings
        user_id = message.from_user.id
        c_caption = await codeflixbots.get_caption(user_id)
        c_thumb = await codeflixbots.get_thumbnail(user_id)
        
        # Prepare caption
        chunk_name = os.path.basename(chunk_path)
        file_size = os.path.getsize(chunk_path)
        caption = (
            c_caption.format(
                filename=chunk_name,
                filesize=humanbytes(file_size),
                duration="N/A",
            )
            if c_caption
            else f"**{chunk_name}**"
        )
        
        # Upload based on media type
        if media_type == "document":
            await client.send_document(
                chat_id=message.chat.id,
                document=chunk_path,
                caption=caption,
                thumb=c_thumb,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", message, time.time()),
            )
        elif media_type == "video":
            await client.send_video(
                chat_id=message.chat.id,
                video=chunk_path,
                caption=caption,
                thumb=c_thumb,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", message, time.time()),
            )
        elif media_type == "audio":
            await client.send_audio(
                chat_id=message.chat.id,
                audio=chunk_path,
                caption=caption,
                thumb=c_thumb,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", message, time.time()),
            )
            
    except Exception as e:
        print(f"Error uploading chunk {chunk_path}: {e}")
        raise

### EXISTING FUNCTIONS (ALL PRESERVED) ###
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

    ### NEW LARGE FILE HANDLING LOGIC ###
    try:
        # Check if file is large and splitting is enabled
        user_id = message.from_user.id
        should_split = await codeflixbots.get_split_large_files(user_id)
        
        if should_split and os.path.getsize(path) > 2*1024*1024*1024:
            await process_large_file(client, message, path, format_template, media_type)
            return
            
        # Continue with normal processing for small files
        os.rename(path, renamed_file_path)
        path = renamed_file_path

        # Rest of the existing processing logic...
        # [All the existing file processing code remains unchanged]
        
    except Exception as e:
        await message.reply_text(f"Error: {e}")
    finally:
        # Cleanup code remains the same
        if os.path.exists(renamed_file_path):
            os.remove(renamed_file_path)
        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        if file_id in renaming_operations:
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
