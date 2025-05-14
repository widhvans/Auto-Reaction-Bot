import motor
from motor.motor_asyncio import AsyncIOMotorClient
import datetime

class Database:
    def __init__(self, url, database_name):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.clones = self.db.clones

    def new_user(self, user_id):
        return dict(id=user_id)

    async def add_user(self, user_id):
        user = self.new_user(user_id)
        await self.users.insert_one(user)

    async def is_user_exist(self, user_id):
        user = await self.users.find_one({'id': int(user_id)})
        return True if user else False

    async def total_users_count(self):
        count = await self.users.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.users.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.users.delete_many({'id': int(user_id)})

    async def add_clone(self, user_id, token, clone_username):
        clone_data = {
            'user_id': user_id,
            'token': token,
            'username': clone_username,
            'parent_bot': "QuickReactRobot",
            'active': True,
            'created_at': datetime.datetime.now(),
            'connected_chats': [],
            'connected_users': []
        }
        await self.clones.insert_one(clone_data)
        return clone_data

    async def get_user_clones(self, user_id):
        clones = self.clones.find({'user_id': user_id})
        return await clones.to_list(length=None)

    async def toggle_clone(self, clone_id, active):
        await self.clones.update_one({'_id': clone_id}, {'$set': {'active': active}})

    async def get_clone(self, token):
        return await self.clones.find_one({'token': token})

    async def get_all_clones(self):
        clones = self.clones.find({})
        return await clones.to_list(length=None)

    async def update_connected_chats(self, clone_id, chat_id):
        await self.clones.update_one(
            {'_id': clone_id},
            {'$addToSet': {'connected_chats': chat_id}}
        )

    async def remove_connected_chat(self, clone_id, chat_id):
        await self.clones.update_one(
            {'_id': clone_id},
            {'$pull': {'connected_chats': chat_id}}
        )

    async def total_clones_count(self):
        count = await self.clones.count_documents({})
        return count

    async def update_connected_users(self, clone_id, user_id):
        await self.clones.update_one(
            {'_id': clone_id},
            {'$addToSet': {'connected_users': user_id}}
        )

    async def get_all_connected_users(self):
        all_users = await self.users.find({}).to_list(length=None)
        all_clones = await self.clones.find({}).to_list(length=None)
        
        user_ids = set(user['id'] for user in all_users)
        for clone in all_clones:
            user_ids.update(clone.get('connected_users', []))
        return list(user_ids)
