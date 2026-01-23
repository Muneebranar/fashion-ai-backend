# app/tasks/notification_scheduler.py
import asyncio
import logging
from datetime import datetime, time
from typing import List
from app.database import Database
from app.services.push_notification_service import push_notification_service

logger = logging.getLogger(__name__)

class NotificationScheduler:
    """Background task scheduler for push notifications"""
    
    def __init__(self):
        self.running = False
    
    async def start(self):
        """Start the notification scheduler"""
        self.running = True
        logger.info("📅 Notification scheduler started")
        
        # Start background tasks
        asyncio.create_task(self.daily_reminder_loop())
        asyncio.create_task(self.weather_alert_loop())
    
    async def stop(self):
        """Stop the notification scheduler"""
        self.running = False
        logger.info("📅 Notification scheduler stopped")
    
    async def daily_reminder_loop(self):
        """Send daily outfit reminders at specified times"""
        while self.running:
            try:
                db = Database.get_database()
                
                # Get current time
                now = datetime.utcnow()
                current_hour = now.hour
                current_minute = now.minute
                
                # Find users whose reminder time matches current time
                # (within 5 minute window)
                users = await db.users.find({
                    "notification_settings.daily_outfit_reminder": True,
                    "notification_settings.notifications_enabled": True
                }).to_list(length=None)
                
                for user in users:
                    settings = user.get("notification_settings", {})
                    reminder_time = settings.get("daily_outfit_time", "09:00")
                    
                    # Parse reminder time
                    try:
                        hour, minute = map(int, reminder_time.split(":"))
                        
                        # Check if it's time to send
                        if (hour == current_hour and 
                            abs(minute - current_minute) < 5):
                            
                            # Check if already sent today
                            last_sent = user.get("last_daily_reminder")
                            if last_sent:
                                last_sent_date = last_sent.date()
                                if last_sent_date == now.date():
                                    continue
                            
                            # Send reminder
                            await push_notification_service.send_daily_outfit_reminder(
                                user_id=str(user["_id"]),
                                db=db
                            )
                            
                            # Update last sent time
                            await db.users.update_one(
                                {"_id": user["_id"]},
                                {"$set": {"last_daily_reminder": now}}
                            )
                            
                    except ValueError:
                        logger.error(f"Invalid reminder time format: {reminder_time}")
                        continue
                
                # Sleep for 1 minute before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Daily reminder loop error: {e}")
                await asyncio.sleep(60)
    
    async def weather_alert_loop(self):
        """Check for weather changes and send alerts"""
        while self.running:
            try:
                db = Database.get_database()
                
                # Get users with weather alerts enabled
                users = await db.users.find({
                    "notification_settings.weather_alerts": True,
                    "notification_settings.notifications_enabled": True
                }).to_list(length=None)
                
                for user in users:
                    try:
                        location = user.get("location", "New York")
                        
                        # Get weather
                        from app.services.weather_service import weather_service
                        weather = weather_service.get_current_weather(location)
                        
                        if weather:
                            condition = weather.get("condition", "").lower()
                            temp = weather.get("temperature", 72)
                            
                            # Check for extreme conditions
                            alert_message = None
                            
                            if "rain" in condition or "storm" in condition:
                                alert_message = "Don't forget your umbrella! Rain expected today."
                            elif "snow" in condition:
                                alert_message = "Snow expected! Dress warmly and wear appropriate footwear."
                            elif temp > 95:
                                alert_message = f"Extreme heat warning! {temp}°F - Stay hydrated and dress light."
                            elif temp < 32:
                                alert_message = f"Freezing temperatures! {temp}°F - Bundle up!"
                            
                            if alert_message:
                                await push_notification_service.send_weather_alert(
                                    user_id=str(user["_id"]),
                                    weather_condition=condition.title(),
                                    message=alert_message,
                                    db=db
                                )
                    
                    except Exception as e:
                        logger.error(f"Weather alert error for user {user.get('_id')}: {e}")
                        continue
                
                # Check every 2 hours
                await asyncio.sleep(7200)
                
            except Exception as e:
                logger.error(f"❌ Weather alert loop error: {e}")
                await asyncio.sleep(7200)

# Singleton instance
notification_scheduler = NotificationScheduler()