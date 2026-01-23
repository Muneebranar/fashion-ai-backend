# app/models/push_notification.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class PushNotificationPriority(str, Enum):
    """Push notification priority"""
    DEFAULT = "default"
    NORMAL = "normal"
    HIGH = "high"

class PushNotificationSound(str, Enum):
    """Notification sound options"""
    DEFAULT = "default"
    CUSTOM = "custom"
    NONE = None

class ExpoPushToken(BaseModel):
    """Expo push token model"""
    # ✅ FIXED: Changed 'regex' to 'pattern' for Pydantic v2
    # ✅ FIXED: Properly escaped the regex pattern
    token: str = Field(..., pattern=r"^ExponentPushToken\[.+\]$")
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    platform: Optional[str] = None  # ios, android

class PushNotificationData(BaseModel):
    """Push notification data structure"""
    title: str = Field(..., max_length=200)
    body: str = Field(..., max_length=500)
    data: Optional[Dict[str, Any]] = None
    priority: PushNotificationPriority = PushNotificationPriority.DEFAULT
    sound: Optional[str] = "default"
    badge: Optional[int] = None
    channel_id: Optional[str] = None  # Android only
    category_id: Optional[str] = None  # iOS only
    ttl: Optional[int] = None  # Time to live in seconds
    expiration: Optional[int] = None  # Expiration timestamp
    mutable_content: Optional[bool] = None  # iOS only

class NotificationSettings(BaseModel):
    """User notification settings"""
    notifications_enabled: bool = True
    daily_outfit_reminder: bool = True
    daily_outfit_time: str = "09:00"  # HH:MM format
    weather_alerts: bool = True
    outfit_suggestions: bool = True
    achievement_notifications: bool = True
    system_notifications: bool = True
    favorite_match_alerts: bool = True