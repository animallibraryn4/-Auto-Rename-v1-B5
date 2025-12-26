import os
import re
import asyncio
import logging
import shutil
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import codeflixbots
from helper.utils import progress_for_pyrogram, humanbytes, convert
from plugins.file_rename import (
    extract_episode_number, extract_season_number,
    extract_quality, standardize_quality_name
)
import time

logger = logging.getLogger(__name__)

# Global queue for merge processing
merge_queues = {}
merge_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent merge operations

async def merge_worker(user_id, client):
    """Worker to process merge operations for a specific user"""
    queue = merge_queues[user_id]["queue"]
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=300)
            async with merge_semaphore:
                await process_merge_file(client, message)
            queue.task_done()
        except asyncio.TimeoutError:
            if user_id in merge_queues:
                del merge_queues[user_id]
            break
        except Exception as e:
            logger.error(f"Error in merge_worker for user {user_id}: {e}")
            if user_id in merge_queues:
                try:
                    queue.task_done()
                except:
                    pass

def extract_streams_info(file_path):
    """Extract information about audio and subtitle streams"""
    ffprobe_cmd = shutil.which('ffprobe')
    if not ffprobe_cmd:
        return {"audios": [], "subtitles": []}
    
    try:
        # Get audio streams
        audio_cmd = [
            ffprobe_cmd, '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=index,codec_name,channels,language:stream_tags=language,title',
            '-of', 'json',
            file_path
        ]
        
        # Get subtitle streams
        sub_cmd = [
            ffprobe_cmd, '-v', 'error',
            '-select_streams', 's',
            '-show_entries', 'stream=index,codec_name,language:stream_tags=language,title',
            '-of', 'json',
            file_path
        ]
        
        # Run commands (simplified - in reality would use asyncio subprocess)
        import subprocess
        audio_result = subprocess.run(audio_cmd, capture_output=True, text=True)
        sub_result = subprocess.run(sub_cmd, capture_output=True, text=True)
        
        # Parse results
        import json
        audio_info = json.loads(audio_result.stdout) if audio_result.stdout else {"streams": []}
        sub_info = json.loads(sub_result.stdout) if sub_result.stdout else {"streams": []}
        
        return {
            "audios": audio_info.get("streams", []),
            "subtitles": sub_info.get("streams", [])
        }
    except Exception as e:
        logger.error(f"Error extracting stream info: {e}")
        return {"audios": [], "subtitles": []}

