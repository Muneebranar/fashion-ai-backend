from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class Database:
    client: AsyncIOMotorClient | None = None

    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        try:
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
            )

            # Test connection
            await cls.client.admin.command("ping")
            logger.info("✅ Successfully connected to MongoDB")

            # Create indexes
            await cls.create_indexes()

        except Exception as e:
            cls.client = None
            logger.critical(f"❌ Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            logger.info("MongoDB connection closed")

    @classmethod
    def get_database(cls):
        """Get database instance (FAIL FAST)"""
        if cls.client is None:
            raise RuntimeError(
                "Database not connected. connect_db() was not called or failed."
            )
        return cls.client[settings.DATABASE_NAME]

    @classmethod
    async def create_indexes(cls):
        """Create database indexes for optimization"""
        db = cls.get_database()

        # Users
        await db.users.create_index([("email", ASCENDING)], unique=True)
        await db.users.create_index([("created_at", DESCENDING)])

        # Clothing
        await db.clothing.create_index([("user_id", ASCENDING)])
        await db.clothing.create_index([("category", ASCENDING)])
        await db.clothing.create_index([("created_at", DESCENDING)])
        await db.clothing.create_index(
            [("user_id", ASCENDING), ("category", ASCENDING)]
        )

        # Outfits
        await db.outfits.create_index([("user_id", ASCENDING)])
        await db.outfits.create_index([("created_at", DESCENDING)])
        await db.outfits.create_index([("is_favorite", ASCENDING)])

        # Favorites
        await db.favorites.create_index(
            [("user_id", ASCENDING), ("item_id", ASCENDING)], unique=True
        )

        # Notifications
        await db.notifications.create_index([("user_id", ASCENDING)])
        await db.notifications.create_index([("created_at", DESCENDING)])
        await db.notifications.create_index([("is_read", ASCENDING)])

        logger.info("✅ Database indexes created successfully")
# app/database.py - Add index creation

async def create_indexes():
    """Create database indexes for optimal performance"""
    db = Database.get_database()
    
    # Outfit History Indexes
    await db.outfit_history.create_index([
        ("user_id", 1),
        ("date", -1)
    ])
    
    await db.outfit_history.create_index([
        ("user_id", 1),
        ("is_favorite", 1),
        ("date", -1)
    ])
    
    await db.outfit_history.create_index([
        ("user_id", 1),
        ("selection_source", 1),
        ("date", -1)
    ])
    
    # For aggregation queries
    await db.outfit_history.create_index([
        ("user_id", 1),
        ("created_at", -1)
    ])
    
    logger.info("✅ Database indexes created successfully")
# app/database.py - Add to create_indexes function

async def create_indexes():
    """Create database indexes for optimal performance"""
    db = Database.get_database()
    
    # Notification Indexes
    await db.notifications.create_index([
        ("user_id", 1),
        ("created_at", -1)
    ])
    
    await db.notifications.create_index([
        ("user_id", 1),
        ("is_read", 1),
        ("created_at", -1)
    ])
    
    await db.notifications.create_index([
        ("user_id", 1),
        ("type", 1),
        ("created_at", -1)
    ])
    
    # For cleanup of old notifications
    await db.notifications.create_index([
        ("created_at", 1)
    ], expireAfterSeconds=2592000)  # Auto-delete after 30 days
    
    logger.info("✅ Notification indexes created successfully")
# Dependency
async def get_database():
    return Database.get_database()
