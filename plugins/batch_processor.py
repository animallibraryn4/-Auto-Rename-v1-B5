import os
import re
import asyncio
import tempfile
import shutil
import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from plugins.file_rename import extract_episode_number
from config import Config

logger = logging.getLogger(__name__)

# ===== BATCH PROCESSING SYSTEM =====
class BatchProcessor:
    def __init__(self):
        self.user_batches = defaultdict(lambda: {
            'batch1': {},  # episode_num -> file_info
            'batch2': {},  # episode_num -> file_info
            'state': 'idle',  # idle, waiting_batch1, waiting_batch2
            'current_batch': None,
            'mode': None  # '480p_to_720p' or '720p_to_480p'
        })
        
    async def start_batch_processing(self, user_id: int, mode: str):
        """Start batch processing for a user"""
        self.user_batches[user_id]['state'] = 'waiting_batch1'
        self.user_batches[user_id]['mode'] = mode
        self.user_batches[user_id]['current_batch'] = 1
        return mode
    
    async def add_file_to_batch(self, user_id: int, message: Message, file_info: dict):
        """Add a file to the appropriate batch"""
        episode_num = extract_episode_number(file_info['file_name'])
        if not episode_num:
            return None, "Could not extract episode number from filename"
        
        user_data = self.user_batches[user_id]
        
        if user_data['state'] == 'waiting_batch1':
            user_data['batch1'][episode_num] = file_info
            return episode_num, "added_to_batch1"
        elif user_data['state'] == 'waiting_batch2':
            user_data['batch2'][episode_num] = file_info
            return episode_num, "added_to_batch2"
        
        return None, "invalid_state"
    
    async def check_batch_completion(self, user_id: int):
        """Check if both batches have matching episodes"""
        user_data = self.user_batches[user_id]
        batch1_eps = set(user_data['batch1'].keys())
        batch2_eps = set(user_data['batch2'].keys())
        
        # Check if all episodes from batch1 exist in batch2
        missing_in_batch2 = batch1_eps - batch2_eps
        missing_in_batch1 = batch2_eps - batch1_eps
        
        if missing_in_batch2:
            return False, f"Missing episodes in batch 2: {', '.join(sorted(missing_in_batch2))}"
        
        if missing_in_batch1:
            return False, f"Missing episodes in batch 1: {', '.join(sorted(missing_in_batch1))}"
        
        return True, "complete"
    
    async def get_matching_episodes(self, user_id: int):
        """Get all episodes that exist in both batches"""
        user_data = self.user_batches[user_id]
        batch1_eps = set(user_data['batch1'].keys())
        batch2_eps = set(user_data['batch2'].keys())
        return sorted(batch1_eps.intersection(batch2_eps))
    
    def reset_user(self, user_id: int):
        """Reset user's batch processing"""
        if user_id in self.user_batches:
            self.user_batches[user_id] = {
                'batch1': {},
                'batch2': {},
                'state': 'idle',
                'current_batch': None,
                'mode': None
            }

# Initialize batch processor
batch_processor = BatchProcessor()

# ===== FILE PROCESSING FUNCTIONS =====
async def extract_audio_and_subtitles(input_path: str, output_dir: str) -> Dict[str, str]:
    """Extract audio and subtitle tracks from a video file"""
    extracted_files = {}
    
    # Use ffprobe to detect streams
    ffprobe_cmd = shutil.which('ffprobe')
    if not ffprobe_cmd:
        raise Exception("FFprobe not found")
    
    # Detect streams
    cmd = [
        ffprobe_cmd, '-v', 'error',
        '-select_streams', 'a',  # Audio streams
        '-show_entries', 'stream=index,codec_name,codec_type,tags:stream_tags=language',
        '-of', 'csv=p=0', input_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    audio_streams = []
    for line in stdout.decode().strip().split('\n'):
        if line:
            parts = line.split(',')
            if len(parts) >= 2:
                audio_streams.append({
                    'index': parts[0],
                    'codec': parts[1],
                    'type': parts[2] if len(parts) > 2 else '',
                    'language': parts[3] if len(parts) > 3 else 'und'
                })
    
    # Extract each audio stream
    for i, stream in enumerate(audio_streams):
        audio_output = os.path.join(output_dir, f"audio_{i}_{stream['language']}.mka")
        cmd = [
            shutil.which('ffmpeg'), '-i', input_path,
            '-map', f"0:{stream['index']}",
            '-c', 'copy',
            '-loglevel', 'error', '-y', audio_output
        ]
        
        process = await asyncio.create_subprocess_exec(*cmd)
        await process.communicate()
        
        if os.path.exists(audio_output):
            extracted_files[f"audio_{stream['language']}"] = audio_output
    
    # Detect and extract subtitles
    cmd = [
        ffprobe_cmd, '-v', 'error',
        '-select_streams', 's',  # Subtitle streams
        '-show_entries', 'stream=index,codec_name,codec_type,tags:stream_tags=language',
        '-of', 'csv=p=0', input_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    subtitle_streams = []
    for line in stdout.decode().strip().split('\n'):
        if line:
            parts = line.split(',')
            if len(parts) >= 2:
                subtitle_streams.append({
                    'index': parts[0],
                    'codec': parts[1],
                    'type': parts[2] if len(parts) > 2 else '',
                    'language': parts[3] if len(parts) > 3 else 'und'
                })
    
    # Extract each subtitle stream
    for i, stream in enumerate(subtitle_streams):
        subtitle_output = os.path.join(output_dir, f"subtitle_{i}_{stream['language']}.ass")
        if stream['codec'] == 'ass':
            cmd = [
                shutil.which('ffmpeg'), '-i', input_path,
                '-map', f"0:{stream['index']}",
                '-c', 'copy',
                '-loglevel', 'error', '-y', subtitle_output
            ]
        else:
            # Convert to ASS if needed
            cmd = [
                shutil.which('ffmpeg'), '-i', input_path,
                '-map', f"0:{stream['index']}",
                '-c:s', 'ass',
                '-loglevel', 'error', '-y', subtitle_output
            ]
        
        process = await asyncio.create_subprocess_exec(*cmd)
        await process.communicate()
        
        if os.path.exists(subtitle_output):
            extracted_files[f"subtitle_{stream['language']}"] = subtitle_output
    
    return extracted_files

async def merge_audio_and_subtitles(
    video_path: str,
    extracted_files: Dict[str, str],
    output_path: str,
    episode_num: str,
    quality: str,
    user_id: int
) -> str:
    """Merge extracted audio and subtitles into the target video"""
    
    # Get format template from database
    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        format_template = "S{season}E{episode} {title} [{quality}]"
    
    # Replace placeholders in format template
    season_num = extract_season_number(os.path.basename(video_path))
    replacements = {
        "[EP.NUM]": episode_num, "{episode}": episode_num,
        "[SE.NUM]": season_num or "", "{season}": season_num or "",
        "[QUALITY]": quality, "{quality}": quality
    }
    
    for old, new in replacements.items():
        format_template = format_template.replace(old, new)
    
    format_template = re.sub(r'\s+', ' ', format_template).strip()
    
    # Prepare FFmpeg command
    ffmpeg_cmd = [
        shutil.which('ffmpeg'),
        '-i', video_path
    ]
    
    # Add input files for extracted audio and subtitles
    input_index = 1
    stream_mapping = ['0:v:0', '0:a:0']  # Original video and audio
    
    for key, file_path in extracted_files.items():
        if 'audio' in key:
            ffmpeg_cmd.extend(['-i', file_path])
            stream_mapping.append(f"{input_index}:a:0")
            input_index += 1
        elif 'subtitle' in key:
            ffmpeg_cmd.extend(['-i', file_path])
            stream_mapping.append(f"{input_index}:s:0")
            input_index += 1
    
    # Add stream mapping
    ffmpeg_cmd.extend(['-map', *stream_mapping])
    
    # Copy all codecs
    ffmpeg_cmd.extend(['-c', 'copy'])
    
    # Set metadata
    title = await codeflixbots.get_title(user_id)
    if title:
        ffmpeg_cmd.extend(['-metadata', f'title={format_template}'])
    
    # Add output file
    final_output = os.path.join(
        os.path.dirname(output_path),
        f"{format_template}.mkv"  # Always output as MKV for better compatibility
    )
    ffmpeg_cmd.extend(['-loglevel', 'error', '-y', final_output])
    
    # Execute FFmpeg
    process = await asyncio.create_subprocess_exec(*ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"FFmpeg error: {stderr.decode()}")
    
    return final_output

def extract_season_number(filename: str) -> str:
    """Extract season number from filename"""
    patterns = [
        re.compile(r'S(\d+)(?:E|EP)(\d+)'),
        re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)'),
        re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
    ]
    
    for pattern in patterns:
        match = pattern.search(filename)
        if match:
            return match.group(1)
    return None

def extract_quality(filename: str) -> str:
    """Extract quality from filename"""
    patterns = [
        (re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE), lambda m: m.group(1) or m.group(2)),
        (re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE), "2160p"),
        (re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE), "1440p"),
        (re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE), "HDrip"),
        (re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE), "4kX264"),
        (re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE), "4kx265"),
    ]
    
    for pattern, quality_func in patterns:
        match = pattern.search(filename)
        if match:
            return quality_func(match) if callable(quality_func) else quality_func
    return "Unknown"

# ===== HANDLERS =====
@Client.on_message(filters.private & filters.command("batch_start"))
async def start_batch_command(client: Client, message: Message):
    """Start batch processing"""
    user_id = message.from_user.id
    
    # Check if user is already in batch mode
    user_data = batch_processor.user_batches[user_id]
    if user_data['state'] != 'idle':
        await message.reply_text(
            "⚠️ You already have a batch in progress. "
            f"Current state: {user_data['state']}\n\n"
            "Use /batch_cancel to cancel or /batch_status to check status."
        )
        return
    
    # Create mode selection buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Batch 1 → Batch 2", callback_data="batch_mode_1to2"),
            InlineKeyboardButton("Batch 2 → Batch 1", callback_data="batch_mode_2to1")
        ],
        [InlineKeyboardButton("Cancel", callback_data="batch_cancel")]
    ])
    
    await message.reply_text(
        "🎬 **Batch Processing Mode**\n\n"
        "Please select the processing mode:\n\n"
        "1. **Batch 1 → Batch 2**:\n"
        "   • Send Batch 1 files first (e.g., 480p Japanese)\n"
        "   • Then send Batch 2 files (e.g., 720p English)\n"
        "   • Audio/subs from Batch 1 will be added to Batch 2\n\n"
        "2. **Batch 2 → Batch 1**:\n"
        "   • Send Batch 2 files first (e.g., 720p English)\n"
        "   • Then send Batch 1 files (e.g., 480p Japanese)\n"
        "   • Audio/subs from Batch 2 will be added to Batch 1\n\n"
        "**Note**: All files must have episode numbers in their names!",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex("^batch_mode_"))
async def handle_batch_mode(client, callback_query):
    """Handle batch mode selection"""
    user_id = callback_query.from_user.id
    mode = callback_query.data.split("_")[2]  # 1to2 or 2to1
    
    if mode == "1to2":
        mode_text = "Batch 1 → Batch 2"
        batch_processor.user_batches[user_id]['mode'] = 'batch1_to_batch2'
    else:
        mode_text = "Batch 2 → Batch 1"
        batch_processor.user_batches[user_id]['mode'] = 'batch2_to_batch1'
    
    batch_processor.user_batches[user_id]['state'] = 'waiting_batch1'
    batch_processor.user_batches[user_id]['current_batch'] = 1
    
    await callback_query.message.edit_text(
        f"✅ **{mode_text} mode activated!**\n\n"
        f"**Step 1/{'2' if mode == '1to2' else '2'}:**\n"
        f"Please send all files for {'Batch 1' if mode == '1to2' else 'Batch 2'}.\n\n"
        "**Instructions:**\n"
        "1. Send all video files one by one\n"
        "2. Each file must contain episode number\n"
        "3. Use /batch_done when finished sending files\n"
        "4. Use /batch_cancel to cancel anytime\n\n"
        "⚠️ **Important**: Files will be processed in the order you send them!"
    )
    await callback_query.answer(f"Mode set: {mode_text}")

@Client.on_message(filters.private & filters.command("batch_status"))
async def batch_status_command(client: Client, message: Message):
    """Check batch processing status"""
    user_id = message.from_user.id
    user_data = batch_processor.user_batches[user_id]
    
    if user_data['state'] == 'idle':
        await message.reply_text("ℹ️ No active batch processing.")
        return
    
    batch1_count = len(user_data['batch1'])
    batch2_count = len(user_data['batch2'])
    
    text = f"📊 **Batch Processing Status**\n\n"
    text += f"**Mode**: {user_data['mode'].replace('_', ' → ')}\n"
    text += f"**State**: {user_data['state']}\n"
    text += f"**Current Batch**: {user_data['current_batch']}\n\n"
    text += f"**Batch 1 files**: {batch1_count}\n"
    text += f"**Batch 2 files**: {batch2_count}\n\n"
    
    if batch1_count > 0:
        text += f"Batch 1 episodes: {', '.join(sorted(user_data['batch1'].keys()))}\n"
    if batch2_count > 0:
        text += f"Batch 2 episodes: {', '.join(sorted(user_data['batch2'].keys()))}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Continue", callback_data="batch_continue"),
         InlineKeyboardButton("Cancel", callback_data="batch_cancel")]
    ]) if user_data['state'] != 'idle' else None
    
    await message.reply_text(text, reply_markup=keyboard)

@Client.on_message(filters.private & filters.command("batch_done"))
async def batch_done_command(client: Client, message: Message):
    """Mark current batch as complete"""
    user_id = message.from_user.id
    user_data = batch_processor.user_batches[user_id]
    
    if user_data['state'] == 'idle':
        await message.reply_text("⚠️ No active batch processing.")
        return
    
    if user_data['state'] == 'waiting_batch1':
        user_data['state'] = 'waiting_batch2'
        user_data['current_batch'] = 2
        
        mode_text = "Batch 1 → Batch 2" if user_data['mode'] == 'batch1_to_batch2' else "Batch 2 → Batch 1"
        
        await message.reply_text(
            f"✅ **Batch 1 complete!**\n\n"
            f"**Step 2/2:**\n"
            f"Please send all files for {'Batch 2' if user_data['mode'] == 'batch1_to_batch2' else 'Batch 1'}.\n\n"
            f"**Mode**: {mode_text}\n"
            f"**Episodes in Batch 1**: {len(user_data['batch1'])}\n\n"
            "Send files one by one, then use /batch_done again when finished."
        )
    elif user_data['state'] == 'waiting_batch2':
        # Both batches complete, start processing
        is_complete, error_msg = await batch_processor.check_batch_completion(user_id)
        
        if not is_complete:
            await message.reply_text(f"❌ {error_msg}\n\nPlease send the missing files.")
            return
        
        # Start processing
        await process_batches(client, user_id, message)

@Client.on_message(filters.private & filters.command("batch_cancel"))
async def batch_cancel_command(client: Client, message: Message):
    """Cancel batch processing"""
    user_id = message.from_user.id
    batch_count = len(batch_processor.user_batches[user_id]['batch1']) + len(batch_processor.user_batches[user_id]['batch2'])
    
    batch_processor.reset_user(user_id)
    
    await message.reply_text(
        f"❌ Batch processing cancelled.\n"
        f"Cleared {batch_count} files from memory."
    )

async def process_batches(client: Client, user_id: int, message: Message):
    """Process both batches and merge audio/subtitles"""
    user_data = batch_processor.user_batches[user_id]
    processing_msg = await message.reply_text("🔄 Starting batch processing...")
    
    try:
        temp_dir = tempfile.mkdtemp(prefix="batch_")
        results = []
        
        # Get all matching episodes
        episodes = await batch_processor.get_matching_episodes(user_id)
        
        for ep_num in episodes:
            try:
                # Determine source and target based on mode
                if user_data['mode'] == 'batch1_to_batch2':
                    source_file = user_data['batch1'][ep_num]
                    target_file = user_data['batch2'][ep_num]
                    target_quality = extract_quality(target_file['file_name'])
                else:
                    source_file = user_data['batch2'][ep_num]
                    target_file = user_data['batch1'][ep_num]
                    target_quality = extract_quality(target_file['file_name'])
                
                await processing_msg.edit_text(f"📥 Downloading files for episode {ep_num}...")
                
                # Download source file
                source_path = os.path.join(temp_dir, f"source_{ep_num}.mkv")
                await client.download_media(source_file['message'], file_name=source_path)
                
                # Download target file
                target_path = os.path.join(temp_dir, f"target_{ep_num}.mkv")
                await client.download_media(target_file['message'], file_name=target_path)
                
                await processing_msg.edit_text(f"🔧 Extracting audio/subs from source (episode {ep_num})...")
                
                # Extract from source
                extract_dir = os.path.join(temp_dir, f"extract_{ep_num}")
                os.makedirs(extract_dir, exist_ok=True)
                
                extracted = await extract_audio_and_subtitles(source_path, extract_dir)
                
                if not extracted:
                    await message.reply_text(f"⚠️ No audio/subtitles found in episode {ep_num}")
                    continue
                
                await processing_msg.edit_text(f"🔄 Merging into target (episode {ep_num})...")
                
                # Merge into target
                output_path = os.path.join(temp_dir, f"output_{ep_num}.mkv")
                final_output = await merge_audio_and_subtitles(
                    target_path, extracted, output_path,
                    ep_num, target_quality, user_id
                )
                
                # Upload result
                await processing_msg.edit_text(f"📤 Uploading episode {ep_num}...")
                
                # Get thumbnail preference
                c_thumb = None
                if await codeflixbots.is_global_thumb_enabled(user_id):
                    c_thumb = await codeflixbots.get_global_thumb(user_id)
                else:
                    c_thumb = await codeflixbots.get_thumbnail(user_id)
                
                # Prepare caption
                c_caption = await codeflixbots.get_caption(message.chat.id)
                file_size = os.path.getsize(final_output)
                
                from helper.utils import humanbytes
                caption = c_caption.format(
                    filename=os.path.basename(final_output),
                    filesize=humanbytes(file_size),
                    duration="N/A"
                ) if c_caption else f"**{os.path.basename(final_output)}**"
                
                # Send the file
                await client.send_video(
                    chat_id=user_id,
                    video=final_output,
                    caption=caption,
                    thumb=c_thumb,
                    file_name=os.path.basename(final_output)
                )
                
                results.append(f"✅ Episode {ep_num}: Success")
                
            except Exception as e:
                logger.error(f"Error processing episode {ep_num}: {e}")
                results.append(f"❌ Episode {ep_num}: Failed - {str(e)}")
        
        # Send summary
        summary = "📋 **Batch Processing Complete**\n\n"
        summary += f"**Mode**: {user_data['mode'].replace('_', ' → ')}\n"
        summary += f"**Total Episodes**: {len(episodes)}\n"
        summary += f"**Successful**: {len([r for r in results if '✅' in r])}\n"
        summary += f"**Failed**: {len([r for r in results if '❌' in r])}\n\n"
        summary += "\n".join(results)
        
        await message.reply_text(summary)
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        await message.reply_text(f"❌ Batch processing failed: {str(e)}")
    
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        
        # Reset user
        batch_processor.reset_user(user_id)
        
        if processing_msg:
            await processing_msg.delete()