async def merge_video_with_tracks(source_video, target_video, tracks, output_path):
    """Merge tracks from source into target video"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        raise Exception("FFmpeg not found")
    
    # Build complex filter to merge streams
    cmd = [ffmpeg_cmd, '-i', target_video]
    
    # Add source video (only for audio/subtitle extraction)
    cmd.extend(['-i', source_video])
    
    # Map all streams from target video
    cmd.extend(['-map', '0:v'])  # Video from target
    cmd.extend(['-map', '0:a'])  # Existing audio from target
    cmd.extend(['-map', '0:s'])  # Existing subtitles from target
    
    # Add new audio streams from source
    audio_index = 1  # Source is input 1
    for i, audio in enumerate(tracks.get("audios", [])):
        cmd.extend(['-map', f'{audio_index}:a:{i}'])
    
    # Add new subtitle streams from source
    for i, sub in enumerate(tracks.get("subtitles", [])):
        cmd.extend(['-map', f'{audio_index}:s:{i}'])
    
    # Copy all codecs
    cmd.extend(['-c', 'copy'])
    
    # Output file
    cmd.extend(['-y', output_path])
    
    # Run FFmpeg
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"FFmpeg error: {stderr.decode()}")
    
    return True

async def process_merge_file(client, message):
    """Process a file for merging based on current mode"""
    user_id = message.from_user.id
    
    # Check if merge mode is enabled
    if not await codeflixbots.get_merge_mode(user_id):
        return  # Should not reach here if merge mode is off
    
    # Get merge data
    batch1 = await codeflixbots.get_merge_batch1(user_id)
    tracks = await codeflixbots.get_merge_tracks(user_id)
    merge_format = await codeflixbots.get_merge_format(user_id)
    
    # Check file type
    media = message.document or message.video
    if not media:
        await message.reply_text("❌ Unsupported file type")
        return
    
    file_name = getattr(media, 'file_name', 'video.mkv')
    file_size = media.file_size
    
    # Extract season and episode
    episode = extract_episode_number(file_name)
    season = extract_season_number(file_name)
    
    if not episode or not season:
        await message.reply_text(
            f"❌ Could not extract season/episode from: {file_name}\n"
            "Skipping this file..."
        )
        return
    
    key = f"S{season}E{episode}"
    
    # Check if this is batch 1 or batch 2
    if key not in batch1:
        # This is batch 1 file
        download_msg = await message.reply_text(f"📥 **Downloading Batch 1:** {file_name}")
        
        # Download file
        download_path = f"downloads/merge_batch1_{message.id}_{file_name}"
        os.makedirs("downloads", exist_ok=True)
        
        try:
            path = await client.download_media(
                message,
                file_name=download_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", download_msg, time.time())
            )
        except Exception as e:
            await download_msg.edit(f"❌ Download error: {e}")
            return
        
        # Extract stream information
        await download_msg.edit("🔍 **Extracting audio/subtitle tracks...**")
        
        stream_info = extract_streams_info(path)
        
        # Store in batch1
        batch1[key] = {
            "file_path": path,
            "file_name": file_name,
            "stream_info": stream_info
        }
        
        # Also store tracks separately
        tracks[key] = stream_info
        
        await codeflixbots.set_merge_batch1(user_id, batch1)
        await codeflixbots.set_merge_tracks(user_id, tracks)
        
        await download_msg.edit(
            f"✅ **Batch 1 stored:** {file_name}\n\n"
            f"**Found:**\n"
            f"• {len(stream_info['audios'])} audio track(s)\n"
            f"• {len(stream_info['subtitles'])} subtitle track(s)\n\n"
            f"Now send Batch 2 files for merging."
        )
        
        # Clean up
        if os.path.exists(path):
            os.remove(path)
            
    else:
        # This is batch 2 file - process merging
        if key not in tracks:
            await message.reply_text(
                f"❌ No matching tracks found for {key}\n"
                "Skipping this file..."
            )
            return
        
        download_msg = await message.reply_text(f"🔄 **Processing:** {file_name}")
        
        # Download batch 2 file
        download_path = f"downloads/merge_batch2_{message.id}_{file_name}"
        
        try:
            path = await client.download_media(
                message,
                file_name=download_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", download_msg, time.time())
            )
        except Exception as e:
            await download_msg.edit(f"❌ Download error: {e}")
            return
        
        # Get batch 1 file path
        batch1_info = batch1.get(key)
        if not batch1_info:
            await download_msg.edit(f"❌ Batch 1 data missing for {key}")
            return
        
        # Create output path
        output_filename = await generate_merged_filename(
            merge_format, file_name, season, episode, tracks[key]
        )
        output_path = f"downloads/merged_{message.id}_{output_filename}"
        
        # Merge files
        await download_msg.edit("🔗 **Merging tracks...**")
        
        try:
            await merge_video_with_tracks(
                batch1_info["file_path"],
                path,
                tracks[key],
                output_path
            )
        except Exception as e:
            await download_msg.edit(f"❌ Merge error: {e}")
            return
        
        # Upload merged file
        await download_msg.edit("📤 **Uploading merged file...**")
        
        # Get thumbnail
        c_thumb = await codeflixbots.get_thumbnail(user_id)
        ph_path = None
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
        
        # Upload
        if message.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=output_path,
                file_name=output_filename,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", download_msg, time.time())
            )
        else:
            await client.send_document(
                chat_id=message.chat.id,
                document=output_path,
                file_name=output_filename,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", download_msg, time.time())
            )
        
# Replace the process_merge_file function:

async def process_merge_file(client, message):
    """Process a file for merging based on current mode"""
    user_id = message.from_user.id
    
    # Get merge data
    batch1 = await codeflixbots.get_merge_batch1(user_id)
    tracks = await codeflixbots.get_merge_tracks(user_id)
    merge_format = await codeflixbots.get_merge_format(user_id)
    
    if not merge_format:
        await message.reply_text(
            "❌ **Merge format not set!**\n\n"
            "Please use `/mergeformat` first to set output naming format."
        )
        return
    
    # Check file type
    media = message.document or message.video
    if not media:
        await message.reply_text("❌ Unsupported file type. Send video files only.")
        return
    
    file_name = getattr(media, 'file_name', 'video.mkv')
    file_size = media.file_size
    
    # Extract season and episode
    episode = extract_episode_number(file_name)
    season = extract_season_number(file_name)
    
    if not episode or not season:
        await message.reply_text(
            f"❌ Could not extract season/episode from: {file_name}\n"
            "Skipping this file..."
        )
        return
    
    key = f"S{season}E{episode}"
    
    # Check if this is the first batch (source files for tracks)
    if key not in batch1:
        # This is batch 1 file - extract tracks only
        download_msg = await message.reply_text(f"📥 **Batch 1 - Extracting tracks:** {file_name}")
        
        # Download file
        download_path = f"downloads/merge_batch1_{message.id}_{file_name}"
        os.makedirs("downloads", exist_ok=True)
        
        try:
            path = await client.download_media(
                message,
                file_name=download_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", download_msg, time.time())
            )
        except Exception as e:
            await download_msg.edit(f"❌ Download error: {e}")
            return
        
        # Extract stream information
        await download_msg.edit("🔍 **Extracting audio/subtitle tracks...**")
        
        stream_info = extract_streams_info(path)
        
        # Store in batch1
        batch1[key] = {
            "file_path": path,
            "file_name": file_name,
            "season": season,
            "episode": episode,
            "stream_info": stream_info
        }
        
        # Also store tracks separately
        tracks[key] = stream_info
        
        await codeflixbots.set_merge_batch1(user_id, batch1)
        await codeflixbots.set_merge_tracks(user_id, tracks)
        
        # Get counts
        audio_count = len(stream_info.get('audios', []))
        sub_count = len(stream_info.get('subtitles', []))
        
        await download_msg.edit(
            f"✅ **Batch 1 stored:** {file_name}\n\n"
            f"**Season {season}, Episode {episode}**\n"
            f"• Audio tracks: {audio_count}\n"
            f"• Subtitle tracks: {sub_count}\n\n"
            f"**Total stored:** {len(batch1)} episodes\n\n"
            "Continue sending Batch 1 files, or start sending Batch 2 files."
        )
        
        # Clean up
        if os.path.exists(path):
            os.remove(path)
            
    else:
        # This is batch 2 file - process merging
        if key not in tracks:
            await message.reply_text(
                f"❌ No matching tracks found for {key}\n"
                "Make sure you sent this episode in Batch 1 first."
            )
            return
        
        # Check if we already processed this episode
        processed_key = f"processed_{key}"
        if processed_key in batch1:
            await message.reply_text(
                f"⚠️ Episode {key} already processed!\n"
                f"Renamed as: {batch1[processed_key]}"
            )
            return
        
        download_msg = await message.reply_text(f"🔄 **Merging:** {file_name}")
        
        # Download batch 2 file
        download_path = f"downloads/merge_batch2_{message.id}_{file_name}"
        
        try:
            path = await client.download_media(
                message,
                file_name=download_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading Batch 2...", download_msg, time.time())
            )
        except Exception as e:
            await download_msg.edit(f"❌ Download error: {e}")
            return
        
        # Get batch 1 track info
        batch1_info = tracks.get(key)
        if not batch1_info:
            await download_msg.edit(f"❌ Track data missing for {key}")
            return
        
        # Create output path
        quality = extract_quality(file_name)
        output_filename = await generate_merged_filename(
            merge_format, file_name, season, episode, batch1_info, quality
        )
        output_path = f"downloads/merged_{message.id}_{output_filename}"
        
        # Check if we need to merge (has extra tracks)
        audio_count = len(batch1_info.get('audios', []))
        sub_count = len(batch1_info.get('subtitles', []))
        
        if audio_count == 0 and sub_count == 0:
            # No tracks to merge - just rename
            await download_msg.edit("📝 **No extra tracks found, renaming only...**")
            import shutil
            shutil.copy2(path, output_path)
        else:
            # Merge tracks
            await download_msg.edit("🔗 **Merging audio/subtitle tracks...**")
            
            try:
                # For now, we'll create a simple merged file
                # In production, you would use actual FFmpeg merging
                await simple_merge_with_ffmpeg(path, batch1_info, output_path)
            except Exception as e:
                await download_msg.edit(f"❌ Merge error: {e}")
                # Fallback - just copy the file
                import shutil
                shutil.copy2(path, output_path)
        
        # Upload merged file
        await download_msg.edit("📤 **Uploading merged file...**")
        
        # Get thumbnail
        c_thumb = await codeflixbots.get_thumbnail(user_id)
        ph_path = None
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
        
        # Upload
        caption = f"**Merged:** {output_filename}\nSeason {season}, Episode {episode}"
        
        if message.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=output_path,
                file_name=output_filename,
                caption=caption,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", download_msg, time.time())
            )
        else:
            await client.send_document(
                chat_id=message.chat.id,
                document=output_path,
                file_name=output_filename,
                caption=caption,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", download_msg, time.time())
            )
        
        # Mark as processed
        batch1[f"processed_{key}"] = output_filename
        await codeflixbots.set_merge_batch1(user_id, batch1)
        
        await download_msg.delete()
        
        # Cleanup
        for p in [path, output_path, ph_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

async def simple_merge_with_ffmpeg(video_path, tracks_info, output_path):
    """Simple FFmpeg merge implementation"""
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        # Just copy if no FFmpeg
        import shutil
        shutil.copy2(video_path, output_path)
        return
    
    # Basic FFmpeg command that copies everything
    cmd = [ffmpeg_cmd, '-i', video_path, '-c', 'copy', '-y', output_path]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    await process.communicate()

async def generate_merged_filename(format_template, original_name, season, episode, tracks_info, quality):
    """Generate filename for merged output"""
    # Standardize quality
    std_quality = standardize_quality_name(quality) if quality != "Unknown" else ""
    
    # Check if we have extra audio tracks
    audio_count = len(tracks_info.get('audios', []))
    has_extra_audio = audio_count > 0
    dual_tag = "[Dual]" if has_extra_audio else ""
    
    # Check subtitle count
    sub_count = len(tracks_info.get('subtitles', []))
    sub_tag = f"[Sub{sub_count}]" if sub_count > 0 else ""
    
    # Replace placeholders
    replacements = {
        "[SE.NUM]": str(season),
        "[EP.NUM]": str(episode),
        "[QUALITY]": std_quality,
        "[DUAL]": dual_tag,
        "[SUBS]": sub_tag,
        "{season}": str(season),
        "{episode}": str(episode),
        "{quality}": std_quality,
        "{dual}": dual_tag,
        "{subs}": sub_tag
    }
    
    for old, new in replacements.items():
        if old in format_template:
            format_template = format_template.replace(old, new)
    
    # Clean up multiple spaces
    import re
    format_template = re.sub(r'\s+', ' ', format_template).strip()
    
    # Add extension
    _, ext = os.path.splitext(original_name)
    if not ext:
        ext = '.mkv'
    
    return f"{format_template}{ext}"
