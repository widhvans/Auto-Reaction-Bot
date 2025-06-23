# database.py

import motor
from motor.motor_asyncio import AsyncIOMotorClient
import datetime

class Database:
    def __init__(self, url, database_name):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client[database_name]
        self.users = self.db.users
        # Changed 'clones' collection to 'army_bots' for clarity
        self.army_bots = self.db.army_bots

    # --- User Management ---
    def new_user(self, user_id):
        return dict(id=user_id)

    async def add_user(self, user_id):
        user = self.new_user(user_id)
        await self.users.insert_one(user)

    async def is_user_exist(self, user_id):
        user = await self.users.find_one({'id': int(user_id)})
        return True if user else False

    async def total_users_count(self):
        return await self.users.count_documents({})

    async def get_all_users(self):
        return self.users.find({})

    async def delete_user(self, user_id):
        await self.users.delete_many({'id': int(user_id)})

    # --- Army Bot Management (Replaces Clone Logic) ---
    async def add_army_bot(self, token, bot_id, username):
        bot_data = {
            'token': token,
            'bot_id': bot_id,
            'username': username,
            'added_by': 'owner',
            'active': True,
            'created_at': datetime.datetime.now()
        }
        await self.army_bots.insert_one(bot_data)
        return bot_data

    async def get_army_bot_by_token(self, token):
        return await self.army_bots.find_one({'token': token})

    async def get_army_bot_by_id(self, bot_id):
        return await self.army_bots.find_one({'bot_id': bot_id})

    async def remove_army_bot(self, bot_id):
        await self.army_bots.delete_one({'bot_id': int(bot_id)})

    async def get_all_army_bots(self):
        bots = self.army_bots.find({'active': True})
        return await bots.to_list(length=None)

    async def total_army_bots_count(self):
        return await self.army_bots.count_documents({})
