import motor
from motor.motor_asyncio import AsyncIOMotorClient
import datetime

class Database:
    def __init__(self, url, database_name):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.army = self.db.army # New collection for army bots

    # User-related methods
    def new_user(self, user_id):
        return dict(id=user_id)

    async def add_user(self, user_id):
        user = self.new_user(user_id)
        await self.users.insert_one(user)

    async def is_user_exist(self, user_id):
        user = await self.users.find_one({'id': int(user_id)})
        return bool(user)

    async def total_users_count(self):
        return await self.users.count_documents({})

    async def get_all_users(self):
        return self.users.find({})

    async def delete_user(self, user_id):
        await self.users.delete_many({'id': int(user_id)})

    # Army Bot Management Methods
    async def add_army_bot(self, token, bot_id, bot_username):
        bot_data = {
            'bot_id': bot_id,
            'token': token,
            'username': bot_username,
            'added_at': datetime.datetime.now()
        }
        await self.army.insert_one(bot_data)

    async def remove_army_bot(self, bot_id):
        await self.army.delete_one({'bot_id': bot_id})

    async def get_all_army_bots(self):
        army_bots = self.army.find({})
        return await army_bots.to_list(length=None)

    async def is_army_bot_exist(self, bot_id):
        bot = await self.army.find_one({'bot_id': int(bot_id)})
        return bool(bot)
