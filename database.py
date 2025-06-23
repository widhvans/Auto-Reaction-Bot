import motor.motor_asyncio

class Database:
    """
    Handles all interactions with the MongoDB database.
    This version is simplified and tailored for the reaction bot's needs.
    """
    def __init__(self, url, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(url)
        self.db = self._client[database_name]
        # Collection to store general users of the bot
        self.users = self.db.users
        # Collection to store the owner's army of reaction bots
        self.army = self.db.army_bots

    # --- User Management ---

    def new_user(self, user_id):
        """Creates a new user document."""
        return dict(id=user_id)

    async def add_user(self, user_id):
        """Adds a new user to the database."""
        user = self.new_user(user_id)
        await self.users.insert_one(user)

    async def is_user_exist(self, user_id):
        """Checks if a user already exists in the database."""
        user = await self.users.find_one({'id': int(user_id)})
        return bool(user)

    async def total_users_count(self):
        """Returns the total number of users."""
        return await self.users.count_documents({})

    async def get_all_users(self):
        """Returns a cursor for all user documents."""
        return self.users.find({})

    async def delete_user(self, user_id):
        """Deletes a user from the database."""
        await self.users.delete_many({'id': int(user_id)})

    # --- Bot Army Management (for Bot Owner) ---

    async def add_army_bot(self, owner_id, bot_id, bot_token, bot_username):
        """Adds a new bot to the owner's army."""
        army_bot_data = {
            'owner_id': owner_id,
            'bot_id': bot_id,
            'token': bot_token,
            'bot_username': bot_username
        }
        await self.army.update_one(
            {'owner_id': owner_id, 'bot_id': bot_id},
            {'$set': army_bot_data},
            upsert=True
        )

    async def remove_army_bot(self, owner_id, bot_id):
        """Removes a bot from the owner's army."""
        await self.army.delete_one({'owner_id': owner_id, 'bot_id': bot_id})

    async def get_army_bots(self, owner_id):
        """Retrieves all bots in the owner's army."""
        cursor = self.army.find({'owner_id': owner_id})
        return await cursor.to_list(length=None) # Return as a list

    async def get_army_bots_count(self, owner_id):
        """Returns the total number of bots in the owner's army."""
        return await self.army.count_documents({'owner_id': owner_id})

    async def is_army_bot_exist(self, owner_id, bot_id):
        """Checks if a specific bot is already in the army."""
        bot = await self.army.find_one({'owner_id': owner_id, 'bot_id': bot_id})
        return bool(bot)
