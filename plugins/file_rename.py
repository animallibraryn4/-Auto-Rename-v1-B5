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
from helper.utils import progress_for_pyrogram, humanbytes, convert, add_prefix_suffix
from helper.database import codeflixbots
from config import Config, Txt
from helper.ban_filter import is_not_banned_filter # <-- NEW IMPORT
import logging

# Global dictionary to prevent duplicate renaming within a short time
renaming_operations = {}

# Asyncio Queue to manage file renaming tasks
rename_queue = asyncio.Queue()

# Patterns for extracting file information
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\\]>}]?|4K')

# Initialize logger
logger = logging.getLogger(__name__)

# Function to extract episode/season info
def extract_episode_info(filename):
    # Try pattern 1: SxxExx
    match1 = pattern1.search(filename)
    if match1:
        return match1.groups()

    # Try pattern 2: Sxx E/EP xx
    match2 = pattern2.search(filename)
    if match2:
        return match2.groups()

    # Try pattern 3: (EPxx) or -xx (Episode only)
    match3 = pattern3.search(filename)
    if match3:
        return (None, match3.group(1))

    match3_2 = pattern3_2.search(filename)
    if match3_2:
        return (None, match3_2.group(1))

    # Try pattern 4: Sxx...xx
    match4 = pattern4.search(filename)
    if match4:
        return match4.groups()

    # Fallback to general number extraction
    matchX = patternX.search(filename)
    if matchX:
        return (None, matchX.group(1))
        
    return (None, None)

# Function to extract quality info
def extract_quality(filename):
    match4k = pattern6.search(filename)
    if match4k:
        return "4K"
        
    match = pattern5.search(filename)
    if match:
        return match.group(1) or match.group(2)
        
    return None

def find_thumb_by_quality(all_thumbnails, quality):
    if quality in all_thumbnails:
        return all_thumbnails[quality]
    
    # Simple fallback: if quality is HDrip, check 720p or 1080p
    if quality == "HDrip":
        return all_thumbnails.get("720p") or all_thumbnails.get("1080p")
        
    # If the exact quality is not found, use the temporary/fallback setting (if applicable)
    # The temporary quality logic is better handled outside this pure extraction function

    return None

