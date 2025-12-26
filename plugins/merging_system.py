import os
import re
import time
import shutil
import asyncio
import logging
import json
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from helper.database import codeflixbots
from config import Config
from plugins import is_user_verified, send_verification
from helper.utils import progress_for_pyrogram, humanbytes, convert

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== Global State for Merging =====
# These will be loaded from database on demand
merging_mode_cache = {}  # user_id -> True/False (cache)
batch1_tracks_cache = {}  # user_id -> {season_episode: {audio_tracks: [], subtitle_tracks: []}}
batch1_files_cache = {}   # user_id -> list of batch1 file paths (for cleanup)
batch2_waiting_cache = {} # user_id -> True if waiting for batch2

# Patterns for extracting season/episode
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern11 = re.compile(r'Vol(\d+)\s*-\s*Ch(\d+)', re.IGNORECASE)

# ===== Database Helper Functions =====

async def get_merging_mode(user_id):
    """Get merging mode from cache or database"""
    if user_id in merging_mode_cache:
        return merging_mode_cache[user_id]
    
    status = await codeflixbots.get_merging_mode(user_id)
    merging_mode_cache[user_id] = status
    return status

async def set_merging_mode(user_id, status):
    """Set merging mode in both cache and database"""
    merging_mode_cache[user_id] = status
    await codeflixbots.set_merging_mode(user_id, status)

async def get_merging_state(user_id):
    """Get merging state from cache or database"""
    if user_id in batch1_tracks_cache and user_id in batch2_waiting_cache:
        return {
            'batch1_tracks': batch1_tracks_cache.get(user_id, {}),
            'batch2_waiting': batch2_waiting_cache.get(user_id, False)
        }
    
    state = await codeflixbots.get_merging_state(user_id)
    batch1_tracks_cache[user_id] = state.get('batch1_tracks', {})
    batch2_waiting_cache[user_id] = state.get('batch2_waiting', False)
    return state

async def set_merging_state(user_id, batch1_tracks=None, batch2_waiting=None):
    """Set merging state in both cache and database"""
    if batch1_tracks is not None:
        batch1_tracks_cache[user_id] = batch1_tracks
    
    if batch2_waiting is not None:
        batch2_waiting_cache[user_id] = batch2_waiting
    
    state = {
        'batch1_tracks': batch1_tracks_cache.get(user_id, {}),
        'batch2_waiting': batch2_waiting_cache.get(user_id, False)
    }
    await codeflixbots.set_merging_state(user_id, state)

async def clear_merging_state(user_id):
    """Clear merging state from cache and database"""
    merging_mode_cache.pop(user_id, None)
    batch1_tracks_cache.pop(user_id, None)
    batch1_files_cache.pop(user_id, None)
    batch2_waiting_cache.pop(user_id, None)
    await codeflixbots.clear_merging_state(user_id)

def extract_season_episode(filename):
    """Extract season and episode numbers from filename"""
    # Try different patterns
    for pattern in [pattern1, pattern2, pattern4]:
        match = re.search(pattern, filename)
        if match:
            if pattern in [pattern1, pattern2, pattern4]:
                return match.group(1), match.group(2)
    
    # Try episode-only patterns
    for pattern in [pattern3, pattern3_2, patternX]:
        match = re.search(pattern, filename)
        if match:
            return "1", match.group(1)  # Default season 1
    
    # Try volume/chapter pattern
    match = re.search(pattern11, filename)
    if match:
        return match.group(1), match.group(2)
    
    return None, None

async def extract_tracks(input_path, user_id, season, episode):
    """Extract audio and subtitle tracks from a file"""
    try:
        ffprobe_cmd = shutil.which('ffprobe')
        if not ffprobe_cmd:
            raise Exception("FFprobe not found")
        
        # Get stream information
        cmd = [
            ffprobe_cmd,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            input_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFprobe error: {stderr.decode()}")
            return [], []
        
        import json
        data = json.loads(stdout.decode())
        
        audio_tracks = []
        subtitle_tracks = []
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                # Extract audio track
                audio_idx = stream.get('index', 0)
                audio_lang = stream.get('tags', {}).get('language', 'und')
                audio_title = stream.get('tags', {}).get('title', '')
                
                # Save audio track to temporary file
                audio_path = f"temp/{user_id}/batch1/S{season}E{episode}_audio_{audio_idx}_{audio_lang}.mka"
                os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                
                extract_cmd = [
                    shutil.which('ffmpeg'),
                    '-i', input_path,
                    '-map', f'0:a:{audio_idx}',
                    '-c', 'copy',
                    '-loglevel', 'error',
                    '-y', audio_path
                ]
                
                proc = await asyncio.create_subprocess_exec(*extract_cmd)
                await proc.communicate()
                
                if os.path.exists(audio_path):
                    audio_tracks.append({
                        'path': audio_path,
                        'language': audio_lang,
                        'title': audio_title,
                        'index': audio_idx
                    })
            
            elif stream.get('codec_type') == 'subtitle':
                # Extract subtitle track
                sub_idx = stream.get('index', 0)
                sub_lang = stream.get('tags', {}).get('language', 'und')
                sub_title = stream.get('tags', {}).get('title', '')
                
                # Determine subtitle codec and extension
                codec_name = stream.get('codec_name', '')
                if codec_name in ['ass', 'ssa']:
                    sub_ext = '.ass'
                elif codec_name == 'subrip':
                    sub_ext = '.srt'
                elif codec_name == 'mov_text':
                    sub_ext = '.srt'
                else:
                    sub_ext = '.sub'
                
                sub_path = f"temp/{user_id}/batch1/S{season}E{episode}_sub_{sub_idx}_{sub_lang}{sub_ext}"
                
                extract_cmd = [
                    shutil.which('ffmpeg'),
                    '-i', input_path,
                    '-map', f'0:s:{sub_idx}',
                    '-c', 'copy',
                    '-loglevel', 'error',
                    '-y', sub_path
                ]
                
                proc = await asyncio.create_subprocess_exec(*extract_cmd)
                await proc.communicate()
                
                if os.path.exists(sub_path):
                    subtitle_tracks.append({
                        'path': sub_path,
                        'language': sub_lang,
                        'title': sub_title,
                        'index': sub_idx
                    })
        
        return audio_tracks, subtitle_tracks
        
    except Exception as e:
        logger.error(f"Error extracting tracks: {e}")
        return [], []

async def merge_tracks(source_path, audio_tracks, subtitle_tracks, output_path):
    """Merge audio and subtitle tracks into source video"""
    try:
        ffmpeg_cmd = shutil.which('ffmpeg')
        if not ffmpeg_cmd:
            raise Exception("FFmpeg not found")
        
        # Build complex filter command
        cmd = [ffmpeg_cmd, '-i', source_path]
        
        # Add all audio tracks
        audio_map = ['0:v:0']  # Keep original video
        audio_map.append('0:a:0')  # Keep first original audio
        
        for i, audio in enumerate(audio_tracks):
            cmd.extend(['-i', audio['path']])
            audio_map.append(f'{i+1}:a:0')
        
        # Add all subtitle tracks
        subtitle_start_idx = len(audio_tracks) + 1
        for i, sub in enumerate(subtitle_tracks):
            cmd.extend(['-i', sub['path']])
            audio_map.append(f'{i+subtitle_start_idx}:s:0')
        
        # Build map arguments
        for i in range(len(audio_map)):
            cmd.extend(['-map', audio_map[i]])
        
        # Copy all codecs
        cmd.extend(['-c', 'copy'])
        
        # For MP4 containers, convert subtitles to mov_text
        if output_path.lower().endswith('.mp4'):
            # Find subtitle stream indices
            sub_indices = list(range(len(audio_tracks) + 1, len(audio_tracks) + len(subtitle_tracks) + 1))
            for idx in sub_indices:
                cmd.extend([f'-c:s:{idx}', 'mov_text'])
        
        cmd.extend(['-loglevel', 'error', '-y', output_path])
        
        process = await asyncio.create_subprocess_exec(*cmd)
        await process.communicate()
        
        return process.returncode == 0
        
    except Exception as e:
        logger.error(f"Error merging tracks: {e}")
        return False

async def cleanup_user_temp(user_id):
    """Clean up temporary files for a user"""
    temp_dir = f"temp/{user_id}"
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning temp dir for user {user_id}: {e}")

# ===== Command Handlers =====

@Client.on_message(filters.private & filters.command("merging"))
async def merging_toggle(client, message):
    """Toggle merging mode ON/OFF"""
    user_id = message.from_user.id
    
    # Create toggle buttons
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 ON", callback_data="merging_on"),
            InlineKeyboardButton("🔴 OFF", callback_data="merging_off")
        ]
    ])
    
    current_status = await get_merging_mode(user_id)
    status_text = "🟢 **ON**" if current_status else "🔴 **OFF**"
    
    text = (
        f"**Auto File Merging System**\n\n"
        f"Current Status: {status_text}\n\n"
        f"🔁 **When ON:**\n"
        f"• Auto rename is disabled\n"
        f"• Merging mode is enabled\n"
        f"• Process: Batch1 (extract) → Batch2 (merge)\n\n"
        f"📝 **When OFF:**\n"
        f"• Normal auto rename works\n"
        f"• Merging is disabled\n\n"
        f"Select your mode:"
    )
    
    await message.reply_text(text, reply_markup=buttons)

@Client.on_callback_query(filters.regex(r'^merging_(on|off)$'))
async def merging_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data.split('_')[1]

    # 🔍 DEBUG LOGGING (ADD THIS)
    logger.info(f"Merging callback: user_id={user_id}, action={action}")

    if action == 'on':
        await set_merging_mode(user_id, True)
        
        # Clear any previous batch data
        await clear_merging_state(user_id)
        await cleanup_user_temp(user_id)

        # 🔍 DEBUG LOGGING
        logger.info(f"Merging mode enabled for user {user_id}")

        await query.answer("✅ Merging mode enabled! Auto rename is now disabled.")
        text = (
            "🟢 **Merging Mode ENABLED**\n\n"
            "📦 **Step 1:** Send your first batch of files (source files).\n"
            "I will extract audio and subtitle tracks from these.\n\n"
            "⚠️ **Note:** Send all files from Batch 1 first, then I'll ask for Batch 2."
        )

    else:
        await set_merging_mode(user_id, False)
        await cleanup_user_temp(user_id)
        await clear_merging_state(user_id)

        # 🔍 DEBUG LOGGING
        logger.info(f"Merging mode disabled for user {user_id}")

        await query.answer("✅ Merging mode disabled! Auto rename is now enabled.")
        text = "🔴 **Merging Mode DISABLED**\n\nNormal auto rename is now active."

    await query.message.edit_text(text)

# ===== File Processing Handler =====

@Client.on_message(filters.private & (filters.document | filters.video))
async def handle_merging_files(client, message):
    """Handle files in merging mode"""
    user_id = message.from_user.id
    
    # Check if user is verified
    if not await is_user_verified(user_id):
        await send_verification(client, message)
        return
    
    # Check if merging mode is enabled
    if not await get_merging_mode(user_id):
        # Pass to normal auto rename handler
        return
    
    # Check if we're waiting for batch2
    state = await get_merging_state(user_id)
    if state.get('batch2_waiting', False):
        await process_batch2_file(client, message)
    else:
        await process_batch1_file(client, message)

async def process_batch1_file(client, message):
    """Process files from batch 1 (extract tracks)"""
    user_id = message.from_user.id
    
    # Get current state
    state = await get_merging_state(user_id)
    batch1_tracks = state.get('batch1_tracks', {})
    
    # Initialize batch1 files if not exists
    if user_id not in batch1_files_cache:
        batch1_files_cache[user_id] = []
    
    media = message.document or message.video
    if not media:
        return
    
    file_name = getattr(media, 'file_name', 'video.mp4')
    season, episode = extract_season_episode(file_name)
    
    if not season or not episode:
        await message.reply_text(
            "⚠️ Could not detect season/episode number in filename.\n"
            "Please use standard naming like: S01E03.mkv or Episode 03.mp4"
        )
        return
    
    key = f"S{season}E{episode}"
    
    # Download the file
    os.makedirs(f"temp/{user_id}/downloads", exist_ok=True)
    download_path = f"temp/{user_id}/downloads/{message.id}_{file_name}"
    
    download_msg = await message.reply_text("**Downloading Batch 1 file...**")
    
    try:
        path = await client.download_media(
            message, 
            file_name=download_path,
            progress=progress_for_pyrogram,
            progress_args=("Downloading...", download_msg, time.time())
        )
        
        await download_msg.edit_text("**Extracting audio and subtitle tracks...**")
        
        # Extract tracks
        audio_tracks, subtitle_tracks = await extract_tracks(path, user_id, season, episode)
        
        if not audio_tracks and not subtitle_tracks:
            await download_msg.edit_text("⚠️ No audio or subtitle tracks found in this file.")
            os.remove(path)
            return
        
        # Update tracks in state
        if key not in batch1_tracks:
            batch1_tracks[key] = {
                'audio': [],
                'subtitle': []
            }
        
        batch1_tracks[key]['audio'].extend(audio_tracks)
        batch1_tracks[key]['subtitle'].extend(subtitle_tracks)
        batch1_files_cache[user_id].append(path)
        
        # Save updated state to database
        await set_merging_state(user_id, batch1_tracks=batch1_tracks)
        
        # Count extracted tracks
        audio_count = len(audio_tracks)
        sub_count = len(subtitle_tracks)
        
        await download_msg.edit_text(
            f"✅ **Batch 1 - File Processed**\n\n"
            f"Season {season}, Episode {episode}\n"
            f"Audio tracks: {audio_count}\n"
            f"Subtitle tracks: {sub_count}\n\n"
            f"Send more Batch 1 files, or send /batch1_done when finished."
        )
        
    except Exception as e:
        logger.error(f"Error processing batch1 file: {e}")
        await download_msg.edit_text(f"❌ Error: {str(e)}")

