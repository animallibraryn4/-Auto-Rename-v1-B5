import motor.motor_asyncio
import datetime
import logging
from config import Config
from .utils import send_log


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.user
        logging.info("MongoDB connected (Motor async)")

    # ---------------- BASIC USER ---------------- #

    def new_user(self, user_id: int):
        return {
            "_id": int(user_id),
            "join_date": datetime.date.today().isoformat(),
            "file_id": None,
            "caption": None,
            "format_template": None,
            "media_type": None,

            "metadata": True,
            "metadata_code": "Telegram : @Animelibraryn4",

            "title": "Encoded by @Animelibraryn4",
            "author": "@Animelibraryn4",
            "artist": "@Animelibraryn4",
            "audio": "By @Animelibraryn4",
            "subtitle": "By @Animelibraryn4",
            "video": "Encoded By @Animelibraryn4",

            "thumbnails": {},
            "temp_quality": None,

            "use_global_thumb": False,
            "global_thumb": None,

            "ban_status": {
                "is_banned": False,
                "ban_reason": "",
                "banned_on": datetime.date.max.isoformat()
            }
        }

    async def add_user(self, bot, message):
        """SAFE add user (no duplicate, no crash)"""
        u = message.from_user

        user_data = self.new_user(u.id)

        await self.col.update_one(
            {"_id": int(u.id)},
            {"$setOnInsert": user_data},
            upsert=True
        )

        await send_log(bot, u)

    async def is_user_exist(self, user_id):
        return bool(await self.col.find_one({"_id": int(user_id)}))

    async def total_users_count(self):
        return await self.col.count_documents({})

    # ---------------- THUMBNAIL ---------------- #

    async def set_thumbnail(self, user_id, file_id):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"file_id": file_id}},
            upsert=True
        )

    async def get_thumbnail(self, user_id):
        user = await self.col.find_one({"_id": int(user_id)})
        return user.get("file_id") if user else None

    # ---------------- CAPTION ---------------- #

    async def set_caption(self, user_id, caption):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"caption": caption}},
            upsert=True
        )

    async def get_caption(self, user_id):
        user = await self.col.find_one({"_id": int(user_id)})
        return user.get("caption") if user else None

    # ---------------- FORMAT ---------------- #

    async def set_format_template(self, user_id, template):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"format_template": template}},
            upsert=True
        )

    async def get_format_template(self, user_id):
        user = await self.col.find_one({"_id": int(user_id)})
        return user.get("format_template") if user else None

    # ---------------- MEDIA PREF ---------------- #

    async def set_media_preference(self, user_id, media_type):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"media_type": media_type}},
            upsert=True
        )

    async def get_media_preference(self, user_id):
        user = await self.col.find_one({"_id": int(user_id)})
        return user.get("media_type") if user else None

    # ---------------- BAN SYSTEM ---------------- #

    async def ban_user(self, user_id, reason=""):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {
                "ban_status.is_banned": True,
                "ban_status.ban_reason": reason,
                "ban_status.banned_on": datetime.date.today().isoformat()
            }},
            upsert=True
        )
        return True

    async def unban_user(self, user_id):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {
                "ban_status.is_banned": False,
                "ban_status.ban_reason": "",
                "ban_status.banned_on": datetime.date.max.isoformat()
            }},
            upsert=True
        )
        return True

    async def is_banned(self, user_id):
        user = await self.col.find_one({"_id": int(user_id)})
        return user.get("ban_status", {}).get("is_banned", False) if user else False

    async def get_ban_info(self, user_id):
        user = await self.col.find_one({"_id": int(user_id)})
        if user and user.get("ban_status", {}).get("is_banned"):
            return user["ban_status"]
        return None


# GLOBAL DB OBJECT
codeflixbots = Database(Config.DB_URL, Config.DB_NAME)
