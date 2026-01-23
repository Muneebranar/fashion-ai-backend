"""
AI Recommendations Routes - Intelligent outfit suggestions
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import logging
import traceback

from app.utils.auth import get_current_user
from app.services.personalized_ai_service import PersonalizedAIService
from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-recommendations", tags=["AI Recommendations"])

ai_service = PersonalizedAIService()


@router.get("/personalized")
async def get_personalized_recommendations(
    location: Optional[str] = Query(None, description="Location for weather"),
    occasion: Optional[str] = Query(None, description="Occasion (casual, formal, etc.)"),
    include_items: Optional[List[str]] = Query(None, description="Include specific items"),
    current_user: dict = Depends(get_current_user)
):
    """
    🧠 Get intelligent personalized outfit recommendations
    """
    try:
        # Extract user ID
        current_user_id = str(current_user["_id"])
        logger.info(f"Personalized AI request from user {current_user_id}, location={location}, occasion={occasion}")

        # Call service
        result = await ai_service.get_personalized_recommendations(
            user_id=current_user_id,
            location=location,
            occasion=occasion,
            specific_items=include_items
        )

        logger.info(f"Service result: success={result.get('success')}, error={result.get('error')}")

        # Check result
        if not result.get("success"):
            error_msg = result.get("error", "AI service failed")
            logger.warning(f"AI service returned error: {error_msg}")
            
            # Return 200 with error info for empty wardrobe (NOT a 500 error!)
            if "No clothing items" in error_msg or "wardrobe" in error_msg.lower():
                return {
                    "success": False,
                    "error": error_msg,
                    "suggestion": result.get("suggestion", "Add items to your wardrobe first!"),
                    "recommendations": {
                        "outfits": [],
                        "total_combinations": 0,
                        "occasion": occasion or "casual",
                        "weather_considered": location is not None
                    },
                    "weather": None,
                    "user_style": []
                }
            
            # For other critical errors, return error response but still 200
            return {
                "success": False,
                "error": error_msg,
                "recommendations": {
                    "outfits": [],
                    "total_combinations": 0,
                    "occasion": occasion or "casual",
                    "weather_considered": False
                }
            }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Personalized recommendations route failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return 200 with error info instead of 500
        return {
            "success": False,
            "error": str(e),
            "recommendations": {
                "outfits": [],
                "total_combinations": 0,
                "occasion": occasion or "casual",
                "weather_considered": False
            }
        }



@router.post("/outfit/analyze")
async def analyze_outfit_coherence(
    outfit_data: dict,
    location: Optional[str] = None,
    occasion: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        weather_data = {}

        if location:
            from app.services.weather_service import weather_service
            weather = weather_service.get_current_weather(location)
            if weather:
                weather_data = {
                    "temperature": weather.get("temperature"),
                    "condition": weather.get("condition"),
                    "humidity": weather.get("humidity")
                }

        analysis = await ai_service.analyze_outfit_coherence(
            outfit_items=outfit_data.get("items", []),
            weather_data=weather_data,
            occasion=occasion or outfit_data.get("occasion", "casual")
        )

        return {
            "success": True,
            "analysis": analysis,
            "outfit": outfit_data
        }

    except Exception as e:
        logger.error(f"Outfit analysis failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Outfit analysis failed: {str(e)}"
        )


@router.get("/style/profile")
async def get_user_style_profile(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    try:
        # ✅ FIX: extract user id
        current_user_id = str(current_user["_id"])

        from app.services.ai_agent_service import FashionAIAgent
        ai_agent = FashionAIAgent()

        style_profile = await ai_agent.analyze_user_style(current_user_id, db)

        insights = {
            "minimalist": "You prefer clean lines and simple silhouettes",
            "bold_expressive": "You're not afraid to make a statement",
            "formal_classic": "You value timeless elegance and quality",
            "casual_comfort": "You prioritize comfort without sacrificing style"
        }

        style_type = style_profile.get("style_profile", "balanced")

        return {
            "success": True,
            "style_profile": style_profile,
            "fashion_personality": insights.get(style_type, "Well-balanced style"),
            "recommended_brands": _get_recommended_brands(style_type),
            "style_evolution_tips": _get_evolution_tips(style_profile)
        }

    except Exception as e:
        logger.error(f"Style profile analysis failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Style analysis failed: {str(e)}"
        )


def _get_recommended_brands(style_type: str) -> List[str]:
    brand_map = {
        "minimalist": ["COS", "Uniqlo", "Everlane", "Arket", "Muji"],
        "bold_expressive": ["Gucci", "Versace", "Moschino", "D&G", "JW Anderson"],
        "formal_classic": ["Brooks Brothers", "Ralph Lauren", "Burberry", "Tom Ford", "Brunello Cucinelli"],
        "casual_comfort": ["Lululemon", "Patagonia", "Aritzia", "Madewell", "Reformation"]
    }
    return brand_map.get(style_type, ["Zara", "Mango", "H&M", "Massimo Dutti"])


def _get_evolution_tips(style_profile: dict) -> List[str]:
    tips = []

    if style_profile.get("total_items", 0) < 20:
        tips.append("Consider building a capsule wardrobe with versatile basics")

    if len(style_profile.get("favorite_colors", [])) < 2:
        tips.append("Experiment with adding one new color to your palette")

    style_type = style_profile.get("style_profile")
    if style_type == "casual_comfort":
        tips.append("Try incorporating one dressier piece each week")
    elif style_type == "formal_classic":
        tips.append("Mix in casual pieces to create interesting contrasts")

    return tips