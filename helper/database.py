import motor.motor_asyncio
import datetime
import logging
import time
from config import Config
from .utils import send_log

class Database:
    def __init__(self, uri, database_name):
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self._client.server_info()
            logging.info("Successfully connected to MongoDB")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise e
        self.codeflixbots = self._client[database_name]
        self.col = self.codeflixbots.user

    def new_user(self, id):
        return dict(
            _id=int(id),
            join_date=datetime.date.today().isoformat(),
            file_id=None,
            caption=None,
            metadata=True,
            metadata_code="Telegram : @Animelibraryn4",
            format_template=None,
            thumbnails={},
            temp_quality=None,
            use_global_thumb=False,  # New field for global thumbnail toggle
            global_thumb=None,       # Stores the global thumbnail file_id
            ban_status=dict(
                is_banned=False,
                ban_duration=0,
                banned_on=datetime.date.max.isoformat(),
                ban_reason=''
            ),
            # Preserving all existing metadata fields
            title='Encoded by @Animelibraryn4',
            author='@Animelibraryn4',
            artist='@Animelibraryn4',
            audio='By @Animelibraryn4',
            subtitle='By @Animelibraryn4',
            video='Encoded By @Animelibraryn4',
            media_type=None
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            try:
                await self.col.insert_one(user)
                await send_log(b, u)
            except Exception as e:
                logging.error(f"Error adding user {u.id}: {e}")

    async def is_user_exist(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return bool(user)
        except Exception as e:
            logging.error(f"Error checking if user {id} exists: {e}")
            return False

    async def total_users_count(self):
        try:
            count = await self.col.count_documents({})
            return count
        except Exception as e:
            logging.error(f"Error counting users: {e}")
            return 0

    async def get_all_users(self):
        try:
            all_users = self.col.find({})
            return all_users
        except Exception as e:
            logging.error(f"Error getting all users: {e}")
            return None

    async def delete_user(self, user_id):
        try:
            await self.col.delete_many({"_id": int(user_id)})
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")

    async def set_thumbnail(self, id, file_id):
        try:
            await self.col.update_one({"_id": int(id)}, {"$set": {"file_id": file_id}})
        except Exception as e:
            logging.error(f"Error setting thumbnail for user {id}: {e}")

    async def get_thumbnail(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("file_id", None) if user else None
        except Exception as e:
            logging.error(f"Error getting thumbnail for user {id}: {e}")
            return None

    async def set_caption(self, id, caption):
        try:
            await self.col.update_one({"_id": int(id)}, {"$set": {"caption": caption}})
        except Exception as e:
            logging.error(f"Error setting caption for user {id}: {e}")

    async def get_caption(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("caption", None) if user else None
        except Exception as e:
            logging.error(f"Error getting caption for user {id}: {e}")
            return None

    async def set_format_template(self, id, format_template):
        try:
            await self.col.update_one(
                {"_id": int(id)}, {"$set": {"format_template": format_template}}
            )
        except Exception as e:
            logging.error(f"Error setting format template for user {id}: {e}")

    async def get_format_template(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("format_template", None) if user else None
        except Exception as e:
            logging.error(f"Error getting format template for user {id}: {e}")
            return None

    async def set_media_preference(self, id, media_type):
        try:
            await self.col.update_one(
                {"_id": int(id)}, {"$set": {"media_type": media_type}}
            )
        except Exception as e:
            logging.error(f"Error setting media preference for user {id}: {e}")

    async def get_media_preference(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("media_type", None) if user else None
        except Exception as e:
            logging.error(f"Error getting media preference for user {id}: {e}")
            return None

    async def get_metadata(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('metadata', "Off")

    async def set_metadata(self, user_id, metadata):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'metadata': metadata}})

    async def get_title(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('title', 'Encoded by @Animelibraryn4')

    async def set_title(self, user_id, title):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'title': title}})

    async def get_author(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('author', '@Animelibraryn4')

    async def set_author(self, user_id, author):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'author': author}})

    async def get_artist(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('artist', '@Animelibraryn4')

    async def set_artist(self, user_id, artist):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'artist': artist}})

    async def get_audio(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio', 'By @Animelibraryn4')

    async def set_audio(self, user_id, audio):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio': audio}})

    async def get_subtitle(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('subtitle', "By @Animelibraryn4")

    async def set_subtitle(self, user_id, subtitle):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'subtitle': subtitle}})

    async def get_video(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('video', 'Encoded By @Animelibraryn4')

    async def set_video(self, user_id, video):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'video': video}})

    # Quality Thumbnail Methods
    async def set_quality_thumbnail(self, id, quality, file_id):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {f"thumbnails.{quality}": file_id}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting thumbnail for quality {quality} for user {id}: {e}")

    async def get_quality_thumbnail(self, id, quality):
        try:
            user = await self.col.find_one({"_id": int(id)})
            if user and "thumbnails" in user:
                return user["thumbnails"].get(quality)
            return None
        except Exception as e:
            logging.error(f"Error getting thumbnail for quality {quality} for user {id}: {e}")
            return None

    async def get_all_thumbnails(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            if user and "thumbnails" in user:
                return user["thumbnails"]
            return {}
        except Exception as e:
            logging.error(f"Error getting all thumbnails for user {id}: {e}")
            return {}

    # Temporary quality storage methods
    async def set_temp_quality(self, id, quality):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"temp_quality": quality}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting temp quality for user {id}: {e}")

    async def get_temp_quality(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("temp_quality") if user else None
        except Exception as e:
            logging.error(f"Error getting temp quality for user {id}: {e}")
            return None

    async def clear_temp_quality(self, id):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$unset": {"temp_quality": ""}}
            )
        except Exception as e:
            logging.error(f"Error clearing temp quality for user {id}: {e}")

    # Global Thumbnail Methods
    async def set_global_thumb(self, id, file_id):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"global_thumb": file_id}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting global thumbnail for user {id}: {e}")

    async def get_global_thumb(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("global_thumb") if user else None
        except Exception as e:
            logging.error(f"Error getting global thumbnail for user {id}: {e}")
            return None

    async def toggle_global_thumb(self, id, status: bool):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"use_global_thumb": status}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error toggling global thumb for user {id}: {e}")

    async def is_global_thumb_enabled(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("use_global_thumb", False) if user else False
        except Exception as e:
            logging.error(f"Error checking global thumb status for user {id}: {e}")
            return False

    # Premium Management Methods
    async def add_premium_user(self, user_id, days):
        """Add a user to premium with expiry time"""
        try:
            expiry_time = time.time() + (days * 24 * 60 * 60)  # Convert days to seconds
            await self.col.update_one(
                {"_id": int(user_id)},
                {"$set": {
                    "premium": {
                        "is_premium": True,
                        "expiry_time": expiry_time,
                        "days": days,
                        "added_at": time.time()
                    }
                }},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error adding premium user {user_id}: {e}")
            return False

    async def remove_premium_user(self, user_id):
        """Remove premium status from user"""
        try:
            await self.col.update_one(
                {"_id": int(user_id)},
                {"$unset": {"premium": ""}}
            )
            return True
        except Exception as e:
            logging.error(f"Error removing premium user {user_id}: {e}")
            return False

    async def get_premium_status(self, user_id):
        """Check if user is premium and not expired"""
        try:
            user = await self.col.find_one({"_id": int(user_id)})
            if user and "premium" in user:
                premium_data = user["premium"]
                if premium_data.get("is_premium", False):
                    expiry_time = premium_data.get("expiry_time", 0)
                    # Check if premium has expired
                    if time.time() < expiry_time:
                        return {
                            "is_premium": True,
                            "expiry_time": expiry_time,
                            "days_left": int((expiry_time - time.time()) / (24 * 60 * 60)) + 1,
                            "added_at": premium_data.get("added_at", 0)
                        }
            return {"is_premium": False}
        except Exception as e:
            logging.error(f"Error getting premium status for user {user_id}: {e}")
            return {"is_premium": False}

    async def get_all_premium_users(self):
        """Get all premium users with their expiry info"""
        try:
            premium_users = []
            async for user in self.col.find({"premium.is_premium": True}):
                premium_data = user.get("premium", {})
                expiry_time = premium_data.get("expiry_time", 0)
                days_left = int((expiry_time - time.time()) / (24 * 60 * 60)) + 1 if expiry_time > time.time() else 0
                
                premium_users.append({
                    "user_id": user["_id"],
                    "expiry_time": expiry_time,
                    "days": premium_data.get("days", 0),
                    "days_left": days_left if days_left > 0 else 0,
                    "added_at": premium_data.get("added_at", 0),
                    "is_expired": time.time() >= expiry_time
                })
            return premium_users
        except Exception as e:
            logging.error(f"Error getting all premium users: {e}")
            return []

    async def cleanup_expired_premium(self):
        """Remove premium status from expired users"""
        try:
            current_time = time.time()
            result = await self.col.update_many(
                {"premium.expiry_time": {"$lt": current_time}},
                {"$unset": {"premium": ""}}
            )
            return result.modified_count
        except Exception as e:
            logging.error(f"Error cleaning up expired premium users: {e}")
            return 0

    # Verification Status Methods
    async def get_verify_status(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            if user:
                return user.get("verify_status", 0)
            return 0
        except Exception as e:
            logging.error(f"Error getting verify status for user {id}: {e}")
            return 0

    async def set_verify_status(self, id, verify_status):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$set": {"verify_status": verify_status}},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error setting verify status for user {id}: {e}")
            return False

    async def delete_verify_status(self, id):
        try:
            await self.col.update_one(
                {"_id": int(id)},
                {"$unset": {"verify_status": ""}}
            )
            return True
        except Exception as e:
            logging.error(f"Error deleting verify status for user {id}: {e}")
            return False

# Initialize database connection
codeflixbots = Database(Config.DB_URL, Config.DB_NAME)

