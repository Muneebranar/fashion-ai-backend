# app/routes/outfit_history.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database import get_database
from app.utils.auth import get_current_user
from app.models.outfit_history import (
    OutfitHistoryCreate,
    OutfitHistoryUpdate,
    OutfitHistoryResponse,
    WeatherData,
    OutfitItem
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outfit-history", tags=["Outfit History"])

# ============================================
# CREATE OUTFIT HISTORY
# ============================================

@router.post("", response_model=OutfitHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_outfit_history(
    outfit_data: OutfitHistoryCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Create a new outfit history entry
    
    - Records what outfit was worn on a specific date
    - Includes weather data and selection source
    - Stores outfit images and item details
    """
    try:
        logger.info(f"📝 Creating outfit history for user: {current_user['email']}")
        
        # Ensure user_id matches current user
        # outfit_data.user_id = current_user["_id"]
        
        # Validate outfit items exist
        item_ids = [ObjectId(item.id) for item in outfit_data.outfit_items]
        items_count = await db.clothing_items.count_documents({
            "_id": {"$in": item_ids},
            "user_id": current_user["_id"]
        })
        
        if items_count != len(item_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more clothing items not found"
            )
        
        # Prepare document
        outfit_doc = {
            "user_id": current_user["_id"],
            "date": outfit_data.date,
            "outfit_items": [item.dict() for item in outfit_data.outfit_items],
            "outfit_image_urls": outfit_data.outfit_image_urls,
            "weather_data": outfit_data.weather_data.dict() if outfit_data.weather_data else None,
            "selection_source": outfit_data.selection_source,
            "is_favorite": outfit_data.is_favorite,
            "notes": outfit_data.notes,
            "occasion": outfit_data.occasion,
            "rating": outfit_data.rating,
            "wear_count": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert into database
        result = await db.outfit_history.insert_one(outfit_doc)
        
        # Increment wear count for each item
        await db.clothing_items.update_many(
            {"_id": {"$in": item_ids}},
            {"$inc": {"wear_count": 1}}
        )
        
        # Fetch and return created document
        created_outfit = await db.outfit_history.find_one({"_id": result.inserted_id})
        created_outfit["_id"] = str(created_outfit["_id"])
        
        logger.info(f"✅ Outfit history created: {created_outfit['_id']}")
        
        return OutfitHistoryResponse(**created_outfit)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating outfit history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create outfit history: {str(e)}"
        )

# ============================================
# GET ALL OUTFIT HISTORY
# ============================================

@router.get("", response_model=List[OutfitHistoryResponse])
async def get_outfit_history(
    current_user: dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_favorite: Optional[bool] = None,
    source: Optional[str] = Query(None, regex="^(ai|manual)$"),
    db = Depends(get_database)
):
    """
    Get outfit history for current user
    
    - Supports pagination
    - Filter by date range
    - Filter by favorite status
    - Filter by selection source (AI/manual)
    """
    try:
        logger.info(f"📋 Fetching outfit history for user: {current_user['email']}")
        
        # Build query
        query = {"user_id": current_user["_id"]}
        
        # Date range filter
        if start_date or end_date:
            query["date"] = {}
            if start_date:
                query["date"]["$gte"] = start_date
            if end_date:
                query["date"]["$lte"] = end_date
        
        # Favorite filter
        if is_favorite is not None:
            query["is_favorite"] = is_favorite
        
        # Source filter
        if source:
            query["selection_source"] = source
        
        # Fetch outfits
        cursor = db.outfit_history.find(query).sort("date", -1).skip(skip).limit(limit)
        outfits = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for outfit in outfits:
            outfit["_id"] = str(outfit["_id"])
        
        logger.info(f"✅ Found {len(outfits)} outfit history entries")
        
        return [OutfitHistoryResponse(**outfit) for outfit in outfits]
        
    except Exception as e:
        logger.error(f"❌ Error fetching outfit history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch outfit history: {str(e)}"
        )

# ============================================
# GET OUTFIT HISTORY BY DATE
# ============================================

@router.get("/by-date/{date}", response_model=List[OutfitHistoryResponse])
async def get_outfit_history_by_date(
    date: datetime,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get outfit history for a specific date
    
    - Returns all outfits worn on the specified date
    - Useful for calendar view
    """
    try:
        # Get start and end of day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # Query
        query = {
            "user_id": current_user["_id"],
            "date": {
                "$gte": start_of_day,
                "$lt": end_of_day
            }
        }
        
        cursor = db.outfit_history.find(query).sort("created_at", -1)
        outfits = await cursor.to_list(length=None)
        
        for outfit in outfits:
            outfit["_id"] = str(outfit["_id"])
        
        return [OutfitHistoryResponse(**outfit) for outfit in outfits]
        
    except Exception as e:
        logger.error(f"❌ Error fetching outfit by date: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch outfit history: {str(e)}"
        )

# ============================================
# GET SINGLE OUTFIT HISTORY
# ============================================

@router.get("/{outfit_id}", response_model=OutfitHistoryResponse)
async def get_outfit_history_detail(
    outfit_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get detailed information about a specific outfit history entry"""
    try:
        outfit = await db.outfit_history.find_one({
            "_id": ObjectId(outfit_id),
            "user_id": current_user["_id"]
        })
        
        if not outfit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Outfit history not found"
            )
        
        outfit["_id"] = str(outfit["_id"])
        
        return OutfitHistoryResponse(**outfit)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching outfit detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch outfit: {str(e)}"
        )

# ============================================
# UPDATE OUTFIT HISTORY
# ============================================

@router.patch("/{outfit_id}", response_model=OutfitHistoryResponse)
async def update_outfit_history(
    outfit_id: str,
    update_data: OutfitHistoryUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Update outfit history entry
    
    - Update favorite status
    - Add/update notes
    - Add/update rating
    """
    try:
        # Build update document
        update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
        
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_dict["updated_at"] = datetime.utcnow()
        
        # Update document
        result = await db.outfit_history.find_one_and_update(
            {
                "_id": ObjectId(outfit_id),
                "user_id": current_user["_id"]
            },
            {"$set": update_dict},
            return_document=True
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Outfit history not found"
            )
        
        result["_id"] = str(result["_id"])
        
        logger.info(f"✅ Outfit history updated: {outfit_id}")
        
        return OutfitHistoryResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating outfit history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update outfit history: {str(e)}"
        )

# ============================================
# DELETE OUTFIT HISTORY
# ============================================

@router.delete("/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outfit_history(
    outfit_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete an outfit history entry"""
    try:
        result = await db.outfit_history.delete_one({
            "_id": ObjectId(outfit_id),
            "user_id": current_user["_id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Outfit history not found"
            )
        
        logger.info(f"✅ Outfit history deleted: {outfit_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting outfit history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete outfit history: {str(e)}"
        )

# ============================================
# RE-WEAR OUTFIT
# ============================================

@router.post("/{outfit_id}/rewear", response_model=OutfitHistoryResponse, status_code=status.HTTP_201_CREATED)
async def rewear_outfit(
    outfit_id: str,
    date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Re-wear a previous outfit
    
    - Creates a new history entry based on existing outfit
    - Updates wear count
    - Uses current date if not specified
    """
    try:
        # Get original outfit
        original_outfit = await db.outfit_history.find_one({
            "_id": ObjectId(outfit_id),
            "user_id": current_user["_id"]
        })
        
        if not original_outfit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original outfit not found"
            )
        
        # Create new outfit history entry
        new_outfit = {
            "user_id": current_user["_id"],
            "date": date or datetime.utcnow(),
            "outfit_items": original_outfit["outfit_items"],
            "outfit_image_urls": original_outfit["outfit_image_urls"],
            "weather_data": None,  # Will be filled by frontend
            "selection_source": "manual",  # Re-wear is always manual
            "is_favorite": original_outfit.get("is_favorite", False),
            "notes": f"Re-worn from {original_outfit['date'].strftime('%Y-%m-%d')}",
            "occasion": original_outfit.get("occasion"),
            "rating": None,
            "wear_count": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.outfit_history.insert_one(new_outfit)
        
        # Increment wear count for original outfit
        await db.outfit_history.update_one(
            {"_id": ObjectId(outfit_id)},
            {"$inc": {"wear_count": 1}}
        )
        
        # Increment wear count for items
        item_ids = [ObjectId(item["id"]) for item in original_outfit["outfit_items"]]
        await db.clothing_items.update_many(
            {"_id": {"$in": item_ids}},
            {"$inc": {"wear_count": 1}}
        )
        
        # Fetch created outfit
        created_outfit = await db.outfit_history.find_one({"_id": result.inserted_id})
        created_outfit["_id"] = str(created_outfit["_id"])
        
        logger.info(f"✅ Outfit re-worn: {outfit_id}")
        
        return OutfitHistoryResponse(**created_outfit)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error re-wearing outfit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to re-wear outfit: {str(e)}"
        )

# ============================================
# GET STATISTICS
# ============================================

@router.get("/stats/summary")
async def get_outfit_statistics(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get outfit history statistics
    
    - Total outfits worn
    - Favorite count
    - AI vs Manual selection ratio
    - Most worn items
    - Recent activity
    """
    try:
        pipeline = [
            {"$match": {"user_id": current_user["_id"]}},
            {"$group": {
                "_id": None,
                "total_outfits": {"$sum": 1},
                "favorite_count": {
                    "$sum": {"$cond": [{"$eq": ["$is_favorite", True]}, 1, 0]}
                },
                "ai_count": {
                    "$sum": {"$cond": [{"$eq": ["$selection_source", "ai"]}, 1, 0]}
                },
                "manual_count": {
                    "$sum": {"$cond": [{"$eq": ["$selection_source", "manual"]}, 1, 0]}
                }
            }}
        ]
        
        cursor = db.outfit_history.aggregate(pipeline)
        stats = await cursor.to_list(length=1)
        
        if not stats:
            return {
                "total_outfits": 0,
                "favorite_count": 0,
                "ai_count": 0,
                "manual_count": 0,
                "ai_percentage": 0,
                "manual_percentage": 0
            }
        
        result = stats[0]
        total = result["total_outfits"]
        
        return {
            "total_outfits": total,
            "favorite_count": result["favorite_count"],
            "ai_count": result["ai_count"],
            "manual_count": result["manual_count"],
            "ai_percentage": round((result["ai_count"] / total * 100) if total > 0 else 0, 1),
            "manual_percentage": round((result["manual_count"] / total * 100) if total > 0 else 0, 1)
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )