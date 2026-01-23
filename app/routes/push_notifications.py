# app/routes/push_notifications.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.database import get_database
from app.utils.auth import get_current_user
from app.models.push_notification import (
    ExpoPushToken,
    PushNotificationData,
    NotificationSettings
)
from app.services.push_notification_service import push_notification_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["Push Notifications"])

# ============================================
# REGISTER PUSH TOKEN
# ============================================

@router.post("/register-token")
async def register_push_token(
    token_data: ExpoPushToken,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Register Expo push token for the user
    
    - Stores token in user's document
    - Supports multiple devices
    - Validates Expo token format
    """
    try:
        logger.info(f"📱 Registering push token for user: {current_user['email']}")
        
        # Get existing tokens
        user = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
        existing_tokens = user.get("push_tokens", [])
        
        # Ensure it's a list
        if isinstance(existing_tokens, str):
            existing_tokens = [existing_tokens]
        
        # Add new token if not already present
        if token_data.token not in existing_tokens:
            existing_tokens.append(token_data.token)
            
            # Update user document
            await db.users.update_one(
                {"_id": ObjectId(current_user["_id"])},
                {
                    "$set": {
                        "push_tokens": existing_tokens,
                        "last_token_update": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"✅ Push token registered successfully")
        else:
            logger.info(f"ℹ️ Token already registered")
        
        return {
            "success": True,
            "message": "Push token registered successfully",
            "token_count": len(existing_tokens)
        }
        
    except Exception as e:
        logger.error(f"❌ Error registering push token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register push token: {str(e)}"
        )

# ============================================
# REMOVE PUSH TOKEN
# ============================================

@router.delete("/remove-token")
async def remove_push_token(
    token: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Remove a push token from user's account"""
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(current_user["_id"])},
            {"$pull": {"push_tokens": token}}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Push token removed")
            return {"success": True, "message": "Token removed"}
        else:
            return {"success": False, "message": "Token not found"}
        
    except Exception as e:
        logger.error(f"❌ Error removing token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================
# UPDATE NOTIFICATION SETTINGS
# ============================================

@router.put("/settings")
async def update_notification_settings(
    settings: NotificationSettings,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Update user's notification preferences
    
    - Enable/disable notifications
    - Configure daily reminders
    - Set alert preferences
    """
    try:
        logger.info(f"⚙️ Updating notification settings for user: {current_user['email']}")
        
        settings_dict = settings.dict()
        
        result = await db.users.find_one_and_update(
            {"_id": ObjectId(current_user["_id"])},
            {"$set": {"notification_settings": settings_dict}},
            return_document=True
        )
        
        logger.info(f"✅ Notification settings updated")
        
        return {
            "success": True,
            "message": "Settings updated successfully",
            "settings": result.get("notification_settings", {})
        }
        
    except Exception as e:
        logger.error(f"❌ Error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================
# GET NOTIFICATION SETTINGS
# ============================================

@router.get("/settings", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get user's notification settings"""
    try:
        user = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
        
        settings = user.get("notification_settings", {
            "notifications_enabled": True,
            "daily_outfit_reminder": True,
            "daily_outfit_time": "09:00",
            "weather_alerts": True,
            "outfit_suggestions": True,
            "achievement_notifications": True,
            "system_notifications": True,
            "favorite_match_alerts": True
        })
        
        return NotificationSettings(**settings)
        
    except Exception as e:
        logger.error(f"❌ Error getting settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================
# SEND TEST NOTIFICATION
# ============================================

@router.post("/test")
async def send_test_notification(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Send a test push notification to verify setup"""
    try:
        logger.info(f"🧪 Sending test notification to user: {current_user['email']}")
        
        result = await push_notification_service.send_to_user(
            user_id=current_user["_id"],
            title="🎉 Test Notification",
            body="Your push notifications are working perfectly!",
            data={"type": "test"},
            db=db
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Test notification sent successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to send notification")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test notification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ============================================
# TRIGGER DAILY REMINDER (FOR TESTING)
# ============================================

@router.post("/trigger-daily-reminder")
async def trigger_daily_reminder(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Manually trigger daily outfit reminder (for testing)"""
    try:
        background_tasks.add_task(
            push_notification_service.send_daily_outfit_reminder,
            current_user["_id"],
            db
        )
        
        return {
            "success": True,
            "message": "Daily reminder scheduled"
        }
        
    except Exception as e:
        logger.error(f"❌ Error triggering reminder: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )