# app/services/push_notification_service.py
import requests
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from bson import ObjectId  # ✅ ADD THIS IMPORT
from app.database import get_database

logger = logging.getLogger(__name__)

class PushNotificationService:
    """Service for sending Expo push notifications"""
    
    EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
    MAX_BATCH_SIZE = 100  # Expo limit
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
        })
    
    async def send_push_notification(
        self,
        push_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "default",
        sound: str = "default",
        badge: Optional[int] = None,
        channel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send push notification to one or more devices
        
        Args:
            push_tokens: List of Expo push tokens
            title: Notification title
            body: Notification body
            data: Additional data payload
            priority: default, normal, or high
            sound: default or custom sound name
            badge: Badge count (iOS)
            channel_id: Android notification channel
        
        Returns:
            Dict with success status and results
        """
        try:
            if not push_tokens:
                logger.warning("No push tokens provided")
                return {"success": False, "error": "No push tokens"}
            
            # Filter valid tokens
            valid_tokens = [
                token for token in push_tokens 
                if token and token.startswith('ExponentPushToken[')
            ]
            
            if not valid_tokens:
                logger.warning("No valid Expo push tokens")
                return {"success": False, "error": "No valid tokens"}
            
            # Prepare messages
            messages = []
            for token in valid_tokens:
                message = {
                    "to": token,
                    "title": title,
                    "body": body,
                    "priority": priority,
                    "sound": sound,
                }
                
                if data:
                    message["data"] = data
                
                if badge is not None:
                    message["badge"] = badge
                
                if channel_id:
                    message["channelId"] = channel_id
                
                messages.append(message)
            
            # Send in batches
            results = []
            for i in range(0, len(messages), self.MAX_BATCH_SIZE):
                batch = messages[i:i + self.MAX_BATCH_SIZE]
                batch_result = await self._send_batch(batch)
                results.extend(batch_result)
            
            # Process results
            success_count = sum(1 for r in results if r.get('status') == 'ok')
            error_count = len(results) - success_count
            
            logger.info(f"📤 Push notifications sent: {success_count} success, {error_count} errors")
            
            return {
                "success": True,
                "total": len(results),
                "success_count": success_count,
                "error_count": error_count,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"❌ Push notification error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_batch(self, messages: List[Dict]) -> List[Dict]:
        """Send a batch of push notifications"""
        try:
            response = await asyncio.to_thread(
                self.session.post,
                self.EXPO_PUSH_URL,
                json=messages,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data.get('data', [])
            
        except requests.RequestException as e:
            logger.error(f"❌ Batch send error: {e}")
            return [{"status": "error", "message": str(e)} for _ in messages]
    
    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        db = None
    ) -> Dict[str, Any]:
        """
        Send push notification to a specific user
        
        Args:
            user_id: User ID (string)
            title: Notification title
            body: Notification body
            data: Additional data
            db: Database connection
        """
        try:
            if db is None:
                from app.database import Database
                db = Database.get_database()
            
            # ✅ FIX: Convert string user_id to ObjectId for MongoDB query
            try:
                user_oid = ObjectId(user_id)
            except Exception as e:
                logger.error(f"❌ Invalid user_id format: {user_id}")
                return {"success": False, "error": f"Invalid user_id: {str(e)}"}
            
            # Get user's push tokens
            user = await db.users.find_one({"_id": user_oid})
            
            if not user:
                logger.error(f"❌ User not found with id: {user_id}")
                return {"success": False, "error": "User not found"}
            
            logger.info(f"✅ Found user: {user.get('email', 'unknown')}")
            
            # Check notification settings
            settings = user.get("notification_settings", {})
            if not settings.get("notifications_enabled", True):
                logger.info(f"Notifications disabled for user {user_id}")
                return {"success": False, "error": "Notifications disabled"}
            
            # Get push tokens
            push_tokens = user.get("push_tokens", [])
            if isinstance(push_tokens, str):
                push_tokens = [push_tokens]
            
            if not push_tokens:
                logger.warning(f"⚠️ No push tokens for user {user.get('email', user_id)}")
                return {"success": False, "error": "No push tokens"}
            
            logger.info(f"📱 Found {len(push_tokens)} push token(s) for user")
            
            # Send notification
            result = await self.send_push_notification(
                push_tokens=push_tokens,
                title=title,
                body=body,
                data=data
            )
            
            # Log notification in database
            try:
                await db.push_logs.insert_one({
                    "user_id": user_oid,
                    "title": title,
                    "body": body,
                    "data": data,
                    "success": result.get("success"),
                    "sent_at": datetime.utcnow()
                })
            except Exception as log_error:
                logger.warning(f"⚠️ Failed to log notification: {log_error}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Send to user error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def send_to_multiple_users(
        self,
        user_ids: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        db = None
    ) -> Dict[str, Any]:
        """Send push notification to multiple users"""
        try:
            if db is None:
                from app.database import Database
                db = Database.get_database()
            
            # Collect all push tokens
            all_tokens = []
            
            for user_id in user_ids:
                try:
                    user_oid = ObjectId(user_id)
                    user = await db.users.find_one({"_id": user_oid})
                    if user:
                        settings = user.get("notification_settings", {})
                        if settings.get("notifications_enabled", True):
                            tokens = user.get("push_tokens", [])
                            if isinstance(tokens, str):
                                tokens = [tokens]
                            all_tokens.extend(tokens)
                except Exception as e:
                    logger.warning(f"⚠️ Skipping invalid user_id {user_id}: {e}")
                    continue
            
            if not all_tokens:
                return {"success": False, "error": "No push tokens found"}
            
            # Send to all tokens
            result = await self.send_push_notification(
                push_tokens=all_tokens,
                title=title,
                body=body,
                data=data
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Send to multiple users error: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_daily_outfit_reminder(self, user_id: str, db = None):
        """Send daily outfit reminder"""
        try:
            if db is None:
                from app.database import Database
                db = Database.get_database()
            
            user_oid = ObjectId(user_id)
            user = await db.users.find_one({"_id": user_oid})
            if not user:
                return
            
            settings = user.get("notification_settings", {})
            if not settings.get("daily_outfit_reminder", True):
                return
            
            # Get weather for user's location
            from app.services.weather_service import weather_service
            location = user.get("location", "New York")
            weather = weather_service.get_current_weather(location)
            
            if weather:
                temp = weather.get("temperature", 72)
                condition = weather.get("condition", "Sunny")
                
                title = f"☀️ Good Morning! It's {temp}°F"
                body = f"{condition} today - Time to pick your outfit!"
            else:
                title = "☀️ Good Morning!"
                body = "Time to pick your perfect outfit for the day!"
            
            await self.send_to_user(
                user_id=user_id,
                title=title,
                body=body,
                data={
                    "type": "daily_reminder",
                    "screen": "Suggestions"
                },
                db=db
            )
            
            logger.info(f"📤 Daily reminder sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Daily reminder error: {e}")
    
    async def send_weather_alert(
        self,
        user_id: str,
        weather_condition: str,
        message: str,
        db = None
    ):
        """Send weather-based alert"""
        try:
            if db is None:
                from app.database import Database
                db = Database.get_database()
            
            user_oid = ObjectId(user_id)
            user = await db.users.find_one({"_id": user_oid})
            if not user:
                return
            
            settings = user.get("notification_settings", {})
            if not settings.get("weather_alerts", True):
                return
            
            await self.send_to_user(
                user_id=user_id,
                title=f"🌤️ Weather Alert: {weather_condition}",
                body=message,
                data={
                    "type": "weather_alert",
                    "screen": "Home"
                },
                db=db
            )
            
        except Exception as e:
            logger.error(f"❌ Weather alert error: {e}")
    
    async def send_outfit_suggestion_notification(
        self,
        user_id: str,
        outfit_count: int,
        db = None
    ):
        """Send notification about new outfit suggestions"""
        try:
            if db is None:
                from app.database import Database
                db = Database.get_database()
            
            user_oid = ObjectId(user_id)
            user = await db.users.find_one({"_id": user_oid})
            if not user:
                return
            
            settings = user.get("notification_settings", {})
            if not settings.get("outfit_suggestions", True):
                return
            
            await self.send_to_user(
                user_id=user_id,
                title="✨ New Outfit Suggestions Ready!",
                body=f"We've created {outfit_count} personalized outfit suggestions for you",
                data={
                    "type": "outfit_suggestion",
                    "screen": "Suggestions"
                },
                db=db
            )
            
        except Exception as e:
            logger.error(f"❌ Outfit suggestion notification error: {e}")
    
    async def send_achievement_notification(
        self,
        user_id: str,
        achievement_title: str,
        achievement_message: str,
        db = None
    ):
        """Send achievement notification"""
        try:
            if db is None:
                from app.database import Database
                db = Database.get_database()
            
            user_oid = ObjectId(user_id)
            user = await db.users.find_one({"_id": user_oid})
            if not user:
                return
            
            settings = user.get("notification_settings", {})
            if not settings.get("achievement_notifications", True):
                return
            
            await self.send_to_user(
                user_id=user_id,
                title=f"🏆 {achievement_title}",
                body=achievement_message,
                data={
                    "type": "achievement",
                    "screen": "Profile"
                },
                db=db
            )
            
        except Exception as e:
            logger.error(f"❌ Achievement notification error: {e}")

# Singleton instance
push_notification_service = PushNotificationService()