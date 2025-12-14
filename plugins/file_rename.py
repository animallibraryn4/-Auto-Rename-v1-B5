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
            f"» **ID:** `{user_info['_id']}`\n"
            f"» **Original:** `{file_name}`\n"
            f"» **Renamed:** `{renamed_file_name}`"
        )
        
        # Check if the file is an image for the dump
        is_photo = (media_type == "photo" or (media_type == "document" and file_name.lower().endswith(('.jpg', '.jpeg', '.png'))))

        if is_photo or media_type == "photo":
            await client.send_photo(
                chat_id=Config.DUMP_CHANNEL,
                photo=path,
                caption=dump_caption
            )
        elif media_type == "video" or media_type == "document":
            if ph_path:
                await client.send_document(
                    chat_id=Config.DUMP_CHANNEL,
                    document=path,
                    caption=dump_caption,
                    thumb=ph_path
                )
            else:
                await client.send_document(
                    chat_id=Config.DUMP_CHANNEL,
                    document=path,
                    caption=dump_caption
                )
        elif media_type == "audio":
            await client.send_audio(
                chat_id=Config.DUMP_CHANNEL,
                audio=path,
                caption=dump_caption
            )

        print(f"[DUMP] Successfully forwarded {renamed_file_name} to dump channel.")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await forward_to_dump_channel(client, path, media_type, ph_path, file_name, renamed_file_name, user_info)
    except Exception as e:
        print(f"[DUMP ERROR] Failed to forward to dump channel: {e}")

