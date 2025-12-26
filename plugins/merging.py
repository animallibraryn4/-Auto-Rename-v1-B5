import os
import re
import asyncio
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from plugins import is_user_verified
from config import Config

# Setup logging
logger = logging.getLogger(__name__)

# ===== User State Management =====
user_states = {}  # user_id -> {"state": "waiting_for_source" | "processing_source" | "waiting_for_target" | "processing"}

# ===== File Storage =====
user_source_files = {}  # user_id -> {ep_key: {"audio_path": "...", "subtitle_path": "...", "filename": "..."}}
user_temp_files = {}    # user_id -> list of temp files to cleanup

# ===== Patterns for extracting episode info =====
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE)
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)', re.IGNORECASE)
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE)
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)

def extract_episode_info(filename: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract season and episode numbers from filename."""
    patterns = [pattern1, pattern2, pattern4]
    
    for pattern in patterns:
        match = pattern.search(filename)
        if match:
            if len(match.groups()) >= 2:
                season = int(match.group(1))
                episode = int(match.group(2))
                return season, episode
    
    # Try to get just episode number if season not found
    match = pattern3.search(filename)
    if match:
        episode = int(match.group(1))
        return 1, episode  # Default to season 1
    
    return None, None

def get_episode_key(season: int, episode: int) -> str:
    """Create a unique key for episode identification."""
    return f"S{season:02d}E{episode:02d}"

async def extract_audio_tracks(input_path: str, output_dir: str) -> List[str]:
    """Extract all audio tracks from video file."""
    extracted_audio = []
    ffprobe_cmd = shutil.which('ffprobe')
    ffmpeg_cmd = shutil.which('ffmpeg')
    
    if not ffprobe_cmd or not ffmpeg_cmd:
        raise Exception("FFmpeg/FFprobe not found")
    
    # Get audio track information
    cmd = [
        ffprobe_cmd, '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=index,codec_name,channels,language',
        '-of', 'csv=p=0',
        input_path
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    
    audio_streams = []
    for line in stdout.decode().strip().split('\n'):
        if line:
            parts = line.split(',')
            if len(parts) >= 3:
                idx = parts[0]
                codec = parts[1]
                channels = parts[2] if len(parts) > 2 else "2"
                language = parts[3] if len(parts) > 3 else "und"
                audio_streams.append({
                    'index': idx,
                    'codec': codec,
                    'channels': channels,
                    'language': language
                })
    
    # Extract each audio track
    for i, stream in enumerate(audio_streams):
        audio_ext = {
            'aac': '.m4a',
            'mp3': '.mp3',
            'ac3': '.ac3',
            'dts': '.dts',
            'flac': '.flac',
            'opus': '.opus'
        }.get(stream['codec'], '.mka')
        
        output_file = os.path.join(output_dir, f"audio_{i+1}_{stream['language']}{audio_ext}")
        
        # Extract audio track
        cmd = [
            ffmpeg_cmd, '-i', input_path,
            '-map', f'0:a:{stream["index"]}',
            '-c', 'copy',
            '-loglevel', 'error',
            '-y', output_file
        ]
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            extracted_audio.append(output_file)
    
    return extracted_audio

async def extract_subtitle_tracks(input_path: str, output_dir: str) -> List[str]:
    """Extract all subtitle tracks from video file."""
    extracted_subs = []
    ffprobe_cmd = shutil.which('ffprobe')
    ffmpeg_cmd = shutil.which('ffmpeg')
    
    if not ffprobe_cmd or not ffmpeg_cmd:
        raise Exception("FFmpeg/FFprobe not found")
    
    # Get subtitle track information
    cmd = [
        ffprobe_cmd, '-v', 'error',
        '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name,language',
        '-of', 'csv=p=0',
        input_path
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    
    subtitle_streams = []
    for line in stdout.decode().strip().split('\n'):
        if line:
            parts = line.split(',')
            if len(parts) >= 2:
                idx = parts[0]
                codec = parts[1]
                language = parts[2] if len(parts) > 2 else "und"
                subtitle_streams.append({
                    'index': idx,
                    'codec': codec,
                    'language': language
                })
    
    # Extract each subtitle track
    for i, stream in enumerate(subtitle_streams):
        sub_ext = {
            'ass': '.ass',
            'ssa': '.ssa',
            'subrip': '.srt',
            'webvtt': '.vtt',
            'hdmv_pgs_subtitle': '.sup',
            'dvb_subtitle': '.sub'
        }.get(stream['codec'], '.srt')
        
        output_file = os.path.join(output_dir, f"sub_{i+1}_{stream['language']}{sub_ext}")
        
        # Extract subtitle track
        cmd = [
            ffmpeg_cmd, '-i', input_path,
            '-map', f'0:s:{stream["index"]}',
            '-c', 'copy',
            '-loglevel', 'error',
            '-y', output_file
        ]
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        
        # Convert to SRT if needed (for compatibility)
        if stream['codec'] in ['ass', 'ssa']:
            srt_file = output_file.replace(sub_ext, '.srt')
            cmd = [
                ffmpeg_cmd, '-i', output_file,
                '-loglevel', 'error',
                '-y', srt_file
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
            
            if os.path.exists(srt_file) and os.path.getsize(srt_file) > 0:
                os.remove(output_file)
                extracted_subs.append(srt_file)
            else:
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    extracted_subs.append(output_file)
        else:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                extracted_subs.append(output_file)
    
    return extracted_subs

async def merge_audio_subtitles(source_tracks: Dict, target_path: str, output_path: str) -> bool:
    """Merge audio and subtitles from source to target file."""
    ffmpeg_cmd = shutil.which('ffmpeg')
    
    if not ffmpeg_cmd:
        raise Exception("FFmpeg not found")
    
    # Build ffmpeg command
    cmd = [ffmpeg_cmd, '-i', target_path]
    
    # Add input files for extracted audio and subtitles
    input_files = []
    audio_tracks = source_tracks.get('audio', [])
    sub_tracks = source_tracks.get('subtitle', [])
    
    # Add audio tracks
    for i, audio_file in enumerate(audio_tracks):
        cmd.extend(['-i', audio_file])
        input_files.append(audio_file)
    
    # Add subtitle tracks
    for i, sub_file in enumerate(sub_tracks):
        cmd.extend(['-i', sub_file])
        input_files.append(sub_file)
    
    # Map all streams
    cmd.extend(['-map', '0:v'])  # Original video
    
    # Map original audio tracks
    cmd.extend(['-map', '0:a'])
    
    # Map new audio tracks
    for i in range(len(audio_tracks)):
        cmd.extend(['-map', f'{i+1}:a'])
    
    # Map original subtitle tracks
    cmd.extend(['-map', '0:s'])
    
    # Map new subtitle tracks
    for i in range(len(sub_tracks)):
        cmd.extend(['-map', f'{i+1 + len(audio_tracks)}:s'])
    
    # Copy all codecs
    cmd.extend(['-c', 'copy'])
    
    # Add metadata
    cmd.extend(['-metadata:s:v:0', 'title="Video"'])
    
    # Add language metadata for audio
    for i in range(len(audio_tracks) + 1):  # +1 for original audio
        cmd.extend(['-metadata:s:a:{}'.format(i), 'language=eng'])
    
    # Add language metadata for subtitles
    for i in range(len(sub_tracks) + 1):  # +1 for original subtitles
        cmd.extend(['-metadata:s:s:{}'.format(i), 'language=eng'])
    
    cmd.extend(['-loglevel', 'error', '-y', output_path])
    
    # Execute command
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        logger.error(f"Merge failed: {stderr.decode()}")
        return False
    
    return True

async def cleanup_user_files(user_id: int):
    """Clean up temporary files for a user."""
    if user_id in user_temp_files:
        for file_path in user_temp_files[user_id]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error cleaning up file {file_path}: {e}")
        user_temp_files.pop(user_id, None)
    
    if user_id in user_source_files:
        user_source_files.pop(user_id, None)

def register_temp_file(user_id: int, file_path: str):
    """Register a temp file for cleanup."""
    if user_id not in user_temp_files:
        user_temp_files[user_id] = []
    user_temp_files[user_id].append(file_path)

@Client.on_message(filters.private & filters.command("merging"))
async def merging_command(client: Client, message: Message):
    """Start the merging process."""
    user_id = message.from_user.id
    
    # Check verification
    if not await is_user_verified(user_id):
        await message.reply_text("⚠️ Please verify your account first using /verify command.")
        return
    
    # Check if already in merging process
    if user_id in user_states:
        await message.reply_text("⚠️ You already have a merging session in progress. Use /cancel_merge to cancel it.")
        return
    
    # Initialize user state
    user_states[user_id] = {
        "state": "waiting_for_source",
        "message": None,
        "source_files": {},
        "current_source_index": 0,
        "target_files": [],
        "current_target_index": 0
    }
    
    # Cleanup any previous temp files
    await cleanup_user_files(user_id)
    
    await message.reply_text(
        "🔧 **Audio/Subtitle Merger**\n\n"
        "📁 **Step 1: Send Source Files**\n"
        "Please send the source video files (one by one) from which you want to extract audio and subtitles.\n\n"
        "**Instructions:**\n"
        "1. Send source files containing the audio/subtitles you want to extract\n"
        "2. Files should contain season/episode numbers (e.g., S01E01, Season 1 Episode 1)\n"
        "3. Send files one at a time\n"
        "4. Type /done_sources when finished\n\n"
        "⚠️ **Note:** Auto-rename feature will be disabled during this process."
    )

@Client.on_message(filters.private & filters.command("cancel_merge"))
async def cancel_merge_command(client: Client, message: Message):
    """Cancel the merging process."""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        await message.reply_text("❌ No active merging session found.")
        return
    
    # Cleanup files
    await cleanup_user_files(user_id)
    
    # Remove user state
    user_states.pop(user_id, None)
    
    await message.reply_text("✅ Merging session cancelled. All temporary files have been cleaned up.")

@Client.on_message(filters.private & filters.command("done_sources"))
async def done_sources_command(client: Client, message: Message):
    """Mark source files as complete and ask for target files."""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        await message.reply_text("❌ No active merging session. Start with /merging")
        return
    
    state = user_states[user_id]
    
    if state["state"] != "waiting_for_source":
        await message.reply_text("⚠️ Unexpected command. Currently processing files.")
        return
    
    if not state.get("source_files"):
        await message.reply_text("❌ No source files received. Please send at least one source file.")
        return
    
    state["state"] = "waiting_for_target"
    
    source_count = len(state["source_files"])
    await message.reply_text(
        f"✅ **Source files recorded: {source_count} files**\n\n"
        "📁 **Step 2: Send Target Files**\n"
        "Now send the target video files (one by one) to which you want to add the extracted audio and subtitles.\n\n"
        "**Important:**\n"
        "• Target files should have matching season/episode numbers\n"
        "• Send files one at a time\n"
        "• Type /done_targets when finished\n\n"
        f"Detected source episodes: {', '.join(state['source_files'].keys())}"
    )

@Client.on_message(filters.private & filters.command("done_targets"))
async def done_targets_command(client: Client, message: Message):
    """Start the merging process with collected files."""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        await message.reply_text("❌ No active merging session. Start with /merging")
        return
    
    state = user_states[user_id]
    
    if state["state"] != "waiting_for_target":
        await message.reply_text("⚠️ Unexpected command. Please send target files first.")
        return
    
    if not state.get("target_files"):
        await message.reply_text("❌ No target files received. Please send at least one target file.")
        return
    
    # Start processing
    await process_merging(client, message)

async def process_merging(client: Client, message: Message):
    """Process the merging of all files."""
    user_id = message.from_user.id
    state = user_states[user_id]
    
    state["state"] = "processing"
    status_msg = await message.reply_text("🔄 **Starting merging process...**")
    
    total_files = len(state["target_files"])
    successful = 0
    failed = 0
    
    for i, target_file_info in enumerate(state["target_files"], 1):
        try:
            season, episode = target_file_info["season"], target_file_info["episode"]
            ep_key = get_episode_key(season, episode)
            
            await status_msg.edit_text(
                f"🔄 **Processing file {i}/{total_files}**\n"
                f"Episode: {ep_key}\n"
                f"Target: {target_file_info['filename']}"
            )
            
            # Check if we have source tracks for this episode
            if ep_key not in state["source_files"]:
                await message.reply_text(
                    f"⚠️ No source tracks found for {ep_key}. Skipping..."
                )
                failed += 1
                continue
            
            source_tracks = state["source_files"][ep_key]
            
            # Download target file
            target_path = f"downloads/merge_{user_id}_{i}_{target_file_info['filename']}"
            await client.download_media(
                target_file_info["message"],
                file_name=target_path
            )
            register_temp_file(user_id, target_path)
            
            # Create output path
            output_path = f"downloads/merged_{user_id}_{i}_{target_file_info['filename']}"
            
            # Merge tracks
            success = await merge_audio_subtitles(
                source_tracks,
                target_path,
                output_path
            )
            
            if success and os.path.exists(output_path):
                # Send merged file back to user
                await client.send_document(
                    chat_id=user_id,
                    document=output_path,
                    caption=f"✅ **Merged File**: {target_file_info['filename']}\n"
                           f"Episode: {ep_key}\n"
                           f"Added: {len(source_tracks.get('audio', []))} audio tracks, "
                           f"{len(source_tracks.get('subtitle', []))} subtitle tracks"
                )
                register_temp_file(user_id, output_path)
                successful += 1
            else:
                await message.reply_text(f"❌ Failed to merge {ep_key}")
                failed += 1
            
        except Exception as e:
            logger.error(f"Error processing file {i}: {e}")
            await message.reply_text(f"❌ Error processing file {i}: {str(e)}")
            failed += 1
        
        await asyncio.sleep(1)  # Small delay between files
    
    # Cleanup and finalize
    await cleanup_user_files(user_id)
    user_states.pop(user_id, None)
    
    await status_msg.edit_text(
        f"✅ **Merging Complete!**\n\n"
        f"📊 **Results:**\n"
        f"• Successful: {successful}\n"
        f"• Failed: {failed}\n"
        f"• Total: {total_files}\n\n"
        f"All temporary files have been cleaned up."
    )

@Client.on_message(filters.private & (filters.video | filters.document))
async def handle_merge_files(client: Client, message: Message):
    """Handle incoming files during merging process."""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return  # Not in merging mode, let other handlers process
    
    state = user_states[user_id]
    current_state = state["state"]
    
    # Get filename
    filename = getattr(message.video or message.document, 'file_name', 'video.mp4')
    
    # Extract episode info
    season, episode = extract_episode_info(filename)
    
    if season is None or episode is None:
        await message.reply_text(
            "⚠️ Could not detect season/episode number in filename.\n"
            "Please use files with clear naming (e.g., S01E01, Season 1 Episode 1)"
        )
        return
    
    ep_key = get_episode_key(season, episode)
    
    if current_state == "waiting_for_source":
        # Process source file
        await process_source_file(client, message, user_id, state, filename, season, episode, ep_key)
    
    elif current_state == "waiting_for_target":
        # Process target file
        await process_target_file(client, message, user_id, state, filename, season, episode, ep_key)

async def process_source_file(client: Client, message: Message, user_id: int, state: dict, 
                             filename: str, season: int, episode: int, ep_key: str):
    """Process a source file for audio/subtitle extraction."""
    processing_msg = await message.reply_text(f"📥 Downloading source file: {filename}")
    
    # Download file
    temp_dir = f"downloads/source_{user_id}_{ep_key}"
    os.makedirs(temp_dir, exist_ok=True)
    
    input_path = os.path.join(temp_dir, filename)
    await client.download_media(message, file_name=input_path)
    register_temp_file(user_id, input_path)
    
    await processing_msg.edit_text(f"🔧 Extracting tracks from: {filename}")
    
    try:
        # Extract audio tracks
        audio_dir = os.path.join(temp_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        audio_tracks = await extract_audio_tracks(input_path, audio_dir)
        
        # Extract subtitle tracks
        sub_dir = os.path.join(temp_dir, "subtitles")
        os.makedirs(sub_dir, exist_ok=True)
        sub_tracks = await extract_subtitle_tracks(input_path, sub_dir)
        
        # Store tracks
        if ep_key not in state["source_files"]:
            state["source_files"][ep_key] = {
                "audio": [],
                "subtitle": [],
                "filename": filename
            }
        
        # Register temp files for cleanup
        for track in audio_tracks + sub_tracks:
            register_temp_file(user_id, track)
        
        state["source_files"][ep_key]["audio"].extend(audio_tracks)
        state["source_files"][ep_key]["subtitle"].extend(sub_tracks)
        
        await processing_msg.edit_text(
            f"✅ **Source file processed:** {filename}\n"
            f"Episode: {ep_key}\n"
            f"Audio tracks: {len(audio_tracks)}\n"
            f"Subtitle tracks: {len(sub_tracks)}\n\n"
            f"Send next source file or type /done_sources"
        )
        
    except Exception as e:
        logger.error(f"Error processing source file: {e}")
        await processing_msg.edit_text(f"❌ Error processing {filename}: {str(e)}")

async def process_target_file(client: Client, message: Message, user_id: int, state: dict, 
                             filename: str, season: int, episode: int, ep_key: str):
    """Process a target file for merging."""
    # Check if we have source tracks for this episode
    if ep_key not in state["source_files"]:
        await message.reply_text(
            f"⚠️ No source tracks found for episode {ep_key}\n"
            f"Skipping this file. Make sure your source files have matching episode numbers."
        )
        return
    
    # Store target file info
    state["target_files"].append({
        "message": message,
        "filename": filename,
        "season": season,
        "episode": episode
    })
    
    source_info = state["source_files"][ep_key]
    await message.reply_text(
        f"✅ **Target file queued:** {filename}\n"
        f"Episode: {ep_key}\n"
        f"Will merge: {len(source_info['audio'])} audio tracks, "
        f"{len(source_info['subtitle'])} subtitle tracks\n\n"
        f"Send next target file or type /done_targets to start merging"
      )
    
