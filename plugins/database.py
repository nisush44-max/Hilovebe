import datetime
import motor.motor_asyncio
from config import DB_NAME, DB_URI


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            retryWrites=True,
        )
        self.db = self._client[database_name]
        self.col = self.db.users
        self.stats = self.db.daily_stats
        self.accept_logs = self.db.accept_logs
        self.broadcasts = self.db.broadcasts
        self.bans = self.db.bans
        self.settings = self.db.settings

    @staticmethod
    def today_key():
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    def new_user(self, id, name):
        return {
            "id": int(id),
            "name": name or "Unknown",
            "session": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "last_seen": datetime.datetime.now(datetime.timezone.utc),
        }

    async def add_user(self, id, name):
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.col.update_one(
            {"id": int(id)},
            {
                "$setOnInsert": self.new_user(id, name),
                "$set": {"name": name or "Unknown", "last_seen": now},
            },
            upsert=True,
        )

    async def touch_user(self, id, name=None):
        data = {"last_seen": datetime.datetime.now(datetime.timezone.utc)}
        if name:
            data["name"] = name
        await self.col.update_one({"id": int(id)}, {"$set": data}, upsert=True)

    async def is_user_exist(self, id):
        return bool(await self.col.find_one({"id": int(id)}, {"_id": 1}))

    async def total_users_count(self):
        return await self.col.count_documents({})

    async def active_sessions_count(self):
        return await self.col.count_documents({"session": {"$ne": None}})

    async def get_all_users(self):
        return self.col.find({})

    async def get_recent_users(self, limit=10):
        return await self.col.find({}).sort("created_at", -1).to_list(length=limit)

    async def delete_user(self, user_id):
        await self.col.delete_many({"id": int(user_id)})

    async def set_session(self, id, session):
        await self.col.update_one(
            {"id": int(id)},
            {"$set": {"session": session, "last_seen": datetime.datetime.now(datetime.timezone.utc)}},
            upsert=True,
        )

    async def get_session(self, id):
        user = await self.col.find_one({"id": int(id)})
        return user.get("session") if user else None

    async def record_accept(self, user_id, status, chat_id=None, chat_title=None, amount=1):
        """Record an approval result for the account that initiated /accept."""
        day = self.today_key()
        field = {
            "success": "success",
            "dead": "dead",
            "error": "error",
        }.get(status, "error")
        await self.stats.update_one(
            {"user_id": int(user_id), "day": day},
            {
                "$inc": {"total": int(amount), field: int(amount)},
                "$set": {"updated_at": datetime.datetime.now(datetime.timezone.utc)},
            },
            upsert=True,
        )
        await self.accept_logs.insert_one(
            {
                "user_id": int(user_id),
                "status": status,
                "amount": int(amount),
                "chat_id": chat_id,
                "chat_title": chat_title,
                "created_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )

    async def get_user_stats(self, user_id, day=None):
        day = day or self.today_key()
        doc = await self.stats.find_one({"user_id": int(user_id), "day": day})
        return doc or {"total": 0, "success": 0, "dead": 0, "error": 0, "day": day}

    async def get_global_stats(self, day=None):
        day = day or self.today_key()
        pipeline = [
            {"$match": {"day": day}},
            {"$group": {
                "_id": None,
                "total": {"$sum": "$total"},
                "success": {"$sum": "$success"},
                "dead": {"$sum": "$dead"},
                "error": {"$sum": "$error"},
            }},
        ]
        rows = await self.stats.aggregate(pipeline).to_list(length=1)
        return rows[0] if rows else {"total": 0, "success": 0, "dead": 0, "error": 0}

    async def get_top_users(self, day=None, limit=10):
        day = day or self.today_key()
        return await self.stats.find({"day": day}).sort("success", -1).limit(limit).to_list(length=limit)

    async def get_recent_accepts(self, limit=15):
        return await self.accept_logs.find({}).sort("created_at", -1).to_list(length=limit)

    async def save_broadcast(self, data):
        await self.broadcasts.insert_one(data)

    async def get_broadcasts(self, limit=10):
        return await self.broadcasts.find({}).sort("started_at", -1).to_list(length=limit)

    async def set_ban(self, user_id, reason="Admin ban"):
        await self.bans.update_one(
            {"user_id": int(user_id)},
            {"$set": {"user_id": int(user_id), "reason": reason, "created_at": datetime.datetime.now(datetime.timezone.utc)}},
            upsert=True,
        )

    async def remove_ban(self, user_id):
        await self.bans.delete_one({"user_id": int(user_id)})

    async def is_banned(self, user_id):
        return bool(await self.bans.find_one({"user_id": int(user_id)}, {"_id": 1}))

    async def get_setting(self, key, default=None):
        doc = await self.settings.find_one({"key": str(key)})
        return doc.get("value", default) if doc else default

    async def set_setting(self, key, value):
        await self.settings.update_one(
            {"key": str(key)},
            {"$set": {"key": str(key), "value": value, "updated_at": datetime.datetime.now(datetime.timezone.utc)}},
            upsert=True,
        )
        return value

    async def db_ping(self):
        return await self._client.admin.command("ping")


# Warning - DB_URI must be supplied through the deployment environment.
db = Database(DB_URI, DB_NAME)