# ===== MODIFIED AUTO RENAME HANDLER =====
# We need to modify the auto rename handler to support batch mode
@Client.on_message(filters.private & (filters.document | filters.video))
async def handle_file_with_batch_support(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if user is in batch mode
    user_data = batch_processor.user_batches[user_id]
    if user_data['state'] in ['waiting_batch1', 'waiting_batch2']:
        # Process as batch file
        media = message.document or message.video
        if not media:
            return
        
        file_info = {
            'file_name': getattr(media, 'file_name', 'video.mkv'),
            'message': message,
            'file_id': media.file_id,
            'file_size': media.file_size
        }
        
        episode_num, result = await batch_processor.add_file_to_batch(user_id, message, file_info)
        
        if episode_num:
            batch_num = user_data['current_batch']
            await message.reply_text(
                f"✅ Added to **Batch {batch_num}**\n"
                f"**Episode**: {episode_num}\n"
                f"**File**: {file_info['file_name']}\n\n"
                f"Send more files or use /batch_done when finished."
            )
        else:
            await message.reply_text(f"❌ {result}")
        
        return
    
    # If not in batch mode, use existing auto rename functionality
    from plugins.file_rename import auto_rename_files
    await auto_rename_files(client, message)

# ===== BATCH HELP COMMAND =====
@Client.on_message(filters.private & filters.command("batch_help"))
async def batch_help_command(client: Client, message: Message):
    """Show batch processing help"""
    help_text = """
🎬 **Batch Processing Help**

**Commands:**
/batch_start - Start batch processing
/batch_status - Check current status
/batch_done - Mark current batch as complete
/batch_cancel - Cancel batch processing
/batch_help - Show this help message

**How it works:**
1. Use `/batch_start` to begin
2. Select processing mode:
   - Batch 1 → Batch 2: Add audio/subs from first batch to second
   - Batch 2 → Batch 1: Add audio/subs from second batch to first
3. Send all files for Batch 1
4. Use `/batch_done` when finished
5. Send all files for Batch 2
6. Use `/batch_done` again to start processing

**Requirements:**
• All files must contain episode numbers
• Both batches must have same episodes
• Supported formats: MKV, MP4
• Max file size: 2GB (Telegram limit)

**Example workflow:**
1. `/batch_start`
2. Select "Batch 1 → Batch 2"
3. Send all 480p Japanese files
4. `/batch_done`
5. Send all 720p English files
6. `/batch_done`
7. Wait for processing

**Result**: 720p files with Japanese audio and subtitles added!
    """
    
    await message.reply_text(help_text)
