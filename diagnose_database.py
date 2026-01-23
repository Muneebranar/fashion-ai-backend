"""
Database Diagnostic Script
Check what's actually in the database and find the issue
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URL = "mongodb://localhost:27017"
DATABASE_NAME = "Outfit"
USER_ID = "694f8c9625fdcfe41c47422e"

async def diagnose_database():
    """Diagnose database state"""
    
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DATABASE_NAME]
        
        logger.info("="*70)
        logger.info("DATABASE DIAGNOSTIC REPORT")
        logger.info("="*70)
        
        # Check all collections
        collections = await db.list_collection_names()
        logger.info(f"\n📚 Available Collections: {collections}")
        
        # Check users
        logger.info("\n" + "="*70)
        logger.info("👤 USERS")
        logger.info("="*70)
        users = await db.users.find({}).to_list(length=None)
        logger.info(f"Total users: {len(users)}")
        for user in users:
            logger.info(f"  - {user.get('email')} (ID: {user.get('_id')})")
        
        # Check if target user exists
        target_user = await db.users.find_one({"_id": ObjectId(USER_ID)})
        if target_user:
            logger.info(f"\n✅ Target user found: {target_user.get('email')}")
        else:
            logger.error(f"\n❌ Target user NOT FOUND: {USER_ID}")
            logger.error("This might be why items aren't showing!")
        
        # Check clothing - with ALL possible user_id formats
        logger.info("\n" + "="*70)
        logger.info("👔 CLOTHING COLLECTION")
        logger.info("="*70)
        
        # Try different query formats
        all_clothing = await db.clothing.find({}).to_list(length=None)
        logger.info(f"Total clothing items (all users): {len(all_clothing)}")
        
        if all_clothing:
            logger.info("\n📦 All clothing items in database:")
            for idx, item in enumerate(all_clothing, 1):
                user_id = item.get('user_id')
                user_id_type = type(user_id).__name__
                logger.info(f"\n  {idx}. {item.get('item_name')}")
                logger.info(f"     Category: {item.get('category')}")
                logger.info(f"     Color: {item.get('color')}")
                logger.info(f"     User ID: {user_id} (type: {user_id_type})")
                logger.info(f"     Created: {item.get('created_at')}")
        
        # Try to find items for target user with different formats
        logger.info(f"\n🔍 Searching for items belonging to user {USER_ID}...")
        
        # Try ObjectId format
        items_objectid = await db.clothing.find({"user_id": ObjectId(USER_ID)}).to_list(length=None)
        logger.info(f"  - Query with ObjectId: {len(items_objectid)} items")
        
        # Try string format
        items_string = await db.clothing.find({"user_id": USER_ID}).to_list(length=None)
        logger.info(f"  - Query with String: {len(items_string)} items")
        
        # Check outfits
        logger.info("\n" + "="*70)
        logger.info("👗 OUTFITS COLLECTION")
        logger.info("="*70)
        
        all_outfits = await db.outfits.find({}).to_list(length=None)
        logger.info(f"Total outfits (all users): {len(all_outfits)}")
        
        if all_outfits:
            logger.info("\n📦 All outfits in database:")
            for idx, outfit in enumerate(all_outfits, 1):
                user_id = outfit.get('user_id')
                user_id_type = type(user_id).__name__
                items = outfit.get('items', [])
                logger.info(f"\n  {idx}. {outfit.get('name', 'Unnamed')}")
                logger.info(f"     Items: {len(items)}")
                logger.info(f"     User ID: {user_id} (type: {user_id_type})")
                
                # Show items in this outfit
                if items:
                    logger.info(f"     Contains:")
                    for item in items:
                        logger.info(f"       - {item.get('item_name')} ({item.get('category')})")
        
        # Try to find outfits for target user
        logger.info(f"\n🔍 Searching for outfits belonging to user {USER_ID}...")
        
        outfits_objectid = await db.outfits.find({"user_id": ObjectId(USER_ID)}).to_list(length=None)
        logger.info(f"  - Query with ObjectId: {len(outfits_objectid)} outfits")
        
        outfits_string = await db.outfits.find({"user_id": USER_ID}).to_list(length=None)
        logger.info(f"  - Query with String: {len(outfits_string)} outfits")
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("📊 SUMMARY")
        logger.info("="*70)
        logger.info(f"Total clothing items in DB: {len(all_clothing)}")
        logger.info(f"Target user's clothing (ObjectId): {len(items_objectid)}")
        logger.info(f"Target user's clothing (String): {len(items_string)}")
        logger.info(f"Total outfits in DB: {len(all_outfits)}")
        logger.info(f"Target user's outfits (ObjectId): {len(outfits_objectid)}")
        logger.info(f"Target user's outfits (String): {len(outfits_string)}")
        
        # Diagnosis
        logger.info("\n" + "="*70)
        logger.info("🔬 DIAGNOSIS")
        logger.info("="*70)
        
        if len(all_clothing) == 0:
            logger.error("❌ PROBLEM: Clothing collection is completely empty!")
            logger.error("   The migration script may have failed silently.")
            logger.error("   OR items were deleted after migration.")
        elif len(items_objectid) == 0 and len(all_clothing) > 0:
            logger.error("❌ PROBLEM: Clothing items exist but not for your user!")
            logger.error("   User ID mismatch - items belong to different user.")
        
        if len(outfits_objectid) > 0:
            logger.info(f"✅ Found {len(outfits_objectid)} outfits for target user")
            logger.info("   We can re-run migration to extract items from these outfits.")
        
        client.close()
        
    except Exception as e:
        logger.error(f"❌ Diagnostic failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(diagnose_database())