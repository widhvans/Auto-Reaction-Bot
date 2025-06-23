# database.py

import motor
from motor.motor_asyncio import AsyncIOMotorClient

class Database:
    def __init__(self, url, database_name):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.army_accounts = self.db.army_accounts

    # User related methods
    async def add_user(self, user_id):
        await self.users.insert_one({'id': user_id})

    async def is_user_exist(self, user_id):
        return bool(await self.users.find_one({'id': int(user_id)}))

    async def total_users_count(self):
        return await self.users.count_documents({})

    # Army Account related methods
    async def add_army_account(self, user_id: int, first_name: str):
        # अब हम सिर्फ़ user_id और नाम स्टोर करेंगे
        account_data = {'user_id': user_id, 'first_name': first_name}
        await self.army_accounts.insert_one(account_data)

    async def remove_army_account(self, user_id: int):
        await self.army_accounts.delete_one({'user_id': user_id})

    async def get_all_army_accounts(self):
        accounts = self.army_accounts.find({})
        return await accounts.to_list(length=None)

    async def is_army_account_exist(self, user_id: int):
        return bool(await self.army_accounts.find_one({'user_id': user_id}))