async def process_rename(client, message):
    """Handles the actual file downloading, renaming, metadata setting, and uploading."""
    file_id = f"{message.from_user.id}-{message.id}"
    
    # Placeholder for file paths
    path = ""
    renamed_file_path = ""
    metadata_file_path = ""
    ph_path = ""
    
    try:
        # Check if the operation is already in progress
        if file_id in renaming_operations:
            return await message.reply_text("This rename operation is already in progress. Please wait.")
        renaming_operations[file_id] = True

        # Initial message
        msg = await message.reply_text("Tʀʏɪɴɢ ᴛᴏ Dᴏᴡɴʟᴏᴀᴅɪɴɢ... ⏳", quote=True)

        # 1. Download File
        start_time = time.time()
        path = await client.download_media(
            message=message,
            progress=progress_for_pyrogram,
            progress_args=("Dᴏᴡɴʟᴏᴀᴅɪɴɢ ɪɴ Pʀᴏɢʀᴇss... ⏳", msg, start_time)
        )
        if path is None:
            raise Exception("Failed to download file.")
            
        await msg.edit_text("Dᴏᴡɴʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ, Sᴛᴀʀᴛɪɴɢ ʀᴇɴᴀᴍɪɴɢ & ᴘʀᴏᴄᴇꜱꜱɪɴɢ... ✨")

        # 2. Extract File Info and User Preferences
        
        # Get original file details
        media = message.document or message.video or message.animation or message.photo
        
        if message.photo:
            original_filename = f"Photo_{message.photo.date.isoformat().split('T')[0]}.jpg"
            file_extension = ".jpg"
        else:
            original_filename = getattr(media, 'file_name', f"file_{message.id}{os.path.splitext(path)[1]}")
            file_extension = os.path.splitext(original_filename)[1]

        file_size = media.file_size
        duration = getattr(media, 'duration', None)
        mime_type = media.mime_type
        
        # User preferences
        user_id = message.from_user.id
        caption_template = await codeflixbots.get_caption(user_id)
        format_template = await codeflixbots.get_format_template(user_id)
        metadata_enabled = await codeflixbots.get_metadata(user_id)
        all_thumbnails = await codeflixbots.get_all_quality_thumbnails(user_id)
        is_global_thumb_enabled = await codeflixbots.is_global_thumb_enabled(user_id)
        global_thumb = await codeflixbots.get_global_thumb(user_id)
        preferred_media_type = await codeflixbots.get_media_preference(user_id)
        
        # Metadata fields
        metadata_title = await codeflixbots.get_title(user_id)
        metadata_author = await codeflixbots.get_author(user_id)
        metadata_artist = await codeflixbots.get_artist(user_id)
        metadata_audio = await codeflixbots.get_audio(user_id)
        metadata_subtitle = await codeflixbots.get_subtitle(user_id)
        metadata_video_title = await codeflixbots.get_video_title(user_id)


        # 3. Rename Logic
        
        # Clean the original filename (remove extension for processing)
        base_filename = os.path.splitext(original_filename)[0]
        
        # Extract season, episode, quality
        season, episode = extract_episode_info(base_filename)
        quality = extract_quality(base_filename)
        
        # Prepare placeholders for template
        placeholders = {
            r'\[EP.NUM\]': episode or '00',
            r'\[SE.NUM\]': season or '0',
            r'\[QUALITY\]': quality or '',
            r'\{filename\}': base_filename,
            r'\{filesize\}': humanbytes(file_size),
            r'\{duration\}': convert(duration) if duration else '00:00:00'
        }
        
        # Replace placeholders in the format template
        new_filename = format_template
        for pattern, replacement in placeholders.items():
            # Use re.sub for robust replacement, especially for complex placeholders like [SE.NUM]
            new_filename = re.sub(pattern, replacement, new_filename, flags=re.IGNORECASE)
            
        # Tidy up the new filename (remove excessive spaces, leading/trailing punctuation)
        new_filename = re.sub(r'[ ]{2,}', ' ', new_filename).strip()
        new_filename = new_filename.strip('.-_ ')

        # Final renamed path
        renamed_file_path = os.path.join(os.path.dirname(path), new_filename + file_extension)

        # Handle simple case where path and renamed_path are the same (no need to move/rename)
        if path != renamed_file_path:
            shutil.move(path, renamed_file_path)

        # Update path to the renamed path
        path = renamed_file_path

        # 4. Thumbnail Logic
        thumb_file_id = None
        
        # Determine thumbnail to use
        if is_global_thumb_enabled and global_thumb:
            thumb_file_id = global_thumb
            quality = 'global' # For clarity
        elif quality and quality in all_thumbnails:
            thumb_file_id = all_thumbnails[quality]
        elif global_thumb:
            # Fallback to global if quality-specific is not set
            thumb_file_id = global_thumb
            quality = 'global'
            
        # Download thumbnail if an ID was found
        if thumb_file_id:
            try:
                ph_path = await client.download_media(thumb_file_id)
            except Exception as e:
                logger.error(f"Failed to download thumbnail {thumb_file_id}: {e}")
                ph_path = None # Reset path if download fails

        # 5. Metadata Logic (If enabled and video file)
        if metadata_enabled and file_extension.lower() in ('.mkv', '.mp4') and not message.photo:
            
            # Use the renamed file for metadata
            metadata_file_path = os.path.splitext(renamed_file_path)[0] + "_meta" + file_extension

            # Prepare the command using the configured metadata fields
            metadata_args = []
            
            # Using the simplified metadata code/fields
            if metadata_title:
                metadata_args.extend(['-metadata', f'title={metadata_title}'])
            if metadata_author:
                metadata_args.extend(['-metadata', f'author={metadata_author}'])
            if metadata_artist:
                metadata_args.extend(['-metadata', f'artist={metadata_artist}'])
            if metadata_audio:
                metadata_args.extend(['-metadata:s:a', f'title={metadata_audio}']) # Apply to audio streams
            if metadata_subtitle:
                metadata_args.extend(['-metadata:s:s', f'title={metadata_subtitle}']) # Apply to subtitle streams
            if metadata_video_title:
                metadata_args.extend(['-metadata:s:v', f'title={metadata_video_title}']) # Apply to video streams

            
            # Construct the FFmpeg command
            cmd = [
                'ffmpeg',
                '-i', renamed_file_path,  # Input file
                *metadata_args,           # Metadata flags
                '-c', 'copy',             # Copy all streams
                metadata_file_path        # Output file
            ]

            try:
                await msg.edit_text("Aᴅᴅɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ... 🏷️")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    # Metadata successfully added, replace the original file with the new one
                    os.remove(renamed_file_path)
                    shutil.move(metadata_file_path, renamed_file_path)
                    path = renamed_file_path # Update path to the final file
                else:
                    logger.error(f"FFmpeg failed (Metadata): {stderr.decode()}")
                    await msg.edit_text(f"⚠️ FFmpeg Error during metadata addition: {stderr.decode()}")
                    # Proceed with the non-metadata file
            except Exception as e:
                logger.error(f"Error during FFmpeg metadata process: {e}")
                await msg.edit_text(f"⚠️ An error occurred during metadata processing: {e}")
                # Proceed with the non-metadata file

        # 6. Upload File
        await msg.edit_text("Uᴘʟᴏᴀᴅɪɴɢ ɪɴ Pʀᴏɢʀᴇss... 📤")
        upload_start_time = time.time()
        
        # Prepare caption
        final_caption = None
        if caption_template:
            final_caption = caption_template.format(
                filename=new_filename,
                filesize=humanbytes(file_size),
                duration=convert(duration) if duration else '00:00:00'
            )
            # Replace remaining placeholders that were not handled (if any)
            final_caption = re.sub(r'\[EP.NUM\]|\[SE.NUM\]|\[QUALITY\]', '', final_caption, flags=re.IGNORECASE).strip()
            
        # Determine upload method and arguments
        upload_args = {
            'chat_id': message.chat.id,
            'caption': final_caption,
            'parse_mode': 'html',
            'progress': progress_for_pyrogram,
            'progress_args': ("Uᴘʟᴏᴀᴅɪɴɢ ɪɴ Pʀᴏɢʀᴇss... 📤", msg, upload_start_time),
        }
        
        if ph_path:
            upload_args['thumb'] = ph_path
        
        if preferred_media_type == 'video' and file_extension.lower() in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
            upload_func = client.send_video
            upload_args['video'] = path
            upload_args['duration'] = duration
            if message.video:
                upload_args['width'] = message.video.width
                upload_args['height'] = message.video.height
        else: # Default to document for all others or explicitly preferred
            upload_func = client.send_document
            upload_args['document'] = path
            # For documents, file name is taken from the path, which is already renamed
            
        # Perform the upload
        await upload_func(**upload_args)

        # 7. Final Clean-up and Logging
        await msg.delete()

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await process_rename(client, message) # Retry
        
    except Exception as e:
        logger.error(f"Error in file_rename.py process_rename: {e}")
        await msg.edit_text(f"Error during processing: {e}")
        
    finally:
        # Ensure files are cleaned up
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(renamed_file_path):
            os.remove(renamed_file_path)
        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
            
        # Clean up the operation flag
        if file_id in renaming_operations:
            del renaming_operations[file_id]

async def rename_worker():
    while True:
        # Get the next item from the queue
        client, message = await rename_queue.get()
        try:
            await process_rename(client, message)
        except Exception as e:
            logger.error(f"Error processing rename task from queue: {e}")
        finally:
            # Signal that the task is complete
            rename_queue.task_done()

# Start the worker task when the bot starts (This should be handled in bot.py start() or main execution)
# asyncio.create_task(rename_worker()) # Assuming this is started elsewhere

@Client.on_message(filters.private & is_not_banned_filter & (filters.document | filters.video | filters.animation | filters.photo)) # <-- MODIFIED
async def file_rename(client, message: Message):
    """
    Main handler for incoming media/document files.
    Puts the task into the queue to avoid blocking.
    """
    
    # Anti-NSFW check (assuming plugins.antinsfw.check_anti_nsfw is a synchronous function)
    if await check_anti_nsfw(message):
        return await message.reply_text("This file contains NSFW content and cannot be processed.")

    file_id = f"{message.from_user.id}-{message.id}"
    
    if file_id in renaming_operations:
        return await message.reply_text("Your previous rename request is still in progress. Please wait.")
        
    # Put the job into the queue
    await rename_queue.put((client, message))