async def process_rename(client, message: Message):
    user_id = message.from_user.id
    user_info = await codeflixbots.col.find_one({"_id": int(user_id)})
    if not user_info:
        await codeflixbots.add_user(client, message)
        user_info = await codeflixbots.col.find_one({"_id": int(user_id)})
        if not user_info:
             await message.reply_text("Failed to retrieve user data. Please try again.")
             return
             
    file = message.document or message.video or message.audio
    file_id = file.file_id

    if file_id in renaming_operations:
        await message.reply_text("A renaming process is already running for this file. Please wait.")
        return

    renaming_operations[file_id] = True
    
    # --- Check for the trial limit again (safety) ---
    if not user_info.get('is_premium', False) and user_info.get('trial_used', 0) >= 10:
        await message.reply_text(
            "⚠️ **Access Required**\n\n"
            "Your 10 free trial renames have been used.\n"
            "Please provide a valid token to continue using the bot.\n"
            "Send your token now:",
            quote=True
        )
        del renaming_operations[file_id]
        return
    # ------------------------------------------------
        
    editable_message = await message.reply_text("📥 Downloading file...")
    path = None
    ph_path = None
    renamed_file_path = None
    metadata_file_path = None
    
    try:
        # Download the file
        path = await client.download_media(
            message,
            progress=progress_for_pyrogram,
            progress_args=("`Downloading`\n", editable_message, time.time())
        )
        
        if not path:
            await editable_message.edit("❌ Download failed.")
            return

        # Anti-NSFW Check
        if Config.ANTINFSW and file.mime_type.startswith('video'):
            await editable_message.edit("⏳ Running Anti-NSFW Check...")
            if await check_anti_nsfw(path):
                await editable_message.edit("🚫 **NSFW Content Detected.**\n\nThis content is prohibited.")
                return
        
        # Determine original file name and extension
        file_name = os.path.basename(path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # Check for ASS subtitles and convert to MKV if needed (for metadata compatibility)
        if file_ext == '.ass':
            await editable_message.edit("🔄 Converting ASS subtitle to MOV_TEXT...")
            temp_mkv_path = os.path.splitext(path)[0] + "_temp.mkv"
            try:
                await convert_ass_subtitles(path, temp_mkv_path)
                os.remove(path)
                path = temp_mkv_path
                file_name = os.path.basename(path)
                file_ext = os.path.splitext(file_name)[1].lower()
            except Exception as e:
                await editable_message.edit(f"❌ Subtitle conversion failed: {e}")
                return

        # Prepare for renaming
        await editable_message.edit("📝 Preparing to rename...")

        format_template = await codeflixbots.get_format_template(user_id)
        if not format_template:
            format_template = "{filename}" # Default fallback

        # Extract info for renaming
        episode = extract_episode_number(file_name)
        season = extract_season_number(file_name)
        volume, chapter = extract_volume_chapter(file_name)
        quality = standardize_quality_name(extract_quality(file_name))
        
        # Get file metadata
        metadata = extractMetadata(createParser(path))
        duration = int(metadata.get('duration', 0) if metadata else 0)
        
        # Prepare variables for template formatting
        safe_file_name = os.path.splitext(os.path.basename(file_name))[0]
        filesize = humanbytes(file.file_size)
        
        # Dynamic template replacement map
        template_map = {
            "{filename}": safe_file_name,
            "{fileext}": file_ext,
            "{filesize}": filesize,
            "{duration}": convert(duration),
            "{duration_sec}": str(duration),
            "{quality}": quality
        }
        
        # Add dynamic parts
        if episode:
            template_map["{EP.NUM}"] = episode
            template_map["{ep.num}"] = episode
        if season:
            template_map["{SE.NUM}"] = season
            template_map["{se.num}"] = season
        if volume:
            template_map["{VOL.NUM}"] = volume
            template_map["{vol.num}"] = volume
        if chapter:
            template_map["{CH.NUM}"] = chapter
            template_map["{ch.num}"] = chapter

        # Apply replacements to the format template
        renamed_file_name = format_template
        for key, value in template_map.items():
            renamed_file_name = renamed_file_name.replace(key, str(value))

        # Sanitize and finalize file name
        renamed_file_name = re.sub(r'[\\/:*?"<>|]', '_', renamed_file_name) # Remove illegal characters
        renamed_file_name += file_ext
        renamed_file_path = os.path.join(os.path.dirname(path), renamed_file_name)
        os.rename(path, renamed_file_path)
        path = renamed_file_path
        
        # --- Metadata Handling ---
        use_metadata = await codeflixbots.get_metadata(user_id)
        media_type = await codeflixbots.get_media_preference(user_id)
        
        if use_metadata and (media_type in ["video", "document"] and file_ext.lower() == '.mkv'):
            await editable_message.edit("⚙️ Applying Custom Metadata...")
            
            # Get custom metadata values
            title = await codeflixbots.get_title(user_id)
            author = await codeflixbots.get_author(user_id)
            artist = await codeflixbots.get_artist(user_id)
            audio = await codeflixbots.get_audio(user_id)
            subtitle = await codeflixbots.get_subtitle(user_id)
            video = await codeflixbots.get_video(user_id)
            
            metadata_file_path = os.path.join(os.path.dirname(path), "metadata_" + os.path.basename(path))

            # FFmpeg command for metadata application
            ffmpeg_cmd = shutil.which('ffmpeg')
            if ffmpeg_cmd is None:
                raise Exception("FFmpeg not found")
                
            command = [
                ffmpeg_cmd,
                '-i', path,
                '-map', '0', # Map all streams
                '-c', 'copy', # Copy all codecs
                '-metadata', f'title={title}',
                '-metadata', f'author={author}',
                '-metadata', f'artist={artist}',
                '-metadata:s:a:0', f'title={audio}',
                '-metadata:s:s:0', f'title={subtitle}',
                '-metadata:s:v:0', f'title={video}',
                '-loglevel', 'error',
                metadata_file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"Metadata failed: {stderr.decode()}")
                await editable_message.edit(f"❌ Metadata application failed! Sending original renamed file.")
            else:
                os.remove(path)
                path = metadata_file_path
                await editable_message.edit("✅ Metadata applied successfully!")
        
        # --- Thumbnail Logic ---
        await editable_message.edit("🖼️ Checking for thumbnail...")
        
        if await codeflixbots.is_global_thumb_enabled(user_id):
            thumb_file_id = await codeflixbots.get_global_thumb(user_id)
            if thumb_file_id:
                ph_path = await client.download_media(thumb_file_id)
        else:
            thumb_file_id = await codeflixbots.get_quality_thumbnail(user_id, quality)
            if thumb_file_id:
                ph_path = await client.download_media(thumb_file_id)

        # Get default caption
        caption = await codeflixbots.get_caption(user_id)
        if not caption:
            caption = Txt.DEFAULT_CAPTION # Fallback to a default if user has none

        # Final caption formatting
        final_caption = caption.format(
            filename=os.path.splitext(renamed_file_name)[0],
            fileext=file_ext,
            filesize=humanbytes(os.path.getsize(path)),
            duration=convert(duration)
        )
        
        # --- Final Upload ---
        await editable_message.edit("📤 Uploading file...")

        if media_type == "document":
            sent_msg = await client.send_document(
                chat_id=message.chat.id,
                document=path,
                caption=final_caption,
                thumb=ph_path,
                reply_to_message_id=message.id,
                progress=progress_for_pyrogram,
                progress_args=("`Uploading`\n", editable_message, time.time())
            )
        elif media_type == "video" and (file.mime_type.startswith('video') or file_ext.lower() in ('.mkv', '.mp4', '.mov')):
            sent_msg = await client.send_video(
                chat_id=message.chat.id,
                video=path,
                caption=final_caption,
                duration=duration,
                thumb=ph_path,
                supports_streaming=True,
                reply_to_message_id=message.id,
                progress=progress_for_pyrogram,
                progress_args=("`Uploading`\n", editable_message, time.time())
            )
        elif media_type == "audio" and file.mime_type.startswith('audio'):
             sent_msg = await client.send_audio(
                chat_id=message.chat.id,
                audio=path,
                caption=final_caption,
                duration=duration,
                thumb=ph_path,
                reply_to_message_id=message.id,
                progress=progress_for_pyrogram,
                progress_args=("`Uploading`\n", editable_message, time.time())
            )
        else:
            await editable_message.edit("⚠️ **Unsupported Media Type!**\n\nYour file is not a video or document. Defaulting to Document upload.")
            sent_msg = await client.send_document(
                chat_id=message.chat.id,
                document=path,
                caption=final_caption,
                thumb=ph_path,
                reply_to_message_id=message.id,
                progress=progress_for_pyrogram,
                progress_args=("`Uploading`\n", editable_message, time.time())
            )
            
        await editable_message.delete()
        
        # 4. After successful rename, update trial count
        if not user_info.get('is_premium', False):
            new_count = await codeflixbots.increment_trial_count(user_id)
            
            # 5. Check if this was the 10th rename
            if new_count == 10:
                # Notify the user that the trial is finished
                await client.send_message(
                    user_id,
                    "🎉 **Congratulations!**\n\n"
                    "You have successfully used all **10 free trial renames**!\n"
                    "To continue using the bot, please send your valid premium token or type /myusage to check your status."
                )

        # Forward to dump channel (background task)
        user_mention_info = {
            '_id': user_id,
            'mention': message.from_user.mention
        }
        forward_task = asyncio.create_task(
            forward_to_dump_channel(
                client, path, media_type, ph_path, file_name, renamed_file_name, user_mention_info
            )
        )
        
        # Wait a short time for the background task to complete (optional)
        try:
            await asyncio.wait_for(forward_task, timeout=10)
        except asyncio.TimeoutError:
            print("[DUMP] Forwarding task timed out (but user already got their file)")
        
        # Clean up temporary files
        if os.path.exists(path):
            os.remove(path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        print(f"Error in process_rename for user {user_id}: {e}")
        try:
            await editable_message.edit(f"❌ An error occurred during processing: `{e}`")
        except:
            print(f"Could not edit message for error: {e}")
    finally:
        # Final cleanup
        if os.path.exists(renamed_file_path or ""):
            os.remove(renamed_file_path)
        if os.path.exists(metadata_file_path or ""):
            os.remove(metadata_file_path)
        if os.path.exists(path or ""):
            os.remove(path)
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
    user_id = message.from_user.id
    
    # 1. Check if user is verified (Existing check)
    if not await is_user_verified(user_id):
        # Send verification prompt instead of processing the file
        await send_verification(client, message)
        return

    # 2. Check if trial is available
    if not await codeflixbots.check_trial_available(user_id):
        # Trial finished, ask for token
        await message.reply_text(
            "⚠️ **Access Required**\n\n"
            "Your 10 free trial renames have been used.\n"
            "Please provide a valid token to continue using the bot.\n"
            "Send your token now:",
            quote=True
        )
        return  # Stop here, wait for token
    
    # 3. User has trial or is premium - proceed
    # Only add to queue if file is not already in a process
    file = message.document or message.video or message.audio
    if file.file_id in renaming_operations:
        await message.reply_text("A renaming process is already running for this file. Please wait.")
        return
        
    await rename_queue.put((client, message))

# Initialize worker tasks when the module loads
for i in range(Config.WORKERS or 5):
    asyncio.create_task(rename_worker())
        
