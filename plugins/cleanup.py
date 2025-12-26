import os
import shutil
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def cleanup_old_temp_files():
    """Clean up temp files older than 24 hours"""
    while True:
        try:
            if os.path.exists("temp"):
                now = datetime.now()
                for root, dirs, files in os.walk("temp"):
                    for file in files:
                        filepath = os.path.join(root, file)
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if now - mtime > timedelta(hours=24):
                                os.remove(filepath)
                                logger.info(f"Cleaned up old temp file: {filepath}")
                        except:
                            pass
                    
                    # Remove empty directories
                    for dir in dirs:
                        dirpath = os.path.join(root, dir)
                        try:
                            if not os.listdir(dirpath):
                                os.rmdir(dirpath)
                        except:
                            pass
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
        
        # Run every hour
        await asyncio.sleep(3600)

# Start cleanup task when bot starts
async def start_cleanup_task():
    asyncio.create_task(cleanup_old_temp_files())

