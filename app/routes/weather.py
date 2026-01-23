from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Dict
from bson import ObjectId
import logging

from app.utils.auth import get_current_user  # ✅ IMPORT get_current_user
from app.services.weather_service import weather_service
from app.database import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weather", tags=["Weather"])

@router.get("/current")
async def get_current_weather(
    location: str = Query("New York", description="Location to get weather for"),
    include_recommendations: bool = Query(True, description="Include clothing recommendations"),
    current_user: dict = Depends(get_current_user)  # ✅ USE get_current_user
):
    """
    Get current weather with clothing recommendations
    """
    try:
        logger.info(f"🌤️ Getting weather for location: {location} for user: {current_user.get('email')}")
        
        # Get user's location from database if available
        if location == "New York":
            db = Database.get_database()
            user = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
            if user and user.get("location"):
                location = user["location"]
                logger.info(f"Using user's location from DB: {location}")
        
        # Get weather data
        weather_data = None
        try:
            weather_data = weather_service.get_current_weather(location)
        except Exception as e:
            logger.warning(f"Weather API failed: {e}")
        
        # If no real data, use mock data
        if not weather_data:
            logger.info("Using mock weather data")
            weather_data = weather_service.get_mock_weather(location)
        
        # Add temperature category
        temp_c = weather_data.get('temperature', 20)
        weather_data['category'] = weather_service.get_temperature_category(temp_c)
        
        # Get dress recommendations
        dress_recommendation = weather_service.get_dress_recommendation(weather_data)
        weather_data['dress_recommendation'] = dress_recommendation
        
        response = {
            "success": True,
            "data": weather_data,
            "location": location,
            "is_mock": weather_data.get('is_mock', False)
        }
        
        # Add recommendations if requested
        if include_recommendations:
            response["recommendations"] = {
                "dress_recommendation": dress_recommendation,
                "materials": weather_service.get_clothing_material_recommendations(
                    weather_data.get('category', 'moderate'),
                    weather_data.get('condition', '').lower()
                ),
                "tips": weather_service.get_weather_tips(weather_data)
            }
        
        logger.info(f"✅ Weather data retrieved for {location}: {weather_data.get('condition')}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Weather service error: {e}")
        # Return mock data on error
        mock_data = weather_service.get_mock_weather(location)
        mock_data['category'] = weather_service.get_temperature_category(mock_data.get('temperature', 20))
        mock_data['dress_recommendation'] = weather_service.get_dress_recommendation(mock_data)
        
        return {
            "success": True,
            "data": mock_data,
            "location": location,
            "is_mock": True
        }

@router.get("/forecast")
async def get_forecast(
    location: str = Query("New York", description="Location to get forecast for"),
    days: int = Query(7, ge=1, le=16, description="Number of days to forecast (1-16)"),
    current_user: dict = Depends(get_current_user)  # ✅ USE get_current_user
):
    """
    Get weather forecast for upcoming days
    """
    try:
        # Get user's location from database if available
        if location == "New York":
            db = Database.get_database()
            user = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
            if user and user.get("location"):
                location = user["location"]
        
        forecast = weather_service.get_forecast(location, days)
        
        if not forecast:
            raise HTTPException(
                status_code=500,
                detail="Could not fetch forecast"
            )
        
        # Add categories to each day
        for day in forecast:
            temp_c = day.get('temperature', 20)
            day['category'] = weather_service.get_temperature_category(temp_c)
            day['dress_recommendation'] = weather_service.get_dress_recommendation(day)
        
        return {
            "success": True,
            "location": location,
            "days": days,
            "forecast": forecast
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast error: {str(e)}")

@router.get("/clothing-recommendations")
async def get_clothing_recommendations(
    location: str = Query("New York", description="Location for weather"),
    current_user: dict = Depends(get_current_user)  # ✅ USE get_current_user
):
    """
    Get clothing recommendations based on weather
    """
    try:
        # Get user's location from database if available
        if location == "New York":
            db = Database.get_database()
            user = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
            if user and user.get("location"):
                location = user["location"]
        
        weather_data = weather_service.get_current_weather(location)
        
        if not weather_data:
            raise HTTPException(
                status_code=500,
                detail="Could not fetch weather data"
            )
        
        # Add temperature category
        temp_c = weather_data.get('temperature', 20)
        weather_data['category'] = weather_service.get_temperature_category(temp_c)
        
        # Get comprehensive recommendations
        recommendations = {
            "dress_recommendation": weather_service.get_dress_recommendation(weather_data),
            "materials": weather_service.get_clothing_material_recommendations(
                weather_data.get('category', 'moderate'),
                weather_data.get('condition', '').lower()
            ),
            "tips": weather_service.get_weather_tips(weather_data),
            "layers": weather_service.get_clothing_recommendations(weather_data)
        }
        
        return {
            "success": True,
            "weather": weather_data,
            "recommendations": recommendations,
            "location": location
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendations error: {str(e)}")

@router.get("/outfit-recommendations")
async def get_weather_outfit_recommendations(
    location: str = Query("New York", description="Location for weather"),
    temperature: Optional[float] = Query(None, description="Override temperature (for testing)"),
    condition: Optional[str] = Query(None, description="Override condition (for testing)"),
    current_user: dict = Depends(get_current_user)  # ✅ USE get_current_user
):
    """
    Get comprehensive outfit recommendations based on weather
    """
    try:
        # Get or create weather data
        if temperature is not None or condition is not None:
            # Use provided parameters for testing
            weather_data = {
                "temperature": temperature or 20,
                "condition": condition or "Clear",
                "location": location,
                "category": weather_service.get_temperature_category(temperature or 20)
            }
        else:
            # Get real weather
            weather_data = weather_service.get_current_weather(location)
            if not weather_data:
                raise HTTPException(status_code=404, detail="Weather data not found")
            
            # Add temperature category
            temp_c = weather_data.get('temperature', 20)
            weather_data['category'] = weather_service.get_temperature_category(temp_c)
        
        # Get detailed recommendations
        recommendations = {
            "weather": weather_data,
            "dress_recommendation": weather_service.get_dress_recommendation(weather_data),
            "materials": weather_service.get_clothing_material_recommendations(
                weather_data.get('category', 'moderate'),
                weather_data.get('condition', '').lower()
            ),
            "tips": weather_service.get_weather_tips(weather_data),
            "outfit_suggestions": weather_service.generate_clothing_recommendations(weather_data)
        }
        
        return {
            "success": True,
            "data": recommendations,
            "location": location,
            "is_mock": temperature is not None or condition is not None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendations error: {str(e)}")

@router.get("/hourly")
async def get_hourly_forecast(
    location: str = Query("New York", description="Location for forecast"),
    hours: int = Query(24, ge=1, le=168, description="Number of hours to forecast (1-168)"),
    current_user: dict = Depends(get_current_user)  # ✅ USE get_current_user
):
    """
    Get hourly weather forecast
    """
    try:
        # First get coordinates
        location_info = weather_service.get_coordinates(location)
        if not location_info:
            raise HTTPException(status_code=404, detail="Location not found")
        
        # Get hourly forecast
        hourly_forecast = weather_service.get_hourly_forecast(
            location_info["latitude"],
            location_info["longitude"],
            hours
        )
        
        if not hourly_forecast:
            raise HTTPException(status_code=500, detail="Could not fetch hourly forecast")
        
        return {
            "success": True,
            "location": location,
            "hours": len(hourly_forecast),
            "forecast": hourly_forecast
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hourly forecast error: {str(e)}")