async def process_batch2_file(client, message):
    """Process files from batch 2 (merge tracks)"""
    user_id = message.from_user.id
    
    media = message.document or message.video
    if not media:
        return
    
    file_name = getattr(media, 'file_name', 'video.mp4')
    file_size = media.file_size
    season, episode = extract_season_episode(file_name)
    
    if not season or not episode:
        await message.reply_text(
            "⚠️ Could not detect season/episode number in filename.\n"
            "Cannot merge without season/episode information."
        )
        return
    
    key = f"S{season}E{episode}"
    
    # Check if we have tracks for this episode
    state = await get_merging_state(user_id)
    batch1_tracks = state.get('batch1_tracks', {})
    
    if key not in batch1_tracks:
        await message.reply_text(
            f"⚠️ No tracks found for Season {season}, Episode {episode} in Batch 1.\n"
            f"Skipping this file."
        )
        return
    
    tracks = batch1_tracks[key]
    if not tracks.get('audio') and not tracks.get('subtitle'):
        await message.reply_text(
            f"⚠️ No audio or subtitle tracks available for merging.\n"
            f"Skipping this file."
        )
        return
    
    # Download batch2 file
    os.makedirs(f"temp/{user_id}/batch2", exist_ok=True)
    download_path = f"temp/{user_id}/batch2/{message.id}_{file_name}"
    
    download_msg = await message.reply_text("**Downloading Batch 2 file...**")
    
    try:
        path = await client.download_media(
            message,
            file_name=download_path,
            progress=progress_for_pyrogram,
            progress_args=("Downloading...", download_msg, time.time())
        )
        
        await download_msg.edit_text("**Merging audio and subtitle tracks...**")
        
        # Create output filename using auto rename format
        format_template = await codeflixbots.get_format_template(user_id)
        if not format_template:
            # Default format if no template set
            format_template = f"[S[SE.NUM]-E[EP.NUM]] [[QUALITY]] [Dual] @Animelibraryn4"
        
        # Extract quality from filename (similar to auto rename)
        from plugins.file_rename import extract_quality
        quality = extract_quality(file_name) or ""
        
        # Replace placeholders
        renamed = format_template.replace("[SE.NUM]", str(season)) \
                                .replace("[EP.NUM]", str(episode)) \
                                .replace("[QUALITY]", quality) \
                                .replace("{season}", str(season)) \
                                .replace("{episode}", str(episode)) \
                                .replace("{quality}", quality)
        
        # Clean up filename
        renamed = re.sub(r'\s+', ' ', renamed).strip().replace("_", " ")
        
        # Add extension
        _, ext = os.path.splitext(file_name)
        output_filename = f"{renamed}{ext}"
        output_path = f"temp/{user_id}/output/{output_filename}"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Merge tracks
        success = await merge_tracks(
            path,
            tracks.get('audio', []),
            tracks.get('subtitle', []),
            output_path
        )
        
        if not success:
            await download_msg.edit_text("❌ Failed to merge tracks.")
            return
        
        await download_msg.edit_text("**Uploading merged file...**")
        
        # Get thumbnail if available
        ph_path = None
        thumb = await codeflixbots.get_thumbnail(user_id)
        if thumb:
            ph_path = await client.download_media(thumb)
        
        # Get caption
        c_caption = await codeflixbots.get_caption(message.chat.id)
        caption = c_caption.format(
            filename=output_filename,
            filesize=humanbytes(file_size),
            duration=convert(0)
        ) if c_caption else f"**{output_filename}**"
        
        # Upload merged file
        send_args = {
            "chat_id": message.chat.id,
            "caption": caption,
            "progress": progress_for_pyrogram,
            "progress_args": ("Uploading...", download_msg, time.time())
        }
        
        if media.video:
            send_args["video"] = output_path
            send_args["file_name"] = output_filename
            if ph_path:
                send_args["thumb"] = ph_path
            await client.send_video(**send_args)
        else:
            send_args["document"] = output_path
            send_args["file_name"] = output_filename
            await client.send_document(**send_args)
        
        await download_msg.delete()
        
        # Clean up temp files
        os.remove(path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        
    except Exception as e:
        logger.error(f"Error processing batch2 file: {e}")
        await download_msg.edit_text(f"❌ Error: {str(e)}")

# ===== Batch Control Commands =====

@Client.on_message(filters.private & filters.command("batch1_done"))
async def batch1_done(client, message):
    """Finish batch1 and ask for batch2"""
    user_id = message.from_user.id
    
    if not await get_merging_mode(user_id):
        await message.reply_text("❌ Merging mode is not enabled. Use /merging first.")
        return
    
    state = await get_merging_state(user_id)
    batch1_tracks = state.get('batch1_tracks', {})
    
    if not batch1_tracks:
        await message.reply_text("❌ No Batch 1 files processed yet.")
        return
    
    # Count total tracks extracted
    total_episodes = len(batch1_tracks)
    total_audio = 0
    total_subtitle = 0
    
    for episode in batch1_tracks.values():
        total_audio += len(episode.get('audio', []))
        total_subtitle += len(episode.get('subtitle', []))
    
    await set_merging_state(user_id, batch2_waiting=True)
    
    text = (
        f"✅ **Batch 1 Complete!**\n\n"
        f"Episodes processed: {total_episodes}\n"
        f"Audio tracks extracted: {total_audio}\n"
        f"Subtitle tracks extracted: {total_subtitle}\n\n"
        f"📦 **Step 2:** Now send your second batch of files.\n"
        f"I will merge the extracted tracks into these files.\n\n"
        f"⚠️ **Note:** Files will be matched by season/episode numbers."
    )
    
    await message.reply_text(text)

@Client.on_message(filters.private & filters.command("batch2_done"))
async def batch2_done(client, message):
    """Finish batch2 and clean up"""
    user_id = message.from_user.id
    
    if not await get_merging_mode(user_id):
        await message.reply_text("❌ Merging mode is not enabled.")
        return
    
    # Clean up temp files
    await cleanup_user_temp(user_id)
    
    # Reset user state
    await clear_merging_state(user_id)
    
    await message.reply_text(
        "✅ **Merging Complete!**\n\n"
        "All temporary files have been cleaned up.\n"
        "Merging mode is still active. Send more files or use /merging to disable."
    )

@Client.on_message(filters.private & filters.command("merging_status"))
async def merging_status(client, message):
    """Check current merging status"""
    user_id = message.from_user.id
    
    status = await get_merging_mode(user_id)
    status_text = "🟢 **ENABLED**" if status else "🔴 **DISABLED**"
    
    text = f"**Auto Merging Status:** {status_text}\n\n"
    
    if status:
        state = await get_merging_state(user_id)
        batch2_waiting = state.get('batch2_waiting', False)
        batch1_tracks = state.get('batch1_tracks', {})
        
        if batch2_waiting:
            text += "⏳ **Waiting for Batch 2 files**\n"
            if batch1_tracks:
                episodes = len(batch1_tracks)
                text += f"Batch 1: {episodes} episode(s) processed\n"
        else:
            if batch1_tracks:
                episodes = len(batch1_tracks)
                text += f"📦 **Batch 1 in progress:** {episodes} episode(s)\n"
                text += "Send /batch1_done when finished\n"
            else:
                text += "📤 **Ready for Batch 1 files**\n"
                text += "Send source files to extract tracks\n"
    else:
        text += "Auto rename mode is active\n"
    
    await message.reply_text(text)

@Client.on_message(filters.private & filters.command("merging_cancel"))
async def merging_cancel(client, message):
    """Cancel merging and clean up"""
    user_id = message.from_user.id
    
    # Clean up temp files
    await cleanup_user_temp(user_id)
    
    # Reset all states
    await clear_merging_state(user_id)
    await set_merging_mode(user_id, False)
    
    await message.reply_text(
        "✅ **Merging cancelled!**\n\n"
        "All temporary files cleaned up.\n"
        "Auto rename mode is now active."
    )
