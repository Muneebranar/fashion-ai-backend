from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import get_database
from app.models.user import UserResponse, UserUpdate
from app.models.clothing import ClothingResponse
from app.models.outfit import OutfitResponse
from app.utils.auth import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin"])

# Dashboard Stats
@router.get("/dashboard")
async def get_dashboard_stats(
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Get admin dashboard statistics"""
    
    # Total users
    total_users = await db.users.count_documents({})
    
    # New users this month
    month_ago = datetime.utcnow() - timedelta(days=30)
    new_users = await db.users.count_documents({
        "created_at": {"$gte": month_ago}
    })
    
    # Total clothing items
    total_items = await db.clothing.count_documents({})
    
    # Total outfits
    total_outfits = await db.outfits.count_documents({})
    
    # Active users (logged in last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    active_users = await db.users.count_documents({
        "last_login": {"$gte": week_ago}
    })
    
    # Items by category
    items_by_category = await db.clothing.aggregate([
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]).to_list(length=None)
    
    category_stats = {item["_id"]: item["count"] for item in items_by_category}
    
    # User registration trend (last 30 days)
    registration_trend = []
    for i in range(30, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        count = await db.users.count_documents({
            "created_at": {"$gte": start_of_day, "$lte": end_of_day}
        })
        
        registration_trend.append({
            "date": start_of_day.strftime("%Y-%m-%d"),
            "count": count
        })
    
    return {
        "total_users": total_users,
        "new_users_this_month": new_users,
        "active_users": active_users,
        "total_items": total_items,
        "total_outfits": total_outfits,
        "items_by_category": category_stats,
        "registration_trend": registration_trend
    }

# User Management
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    search: Optional[str] = None,
    is_admin: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Get all users with filtering"""
    
    query = {}
    
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    if is_admin is not None:
        query["is_admin"] = is_admin
    
    cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    
    for user in users:
        user["_id"] = str(user["_id"])
    
    return [UserResponse(**user) for user in users]

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: str,
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Get specific user details"""
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user["_id"] = str(user["_id"])
    return UserResponse(**user)

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Update user details"""
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.dict(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
    
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    updated_user["_id"] = str(updated_user["_id"])
    
    return UserResponse(**updated_user)

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Delete a user and all their data"""
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Don't allow deleting admin users
    if user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete admin users"
        )
    
    # Delete user's clothing items
    await db.clothing.delete_many({"user_id": user_id})
    
    # Delete user's outfits
    await db.outfits.delete_many({"user_id": user_id})
    
    # Delete user's favorites
    await db.favorites.delete_many({"user_id": user_id})
    
    # Delete user
    await db.users.delete_one({"_id": ObjectId(user_id)})
    
    return None

@router.post("/users/{user_id}/toggle-admin", response_model=UserResponse)
async def toggle_admin_status(
    user_id: str,
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Toggle admin status of a user"""
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    new_admin_status = not user.get("is_admin", False)
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "is_admin": new_admin_status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    updated_user["_id"] = str(updated_user["_id"])
    
    return UserResponse(**updated_user)

# Clothing Management
@router.get("/clothing", response_model=List[ClothingResponse])
async def get_all_clothing_items(
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Get all clothing items across all users"""
    
    query = {}
    
    if user_id:
        query["user_id"] = user_id
    
    if category:
        query["category"] = category
    
    cursor = db.clothing.find(query).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    
    for item in items:
        item["_id"] = str(item["_id"])
    
    return [ClothingResponse(**item) for item in items]

@router.delete("/clothing/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clothing_item(
    item_id: str,
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Delete a clothing item"""
    
    item = await db.clothing.find_one({"_id": ObjectId(item_id)})
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clothing item not found"
        )
    
    await db.clothing.delete_one({"_id": ObjectId(item_id)})
    return None

# Outfit Management
@router.get("/outfits", response_model=List[OutfitResponse])
async def get_all_outfits(
    user_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Get all outfits across all users"""
    
    query = {}
    
    if user_id:
        query["user_id"] = user_id
    
    cursor = db.outfits.find(query).sort("created_at", -1).skip(skip).limit(limit)
    outfits = await cursor.to_list(length=limit)
    
    for outfit in outfits:
        outfit["_id"] = str(outfit["_id"])
    
    return [OutfitResponse(**outfit) for outfit in outfits]

@router.delete("/outfits/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outfit(
    outfit_id: str,
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Delete an outfit"""
    
    outfit = await db.outfits.find_one({"_id": ObjectId(outfit_id)})
    
    if not outfit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outfit not found"
        )
    
    await db.outfits.delete_one({"_id": ObjectId(outfit_id)})
    return None

# Analytics
@router.get("/analytics/users")
async def get_user_analytics(
    admin_id: str = Depends(get_current_admin),
    db = Depends(get_database)
):
    """Get detailed user analytics"""
    
    # Users with most items
    top_users = await db.clothing.aggregate([
        {"$group": {
            "_id": "$user_id",
            "item_count": {"$sum": 1}
        }},
        {"$sort": {"item_count": -1}},
        {"$limit": 10}
    ]).to_list(length=10)
    
    # Enrich with user data
    for user_stat in top_users:
        user = await db.users.find_one({"_id": ObjectId(user_stat["_id"])})
        if user:
            user_stat["user_email"] = user.get("email")
            user_stat["user_name"] = user.get("full_name")
    
    # Most popular categories
    popular_categories = await db.clothing.aggregate([
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]).to_list(length=None)
    
    # Most popular occasions
    popular_occasions = await db.clothing.aggregate([
        {"$unwind": "$occasions"},
        {"$group": {
            "_id": "$occasions",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]).to_list(length=None)
    
    return {
        "top_users_by_items": top_users,
        "popular_categories": popular_categories,
        "popular_occasions": popular_occasions
    }