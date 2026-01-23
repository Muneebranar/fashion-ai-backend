from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging
import tempfile
import os

from app.database import get_database
from app.models.clothing import (
    ClothingCreate,
    ClothingUpdate,
    ClothingResponse,
    ClothingStats,
    ClothingCategory,
    Season,
    Occasion
)
from app.services.image_service import image_service
from app.services.clip_service import get_clip_service
from app.utils.auth import get_current_user_id
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clothing", tags=["Clothing"])


# ============================================
# IMPORTANT: Static routes MUST come BEFORE parameterized routes!
# ============================================

# Stats endpoint (static route)
@router.get("/stats", response_model=ClothingStats)
async def get_clothing_stats(
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Get wardrobe statistics"""
    
    total_items = await db.clothing_items.count_documents({"user_id": current_user_id})
    
    favorites_count = await db.clothing_items.count_documents({
        "user_id": current_user_id,
        "is_favorite": True
    })
    
    # By category
    by_category = {}
    categories = await db.clothing_items.aggregate([
        {"$match": {"user_id": current_user_id}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]).to_list(length=None)
    for cat in categories:
        by_category[cat["_id"]] = cat["count"]
    
    # By season
    by_season = {}
    items = await db.clothing_items.find({"user_id": current_user_id}).to_list(length=None)
    for item in items:
        for season in item.get("seasons", []):
            by_season[season] = by_season.get(season, 0) + 1
    
    # By occasion
    by_occasion = {}
    for item in items:
        for occasion in item.get("occasions", []):
            by_occasion[occasion] = by_occasion.get(occasion, 0) + 1
    
    # Most worn
    most_worn_cursor = db.clothing_items.find(
        {"user_id": current_user_id}
    ).sort("times_worn", -1).limit(5)
    most_worn = await most_worn_cursor.to_list(length=5)
    for item in most_worn:
        item["_id"] = str(item["_id"])
    
    # Least worn
    least_worn_cursor = db.clothing_items.find(
        {"user_id": current_user_id}
    ).sort("times_worn", 1).limit(5)
    least_worn = await least_worn_cursor.to_list(length=5)
    for item in least_worn:
        item["_id"] = str(item["_id"])
    
    # Total value
    total_value = 0
    for item in items:
        if item.get("price"):
            total_value += item["price"]
    
    return ClothingStats(
        total_items=total_items,
        by_category=by_category,
        by_season=by_season,
        by_occasion=by_occasion,
        favorites_count=favorites_count,
        most_worn=[ClothingResponse(**item) for item in most_worn],
        least_worn=[ClothingResponse(**item) for item in least_worn],
        total_value=total_value
    )


# Regenerate ALL embeddings (static route - MUST be before /{item_id})
@router.post("/regenerate-all-embeddings")
async def regenerate_all_embeddings(
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """
    🔄 Regenerate CLIP embeddings for ALL user's clothing items
    
    This processes all items that have images but missing or outdated embeddings.
    Useful after CLIP integration or model updates.
    """
    try:
        logger.info(f"Starting batch embedding regeneration for user {current_user_id}")
        
        # Get all user's items with images
        items = await db.clothing_items.find({
            "user_id": current_user_id,
            "image_url": {"$exists": True, "$ne": None}
        }).to_list(length=None)
        
        if not items:
            return {
                "success": False,
                "message": "No items with images found",
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0
            }
        
        # Initialize CLIP service
        try:
            clip_service = get_clip_service()
            logger.info(f"✅ CLIP service loaded on {clip_service.device}")
        except Exception as e:
            logger.error(f"Failed to load CLIP service: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"CLIP service unavailable: {str(e)}"
            )
        
        processed = 0
        failed = 0
        skipped = 0
        
        for item in items:
            item_id = item["_id"]
            item_name = item.get("item_name", "Unknown")
            image_url = item.get("image_url")
            
            try:
                # Skip if already has embedding
                if item.get("embedding") is not None:
                    skipped += 1
                    logger.info(f"⏭️  Skipping '{item_name}' - already has embedding")
                    continue
                
                logger.info(f"🔄 Processing '{item_name}' (ID: {item_id})")
                
                # Generate embedding
                embedding = clip_service.get_image_embedding(image_url)
                
                if embedding is not None:
                    # Update item with embedding
                    await db.clothing_items.update_one(
                        {"_id": item_id},
                        {
                            "$set": {
                                "embedding": embedding.tolist(),
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    processed += 1
                    logger.info(f"✅ Generated embedding for '{item_name}' (dim: {len(embedding)})")
                else:
                    failed += 1
                    logger.warning(f"❌ Failed to generate embedding for '{item_name}'")
                    
            except Exception as e:
                failed += 1
                logger.error(f"❌ Error processing '{item_name}': {e}")
        
        result = {
            "success": True,
            "message": "Batch embedding regeneration complete",
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "total": len(items)
        }
        
        logger.info(f"🎉 Batch complete: {result}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch regeneration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch regeneration failed: {str(e)}"
        )
# Add this AFTER the regenerate-all-embeddings endpoint

@router.post("/force-regenerate-embeddings")
async def force_regenerate_embeddings(
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """
    🔄 FORCE regenerate ALL embeddings (removes existing ones first)
    
    Use this when embeddings are corrupted or you want to regenerate everything
    """
    try:
        logger.info("=" * 80)
        logger.info("🔄 FORCE REGENERATION - Removing all existing embeddings first")
        
        # Step 1: REMOVE ALL existing embeddings
        result = await db.clothing_items.update_many(
            {"user_id": current_user_id},
            {"$unset": {"embedding": ""}}
        )
        logger.info(f"   ✓ Removed embeddings from {result.modified_count} items")
        
        # Step 2: Fetch all items with images
        items = await db.clothing_items.find({
            "user_id": current_user_id,
            "image_url": {"$exists": True, "$ne": None}
        }).to_list(length=None)
        
        logger.info(f"   ✓ Found {len(items)} items to process")
        
        if not items:
            return {
                "success": False,
                "message": "No items with images found",
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0
            }
        
        # Step 3: Get CLIP service
        try:
            clip_service = get_clip_service()
            logger.info(f"✅ CLIP service loaded on {clip_service.device}")
        except Exception as e:
            logger.error(f"Failed to load CLIP service: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"CLIP service unavailable: {str(e)}"
            )
        
        # Step 4: Generate embeddings for ALL items (no skipping)
        processed = 0
        failed = 0
        
        for item in items:
            item_id = item["_id"]
            item_name = item.get("item_name", "Unknown")
            image_url = item.get("image_url")
            
            try:
                logger.info(f"🔄 Processing '{item_name}' (ID: {item_id})")
                
                # Generate embedding
                embedding = clip_service.get_image_embedding(image_url)
                
                if embedding is not None:
                    # Update item with embedding
                    await db.clothing_items.update_one(
                        {"_id": item_id},
                        {
                            "$set": {
                                "embedding": embedding.tolist(),
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    processed += 1
                    logger.info(f"   ✅ Generated {len(embedding)}-dim embedding")
                else:
                    failed += 1
                    logger.warning(f"   ❌ Failed to generate embedding")
                    
            except Exception as e:
                failed += 1
                logger.error(f"   ❌ Error: {e}")
        
        result_data = {
            "success": True,
            "message": "Force regeneration complete",
            "processed": processed,
            "failed": failed,
            "skipped": 0,  # No skipping in force mode
            "total": len(items)
        }
        
        logger.info(f"🎉 Force regeneration complete: {result_data}")
        logger.info("=" * 80)
        
        return result_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Force regeneration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate embeddings: {str(e)}"
        )

# Create clothing item
@router.post("", response_model=ClothingResponse, status_code=status.HTTP_201_CREATED)
async def create_clothing_item(
    item_data: ClothingCreate,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Create a new clothing item"""
    
    item_dict = item_data.dict()
    item_dict.update({
        "user_id": current_user_id,
        "image_url": None,
        "embedding": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    result = await db.clothing_items.insert_one(item_dict)
    item_dict["_id"] = str(result.inserted_id)
    
    return ClothingResponse(**item_dict)


# Get all clothing items
@router.get("", response_model=List[ClothingResponse])
async def get_clothing_items(
    category: Optional[ClothingCategory] = None,
    season: Optional[Season] = None,
    occasion: Optional[Occasion] = None,
    color: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Get user's clothing items with filters"""
    
    query = {"user_id": current_user_id}
    
    if category:
        query["category"] = category
    
    if season:
        query["seasons"] = season
    
    if occasion:
        query["occasions"] = occasion
    
    if color:
        query["color"] = {"$regex": color, "$options": "i"}
    
    if is_favorite is not None:
        query["is_favorite"] = is_favorite
    
    if search:
        query["$or"] = [
            {"item_name": {"$regex": search, "$options": "i"}},
            {"brand": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}}
        ]
    
    cursor = db.clothing_items.find(query).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    
    for item in items:
        item["_id"] = str(item["_id"])
    
    return [ClothingResponse(**item) for item in items]


# ============================================
# Parameterized routes (with {item_id}) MUST come AFTER static routes
# ============================================

# Get single clothing item
@router.get("/{item_id}", response_model=ClothingResponse)
async def get_clothing_item(
    item_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Get a specific clothing item"""
    
    item = await db.clothing_items.find_one({
        "_id": ObjectId(item_id),
        "user_id": current_user_id
    })
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    item["_id"] = str(item["_id"])
    return ClothingResponse(**item)


# Update clothing item
@router.put("/{item_id}", response_model=ClothingResponse)
async def update_clothing_item(
    item_id: str,
    item_update: ClothingUpdate,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Update a clothing item"""
    
    item = await db.clothing_items.find_one({
        "_id": ObjectId(item_id),
        "user_id": current_user_id
    })
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    update_data = item_update.dict(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.clothing_items.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": update_data}
        )
    
    updated_item = await db.clothing_items.find_one({"_id": ObjectId(item_id)})
    updated_item["_id"] = str(updated_item["_id"])
    
    return ClothingResponse(**updated_item)


# Delete clothing item
@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clothing_item(
    item_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Delete a clothing item"""
    
    item = await db.clothing_items.find_one({
        "_id": ObjectId(item_id),
        "user_id": current_user_id
    })
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    if item.get("image_url"):
        await image_service.delete_image(item["image_url"])
    
    await db.clothing_items.delete_one({"_id": ObjectId(item_id)})
    
    return None


# Upload image for clothing item
@router.post("/{item_id}/image", response_model=ClothingResponse)
async def upload_clothing_image(
    item_id: str,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """
    Upload image for a clothing item
    Automatically generates CLIP embedding for AI-powered search
    """
    
    item = await db.clothing_items.find_one({
        "_id": ObjectId(item_id),
        "user_id": current_user_id
    })
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    # Delete old image if exists
    if item.get("image_url"):
        await image_service.delete_image(item["image_url"])
    
    # Upload new image
    image_url = await image_service.upload_image(file, folder="clothing")
    
    # Generate CLIP embedding
    embedding = None
    try:
        logger.info(f"Generating CLIP embedding for item {item_id}")
        clip_service = get_clip_service()
        
        embedding = clip_service.get_image_embedding(image_url)
        
        if embedding is not None:
            logger.info(f"✅ CLIP embedding generated (dim: {len(embedding)})")
        else:
            logger.warning(f"⚠️  CLIP embedding generation returned None")
            
    except Exception as e:
        logger.error(f"Failed to generate CLIP embedding: {e}")
        # Continue without embedding - don't fail the upload
    
    # Update item
    update_data = {
        "image_url": image_url,
        "updated_at": datetime.utcnow()
    }
    
    if embedding is not None:
        update_data["embedding"] = embedding.tolist()
    
    await db.clothing_items.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": update_data}
    )
    
    # Get updated item
    updated_item = await db.clothing_items.find_one({"_id": ObjectId(item_id)})
    updated_item["_id"] = str(updated_item["_id"])
    
    return ClothingResponse(**updated_item)


# Toggle favorite
@router.post("/{item_id}/favorite", response_model=ClothingResponse)
async def toggle_favorite(
    item_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Toggle favorite status"""
    
    item = await db.clothing_items.find_one({
        "_id": ObjectId(item_id),
        "user_id": current_user_id
    })
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    new_favorite_status = not item.get("is_favorite", False)
    await db.clothing_items.update_one(
        {"_id": ObjectId(item_id)},
        {
            "$set": {
                "is_favorite": new_favorite_status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    updated_item = await db.clothing_items.find_one({"_id": ObjectId(item_id)})
    updated_item["_id"] = str(updated_item["_id"])
    
    return ClothingResponse(**updated_item)


# Record wear
@router.post("/{item_id}/wear", response_model=ClothingResponse)
async def record_wear(
    item_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """Record that an item was worn"""
    
    item = await db.clothing_items.find_one({
        "_id": ObjectId(item_id),
        "user_id": current_user_id
    })
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    await db.clothing_items.update_one(
        {"_id": ObjectId(item_id)},
        {
            "$inc": {"times_worn": 1},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    updated_item = await db.clothing_items.find_one({"_id": ObjectId(item_id)})
    updated_item["_id"] = str(updated_item["_id"])
    
    return ClothingResponse(**updated_item)


# Regenerate single item embedding
@router.post("/{item_id}/regenerate-embedding")
async def regenerate_embedding(
    item_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """
    🔄 Regenerate CLIP Embedding for a single item
    
    Works with both local files and remote URLs (S3, etc.)
    """
    try:
        item = await db.clothing_items.find_one({
            "_id": ObjectId(item_id),
            "user_id": current_user_id
        })
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        
        image_url = item.get("image_url")
        if not image_url:
            raise HTTPException(
                status_code=400,
                detail="Item has no image"
            )
        
        # Initialize CLIP
        logger.info(f"Regenerating embedding for item {item_id}")
        clip_service = get_clip_service()
        
        # Generate embedding
        embedding = clip_service.get_image_embedding(image_url)
        
        if embedding is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate embedding from image"
            )
        
        # Update database
        await db.clothing_items.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {
                "embedding": embedding.tolist(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"✅ Embedding regenerated for item {item_id} (dim: {len(embedding)})")
        
        return {
            "success": True,
            "message": "CLIP embedding regenerated successfully",
            "item_id": item_id,
            "embedding_dimension": len(embedding)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regenerate embedding failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate embedding: {str(e)}"
        )
        # Add this to app/routes/clothing.py

@router.get("/debug/check-items")
async def debug_check_items(
    current_user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
):
    """
    🔍 Debug endpoint to check all items and their embeddings
    """
    try:
        # Get all items for user
        all_items = await db.clothing_items.find({
            "user_id": current_user_id
        }).to_list(length=None)
        
        items_info = []
        for item in all_items:
            items_info.append({
                "id": str(item["_id"]),
                "name": item.get("item_name"),
                "category": item.get("category"),
                "image_url": item.get("image_url"),
                "has_embedding": item.get("embedding") is not None,
                "embedding_length": len(item["embedding"]) if item.get("embedding") else 0,
                "created_at": item.get("created_at"),
            })
        
        # Count by status
        total = len(all_items)
        with_images = sum(1 for item in all_items if item.get("image_url"))
        with_embeddings = sum(1 for item in all_items if item.get("embedding"))
        
        return {
            "success": True,
            "total_items": total,
            "items_with_images": with_images,
            "items_with_embeddings": with_embeddings,
            "items": items_info
        }
        
    except Exception as e:
        logger.error(f"Debug check failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }