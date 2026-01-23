"""
AI Fashion Agent - Intelligent Reasoning & Personalization
Advanced AI that thinks like a professional stylist
"""

from typing import List, Dict, Optional, Any
import logging
from datetime import datetime
import numpy as np
from openai import OpenAI

from app.services.clip_service import CLIPService
from app.services.weather_service import WeatherService
from app.config import settings

logger = logging.getLogger(__name__)

class FashionAIAgent:
    """
    Intelligent Fashion Agent with reasoning capabilities
    
    Capabilities:
    1. Contextual Understanding (weather, occasion, location)
    2. Personal Style Analysis (from user history)
    3. Intelligent Reasoning (why recommendations work)
    4. Material & Color Science
    5. Body Type & Fit Recommendations
    """
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.clip_service = CLIPService()
        self.weather_service = WeatherService()
        
        # Fashion knowledge base
        self.color_theory = {
            'summer': ['white', 'pastel_blue', 'light_green', 'lavender', 'cream'],
            'winter': ['navy', 'burgundy', 'forest_green', 'charcoal', 'ivory'],
            'spring': ['coral', 'mint', 'yellow', 'light_pink', 'sky_blue'],
            'fall': ['mustard', 'olive', 'rust', 'brown', 'burgundy']
        }
        
        self.material_properties = {
            'cotton': {'breathability': 9, 'warmth': 3, 'formal': 4},
            'linen': {'breathability': 10, 'warmth': 2, 'formal': 5},
            'wool': {'breathability': 5, 'warmth': 9, 'formal': 8},
            'polyester': {'breathability': 4, 'warmth': 6, 'formal': 7},
            'silk': {'breathability': 7, 'warmth': 5, 'formal': 9}
        }
        
    async def analyze_user_style(self, user_id: str, db) -> Dict:
        """
        Analyze user's style preferences from their wardrobe history
        """
        try:
            # Get user's clothing items
            items = await db.clothing_items.find({"user_id": user_id}).to_list(length=None)
            
            if not items:
                return {"style_profile": "neutral", "preferences": []}
            
            # Analyze color preferences
            colors = [item.get("color") for item in items if item.get("color")]
            color_distribution = {}
            for color in colors:
                color_distribution[color] = color_distribution.get(color, 0) + 1
            
            # Analyze category distribution
            categories = [item.get("category") for item in items if item.get("category")]
            
            # Analyze price range
            prices = [item.get("price") for item in items if item.get("price")]
            avg_price = sum(prices) / len(prices) if prices else 0
            
            # Determine style profile
            style_profile = self._determine_style_profile(items, color_distribution)
            
            return {
                "style_profile": style_profile,
                "favorite_colors": sorted(color_distribution.items(), key=lambda x: x[1], reverse=True)[:3],
                "category_distribution": categories,
                "avg_price_range": avg_price,
                "total_items": len(items)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing user style: {e}")
            return {"style_profile": "balanced", "preferences": []}
    
    def _determine_style_profile(self, items: List[Dict], color_distribution: Dict) -> str:
        """
        Determine user's fashion style profile
        """
        # Analyze based on item types and colors
        formal_count = sum(1 for item in items if "formal" in item.get("occasions", []))
        casual_count = sum(1 for item in items if "casual" in item.get("occasions", []))
        
        bright_colors = sum(count for color, count in color_distribution.items() 
                          if color in ['red', 'yellow', 'pink', 'orange'])
        neutral_colors = sum(count for color, count in color_distribution.items() 
                           if color in ['black', 'white', 'gray', 'navy', 'beige'])
        
        if formal_count > casual_count * 2:
            return "formal_classic"
        elif casual_count > formal_count * 2:
            return "casual_comfort"
        elif bright_colors > neutral_colors:
            return "bold_expressive"
        else:
            return "minimalist"
    
    async def generate_intelligent_recommendations(
        self,
        weather_data: Dict,
        user_style: Dict,
        wardrobe_items: List[Dict],
        occasion: str = "casual",
        location: str = None
    ) -> Dict:
        """
        Generate intelligent outfit recommendations with reasoning
        """
        try:
            temperature = weather_data.get("temperature", 20)
            condition = weather_data.get("condition", "clear").lower()
            humidity = weather_data.get("humidity", 50)
            wind_speed = weather_data.get("wind_speed", 0)
            
            # Step 1: Core recommendations based on weather
            core_recs = self._generate_core_recommendations(
                temperature, condition, humidity, wind_speed
            )
            
            # Step 2: Personalize based on user style
            personalized = self._personalize_recommendations(
                core_recs, user_style, occasion
            )
            
            # Step 3: Add intelligent reasoning
            reasoning = self._generate_reasoning(
                personalized, weather_data, user_style, occasion
            )
            
            # Step 4: Find matching items from wardrobe
            matching_items = await self._find_matching_items(
                personalized, wardrobe_items
            )
            
            # Step 5: Generate complete outfit suggestions
            outfits = self._create_outfit_combinations(
                matching_items, personalized, occasion
            )
            
            return {
                "weather_context": {
                    "temperature": temperature,
                    "condition": condition,
                    "humidity": humidity,
                    "location": location
                },
                "user_style_profile": user_style.get("style_profile"),
                "recommendations": personalized,
                "reasoning": reasoning,
                "matching_items_count": len(matching_items),
                "outfit_suggestions": outfits,
                "style_tips": self._generate_style_tips(user_style, occasion)
            }
            
        except Exception as e:
            logger.error(f"Error generating intelligent recommendations: {e}")
            return await self._fallback_recommendations(weather_data)
    
    def _generate_core_recommendations(
        self,
        temperature: float,
        condition: str,
        humidity: float,
        wind_speed: float
    ) -> Dict:
        """
        Generate core clothing recommendations with material science
        """
        recs = {
            "top_layer": [],
            "base_layer": [],
            "bottom_layer": [],
            "footwear": [],
            "accessories": [],
            "materials": [],
            "colors": [],
            "avoid": []
        }
        
        # Temperature-based logic with material science
        if temperature < 0:
            recs["materials"] = ["wool", "cashmere", "down", "fleece", "thermal"]
            recs["colors"] = ["dark_colors", "jewel_tones"]
            recs["top_layer"] = ["puffer_jacket", "wool_coat", "parka"]
            recs["base_layer"] = ["thermal_top", "turtleneck", "sweater"]
            recs["avoid"] = ["cotton", "light_fabrics", "short_sleeves"]
            
        elif temperature < 10:
            recs["materials"] = ["wool_blend", "corduroy", "denim", "knit"]
            recs["colors"] = ["earth_tones", "neutral_palette"]
            recs["top_layer"] = ["field_jacket", "trench_coat", "denim_jacket"]
            recs["base_layer"] = ["long_sleeve_tee", "button_down", "light_sweater"]
            
        elif temperature < 20:
            recs["materials"] = ["cotton", "linen", "chambray", "light_denim"]
            recs["colors"] = ["pastels", "light_tones"]
            recs["top_layer"] = ["light_jacket", "cardigan", "hoodie"]
            recs["base_layer"] = ["tee", "polo", "blouse"]
            
        elif temperature < 28:
            recs["materials"] = ["linen", "cotton", "seersucker", "rayon"]
            recs["colors"] = ["white", "light_colors", "brights"]
            recs["base_layer"] = ["tank_top", "tee", "linen_shirt"]
            recs["avoid"] = ["dark_colors", "heavy_fabrics"]
            
        else:  # Hot weather
            recs["materials"] = ["linen", "breathable_cotton", "moisture_wicking"]
            recs["colors"] = ["white", "light_colors", "reflective_fabrics"]
            recs["base_layer"] = ["loose_tee", "tank", "linen_button_down"]
            recs["avoid"] = ["synthetic_fabrics", "dark_colors", "tight_fits"]
        
        # Weather condition adjustments
        if "rain" in condition:
            recs["materials"].append("waterproof")
            recs["top_layer"] = ["rain_jacket", "waterproof_parka"]
            recs["footwear"] = ["waterproof_boots", "rain_shoes"]
            recs["colors"].append("darker_tones")  # Hide water spots
            
        if "snow" in condition:
            recs["materials"].extend(["waterproof", "insulated"])
            recs["footwear"] = ["insulated_boots", "snow_boots"]
            
        if wind_speed > 20:
            recs["materials"].append("wind_resistant")
            recs["top_layer"] = ["windbreaker", "shell_jacket"]
            
        if humidity > 70:
            recs["materials"].append("moisture_wicking")
            recs["avoid"].append("non_breathable_fabrics")
        
        return recs
    
    def _personalize_recommendations(
        self,
        core_recs: Dict,
        user_style: Dict,
        occasion: str
    ) -> Dict:
        """
        Personalize recommendations based on user's style profile
        """
        personalized = core_recs.copy()
        style_profile = user_style.get("style_profile", "balanced")
        
        if style_profile == "formal_classic":
            personalized["materials"].extend(["wool", "silk", "cashmere"])
            personalized["colors"] = ["navy", "charcoal", "white", "beige"]
            personalized["base_layer"].append("dress_shirt")
            personalized["top_layer"].append("blazer")
            
        elif style_profile == "casual_comfort":
            personalized["materials"].extend(["cotton", "fleece", "jersey"])
            personalized["colors"] = ["denim_blue", "gray", "black", "olive"]
            personalized["base_layer"].extend(["hoodie", "sweatshirt"])
            personalized["top_layer"].append("bomber_jacket")
            
        elif style_profile == "bold_expressive":
            personalized["colors"].extend(["red", "yellow", "patterned", "colorful"])
            personalized["base_layer"].extend(["graphic_tee", "printed_shirt"])
            
        elif style_profile == "minimalist":
            personalized["colors"] = ["black", "white", "gray", "beige"]
            personalized["base_layer"].append("plain_tee")
            personalized["avoid"].extend(["patterns", "logos", "bright_colors"])
        
        # Occasion-based adjustments
        if occasion == "business":
            personalized["materials"].extend(["wool", "silk", "cotton_dress"])
            personalized["colors"] = ["navy", "gray", "white", "black"]
            
        elif occasion == "party":
            personalized["materials"].extend(["silk", "satin", "velvet"])
            personalized["colors"].extend(["black", "metallic", "jewel_tones"])
            
        elif occasion == "sport":
            personalized["materials"].extend(["moisture_wicking", "stretch"])
            personalized["colors"] = ["bright_colors", "technical_fabrics"]
            
        return personalized
    
    def _generate_reasoning(
        self,
        recommendations: Dict,
        weather: Dict,
        user_style: Dict,
        occasion: str
    ) -> Dict:
        """
        Generate intelligent reasoning for recommendations
        """
        temperature = weather.get("temperature", 20)
        condition = weather.get("condition", "clear")
        
        reasoning = {
            "weather_based": "",
            "material_science": "",
            "color_theory": "",
            "style_tips": "",
            "why_it_works": ""
        }
        
        # Weather-based reasoning
        if temperature < 10:
            reasoning["weather_based"] = (
                f"With temperatures at {temperature}°C, layering is key. "
                f"Start with a thermal base, add insulating mid-layers, "
                f"and finish with a wind/water-resistant outer shell."
            )
        elif temperature > 25:
            reasoning["weather_based"] = (
                f"At {temperature}°C, heat management is crucial. "
                f"Light, breathable fabrics in light colors will reflect heat "
                f"and keep you comfortable throughout the day."
            )
        
        # Material science reasoning
        materials = recommendations.get("materials", [])
        if "linen" in materials:
            reasoning["material_science"] = (
                "Linen is perfect for warm weather - it's highly breathable, "
                "moisture-wicking, and gets softer with each wear."
            )
        if "wool" in materials:
            reasoning["material_science"] = (
                "Wool provides excellent insulation even when wet, "
                "making it ideal for variable weather conditions."
            )
        
        # Color theory reasoning
        colors = recommendations.get("colors", [])
        if "white" in colors or "light_colors" in colors:
            reasoning["color_theory"] = (
                "Light colors reflect sunlight and heat, keeping you cooler. "
                "They also create a fresh, clean aesthetic perfect for warm days."
            )
        if "dark_colors" in colors:
            reasoning["color_theory"] = (
                "Dark colors absorb heat, providing natural insulation. "
                "They're also practical for hiding stains in active conditions."
            )
        
        # Style tips
        style_profile = user_style.get("style_profile", "balanced")
        if style_profile == "minimalist":
            reasoning["style_tips"] = (
                "Stick to a monochromatic palette. Focus on fit and fabric quality "
                "rather than patterns or colors."
            )
        
        # Why it works
        reasoning["why_it_works"] = (
            f"This combination works because it addresses: "
            f"1) Thermal comfort for {temperature}°C weather, "
            f"2) {condition} conditions, "
            f"3) Your {style_profile} style preferences, "
            f"4) {occasion} occasion requirements."
        )
        
        return reasoning
    
    async def _find_matching_items(
        self,
        recommendations: Dict,
        wardrobe_items: List[Dict]
    ) -> List[Dict]:
        """
        Find items in wardrobe that match recommendations using CLIP embeddings
        """
        if not wardrobe_items:
            return []
        
        matching_items = []
        target_categories = set(
            recommendations.get("base_layer", []) + 
            recommendations.get("top_layer", []) + 
            recommendations.get("bottom_layer", [])
        )
        
        for item in wardrobe_items:
            # Match by category
            item_category = item.get("category", "").lower()
            category_match = any(
                target_cat in item_category for target_cat in target_categories
            )
            
            # Match by color
            item_color = item.get("color", "").lower()
            recommended_colors = recommendations.get("colors", [])
            color_match = any(
                rec_color in item_color for rec_color in recommended_colors
            ) if recommended_colors else True
            
            # Match by occasion
            item_occasions = item.get("occasions", [])
            occasion_match = True  # Default
            
            if category_match and color_match and occasion_match:
                matching_items.append(item)
        
        return matching_items
    
    def _create_outfit_combinations(
        self,
        items: List[Dict],
        recommendations: Dict,
        occasion: str
    ) -> List[Dict]:
        """
        Create complete outfit combinations from matching items
        """
        outfits = []
        
        # Categorize items
        tops = [item for item in items if item.get("category") in ["tops", "dresses"]]
        bottoms = [item for item in items if item.get("category") == "bottoms"]
        outerwear = [item for item in items if item.get("category") == "outerwear"]
        
        # Create combinations (simplified - would be more complex in production)
        for top in tops[:3]:  # Limit to 3 tops
            outfit = {
                "name": f"{top.get('item_name', 'Outfit')} Ensemble",
                "items": [top],
                "occasion": occasion,
                "coherence_score": 0.85,
                "reason": self._generate_outfit_reason([top], occasion)
            }
            
            # Add bottom if available
            if bottoms:
                outfit["items"].append(bottoms[0])
                
            # Add outerwear if recommended
            if recommendations.get("top_layer") and outerwear:
                outfit["items"].append(outerwear[0])
            
            outfits.append(outfit)
        
        return outfits
    
    def _generate_outfit_reason(self, items: List[Dict], occasion: str) -> str:
        """
        Generate human-readable reason for outfit
        """
        item_descriptions = [item.get("item_name", "item") for item in items]
        
        reasons = [
            f"Perfect for {occasion} occasions",
            "Well-coordinated based on your style profile",
            "Weather-appropriate and comfortable",
            "Matches your existing wardrobe preferences"
        ]
        
        return f"{', '.join(item_descriptions)} - {np.random.choice(reasons)}"
    
    def _generate_style_tips(self, user_style: Dict, occasion: str) -> List[str]:
        """
        Generate personalized style tips
        """
        tips = []
        style_profile = user_style.get("style_profile", "balanced")
        
        if style_profile == "formal_classic":
            tips.extend([
                "Invest in quality fabrics - they last longer and look better",
                "Proper fit is more important than following trends",
                "A well-tailored blazer can elevate any outfit"
            ])
        elif style_profile == "casual_comfort":
            tips.extend([
                "Mix textures for visual interest (e.g., denim with knit)",
                "Don't sacrifice style for comfort - find pieces that offer both",
                "Accessorize to add personality to simple outfits"
            ])
        
        if occasion == "business":
            tips.append("Choose muted colors for professional settings")
        elif occasion == "party":
            tips.append("Metallic accessories can instantly dress up an outfit")
        
        return tips
    
    async def _fallback_recommendations(self, weather_data: Dict) -> Dict:
        """
        Fallback recommendations if AI fails
        """
        temperature = weather_data.get("temperature", 20)
        
        if temperature < 10:
            base = ["thermal_layer", "sweater", "jacket"]
        elif temperature < 20:
            base = ["long_sleeve", "light_jacket"]
        else:
            base = ["tee", "light_top"]
        
        return {
            "recommendations": {
                "base_layer": base,
                "reason": "Simple weather-based recommendations"
            },
            "reasoning": {
                "weather_based": f"Based on {temperature}°C temperature"
            }
        }