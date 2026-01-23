from fastapi import APIRouter, Depends, Query, HTTPException, Body
from typing import Optional, Dict, Any, List
from bson import ObjectId
from datetime import datetime
import logging

from app.utils.auth import get_current_user
from app.services.outfit_service import outfit_service
from app.services.weather_service import weather_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outfits", tags=["outfits"])


# ============================================
# OUTFIT SUGGESTIONS
# ============================================

@router.get("/suggestions")
async def get_outfit_suggestions(
    current_user: dict = Depends(get_current_user),
    occasion: str = Query("casual", description="Occasion for outfit"),
    count: int = Query(5, ge=1, le=20, description="Number of suggestions"),
    location: str = Query("New York", description="Location for weather consideration"),
    consider_weather: bool = Query(True, description="Consider weather in suggestions"),
    temperature: Optional[float] = None,
    condition: Optional[str] = None
):
    """Get AI-powered outfit suggestions with optional weather filtering"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"🎯 Generating outfit suggestions for user {user_id}")
        logger.info(f"   Location: {location}, Occasion: {occasion}, Count: {count}")
        
        # Get weather data if needed
        weather_data = None
        if consider_weather:
            if temperature is not None or condition is not None:
                weather_data = {
                    "temperature": temperature or 20,
                    "condition": condition or "Clear",
                    "location": location,
                    "category": weather_service.get_temperature_category(temperature or 20)
                }
            else:
                weather_data = weather_service.get_weather_with_category(location)
        
        # Generate outfit suggestions
        suggestions = await outfit_service.generate_suggestions(
            user_id=user_id,
            occasion=occasion,
            count=count,
            location=location,
            weather_data=weather_data
        )
        
        logger.info(f"✅ Generated {len(suggestions)} outfit suggestions")
        
        return {
            "success": True,
            "count": len(suggestions),
            "outfits": suggestions,
            "location": location,
            "occasion": occasion,
            "weather_considered": consider_weather and weather_data is not None,
            "weather_data": weather_data if consider_weather else None
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


@router.get("/suggestions/test")
async def test_outfit_suggestions(
    location: str = Query("London"),
    occasion: str = Query("casual"),
    count: int = Query(3)
):
    """Test endpoint without authentication"""
    try:
        user_id = "test_user_123"
        
        weather_data = weather_service.get_weather_with_category(location)
        
        suggestions = await outfit_service.generate_suggestions(
            user_id=user_id,
            occasion=occasion,
            count=count,
            location=location,
            weather_data=weather_data
        )
        
        return {
            "success": True,
            "message": "Test endpoint working!",
            "location": location,
            "occasion": occasion,
            "weather": weather_data,
            "outfits": suggestions
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================
# SAVE OUTFIT - MAIN ENDPOINT
# ============================================

@router.post("")
async def save_outfit_main(
    outfit_data: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Save an outfit to user's collection - Main endpoint"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"💾 Saving outfit for user {user_id}: {outfit_data.get('name', 'Unnamed')}")
        
        # Extract and format data
        outfit_doc = {
            "name": outfit_data.get("name", f"Outfit {datetime.now().strftime('%Y-%m-%d')}"),
            "items": outfit_data.get("items", []),
            "occasion": outfit_data.get("occasion", "casual"),
            "scores": outfit_data.get("scores", {}),
            "weather_data": outfit_data.get("weather_data"),
            "tags": outfit_data.get("tags", []),
            "notes": outfit_data.get("notes", ""),
        }
        
        result = await outfit_service.save_outfit(
            user_id=user_id,
            outfit_data=outfit_doc,
            occasion=outfit_doc["occasion"]
        )
        
        if result.get("success"):
            logger.info(f"✅ Outfit saved: {result.get('outfit_id')}")
            return {
                "success": True,
                "outfit_id": result.get("outfit_id"),
                "data": result.get("outfit_data"),
                "message": "Outfit saved successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to save outfit"))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error saving outfit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_outfit_legacy(
    outfit_data: Dict[str, Any] = Body(...),
    occasion: str = Query("casual"),
    current_user: dict = Depends(get_current_user)
):
    """Save an outfit to user's collection - Legacy endpoint for backward compatibility"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"💾 [Legacy] Saving outfit for user {user_id}")
        
        result = await outfit_service.save_outfit(
            user_id=user_id,
            outfit_data=outfit_data,
            occasion=occasion
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error saving outfit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save outfit: {str(e)}")


# ============================================
# GET SAVED OUTFITS
# ============================================

@router.get("/saved")
async def get_saved_outfits(
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    occasion: Optional[str] = None
):
    """Get user's saved outfits with pagination"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"📚 Fetching saved outfits for user {user_id} (page {page}, limit {limit})")
        
        # Get all outfits (we'll paginate in memory for now)
        all_outfits = await outfit_service.get_saved_outfits(
            user_id=user_id,
            limit=1000
        )
        
        # Filter by occasion if specified
        if occasion:
            all_outfits = [o for o in all_outfits if o.get("occasion") == occasion]
        
        # Calculate pagination
        total = len(all_outfits)
        skip = (page - 1) * limit
        total_pages = (total + limit - 1) // limit
        
        # Get page of outfits
        outfits = all_outfits[skip:skip + limit]
        
        logger.info(f"✅ Found {len(outfits)} outfits on page {page} of {total_pages}")
        
        return {
            "success": True,
            "outfits": outfits,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": total_pages
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching saved outfits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get saved outfits: {str(e)}")


# ============================================
# DELETE OUTFIT
# ============================================

@router.delete("/{outfit_id}")
async def delete_outfit(
    outfit_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a saved outfit"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"🗑️ Deleting outfit {outfit_id} for user {user_id}")
        
        # Validate outfit_id format
        if not ObjectId.is_valid(outfit_id):
            raise HTTPException(status_code=400, detail="Invalid outfit ID format")
        
        result = await outfit_service.delete_saved_outfit(
            user_id=user_id,
            outfit_id=outfit_id
        )
        
        if result.get("success"):
            logger.info(f"✅ Outfit {outfit_id} deleted successfully")
            return {
                "success": True,
                "message": "Outfit deleted successfully",
                "deleted_count": result.get("deleted_count", 1)
            }
        else:
            error_msg = result.get("error", "Outfit not found")
            logger.warning(f"⚠️ Delete failed: {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting outfit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET OUTFIT BY ID
# ============================================

@router.get("/{outfit_id}")
async def get_outfit_by_id(
    outfit_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific outfit by ID"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"🔍 Fetching outfit {outfit_id} for user {user_id}")
        
        if not ObjectId.is_valid(outfit_id):
            raise HTTPException(status_code=400, detail="Invalid outfit ID format")
        
        # Get from database
        from app.database import get_database
        db = await get_database()
        
        outfit = await db.saved_outfits.find_one({
            "_id": ObjectId(outfit_id),
            "user_id": ObjectId(user_id)
        })
        
        if not outfit:
            raise HTTPException(status_code=404, detail="Outfit not found")
        
        # Convert ObjectIds to strings
        outfit["_id"] = str(outfit["_id"])
        outfit["user_id"] = str(outfit["user_id"])
        
        logger.info(f"✅ Outfit found: {outfit.get('name')}")
        return {
            "success": True,
            "outfit": outfit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching outfit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UPDATE OUTFIT
# ============================================

@router.put("/{outfit_id}")
async def update_outfit(
    outfit_id: str,
    outfit_data: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Update a saved outfit"""
    try:
        user_id = current_user["_id"]
        
        logger.info(f"✏️ Updating outfit {outfit_id} for user {user_id}")
        
        if not ObjectId.is_valid(outfit_id):
            raise HTTPException(status_code=400, detail="Invalid outfit ID format")
        
        from app.database import get_database
        db = await get_database()
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.utcnow()
        }
        
        if "name" in outfit_data:
            update_data["name"] = outfit_data["name"]
        if "items" in outfit_data:
            update_data["items"] = outfit_data["items"]
        if "occasion" in outfit_data:
            update_data["occasion"] = outfit_data["occasion"]
        if "scores" in outfit_data:
            update_data["scores"] = outfit_data["scores"]
        if "weather_data" in outfit_data:
            update_data["weather"] = outfit_data["weather_data"]
        if "tags" in outfit_data:
            update_data["tags"] = outfit_data["tags"]
        if "notes" in outfit_data:
            update_data["notes"] = outfit_data["notes"]
        
        # Update in database
        result = await db.saved_outfits.update_one(
            {
                "_id": ObjectId(outfit_id),
                "user_id": ObjectId(user_id)
            },
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Outfit {outfit_id} updated successfully")
            return {
                "success": True,
                "message": "Outfit updated successfully",
                "outfit_id": outfit_id
            }
        elif result.matched_count > 0:
            return {
                "success": True,
                "message": "Outfit unchanged",
                "outfit_id": outfit_id
            }
        else:
            raise HTTPException(status_code=404, detail="Outfit not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating outfit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# OTHER ENDPOINTS
# ============================================

@router.get("/detailed/{outfit_id}")
async def get_detailed_outfit_analysis(
    outfit_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed analysis for a specific outfit"""
    try:
        user_id = current_user["_id"]
        
        analysis = await outfit_service.get_detailed_outfit_analysis(
            outfit_id=outfit_id,
            user_id=user_id
        )
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Error getting analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get analysis: {str(e)}")


@router.get("/wardrobe-stats")
async def get_wardrobe_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get statistics about user's wardrobe"""
    try:
        user_id = current_user["_id"]
        
        wardrobe_items = await outfit_service.get_user_wardrobe(user_id)
        
        total_items = len(wardrobe_items)
        categorized = outfit_service._categorize_items(wardrobe_items)
        
        stats = {
            "total_items": total_items,
            "categories": {
                category: len(items)
                for category, items in categorized.items()
            },
            "most_common_color": "To be implemented",
            "average_price": "To be implemented"
        }
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/seasonal")
async def get_seasonal_recommendations(
    month: Optional[int] = Query(None, ge=1, le=12)
):
    """Get seasonal fashion recommendations"""
    try:
        recommendations = outfit_service.get_seasonal_recommendations(month)
        
        return {
            "success": True,
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting seasonal recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get seasonal recommendations: {str(e)}")


@router.get("/weather-based")
async def get_weather_based_suggestions(
    location: str = Query(..., description="Location for weather"),
    occasion: str = Query("casual"),
    current_user: dict = Depends(get_current_user)
):
    """Get outfit suggestions specifically based on weather"""
    try:
        user_id = current_user["_id"]
        
        weather = weather_service.get_weather_with_category(location)
        
        if not weather:
            raise HTTPException(status_code=400, detail=f"Could not get weather for {location}")
        
        suggestions = await outfit_service.generate_suggestions(
            user_id=user_id,
            occasion=occasion,
            count=5,
            location=location,
            weather_data=weather
        )
        
        weather_appropriate = [
            outfit for outfit in suggestions 
            if outfit.get('is_weather_appropriate', False)
        ]
        
        return {
            "success": True,
            "location": location,
            "weather": weather,
            "all_suggestions": len(suggestions),
            "weather_appropriate": len(weather_appropriate),
            "outfits": weather_appropriate[:3]
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting weather-based suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get weather-based suggestions: {str(e)}")


@router.get("/debug/wardrobe")
async def debug_user_wardrobe(
    current_user: dict = Depends(get_current_user)
):
    """Debug endpoint to see user's wardrobe items"""
    try:
        user_id = current_user["_id"]
        
        wardrobe = await outfit_service.get_user_wardrobe(user_id)
        
        categories = {}
        for item in wardrobe:
            category = item.get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "success": True,
            "user_id": user_id,
            "total_items": len(wardrobe),
            "categories": categories,
            "sample_items": wardrobe[:5] if wardrobe else []
        }
        
    except Exception as e:
        logger.error(f"❌ Debug error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}