import os
import asyncio
import shutil
from pyrogram import Client, filters
from helper.database import codeflixbots
from config import Config

async def merge_audio_video(video_path, audio_path, output_path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        raise Exception("FFmpeg not found")
    
    command = [
        ffmpeg_cmd,
        '-i', video_path,
        '-i', audio_path,
        '-map', '0',
        '-map', '1:a',
        '-c', 'copy',
        '-metadata:s:a:1', 'language=rus',
        '-y',  # Overwrite without asking
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    
    if process.returncode != 0:
        raise Exception("Merge failed")

@Client.on_message(filters.private & filters.command("audio"))
async def start_merge_session(client, message):
    try:
        # Get number of episodes from command (e.g. "/audio 15")
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Please specify number of episodes\nExample: /audio 15")
            return
        
        total_episodes = int(parts[1])
        await codeflixbots.start_merge_session(message.from_user.id, total_episodes)
        
        await message.reply(
            f"Please send {total_episodes} Russian audio files (E1 to E{total_episodes}) in order"
        )
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

@Client.on_message(filters.private & filters.command("merge_status"))
async def merge_status(client, message):
    session = await codeflixbots.get_merge_session(message.from_user.id)
    if not session:
        await message.reply("No active merge session. Start with /audio <number>")
        return
    
    total = session['total_episodes']
    audio_received = session['audios_received']
    videos_480 = len(session.get('videos_480p', []))
    videos_720 = len(session.get('videos_720p', []))
    videos_1080 = len(session.get('videos_1080p', []))
    
    text = (
        f"Merge Session Status:\n\n"
        f"Episodes: {total}\n"
        f"Audios received: {audio_received}/{total}\n"
        f"480p videos: {videos_480}/{total}\n"
        f"720p videos: {videos_720}/{total}\n"
        f"1080p videos: {videos_1080}/{total}"
    )
    await message.reply(text)

@Client.on_message(filters.private & filters.command("cancel_merge"))
async def cancel_merge(client, message):
    await codeflixbots.clear_merge_session(message.from_user.id)
    await message.reply("Merge session cancelled")

@Client.on_message(filters.private & (filters.audio | filters.voice | filters.document))
async def handle_merge_files(client, message):
    session = await codeflixbots.get_merge_session(message.from_user.id)
    if not session:
        return
    
    if session['state'] == 'awaiting_audio':
        # Handle audio files
        if session['audios_received'] >= session['total_episodes']:
            return await message.reply("Already received all audio files")
        
        await codeflixbots.add_merge_audio(message.from_user.id, message.document.file_id)
        received = session['audios_received'] + 1
        
        if received == session['total_episodes']:
            await codeflixbots.update_merge_state(message.from_user.id, 'awaiting_videos')
            await message.reply(
                f"All {session['total_episodes']} audio files received!\n"
                f"Now please send {session['total_episodes']*3} video files "
                f"({session['total_episodes']} episodes in 480p, 720p, 1080p)"
            )
        else:
            await message.reply(f"Audio {received}/{session['total_episodes']} received")
    
    elif session['state'] == 'awaiting_videos':
        # Handle video files
        # You'll need to detect resolution from filename or ask user to specify
        # This is a simplified version - you'll need to enhance it
        
        # Example: detect resolution from filename
        filename = message.document.file_name.lower()
        if '480' in filename:
            res = '480'
        elif '720' in filename:
            res = '720'
        elif '1080' in filename:
            res = '1080'
        else:
            return await message.reply("Couldn't detect resolution from filename")
        
        await codeflixbots.add_merge_video(message.from_user.id, message.document.file_id, res)
        
        # Check if all videos received and start merging
        session = await codeflixbots.get_merge_session(message.from_user.id)
        total_videos_received = (
            len(session.get('videos_480p', [])) +
            len(session.get('videos_720p', [])) +
            len(session.get('videos_1080p', []))
        
        total_needed = session['total_episodes'] * 3
        
        if total_videos_received >= total_needed:
            await message.reply("Starting merge process...")
            await perform_merging(client, message.from_user.id, session)
            await codeflixbots.clear_merge_session(message.from_user.id)

async def perform_merging(client, user_id, session):
    try:
        msg = await client.send_message(user_id, "Starting merge process...")
        
        # Create temporary directory
        temp_dir = f"merge_temp_{user_id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Download all files
        # Note: In production, you'd want to do this in batches to avoid memory issues
        
        # Download audio files
        audio_paths = []
        for i, audio_id in enumerate(session['audios']):
            path = os.path.join(temp_dir, f"audio_{i}.m4a")
            await client.download_media(audio_id, file_name=path)
            audio_paths.append(path)
        
        # Download videos and merge
        for res in ['480', '720', '1080']:
            videos = session.get(f'videos_{res}p', [])
            for i, video_id in enumerate(videos):
                if i >= len(audio_paths):
                    break
                
                video_path = os.path.join(temp_dir, f"video_{res}_{i}.mp4")
                output_path = os.path.join(temp_dir, f"merged_E{i+1}_{res}p.mp4")
                
                await client.download_media(video_id, file_name=video_path)
                
                try:
                    await merge_audio_video(video_path, audio_paths[i], output_path)
                    await client.send_document(
                        user_id,
                        document=output_path,
                        caption=f"Merged E{i+1} {res}p"
                    )
                except Exception as e:
                    await client.send_message(
                        user_id,
                        f"Failed to merge E{i+1} {res}p: {str(e)}"
                    )
                
                # Clean up
                for f in [video_path, output_path]:
                    if os.path.exists(f):
                        os.remove(f)
        
        await msg.edit("Merge process completed!")
    except Exception as e:
        await client.send_message(user_id, f"Merge failed: {str(e)}")
    finally:
        # Clean up
        for f in audio_paths:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
