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

logger = logging.getLogger(__name__)

# ===== User State Management =====
user_states = {}  # Fixed: initialization issue resolved below

# ===== File Storage =====
user_source_files = {}  
user_temp_files = {}    

# Patterns for extracting episode info
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE)
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)', re.IGNORECASE)
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE)
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)

def extract_episode_info(filename: str) -> Tuple[Optional[int], Optional[int]]:
    patterns = [pattern1, pattern2, pattern4]
    for pattern in patterns:
        match = pattern.search(filename)
        if match:
            if len(match.groups()) >= 2:
                return int(match.group(1)), int(match.group(2))
    match = pattern3.search(filename)
    if match:
        return 1, int(match.group(1))
    return None, None

def get_episode_key(season: int, episode: int) -> str:
    return f"S{season:02d}E{episode:02d}"

async def extract_audio_tracks(input_path: str, output_dir: str) -> List[str]:
    extracted_audio = []
    ffprobe_cmd = shutil.which('ffprobe')
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffprobe_cmd or not ffmpeg_cmd: return []
    
    cmd = [ffprobe_cmd, '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index,codec_name,channels,language', '-of', 'csv=p=0', input_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    
    for i, line in enumerate(stdout.decode().strip().split('\n')):
        if not line: continue
        output_file = os.path.join(output_dir, f"audio_{i+1}.mka")
        cmd = [ffmpeg_cmd, '-i', input_path, '-map', f'0:a:{i}', '-c', 'copy', '-loglevel', 'error', '-y', output_file]
        p = await asyncio.create_subprocess_exec(*cmd)
        await p.communicate()
        if os.path.exists(output_file): extracted_audio.append(output_file)
    return extracted_audio

async def extract_subtitle_tracks(input_path: str, output_dir: str) -> List[str]:
    extracted_subs = []
    ffmpeg_cmd = shutil.which('ffmpeg')
    ffprobe_cmd = shutil.which('ffprobe')
    if not ffmpeg_cmd or not ffprobe_cmd: return []
    
    cmd = [ffprobe_cmd, '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index,codec_name', '-of', 'csv=p=0', input_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    
    for i, line in enumerate(stdout.decode().strip().split('\n')):
        if not line: continue
        output_file = os.path.join(output_dir, f"sub_{i+1}.srt")
        cmd = [ffmpeg_cmd, '-i', input_path, '-map', f'0:s:{i}', '-c', 'copy', '-loglevel', 'error', '-y', output_file]
        p = await asyncio.create_subprocess_exec(*cmd)
        await p.communicate()
        if os.path.exists(output_file): extracted_subs.append(output_file)
    return extracted_subs

async def merge_audio_subtitles(source_tracks: Dict, target_path: str, output_path: str) -> bool:
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd: return False
    cmd = [ffmpeg_cmd, '-i', target_path]
    audio_tracks = source_tracks.get('audio', [])
    sub_tracks = source_tracks.get('subtitle', [])
    for f in audio_tracks + sub_tracks: cmd.extend(['-i', f])
    cmd.extend(['-map', '0:v', '-map', '0:a'])
    for i in range(len(audio_tracks)): cmd.extend(['-map', f'{i+1}:a'])
    cmd.extend(['-map', '0:s'])
    for i in range(len(sub_tracks)): cmd.extend(['-map', f'{i+1+len(audio_tracks)}:s'])
    cmd.extend(['-c', 'copy', '-loglevel', 'error', '-y', output_path])
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    return proc.returncode == 0

async def cleanup_user_files(user_id: int):
    if user_id in user_temp_files:
        for f in user_temp_files[user_id]:
            try: 
                if os.path.exists(f): os.remove(f)
            except: pass
        user_temp_files.pop(user_id, None)
    user_states.get(user_id, {}).get('source_files', {}).clear()

def register_temp_file(user_id: int, file_path: str):
    if user_id not in user_temp_files: user_temp_files[user_id] = []
    user_temp_files[user_id].append(file_path)

@Client.on_message(filters.private & filters.command("merging"))
async def merging_command(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_user_verified(user_id):
        return await message.reply_text("⚠️ Please verify first using /verify")
    
    # Initialize state properly to avoid KeyErrors
    user_states[user_id] = {
        "state": "waiting_for_source",
        "source_files": {},
        "target_files": []
    }
    await cleanup_user_files(user_id)
    await message.reply_text("🔧 **Merger Started**\n\nStep 1: Send **Source** files (with audio/subs).\nType /done_sources when finished.")

@Client.on_message(filters.private & filters.command("merge_status"))
async def status_command(client, message):
    state = user_states.get(message.from_user.id)
    if not state: return await message.reply("No active session.")
    await message.reply(f"State: {state['state']}\nSources: {len(state['source_files'])}\nTargets: {len(state['target_files'])}")

@Client.on_message(filters.private & filters.command("done_sources"))
async def done_sources(client, message):
    state = user_states.get(message.from_user.id)
    if not state or not state["source_files"]:
        return await message.reply("❌ No source files received!")
    state["state"] = "waiting_for_target"
    await message.reply(f"✅ Received {len(state['source_files'])} sources. Now send **Target** files.\nType /done_targets when finished.")

@Client.on_message(filters.private & filters.command("done_targets"))
async def done_targets(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state or not state["target_files"]:
        return await message.reply("❌ No target files received!")
    
    state["state"] = "processing"
    status = await message.reply("🔄 Processing... please wait.")
    
    for i, target in enumerate(state["target_files"]):
        ep_key = get_episode_key(target['season'], target['episode'])
        if ep_key not in state["source_files"]: continue
        
        target_path = await client.download_media(target['message'])
        register_temp_file(user_id, target_path)
        output_path = f"merged_{target['filename']}"
        
        success = await merge_audio_subtitles(state["source_files"][ep_key], target_path, output_path)
        if success:
            await client.send_document(user_id, output_path, caption=f"✅ Merged: {ep_key}")
            register_temp_file(user_id, output_path)
            
    await status.edit("✅ All tasks complete!")
    await cleanup_user_files(user_id)
    user_states.pop(user_id, None)

@Client.on_message(filters.private & (filters.video | filters.document))
async def handle_files(client, message):
    user_id = message.from_user.id
    if user_id not in user_states: return
    
    state = user_states[user_id]
    filename = getattr(message.video or message.document, 'file_name', 'video.mp4')
    s, e = extract_episode_info(filename)
    if s is None: return await message.reply("Could not find Season/Episode in name.")
    ep_key = get_episode_key(s, e)

    if state["state"] == "waiting_for_source":
        msg = await message.reply("📥 Downloading source...")
        path = await client.download_media(message)
        register_temp_file(user_id, path)
        
        temp_dir = f"temp_{user_id}_{ep_key}"
        os.makedirs(temp_dir, exist_ok=True)
        
        audios = await extract_audio_tracks(path, temp_dir)
        subs = await extract_subtitle_tracks(path, temp_dir)
        
        for f in audios + subs: register_temp_file(user_id, f)
        state["source_files"][ep_key] = {"audio": audios, "subtitle": subs}
        await msg.edit(f"✅ Source {ep_key} ready!")

    elif state["state"] == "waiting_for_target":
        state["target_files"].append({"message": message, "filename": filename, "season": s, "episode": e})
        await message.reply(f"✅ Target {ep_key} queued!")

