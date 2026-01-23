# app/models/notification.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId

class NotificationType(str, Enum):
    """Notification types"""
    WEATHER = "weather"
    OUTFIT = "outfit"
    SYSTEM = "system"
    REMINDER = "reminder"
    ACHIEVEMENT = "achievement"

class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationBase(BaseModel):
    """Base notification model"""
    user_id: str
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=500)
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    is_read: bool = False
    deep_link: Optional[str] = None  # Navigation deep link (e.g., "OutfitHistory/123")
    metadata: Optional[Dict[str, Any]] = None  # Additional data
    icon: Optional[str] = None  # Icon name for notification
    action_label: Optional[str] = None  # Action button text
    action_link: Optional[str] = None  # Action button deep link

class NotificationCreate(NotificationBase):
    """Model for creating notification"""
    pass

class NotificationUpdate(BaseModel):
    """Model for updating notification"""
    is_read: Optional[bool] = None

class NotificationResponse(NotificationBase):
    """Model for notification response"""
    id: str = Field(alias="_id")
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class NotificationStats(BaseModel):
    """Notification statistics"""
    total_count: int
    unread_count: int
    by_type: Dict[str, int]
    recent_count: int  # Last 24 hours