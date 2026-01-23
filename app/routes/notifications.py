# app/routes/notifications.py
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database import get_database
from app.utils.auth import get_current_user
from app.models.notification import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    NotificationStats,
    NotificationType,
    NotificationPriority
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["Notifications"])

# ============================================
# CREATE NOTIFICATION
# ============================================

@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_data: NotificationCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Create a new notification
    
    - System-generated or user-triggered
    - Supports different types and priorities
    - Can include deep links for navigation
    """
    try:
        logger.info(f"📬 Creating notification for user: {current_user['email']}")
        
        # Ensure user_id matches current user
        notification_data.user_id = current_user["_id"]
        
        # Prepare document
        notification_doc = {
            "user_id": current_user["_id"],
            "title": notification_data.title,
            "message": notification_data.message,
            "type": notification_data.type,
            "priority": notification_data.priority,
            "is_read": False,
            "deep_link": notification_data.deep_link,
            "metadata": notification_data.metadata or {},
            "icon": notification_data.icon,
            "action_label": notification_data.action_label,
            "action_link": notification_data.action_link,
            "created_at": datetime.utcnow(),
            "read_at": None
        }
        
        # Insert into database
        result = await db.notifications.insert_one(notification_doc)
        
        # Fetch created notification
        created_notification = await db.notifications.find_one({"_id": result.inserted_id})
        created_notification["_id"] = str(created_notification["_id"])
        
        logger.info(f"✅ Notification created: {created_notification['_id']}")
        
        return NotificationResponse(**created_notification)
        
    except Exception as e:
        logger.error(f"❌ Error creating notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}"
        )

# ============================================
# GET ALL NOTIFICATIONS
# ============================================

@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    current_user: dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
    type_filter: Optional[NotificationType] = None,
    db = Depends(get_database)
):
    """
    Get notifications for current user
    
    - Supports pagination
    - Filter by read/unread status
    - Filter by notification type
    - Sorted by creation date (newest first)
    """
    try:
        logger.info(f"📋 Fetching notifications for user: {current_user['email']}")
        
        # Build query
        query = {"user_id": current_user["_id"]}
        
        if unread_only:
            query["is_read"] = False
        
        if type_filter:
            query["type"] = type_filter
        
        # Fetch notifications
        cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
        notifications = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for notification in notifications:
            notification["_id"] = str(notification["_id"])
        
        logger.info(f"✅ Found {len(notifications)} notifications")
        
        return [NotificationResponse(**notification) for notification in notifications]
        
    except Exception as e:
        logger.error(f"❌ Error fetching notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )

# ============================================
# GET SINGLE NOTIFICATION
# ============================================

@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get a specific notification by ID"""
    try:
        notification = await db.notifications.find_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user["_id"]
        })
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification["_id"] = str(notification["_id"])
        
        return NotificationResponse(**notification)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notification: {str(e)}"
        )

# ============================================
# MARK AS READ
# ============================================

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Mark a notification as read"""
    try:
        result = await db.notifications.find_one_and_update(
            {
                "_id": ObjectId(notification_id),
                "user_id": current_user["_id"]
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.utcnow()
                }
            },
            return_document=True
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        result["_id"] = str(result["_id"])
        
        logger.info(f"✅ Notification marked as read: {notification_id}")
        
        return NotificationResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark as read: {str(e)}"
        )

# ============================================
# MARK ALL AS READ
# ============================================

@router.post("/mark-all-read")
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Mark all notifications as read for current user"""
    try:
        result = await db.notifications.update_many(
            {
                "user_id": current_user["_id"],
                "is_read": False
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"✅ Marked {result.modified_count} notifications as read")
        
        return {
            "success": True,
            "message": f"Marked {result.modified_count} notifications as read"
        }
        
    except Exception as e:
        logger.error(f"❌ Error marking all as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all as read: {str(e)}"
        )

# ============================================
# DELETE NOTIFICATION
# ============================================

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete a notification"""
    try:
        result = await db.notifications.delete_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user["_id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        logger.info(f"✅ Notification deleted: {notification_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notification: {str(e)}"
        )

# ============================================
# DELETE ALL READ NOTIFICATIONS
# ============================================

@router.delete("/clear-read")
async def clear_read_notifications(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Delete all read notifications for current user"""
    try:
        result = await db.notifications.delete_many({
            "user_id": current_user["_id"],
            "is_read": True
        })
        
        logger.info(f"✅ Deleted {result.deleted_count} read notifications")
        
        return {
            "success": True,
            "message": f"Deleted {result.deleted_count} notifications",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"❌ Error clearing notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear notifications: {str(e)}"
        )

# ============================================
# GET NOTIFICATION STATISTICS
# ============================================

@router.get("/stats/summary", response_model=NotificationStats)
async def get_notification_stats(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get notification statistics
    
    - Total count
    - Unread count
    - Count by type
    - Recent notifications (last 24 hours)
    """
    try:
        # Total count
        total_count = await db.notifications.count_documents({
            "user_id": current_user["_id"]
        })
        
        # Unread count
        unread_count = await db.notifications.count_documents({
            "user_id": current_user["_id"],
            "is_read": False
        })
        
        # Count by type
        pipeline = [
            {"$match": {"user_id": current_user["_id"]}},
            {"$group": {
                "_id": "$type",
                "count": {"$sum": 1}
            }}
        ]
        
        cursor = db.notifications.aggregate(pipeline)
        type_counts = await cursor.to_list(length=None)
        
        by_type = {item["_id"]: item["count"] for item in type_counts}
        
        # Recent count (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_count = await db.notifications.count_documents({
            "user_id": current_user["_id"],
            "created_at": {"$gte": yesterday}
        })
        
        return NotificationStats(
            total_count=total_count,
            unread_count=unread_count,
            by_type=by_type,
            recent_count=recent_count
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching notification stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )

# ============================================
# HELPER: CREATE SYSTEM NOTIFICATION
# ============================================

async def create_system_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.SYSTEM,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    deep_link: Optional[str] = None,
    metadata: Optional[dict] = None,
    db = None
):
    """
    Helper function to create system notifications
    Used by other services (weather alerts, outfit suggestions, etc.)
    """
    try:
        if db is None:
            from app.database import Database
            db = Database.get_database()
        
        notification_doc = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type,
            "priority": priority,
            "is_read": False,
            "deep_link": deep_link,
            "metadata": metadata or {},
            "icon": None,
            "action_label": None,
            "action_link": None,
            "created_at": datetime.utcnow(),
            "read_at": None
        }
        
        result = await db.notifications.insert_one(notification_doc)
        logger.info(f"✅ System notification created for user {user_id}")
        
        return str(result.inserted_id)
        
    except Exception as e:
        logger.error(f"❌ Failed to create system notification: {e}")
        return None