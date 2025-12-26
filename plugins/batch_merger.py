"""
Dual-Batch Audio & Subtitle Merger
Handles the actual merging of audio and subtitle tracks
"""
import os
import subprocess
import asyncio
import tempfile
import shutil
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class BatchMerger:
    def __init__(self):
        self.ffmpeg_path = shutil.which('ffmpeg')
        self.ffprobe_path = shutil.which('ffprobe')
        
    async def get_stream_info(self, file_path: str) -> Dict:
        """Get detailed information about audio and subtitle streams"""
        if not self.ffprobe_path:
            raise Exception("FFprobe not found in PATH")
        
        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            file_path
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFprobe error: {stderr.decode()}")
                return {'audio_streams': [], 'subtitle_streams': []}
            
            import json
            data = json.loads(stdout.decode())
            
            audio_streams = []
            subtitle_streams = []
            
            for stream in data.get('streams', []):
                if stream['codec_type'] == 'audio':
                    audio_info = {
                        'index': stream['index'],
                        'codec': stream.get('codec_name', 'unknown'),
                        'language': stream.get('tags', {}).get('language', 'und'),
                        'title': stream.get('tags', {}).get('title', ''),
                        'channels': stream.get('channels', 2)
                    }
                    audio_streams.append(audio_info)
                    
                elif stream['codec_type'] == 'subtitle':
                    sub_info = {
                        'index': stream['index'],
                        'codec': stream.get('codec_name', 'unknown'),
                        'language': stream.get('tags', {}).get('language', 'und'),
                        'title': stream.get('tags', {}).get('title', '')
                    }
                    subtitle_streams.append(sub_info)
            
            return {
                'audio_streams': audio_streams,
                'subtitle_streams': subtitle_streams,
                'duration': float(data.get('format', {}).get('duration', 0))
            }
            
        except Exception as e:
            logger.error(f"Error getting stream info: {e}")
            return {'audio_streams': [], 'subtitle_streams': []}
    
    async def extract_streams(self, source_file: str, target_dir: str, 
                            episode_num: int) -> Tuple[List[str], List[str]]:
        """
        Extract audio and subtitle streams from source file
        Returns: (audio_files, subtitle_files)
        """
        if not self.ffmpeg_path:
            raise Exception("FFmpeg not found in PATH")
        
        stream_info = await self.get_stream_info(source_file)
        
        audio_files = []
        subtitle_files = []
        
        # Create temp directory for extracted streams
        temp_dir = os.path.join(target_dir, f"extracted_ep{episode_num}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Extract audio streams
        for i, audio in enumerate(stream_info['audio_streams']):
            audio_file = os.path.join(temp_dir, f"audio_{i}_{audio['language']}.mka")
            cmd = [
                self.ffmpeg_path,
                '-i', source_file,
                '-map', f"0:a:{i}",
                '-c', 'copy',
                '-y',
                audio_file
            ]
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                
                if process.returncode == 0 and os.path.exists(audio_file):
                    audio_files.append(audio_file)
                    logger.info(f"Extracted audio: {audio_file}")
            except Exception as e:
                logger.error(f"Error extracting audio stream {i}: {e}")
        
        # Extract subtitle streams
        for i, sub in enumerate(stream_info['subtitle_streams']):
            # Determine appropriate extension
            codec = sub['codec']
            if codec in ['ass', 'ssa']:
                ext = '.ass'
            elif codec == 'subrip':
                ext = '.srt'
            elif codec == 'webvtt':
                ext = '.vtt'
            else:
                ext = '.sub'
            
            sub_file = os.path.join(temp_dir, f"sub_{i}_{sub['language']}{ext}")
            cmd = [
                self.ffmpeg_path,
                '-i', source_file,
                '-map', f"0:s:{i}",
                '-c', 'copy',
                '-y',
                sub_file
            ]
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                
                if process.returncode == 0 and os.path.exists(sub_file):
                    subtitle_files.append(sub_file)
                    logger.info(f"Extracted subtitle: {sub_file}")
            except Exception as e:
                logger.error(f"Error extracting subtitle stream {i}: {e}")
        
        return audio_files, subtitle_files
    
    async def merge_to_video(self, video_file: str, audio_files: List[str], 
                           subtitle_files: List[str], output_file: str) -> bool:
        """
        Merge extracted audio and subtitles into video file
        Uses stream copying to avoid re-encoding when possible
        """
        if not self.ffmpeg_path:
            raise Exception("FFmpeg not found in PATH")
        
        # Build complex filter command
        inputs = [video_file] + audio_files + subtitle_files
        input_args = []
        map_args = []
        
        # Add video input and map
        input_args.extend(['-i', video_file])
        map_args.extend(['-map', '0:v'])  # Map video from first input
        
        # Add original audio streams from video
        video_info = await self.get_stream_info(video_file)
        for i in range(len(video_info['audio_streams'])):
            map_args.extend(['-map', f'0:a:{i}'])
        
        # Add extracted audio streams
        for i, audio_file in enumerate(audio_files):
            input_idx = i + 1  # +1 because video is input 0
            input_args.extend(['-i', audio_file])
            map_args.extend(['-map', f'{input_idx}:a'])
        
        # Add extracted subtitle streams
        subtitle_start_idx = 1 + len(audio_files)
        for i, sub_file in enumerate(subtitle_files):
            input_idx = subtitle_start_idx + i
            input_args.extend(['-i', sub_file])
            map_args.extend(['-map', f'{input_idx}:s'])
        
        # Build final command
        cmd = [self.ffmpeg_path] + input_args + map_args + [
            '-c:v', 'copy',  # Copy video stream
            '-c:a', 'copy',  # Copy all audio streams
            '-c:s', 'copy',  # Copy all subtitle streams
            '-max_interleave_delta', '0',
            '-y',
            output_file
        ]
        
        try:
            logger.info(f"Merging with command: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor progress
            stderr_lines = []
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode().strip()
                stderr_lines.append(line_str)
                # Log progress updates
                if 'time=' in line_str:
                    logger.debug(f"Merge progress: {line_str}")
            
            await process.wait()
            
            if process.returncode == 0:
                logger.info(f"Successfully merged to: {output_file}")
                return True
            else:
                logger.error(f"Merge failed. Error: {' '.join(stderr_lines[-5:])}")
                return False
                
        except Exception as e:
            logger.error(f"Error during merge: {e}")
            return False
    
    async def create_dual_audio_version(self, merge_data: Dict, 
                                      output_dir: str) -> Optional[str]:
        """
        Create dual-audio version from two batches
        Returns path to merged file if successful
        """
        try:
            episode_num = merge_data['episode']
            first_batch = merge_data['first_batch']
            second_batch = merge_data['second_batch']
            
            # Create output filename
            quality = second_batch['quality']  # Use second batch's quality
            output_filename = f"Episode_{episode_num:02d}_{quality}_dual.mkv"
            output_path = os.path.join(output_dir, output_filename)
            
            # Create temp directory for extracted streams
            temp_dir = os.path.join(output_dir, f"temp_ep{episode_num}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Extract streams from first batch (audio/subs source)
            logger.info(f"Extracting streams from first batch: {first_batch['path']}")
            audio_files, subtitle_files = await self.extract_streams(
                first_batch['path'], temp_dir, episode_num
            )
            
            if not audio_files and not subtitle_files:
                logger.warning(f"No audio/subtitle streams found in first batch")
                # Still proceed with just the second batch file
                shutil.copy2(second_batch['path'], output_path)
                return output_path
            
            # Merge into second batch video
            logger.info(f"Merging streams into: {second_batch['path']}")
            success = await self.merge_to_video(
                second_batch['path'],
                audio_files,
                subtitle_files,
                output_path
            )
            
            # Cleanup temp files
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            
            if success and os.path.exists(output_path):
                return output_path
            else:
                # Fallback to original second batch file
                logger.warning("Merge failed, using original second batch file")
                shutil.copy2(second_batch['path'], output_path)
                return output_path
                
        except Exception as e:
            logger.error(f"Error creating dual audio version: {e}")
            return None

# Global merger instance
batch_merger = BatchMerger()
