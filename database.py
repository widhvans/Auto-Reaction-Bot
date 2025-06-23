# database.py

import motor
from motor.motor_asyncio import AsyncIOMotorClient

class Database:
    def __init__(self, url, database_name):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.army_bots = self.db.army_bots

    # User related methods
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

    # Army Bot related methods
    async def add_army_bot(self, token: str, bot_id: int, username: str):
        """Adds a new bot to the army."""
        bot_data = {
            'token': token,
            'bot_id': bot_id,
            'username': username,
        }
        await self.army_bots.insert_one(bot_data)

    async def remove_army_bot(self, bot_id: int):
        """Removes a bot from the army."""
        await self.army_bots.delete_one({'bot_id': bot_id})

    async def get_all_army_bots(self):
        """Gets all army bots from the database."""
        bots = self.army_bots.find({})
        return await bots.to_list(length=None)

    async def is_army_bot_exist(self, token: str = None, bot_id: int = None):
        """Checks if an army bot already exists by token or bot_id."""
        if token:
            query = {'token': token}
        elif bot_id:
            query = {'bot_id': bot_id}
        else:
            return False
        
        bot = await self.army_bots.find_one(query)
        return bool(bot)
