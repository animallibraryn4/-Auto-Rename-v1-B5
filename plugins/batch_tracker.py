"""
Dual-Batch Audio & Subtitle Merge Tracker
Tracks files across two batches for intelligent merging
"""
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from helper.database import codeflixbots
import logging

logger = logging.getLogger(__name__)

class BatchTracker:
    def __init__(self):
        self.user_batches: Dict[int, Dict] = {}  # user_id -> batch data
        self.file_cache: Dict[int, Dict] = {}    # user_id -> {ep_num: {batch1_file, batch2_file}}
        self.lock = asyncio.Lock()
        
    async def extract_episode_number(self, filename: str) -> Optional[int]:
        """Extract episode number from filename using existing patterns"""
        patterns = [
            r'S\d+(?:E|EP)(\d+)',
            r'S\d+\s*(?:E|EP|-\s*EP)(\d+)',
            r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)',
            r'(?:\s*-\s*(\d+)\s*)',
            r'S\d+[^\d]*(\d+)',
            r'(\d{2,3})'  # Match 2-3 digit episode numbers
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                for group in match.groups():
                    if group and group.isdigit():
                        return int(group)
        return None
    
    async def extract_quality(self, filename: str) -> str:
        """Extract video quality from filename"""
        quality_patterns = [
            (r'(\d{3,4}p)', 1),  # 480p, 720p, 1080p, etc.
            (r'\b(4k|2160p|uhd)\b', '2160p'),
            (r'\b(2k|1440p|qhd)\b', '1440p'),
            (r'\b(hdrip|web-dl)\b', 'HDrip'),
            (r'\b(4kx264)\b', '4kX264'),
            (r'\b(4kx265)\b', '4kx265')
        ]
        
        filename_lower = filename.lower()
        for pattern, quality in quality_patterns:
            if isinstance(quality, int):  # Pattern group
                match = re.search(pattern, filename_lower, re.IGNORECASE)
                if match:
                    return match.group(quality).lower()
            else:  # Direct quality string
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return quality.lower()
        return "unknown"
    
    async def track_file(self, user_id: int, file_path: str, episode_num: int, 
                        quality: str, batch_type: str = None) -> Optional[Dict]:
        """
        Track a file and check if it can be merged with counterpart
        Returns merge data if ready, None if waiting for counterpart
        """
        async with self.lock:
            # Initialize user tracking
            if user_id not in self.user_batches:
                self.user_batches[user_id] = {
                    'batch1_files': {},
                    'batch2_files': {},
                    'current_batch': 1,
                    'last_activity': datetime.now()
                }
            
            user_data = self.user_batches[user_id]
            
            # Auto-detect batch based on quality if not specified
            if not batch_type:
                # First file of a quality becomes batch 1
                if not user_data['batch1_files']:
                    batch_type = 'batch1'
                elif not user_data['batch2_files']:
                    # Check if this is a different quality than batch1
                    batch1_quality = next(iter(user_data['batch1_files'].values()))['quality']
                    if quality != batch1_quality:
                        batch_type = 'batch2'
                    else:
                        batch_type = 'batch1'
                else:
                    # Determine batch based on which one has this episode
                    if episode_num in user_data['batch1_files']:
                        batch_type = 'batch1'
                    else:
                        batch_type = 'batch2'
            
            # Store file info
            file_info = {
                'path': file_path,
                'quality': quality,
                'episode': episode_num,
                'timestamp': datetime.now()
            }
            
            target_dict = user_data['batch1_files'] if batch_type == 'batch1' else user_data['batch2_files']
            target_dict[episode_num] = file_info
            
            # Check for counterpart
            other_dict = user_data['batch2_files'] if batch_type == 'batch1' else user_data['batch1_files']
            
            if episode_num in other_dict:
                # We have both files for this episode!
                batch1_file = user_data['batch1_files'][episode_num]
                batch2_file = user_data['batch2_files'][episode_num]
                
                # Determine which is first batch (earlier timestamp)
                if batch1_file['timestamp'] < batch2_file['timestamp']:
                    first_batch = batch1_file
                    second_batch = batch2_file
                else:
                    first_batch = batch2_file
                    second_batch = batch1_file
                
                return {
                    'episode': episode_num,
                    'first_batch': first_batch,  # Source for audio/subtitles
                    'second_batch': second_batch,  # Source for video (target quality)
                    'ready': True
                }
            
            return None
    
    async def cleanup_user(self, user_id: int, max_age_hours: int = 24):
        """Clean up old batch data for user"""
        async with self.lock:
            if user_id in self.user_batches:
                last_activity = self.user_batches[user_id]['last_activity']
                if datetime.now() - last_activity > timedelta(hours=max_age_hours):
                    del self.user_batches[user_id]
                    logger.info(f"Cleaned up batch data for user {user_id}")
    
    async def get_user_batch_status(self, user_id: int) -> Dict:
        """Get current batch status for user"""
        async with self.lock:
            if user_id not in self.user_batches:
                return {'status': 'no_batches', 'batch1_count': 0, 'batch2_count': 0}
            
            user_data = self.user_batches[user_id]
            return {
                'status': 'active',
                'batch1_count': len(user_data['batch1_files']),
                'batch2_count': len(user_data['batch2_files']),
                'matched_episodes': set(user_data['batch1_files'].keys()) & set(user_data['batch2_files'].keys()),
                'current_batch': user_data['current_batch']
            }

# Global tracker instance
batch_tracker = BatchTracker()
