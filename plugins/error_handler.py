import asyncio
import logging
from pyrogram.errors import FloodWait, TimeoutError

logger = logging.getLogger(__name__)

async def retry_operation(operation, max_retries=3, initial_delay=2, *args, **kwargs):
    """Retry an operation with exponential backoff"""
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await operation(*args, **kwargs)
        except FloodWait as e:
            wait_time = e.value
            logger.warning(f"FloodWait: Waiting {wait_time} seconds (Attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except TimeoutError:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout: Retrying in {delay} seconds (Attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Error: {str(e)[:100]}... Retrying in {delay} seconds")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                break
    
    if last_exception:
        raise last_exception
