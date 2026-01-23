"""
Personalized AI Service - ENHANCED WITH HISTORY-BASED SCORING (Option 2)

New Features:
- History-based personalized scoring using past outfit preferences
- Analyzes user's favorite outfits and wear patterns
- Learns from outfit ratings and wear frequency
- Combines historical data with weather and occasion matching
- Provides personalized recommendations based on proven preferences

Improvements:
- Full async/await support
- Defensive coding for missing keys
- Proper error handling and logging
- Type hints throughout
- Maintains backward compatibility
"""

from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from app.database import Database
from app.services.weather_service import weather_service

logger = logging.getLogger(__name__)


class PersonalizedAIService:
    """Enhanced AI service with history-based personalized recommendations"""

    async def get_personalized_recommendations(
        self,
        user_id: str,
        location: Optional[str] = None,
        occasion: Optional[str] = None,
        specific_items: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get intelligent personalized outfit recommendations
        
        Uses outfit history to personalize scores based on:
        - Past outfit preferences (favorites, ratings)
        - Wear patterns and frequency
        - Color/style/category preferences
        - Weather-appropriate choices from history
        """
        try:
            logger.info(f"🎯 Starting personalized recommendations for user {user_id}")
            
            # Get database connection
            try:
                db = Database.get_database()
                logger.info("✅ Database connection successful")
            except Exception as db_error:
                logger.error(f"❌ Database connection failed: {db_error}", exc_info=True)
                return {"success": False, "error": f"Database connection failed: {str(db_error)}"}

            # ✅ Fetch user
            try:
                user = await db.users.find_one({"_id": ObjectId(user_id)})
                if not user:
                    logger.warning(f"⚠️ User {user_id} not found")
                    return {"success": False, "error": "User not found"}
                logger.info(f"✅ User found: {user.get('email', 'unknown')}")
            except Exception as user_error:
                logger.error(f"❌ Error fetching user: {user_error}", exc_info=True)
                return {"success": False, "error": f"Error fetching user: {str(user_error)}"}

            # ✅ Fetch wardrobe (try both ObjectId and string)
            try:
                try:
                    wardrobe_cursor = db.clothing_items.find({"user_id": ObjectId(user_id)})
                    wardrobe_items = await wardrobe_cursor.to_list(length=None)
                except:
                    wardrobe_cursor = db.clothing_items.find({"user_id": user_id})
                    wardrobe_items = await wardrobe_cursor.to_list(length=None)
                
                logger.info(f"✅ Found {len(wardrobe_items)} wardrobe items")
                
                if not wardrobe_items:
                    return {
                        "success": False,
                        "error": "No clothing items in wardrobe",
                        "suggestion": "Add some items to your wardrobe first!"
                    }
            except Exception as wardrobe_error:
                logger.error(f"❌ Error fetching wardrobe: {wardrobe_error}", exc_info=True)
                return {"success": False, "error": f"Error fetching wardrobe: {str(wardrobe_error)}"}

            # ✅ Fetch outfit history for personalization
            outfit_history = []
            try:
                try:
                    history_cursor = db.outfit_history.find({"user_id": ObjectId(user_id)})
                    outfit_history = await history_cursor.to_list(length=None)
                except:
                    history_cursor = db.outfit_history.find({"user_id": user_id})
                    outfit_history = await history_cursor.to_list(length=None)
                
                logger.info(f"📚 Found {len(outfit_history)} outfit history entries")
            except Exception as history_error:
                logger.warning(f"⚠️ Could not fetch outfit history (non-critical): {history_error}")
                # Continue without history - will use default scoring

            # ✅ Get weather (async-safe)
            weather_data = None
            if location:
                try:
                    logger.info(f"🌤️ Fetching weather for {location}")
                    result = weather_service.get_current_weather(location)
                    if hasattr(result, "__await__"):
                        weather_data = await result
                    else:
                        weather_data = result
                    logger.info(f"✅ Weather data: {weather_data.get('temperature') if weather_data else 'None'}°C")
                except Exception as weather_error:
                    logger.warning(f"⚠️ Weather fetch failed (non-critical): {weather_error}")

            # ✅ Style preferences
            style_preferences = user.get("style_preferences", [])
            logger.info(f"👔 User style preferences: {style_preferences}")

            # ✅ Analyze user history for personalization
            user_preferences = await self._analyze_user_history(
                outfit_history=outfit_history,
                wardrobe_items=wardrobe_items
            )
            logger.info(f"📊 User preferences analyzed: {len(user_preferences.get('favorite_colors', []))} favorite colors, "
                       f"{len(user_preferences.get('preferred_combinations', []))} preferred combinations")

            # ✅ Generate recommendations with history-based scoring
            try:
                logger.info("🎨 Generating outfit recommendations with personalized scoring...")
                recommendations = await self._generate_recommendations(
                    wardrobe_items=wardrobe_items,
                    weather_data=weather_data,
                    occasion=occasion or "casual",
                    style_preferences=style_preferences,
                    specific_items=specific_items,
                    user_preferences=user_preferences  # NEW: Pass history-based preferences
                )
                logger.info(f"✅ Generated {len(recommendations.get('outfits', []))} outfit recommendations")
            except Exception as gen_error:
                logger.error(f"❌ Error generating recommendations: {gen_error}", exc_info=True)
                return {"success": False, "error": f"Error generating recommendations: {str(gen_error)}"}

            return {
                "success": True,
                "recommendations": recommendations,
                "weather": weather_data,
                "user_style": style_preferences,
                "personalization_data": {
                    "history_entries": len(outfit_history),
                    "favorite_colors": user_preferences.get("favorite_colors", [])[:5],
                    "most_worn_categories": user_preferences.get("most_worn_categories", {})
                }
            }

        except Exception as e:
            logger.error(f"❌ Personalized recommendations failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _analyze_user_history(
        self,
        outfit_history: List[Dict[str, Any]],
        wardrobe_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        NEW METHOD: Analyze user's outfit history to extract preferences
        
        Extracts:
        - Favorite colors (from favorited/highly-rated outfits)
        - Preferred category combinations (tops+bottoms patterns)
        - Most worn items
        - Preferred occasions
        - Average ratings by outfit type
        - Weather preferences (temp ranges user has worn certain items)
        """
        preferences = {
            "favorite_colors": [],
            "preferred_combinations": [],
            "most_worn_items": {},
            "occasion_preferences": {},
            "category_wear_frequency": defaultdict(int),
            "most_worn_categories": {},
            "average_ratings": {},
            "color_ratings": defaultdict(list),
            "weather_preferences": {}
        }
        
        if not outfit_history:
            logger.info("📭 No outfit history available - using default preferences")
            return preferences
        
        try:
            # Track colors from favorite/high-rated outfits
            color_scores = defaultdict(float)
            category_combinations = defaultdict(int)
            item_wear_count = defaultdict(int)
            occasion_count = defaultdict(int)
            
            for outfit in outfit_history:
                # Skip invalid entries
                if not outfit.get("outfit_items"):
                    continue
                
                is_favorite = outfit.get("is_favorite", False)
                rating = outfit.get("rating")
                occasion = outfit.get("occasion", "casual")
                items = outfit.get("outfit_items", [])
                
                # Calculate outfit score (favorite = 5, rating, or default 3)
                outfit_score = 5.0 if is_favorite else (float(rating) if rating else 3.0)
                
                # Track occasions
                occasion_count[occasion] += 1
                
                # Extract colors and categories from outfit items
                outfit_colors = []
                outfit_categories = []
                
                for item in items:
                    color = str(item.get("color", "")).lower().strip()
                    category = str(item.get("category", "")).lower().strip()
                    item_id = str(item.get("id", ""))
                    
                    if color and color not in ["", "none", "unknown"]:
                        outfit_colors.append(color)
                        color_scores[color] += outfit_score
                        
                        # Track color ratings
                        if rating:
                            preferences["color_ratings"][color].append(rating)
                    
                    if category:
                        outfit_categories.append(category)
                        preferences["category_wear_frequency"][category] += 1
                    
                    if item_id:
                        item_wear_count[item_id] += 1
                
                # Track category combinations (e.g., "tops+bottoms", "dress+shoes")
                if len(outfit_categories) >= 2:
                    combo = "+".join(sorted(set(outfit_categories)))
                    category_combinations[combo] += 1
            
            # Sort and extract top preferences
            
            # Favorite colors (by score)
            sorted_colors = sorted(color_scores.items(), key=lambda x: x[1], reverse=True)
            preferences["favorite_colors"] = [color for color, _ in sorted_colors[:10]]
            
            # Preferred combinations
            sorted_combos = sorted(category_combinations.items(), key=lambda x: x[1], reverse=True)
            preferences["preferred_combinations"] = [combo for combo, _ in sorted_combos[:5]]
            
            # Most worn items (by wear count)
            sorted_items = sorted(item_wear_count.items(), key=lambda x: x[1], reverse=True)
            preferences["most_worn_items"] = dict(sorted_items[:10])
            
            # Most worn categories
            sorted_categories = sorted(
                preferences["category_wear_frequency"].items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            preferences["most_worn_categories"] = dict(sorted_categories[:5])
            
            # Occasion preferences (normalized)
            total_occasions = sum(occasion_count.values())
            if total_occasions > 0:
                preferences["occasion_preferences"] = {
                    occ: count / total_occasions 
                    for occ, count in occasion_count.items()
                }
            
            # Average ratings by color
            for color, ratings in preferences["color_ratings"].items():
                if ratings:
                    preferences["average_ratings"][color] = sum(ratings) / len(ratings)
            
            logger.info(f"✅ Analyzed {len(outfit_history)} outfits - "
                       f"Found {len(preferences['favorite_colors'])} favorite colors, "
                       f"{len(preferences['preferred_combinations'])} combo patterns")
            
        except Exception as e:
            logger.error(f"❌ Error analyzing user history: {e}", exc_info=True)
            # Return empty preferences on error
        
        return preferences

    async def _generate_recommendations(
        self,
        wardrobe_items: List[Dict[str, Any]],
        weather_data: Optional[Dict[str, Any]],
        occasion: str,
        style_preferences: List[str],
        specific_items: Optional[List[str]] = None,
        user_preferences: Optional[Dict[str, Any]] = None  # NEW PARAMETER
    ) -> Dict[str, Any]:
        """
        Generate outfit recommendations with history-based personalized scoring
        
        MODIFIED: Now uses user_preferences from history analysis
        """
        try:
            # Filter items if specific items requested
            if specific_items:
                specific_set = set(specific_items)
                wardrobe_items = [
                    item for item in wardrobe_items
                    if str(item.get("_id")) in specific_set or item.get("item_type") in specific_set
                ]

            # Categorize items
            categorized = self._categorize_items(wardrobe_items)

            # Generate outfit combinations
            outfits = self._create_outfit_combinations(
                categorized,
                weather_data,
                occasion
            )

            # NEW: Apply history-based personalized scoring
            if user_preferences and len(user_preferences.get("favorite_colors", [])) > 0:
                logger.info("🎯 Applying history-based personalized scoring")
                for outfit in outfits:
                    personalized_score = self._calculate_personalized_score(
                        outfit,
                        user_preferences,
                        occasion
                    )
                    outfit["personalized_score"] = personalized_score
                    outfit["history_based"] = True
                    
                    # Combine base style score with personalized score
                    base_score = outfit.get("style_score", 50.0)
                    # Weight: 40% base score, 60% personalized score
                    outfit["combined_score"] = (base_score * 0.4) + (personalized_score * 0.6)
                    outfit["style_score"] = outfit["combined_score"]  # Update main score
                
                # Re-sort by personalized combined score
                outfits.sort(key=lambda x: x.get("combined_score", x.get("style_score", 0)), reverse=True)
            else:
                logger.info("📊 Using default scoring (no history available)")
                for outfit in outfits:
                    outfit["history_based"] = False

            # Add reasoning for top outfits
            for outfit in outfits[:10]:  # Add reasoning to top 10
                outfit["reasoning"] = self._generate_reasoning(
                    outfit,
                    weather_data,
                    occasion,
                    user_preferences  # NEW: Pass preferences to reasoning
                )

            return {
                "outfits": outfits[:5],  # Return top 5
                "total_combinations": len(outfits),
                "occasion": occasion,
                "weather_considered": weather_data is not None,
                "personalization_active": user_preferences is not None and len(user_preferences.get("favorite_colors", [])) > 0
            }

        except Exception as e:
            logger.error(f"❌ Generate recommendations failed: {e}", exc_info=True)
            raise

    def _calculate_personalized_score(
        self,
        outfit: Dict[str, Any],
        user_preferences: Dict[str, Any],
        occasion: str
    ) -> float:
        """
        NEW METHOD: Calculate personalized score based on user history
        
        Scoring factors:
        - Color match with favorites (+30 points)
        - Category combination match (+20 points)
        - Item wear frequency (+20 points)
        - Occasion preference match (+15 points)
        - Color rating history (+15 points)
        
        Returns score 0-100
        """
        score = 50.0  # Base score
        items = outfit.get("items", [])
        
        if not items or not user_preferences:
            return score
        
        try:
            # 1. Color matching with favorites
            favorite_colors = user_preferences.get("favorite_colors", [])
            if favorite_colors:
                outfit_colors = [
                    str(item.get("color", "")).lower() 
                    for item in items 
                    if item.get("color")
                ]
                
                matching_colors = sum(1 for color in outfit_colors if color in favorite_colors)
                if outfit_colors:
                    color_match_ratio = matching_colors / len(outfit_colors)
                    score += color_match_ratio * 30  # Up to +30 points
                    logger.debug(f"🎨 Color match: {matching_colors}/{len(outfit_colors)} (+{color_match_ratio * 30:.1f})")
            
            # 2. Category combination matching
            preferred_combos = user_preferences.get("preferred_combinations", [])
            if preferred_combos:
                outfit_categories = [
                    str(item.get("category", "")).lower() 
                    for item in items 
                    if item.get("category")
                ]
                if len(outfit_categories) >= 2:
                    outfit_combo = "+".join(sorted(set(outfit_categories)))
                    if outfit_combo in preferred_combos:
                        score += 20  # +20 points for familiar combination
                        logger.debug(f"🔗 Combo match: {outfit_combo} (+20)")
            
            # 3. Item wear frequency (prefer frequently worn items)
            most_worn = user_preferences.get("most_worn_items", {})
            if most_worn:
                worn_items_in_outfit = sum(
                    1 for item in items 
                    if str(item.get("_id", "")) in most_worn or str(item.get("id", "")) in most_worn
                )
                if items:
                    wear_ratio = worn_items_in_outfit / len(items)
                    score += wear_ratio * 20  # Up to +20 points
                    logger.debug(f"👕 Wear frequency: {worn_items_in_outfit}/{len(items)} (+{wear_ratio * 20:.1f})")
            
            # 4. Occasion preference
            occasion_prefs = user_preferences.get("occasion_preferences", {})
            if occasion.lower() in occasion_prefs:
                # Higher score if this occasion is frequently worn
                occasion_weight = occasion_prefs[occasion.lower()]
                score += occasion_weight * 15  # Up to +15 points
                logger.debug(f"🎯 Occasion match: {occasion} ({occasion_weight:.2f}) (+{occasion_weight * 15:.1f})")
            
            # 5. Color rating history
            avg_ratings = user_preferences.get("average_ratings", {})
            if avg_ratings:
                outfit_colors = [
                    str(item.get("color", "")).lower() 
                    for item in items 
                    if item.get("color")
                ]
                color_ratings = [
                    avg_ratings.get(color, 3.0) 
                    for color in outfit_colors 
                    if color in avg_ratings
                ]
                if color_ratings:
                    avg_color_rating = sum(color_ratings) / len(color_ratings)
                    # Convert 1-5 rating to 0-15 score
                    rating_score = ((avg_color_rating - 1) / 4) * 15
                    score += rating_score
                    logger.debug(f"⭐ Color rating: {avg_color_rating:.1f}/5 (+{rating_score:.1f})")
            
        except Exception as e:
            logger.error(f"❌ Error calculating personalized score: {e}")
            return 50.0  # Return base score on error
        
        return min(max(score, 0), 100)  # Clamp to 0-100

    def _categorize_items(self, items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize wardrobe items by type with smart detection"""
        categories = {
            "tops": [],
            "bottoms": [],
            "dresses": [],
            "outerwear": [],
            "shoes": [],
            "accessories": []
        }
        
        for item in items:
            category = str(item.get("category", "")).lower()
            item_name = str(item.get("item_name", "")).lower()
            
            # Smart category mapping
            if any(word in category or word in item_name for word in [
                "shirt", "t-shirt", "blouse", "top", "sweater", "hoodie", "jersey", "polo", "tank"
            ]):
                categories["tops"].append(item)
            
            elif any(word in category or word in item_name for word in [
                "jeans", "pants", "trousers", "skirt", "shorts", "leggings", "chinos"
            ]):
                categories["bottoms"].append(item)
            
            elif any(word in category or word in item_name for word in [
                "dress", "jumpsuit", "romper", "gown"
            ]):
                categories["dresses"].append(item)
            
            elif any(word in category or word in item_name for word in [
                "jacket", "coat", "blazer", "cardigan", "vest", "parka", "outerwear"
            ]):
                categories["outerwear"].append(item)
            
            elif any(word in category or word in item_name for word in [
                "shoes", "sneakers", "boots", "sandals", "heels", "flats", "loafers"
            ]):
                categories["shoes"].append(item)
            
            elif any(word in category or word in item_name for word in [
                "belt", "scarf", "hat", "bag", "wallet", "watch", "jewelry", "accessories"
            ]):
                categories["accessories"].append(item)
            
            else:
                if category in categories:
                    categories[category].append(item)
                else:
                    categories["tops"].append(item)
        
        logger.info(f"📦 Categorized items: {[(k, len(v)) for k, v in categories.items()]}")
        return categories

    def _create_outfit_combinations(
        self,
        categorized: Dict[str, List[Dict[str, Any]]],
        weather_data: Optional[Dict[str, Any]],
        occasion: str
    ) -> List[Dict[str, Any]]:
        """Create outfit combinations"""
        outfits = []

        tops = categorized.get("tops", [])
        bottoms = categorized.get("bottoms", [])
        shoes = categorized.get("shoes", [])
        dresses = categorized.get("dresses", [])
        
        # Strategy 1: Top + Bottom + Shoes
        if tops and bottoms and shoes:
            for top in tops[:5]:
                for bottom in bottoms[:5]:
                    for shoe in shoes[:3]:
                        outfit = {
                            "items": [top, bottom, shoe],
                            "type": "separates",
                            "style_score": self._calculate_style_score(
                                [top, bottom, shoe],
                                weather_data,
                                occasion
                            )
                        }
                        outfits.append(outfit)

        # Strategy 2: Dress + Shoes
        if dresses and shoes:
            for dress in dresses[:5]:
                for shoe in shoes[:3]:
                    outfit = {
                        "items": [dress, shoe],
                        "type": "dress_outfit",
                        "style_score": self._calculate_style_score(
                            [dress, shoe],
                            weather_data,
                            occasion
                        )
                    }
                    outfits.append(outfit)

        if not outfits:
            logger.warning(f"⚠️ No outfit combinations created. Categories: {[(k, len(v)) for k, v in categorized.items()]}")

        # Sort by style score
        outfits.sort(key=lambda x: x["style_score"], reverse=True)
        return outfits

    def _calculate_style_score(
        self,
        items: List[Dict[str, Any]],
        weather_data: Optional[Dict[str, Any]],
        occasion: str
    ) -> float:
        """Calculate base style score (before personalization)"""
        score = 50.0

        # Color coordination
        colors = [str(item.get("color", "")).lower() for item in items if item.get("color")]
        if colors and len(set(colors)) <= 2:
            score += 20

        # Weather appropriateness
        if weather_data:
            temp = weather_data.get("temperature", 20)
            try:
                temp = float(temp)
            except:
                temp = 20.0

            materials = [str(item.get("material", "")).lower() for item in items if item.get("material")]

            if temp < 10:
                if any(m in ["wool", "fleece", "down", "thermal", "knit"] for m in materials):
                    score += 15
            elif temp > 25:
                if any(m in ["cotton", "linen", "breathable", "light"] for m in materials):
                    score += 15

        # Occasion match
        occasion_keywords = {
            "formal": ["suit", "dress", "blazer", "tie", "heels"],
            "casual": ["jeans", "t-shirt", "sneakers", "shorts"],
            "business": ["trousers", "shirt", "blazer", "slacks"]
        }

        if occasion.lower() in occasion_keywords:
            for item in items:
                name = str(item.get("item_name", "")).lower()
                if any(kw in name for kw in occasion_keywords[occasion.lower()]):
                    score += 10

        return min(score, 100.0)

    def _generate_reasoning(
        self,
        outfit: Dict[str, Any],
        weather_data: Optional[Dict[str, Any]],
        occasion: str,
        user_preferences: Optional[Dict[str, Any]] = None  # NEW PARAMETER
    ) -> str:
        """
        Generate human-readable reasoning for outfit choice
        
        MODIFIED: Now includes personalization reasoning
        """
        items = outfit.get("items", [])
        score = outfit.get("style_score", 50)
        personalized_score = outfit.get("personalized_score")
        
        reasoning_parts = []

        # Base quality assessment
        if score >= 80:
            reasoning_parts.append("This outfit is an excellent choice")
        elif score >= 60:
            reasoning_parts.append("This outfit works well together")
        else:
            reasoning_parts.append("This is a decent outfit option")

        # NEW: Add personalization reasoning
        if personalized_score and user_preferences:
            if personalized_score >= 80:
                reasoning_parts.append("and matches your style preferences perfectly")
            elif personalized_score >= 65:
                reasoning_parts.append("and aligns well with your past outfit choices")
            
            # Mention specific preference matches
            favorite_colors = user_preferences.get("favorite_colors", [])
            if favorite_colors:
                outfit_colors = [
                    str(item.get("color", "")).lower() 
                    for item in items 
                    if item.get("color")
                ]
                matching = [c for c in outfit_colors if c in favorite_colors[:3]]
                if matching:
                    reasoning_parts.append(f"featuring your favorite colors: {', '.join(matching)}")

        # Weather reasoning
        if weather_data:
            temp = weather_data.get("temperature", "")
            condition = weather_data.get("condition", "")
            
            if temp != "":
                try:
                    temp_float = float(temp)
                    reasoning_parts.append(f"For {temp}°C {condition} weather")
                    
                    if temp_float < 10:
                        reasoning_parts.append("these pieces provide good warmth")
                    elif temp_float > 25:
                        reasoning_parts.append("the breathable materials will keep you comfortable")
                except:
                    pass

        # Occasion
        reasoning_parts.append(f"Perfect for a {occasion} occasion")

        # Color coordination
        colors = [str(item.get("color", "")).lower() for item in items if item.get("color")]
        if colors and len(set(colors)) <= 2:
            reasoning_parts.append("The color palette is cohesive and elegant")

        return ". ".join(reasoning_parts) + "."

    async def analyze_outfit_coherence(
        self,
        outfit_items: List[Dict[str, Any]],
        weather_data: Optional[Dict[str, Any]],
        occasion: str,
        user_id: Optional[str] = None  # NEW: Optional for personalization
    ) -> Dict[str, Any]:
        """
        Analyze how well an outfit works together
        
        MODIFIED: Can use user history if user_id provided
        """
        try:
            # Get user preferences if user_id provided
            user_preferences = None
            if user_id:
                try:
                    db = Database.get_database()
                    try:
                        history_cursor = db.outfit_history.find({"user_id": ObjectId(user_id)})
                        outfit_history = await history_cursor.to_list(length=None)
                    except:
                        history_cursor = db.outfit_history.find({"user_id": user_id})
                        outfit_history = await history_cursor.to_list(length=None)
                    
                    user_preferences = await self._analyze_user_history(
                        outfit_history=outfit_history,
                        wardrobe_items=[]
                    )
                except Exception as e:
                    logger.warning(f"Could not fetch user history for analysis: {e}")
            
            # Calculate scores
            base_score = self._calculate_style_score(outfit_items, weather_data, occasion)
            
            outfit_dict = {"items": outfit_items, "type": "custom", "style_score": base_score}
            
            # Add personalized score if available
            if user_preferences:
                personalized_score = self._calculate_personalized_score(
                    outfit_dict,
                    user_preferences,
                    occasion
                )
                combined_score = (base_score * 0.4) + (personalized_score * 0.6)
                outfit_dict["personalized_score"] = personalized_score
                outfit_dict["combined_score"] = combined_score
                final_score = combined_score
            else:
                final_score = base_score
            
            reasoning = self._generate_reasoning(
                outfit_dict,
                weather_data,
                occasion,
                user_preferences
            )
            
            return {
                "score": round(final_score, 1),
                "base_score": round(base_score, 1),
                "personalized_score": round(outfit_dict.get("personalized_score", 0), 1) if user_preferences else None,
                "rating": "excellent" if final_score >= 80 else "good" if final_score >= 60 else "fair",
                "reasoning": reasoning,
                "suggestions": self._generate_improvement_suggestions(outfit_items, final_score, user_preferences),
                "personalization_used": user_preferences is not None
            }
        except Exception as e:
            logger.error(f"❌ Outfit analysis failed: {e}", exc_info=True)
            raise

    def _generate_improvement_suggestions(
        self,
        items: List[Dict[str, Any]],
        score: float,
        user_preferences: Optional[Dict[str, Any]] = None  # NEW
    ) -> List[str]:
        """
        Generate suggestions for improving the outfit
        
        MODIFIED: Uses user preferences for personalized suggestions
        """
        suggestions = []

        # General suggestions
        if score < 60:
            suggestions.append("Consider simplifying the color palette")
            suggestions.append("Ensure materials are weather-appropriate")

        if len(items) > 4:
            suggestions.append("Less is more - try removing one piece")

        colors = [str(item.get("color", "")).lower() for item in items if item.get("color")]
        if colors and len(set(colors)) > 3:
            suggestions.append("Try limiting to 2-3 complementary colors")

        # NEW: Personalized suggestions based on history
        if user_preferences:
            favorite_colors = user_preferences.get("favorite_colors", [])
            outfit_colors = [c for c in colors if c]
            
            # Suggest favorite colors if none used
            if favorite_colors and not any(c in favorite_colors for c in outfit_colors):
                suggestions.append(f"Try incorporating your favorite colors: {', '.join(favorite_colors[:3])}")
            
            # Suggest preferred combinations
            preferred_combos = user_preferences.get("preferred_combinations", [])
            if preferred_combos:
                outfit_categories = [
                    str(item.get("category", "")).lower() 
                    for item in items 
                    if item.get("category")
                ]
                outfit_combo = "+".join(sorted(set(outfit_categories)))
                
                if outfit_combo not in preferred_combos and preferred_combos:
                    top_combo = preferred_combos[0].replace("+", " with ")
                    suggestions.append(f"You usually prefer {top_combo} combinations")

        return suggestions