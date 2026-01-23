# app/services/outfit_service.py - COMPLETE FIXED VERSION WITH PROPER INDENTATION

import logging
from typing import List, Dict, Optional, Any, Tuple
from bson import ObjectId
from datetime import datetime
import uuid
import random

from app.database import Database
from app.services.weather_service import weather_service
from app.services.personalized_ai_service import PersonalizedAIService

logger = logging.getLogger(__name__)

class OutfitService:
    def __init__(self):
        # Lazy database connection
        self._db = None
        self.personalized_ai = PersonalizedAIService()
        logger.info("OutfitService initialized with enhanced features")
    
    async def _get_db(self):
        """Lazy database connection"""
        if self._db is None:
            try:
                self._db = Database.get_database()
                logger.info("✅ Database connected in OutfitService")
            except Exception as e:
                logger.error(f"❌ Database connection failed: {e}")
                self._db = None
        return self._db
  # ============ ENHANCED WARDROBE METHODS ============
    
    async def get_user_wardrobe(self, user_id: str) -> List[Dict]:
        """Get ACTUAL user wardrobe from database with enhanced processing"""
        try:
            db = await self._get_db()
            if db is not None:
                # FIX: Use 'clothing_items' collection (not 'clothing')
                try:
                    items = await db.clothing_items.find({"user_id": user_id}).to_list(length=None)
                except Exception as e:
                    logger.error(f"Error querying clothing_items: {e}")
                    items = []
                
                # If no items found with string, try ObjectId format
                if not items:
                    try:
                        items = await db.clothing_items.find({"user_id": ObjectId(user_id)}).to_list(length=None)
                    except:
                        items = []
                
                logger.info(f"Found {len(items)} actual wardrobe items for user: {user_id}")
                
                # Process items - add missing data, categorize, etc.
                processed_items = []
                for item in items:
                    processed_item = self._process_clothing_item(item)
                    processed_items.append(processed_item)
                
                return processed_items
            
            logger.warning("Database not available, returning empty list")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching wardrobe items: {e}", exc_info=True)
            return []
    
    def _process_clothing_item(self, item: Dict) -> Dict:
        """Process and enhance clothing item data"""
        processed = item.copy()
        
        # CRITICAL FIX: Convert ALL ObjectIds to strings for JSON serialization
        for key, value in processed.items():
            if isinstance(value, ObjectId):
                processed[key] = str(value)
        
        # Ensure ID is string for frontend
        if '_id' in processed:
            processed['id'] = str(processed['_id'])
            processed['_id'] = str(processed['_id'])  # Convert _id too
        
        # Ensure user_id is string
        if 'user_id' in processed:
            if isinstance(processed['user_id'], ObjectId):
                processed['user_id'] = str(processed['user_id'])
        
        # Detect category if missing
        if not processed.get('category'):
            processed['category'] = self._detect_category(item)
        
        # Detect subcategory
        if not processed.get('subcategory'):
            processed['subcategory'] = self._detect_subcategory(item)
        
        # Detect seasonality
        if not processed.get('season'):
            processed['season'] = self._detect_seasonality(item)
        
        # Detect formality level
        if not processed.get('formality'):
            processed['formality'] = self._detect_formality(item)
        
        # Ensure material is lowercase for consistency
        if processed.get('material'):
            processed['material'] = processed['material'].lower()
        
        # Ensure color is standardized
        if processed.get('color'):
            processed['color'] = self._standardize_color(processed['color'])
        
        return processed
    
    def _detect_category(self, item: Dict) -> str:
        """Detect clothing category from item data"""
        name = item.get('item_name', '').lower()
        description = item.get('description', '').lower()
        
        # Check for tops
        if any(word in name for word in ['shirt', 't-shirt', 'blouse', 'top', 'sweater', 'hoodie', 'jersey', 'polo']):
            return 'tops'
        
        # Check for bottoms
        if any(word in name for word in ['jeans', 'pants', 'trousers', 'skirt', 'shorts', 'leggings', 'chinos']):
            return 'bottoms'
        
        # Check for dresses
        if any(word in name for word in ['dress', 'jumpsuit', 'romper', 'gown']):
            return 'dresses'
        
        # Check for outerwear
        if any(word in name for word in ['jacket', 'coat', 'blazer', 'cardigan', 'vest', 'parka']):
            return 'outerwear'
        
        # Check for shoes
        if any(word in name for word in ['shoes', 'sneakers', 'boots', 'sandals', 'heels', 'flats', 'loafers']):
            return 'shoes'
        
        # Check for accessories
        if any(word in name for word in ['belt', 'scarf', 'hat', 'bag', 'wallet', 'watch', 'jewelry']):
            return 'accessories'
        
        return 'other'
    
    def _detect_subcategory(self, item: Dict) -> str:
        """Detect more specific subcategory"""
        name = item.get('item_name', '').lower()
        category = item.get('category', '').lower()
        
        if category == 'tops':
            if 't-shirt' in name or 'tee' in name:
                return 't-shirt'
            elif 'shirt' in name:
                return 'shirt'
            elif 'sweater' in name or 'jumper' in name:
                return 'sweater'
            elif 'hoodie' in name:
                return 'hoodie'
            elif 'blouse' in name:
                return 'blouse'
        
        elif category == 'bottoms':
            if 'jeans' in name:
                return 'jeans'
            elif 'pants' in name or 'trousers' in name:
                return 'pants'
            elif 'shorts' in name:
                return 'shorts'
            elif 'skirt' in name:
                return 'skirt'
        
        return 'general'
    
    def _detect_seasonality(self, item: Dict) -> List[str]:
        """Detect which seasons the item is appropriate for"""
        material = item.get('material', '').lower()
        category = item.get('category', '').lower()
        
        seasons = []
        
        # Winter items
        if any(word in material for word in ['wool', 'fleece', 'thermal', 'down', 'cashmere', 'knit']):
            seasons.append('winter')
            seasons.append('fall')
        
        # Summer items
        if any(word in material for word in ['linen', 'cotton', 'breathable', 'light', 'seersucker']):
            seasons.append('summer')
            seasons.append('spring')
        
        # All-season items
        if not seasons:
            seasons = ['spring', 'summer', 'fall', 'winter']
        
        return seasons
    
    def _detect_formality(self, item: Dict) -> str:
        """Detect formality level"""
        name = item.get('item_name', '').lower()
        category = item.get('category', '').lower()
        
        # Formal items
        if any(word in name for word in ['suit', 'blazer', 'tuxedo', 'dress shirt', 'tie', 'heels', 'loafers']):
            return 'formal'
        
        # Business casual
        if any(word in name for word in ['dress pants', 'button-down', 'blouse', 'slacks', 'oxfords']):
            return 'business'
        
        # Casual
        if any(word in name for word in ['t-shirt', 'jeans', 'sneakers', 'hoodie', 'shorts']):
            return 'casual'
        
        # Sport
        if any(word in name for word in ['activewear', 'joggers', 'tank', 'gym', 'sport']):
            return 'sport'
        
        return 'casual'  # Default
    
    def _standardize_color(self, color: str) -> str:
        """Standardize color names"""
        color_lower = color.lower()
        
        color_map = {
            'navy': ['navy', 'dark blue', 'deep blue'],
            'blue': ['blue', 'light blue', 'sky blue'],
            'black': ['black', 'charcoal', 'dark'],
            'white': ['white', 'ivory', 'cream', 'off-white'],
            'gray': ['gray', 'grey', 'slate'],
            'red': ['red', 'crimson', 'scarlet'],
            'green': ['green', 'olive', 'emerald'],
            'brown': ['brown', 'tan', 'beige', 'khaki'],
            'purple': ['purple', 'violet', 'lavender'],
            'yellow': ['yellow', 'gold', 'mustard'],
            'pink': ['pink', 'rose', 'blush'],
            'orange': ['orange', 'rust', 'coral']
        }
        
        for standard_color, variants in color_map.items():
            if any(variant in color_lower for variant in variants):
                return standard_color
        
        return color_lower
    
    # ============ CORE OUTFIT GENERATION ============
    
    async def generate_suggestions(
        self,
        user_id: str,
        occasion: str = "casual",
        count: int = 10,
        location: Optional[str] = None,
        weather_data: Optional[Dict] = None
    ) -> List[Dict]:
        """Generate AI-powered outfit suggestions"""
        try:
            logger.info(f"Generating {count} outfit suggestions for user {user_id}")
            
            # Get user's wardrobe
            wardrobe = await self.get_user_wardrobe(user_id)
            
            if not wardrobe:
                logger.warning(f"No wardrobe found for user {user_id}")
                return self._get_mock_outfits(occasion, location, count)
            
            logger.info(f"User has {len(wardrobe)} wardrobe items")
            
            # Get weather data if location provided
            if location and not weather_data:
                weather_data = weather_service.get_current_weather(location)
                if weather_data:
                    weather_data['category'] = weather_service.get_temperature_category(
                        weather_data.get('temperature', 20)
                    )
            
            # Categorize items
            categorized = self._categorize_items(wardrobe)
            
            # Generate outfit combinations
            outfits = []
            seen_combinations = set()  # Track unique combinations
            attempts = 0
            max_attempts = count * 20  # Increase attempts
            
            while len(outfits) < count and attempts < max_attempts:
                outfit = self._create_outfit_from_categories(categorized, occasion)
                
                if outfit and self._is_outfit_valid(outfit, occasion):
                    # Create a signature for this outfit to avoid duplicates
                    item_ids = tuple(sorted([
                        item.get('id') or str(item.get('_id')) 
                        for item in outfit['items']
                    ]))
                    
                    # Skip if we've seen this exact combination
                    if item_ids in seen_combinations:
                        attempts += 1
                        continue
                    
                    seen_combinations.add(item_ids)
                    
                    # Score the outfit
                    scored_outfit = await self.score_outfit(
                        outfit, 
                        user_id, 
                        occasion, 
                        weather_data
                    )
                    
                    # Add weather score if we have weather data
                    if weather_data:
                        weather_score = self._calculate_weather_score(outfit['items'], weather_data)
                        scored_outfit['weather_score'] = weather_score
                        scored_outfit['combined_score'] = (
                            scored_outfit.get('style_score', 0.7) * 0.3 + 
                            scored_outfit.get('color_score', 0.7) * 0.25 +
                            scored_outfit.get('occasion_score', 0.7) * 0.25 +
                            weather_score * 0.2
                        )
                        scored_outfit['is_weather_appropriate'] = weather_score >= 0.6
                    
                    outfits.append(scored_outfit)
                
                attempts += 1
            
            # Sort by combined score
            outfits.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
            
            logger.info(f"✅ Generated {len(outfits)} outfit suggestions from {attempts} attempts")
            return outfits[:count]
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}", exc_info=True)
            return self._get_mock_outfits(occasion, location, count)
    
    def _categorize_items(self, items: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize items by type for easy selection"""
        categorized = {
            "tops": [],
            "bottoms": [],
            "dresses": [],
            "outerwear": [],
            "shoes": [],
            "accessories": []
        }
        
        for item in items:
            category = item.get("category", "").lower()
            item_name = item.get("item_name", "").lower()
            
            # More flexible categorization
            if any(word in category or word in item_name for word in 
                   ["shirt", "top", "blouse", "t-shirt", "tee", "sweater", "tank", "polo", "jersey"]):
                categorized["tops"].append(item)
            
            elif any(word in category or word in item_name for word in 
                     ["pant", "jean", "trouser", "skirt", "short", "legging", "chino"]):
                categorized["bottoms"].append(item)
            
            elif any(word in category or word in item_name for word in 
                     ["dress", "gown", "jumpsuit", "romper"]):
                categorized["dresses"].append(item)
            
            elif any(word in category or word in item_name for word in 
                     ["jacket", "coat", "hoodie", "blazer", "cardigan", "vest", "parka", "windbreaker"]):
                categorized["outerwear"].append(item)
            
            elif any(word in category or word in item_name for word in 
                     ["shoe", "boot", "sandal", "sneaker", "heel", "flat", "loafer", "slipper"]):
                categorized["shoes"].append(item)
            
            elif any(word in category or word in item_name for word in 
                     ["accessory", "accessories", "bag", "hat", "cap", "scarf", "belt", "watch", "jewelry", "sunglass"]):
                categorized["accessories"].append(item)
            
            else:
                # Default: if unknown, try to guess from item name or put in tops
                logger.warning(f"Unknown category for item: {item.get('item_name')} - category: {category}")
                categorized["tops"].append(item)  # Default to tops
        
        # Log categorization results
        logger.info(f"Categorized items: {', '.join([f'{k}: {len(v)}' for k, v in categorized.items()])}")
        
        return categorized
    
    def _create_outfit_from_categories(
        self, 
        categorized: Dict[str, List[Dict]], 
        occasion: str
    ) -> Optional[Dict]:
        """Create a single outfit from categorized items"""
        try:
            # Select items based on occasion
            items = []
            used_item_ids = set()
            
            # Strategy 1: Dress-based outfit (30% chance)
            if categorized["dresses"] and random.random() < 0.3:
                dress = random.choice(categorized["dresses"])
                items.append(dress)
                used_item_ids.add(dress.get('id') or str(dress.get('_id')))
                
                # Add shoes with dress
                if categorized["shoes"]:
                    shoes = random.choice(categorized["shoes"])
                    items.append(shoes)
                    used_item_ids.add(shoes.get('id') or str(shoes.get('_id')))
                
                # Maybe add outerwear
                if categorized["outerwear"] and random.random() < 0.4:
                    outerwear = random.choice(categorized["outerwear"])
                    items.append(outerwear)
                    used_item_ids.add(outerwear.get('id') or str(outerwear.get('_id')))
                
                # Maybe add 1 accessory
                if categorized["accessories"] and random.random() < 0.5:
                    accessory = random.choice(categorized["accessories"])
                    items.append(accessory)
            
            else:
                # Strategy 2: Top + Bottom combination (70% chance)
                
                # MUST have top
                if categorized["tops"]:
                    top = random.choice(categorized["tops"])
                    items.append(top)
                    used_item_ids.add(top.get('id') or str(top.get('_id')))
                
                # MUST have bottom
                if categorized["bottoms"]:
                    bottom = random.choice(categorized["bottoms"])
                    items.append(bottom)
                    used_item_ids.add(bottom.get('id') or str(bottom.get('_id')))
                
                # SHOULD have shoes (80% chance)
                if categorized["shoes"] and random.random() < 0.8:
                    shoes = random.choice(categorized["shoes"])
                    items.append(shoes)
                    used_item_ids.add(shoes.get('id') or str(shoes.get('_id')))
                
                # Add outerwear based on occasion (50-70% chance)
                outerwear_chance = 0.7 if occasion in ["formal", "business", "winter"] else 0.4
                if categorized["outerwear"] and random.random() < outerwear_chance:
                    outerwear = random.choice(categorized["outerwear"])
                    items.append(outerwear)
                    used_item_ids.add(outerwear.get('id') or str(outerwear.get('_id')))
                
                # Add 1-2 accessories (60% chance)
                if categorized["accessories"] and random.random() < 0.6:
                    num_accessories = min(2, len(categorized["accessories"]))
                    available_accessories = [
                        acc for acc in categorized["accessories"]
                        if (acc.get('id') or str(acc.get('_id'))) not in used_item_ids
                    ]
                    if available_accessories:
                        num_to_add = random.randint(1, min(num_accessories, len(available_accessories)))
                        accessories = random.sample(available_accessories, num_to_add)
                        items.extend(accessories)
            
            if not items or len(items) < 2:
                return None
            
            # Create outfit object
            outfit_name = self._generate_outfit_name(items, occasion)
            outfit_id = f"outfit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
            
            return {
                "outfit_id": outfit_id,
                "name": outfit_name,
                "items": items,
                "occasion": occasion,
                "created_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating outfit: {e}")
            return None
    
    def _is_outfit_valid(self, outfit: Dict, occasion: str) -> bool:
        """Check if outfit is valid for the occasion"""
        items = outfit.get("items", [])
        if len(items) < 2:  # Need at least 2 items
            return False
        
        # Check for dress completeness
        has_dress = any(item.get("category", "").lower() == "dresses" for item in items)
        if has_dress:
            # Dress should be standalone or with minimal additions
            return True
        
        # For other outfits, need at least top and bottom
        has_top = any(
            item.get("category", "").lower() in ["tops", "shirt", "blouse", "t-shirt", "sweater"]
            for item in items
        )
        
        has_bottom = any(
            item.get("category", "").lower() in ["bottoms", "pants", "jeans", "skirt", "shorts"]
            for item in items
        )
        
        return has_top and has_bottom
    
    def _generate_outfit_name(self, items: List[Dict], occasion: str) -> str:
        """Generate a descriptive name for the outfit"""
        colors = []
        categories = []
        
        for item in items[:3]:  # Look at first 3 items
            color = item.get("color", "")
            category = item.get("category", "").split()[0] if item.get("category") else ""
            
            if color and color not in colors:
                colors.append(color.capitalize())
            if category and category.lower() not in [c.lower() for c in categories]:
                categories.append(category)
        
        if colors:
            if categories:
                return f"{' & '.join(colors[:2])} {occasion.capitalize()} Outfit"
            else:
                return f"{' & '.join(colors[:2])} Outfit"
        else:
            return f"{occasion.capitalize()} Outfit #{random.randint(1, 100)}"
    
    # ============ ENHANCED WEATHER SCORING ============
    
    def _calculate_weather_score(self, items: List[Dict], weather_data: Dict) -> float:
        """Better weather scoring based on actual items"""
        if not items or not weather_data:
            return 0.5
        
        score = 0.5
        temp = weather_data.get("temperature", 20)
        condition = weather_data.get("condition", "").lower()
        category = weather_data.get("category", "moderate")
        
        for item in items:
            material = item.get("material", "").lower()
            category_type = item.get("category", "").lower()
            
            # Temperature-based scoring
            if category in ["cold", "freezing"]:  # Very cold
                if any(warm in material for warm in ["wool", "fleece", "thermal", "down", "cashmere", "knit"]):
                    score += 0.15
                if category_type in ["coat", "jacket", "sweater", "hoodie"]:
                    score += 0.1
                if item.get("subcategory") in ["parka", "puffer", "winter coat"]:
                    score += 0.2
            
            elif category == "cool":  # Cool
                if any(mat in material for mat in ["cotton", "denim", "light wool"]):
                    score += 0.1
                if category_type in ["jacket", "cardigan", "light sweater"]:
                    score += 0.1
            
            elif category in ["hot", "warm"]:  # Warm/Hot
                if any(mat in material for mat in ["cotton", "linen", "breathable", "light"]):
                    score += 0.15
                if category_type in ["t-shirt", "shorts", "dress", "tank", "skirt"]:
                    score += 0.1
                if "sleeveless" in item.get("item_name", "").lower():
                    score += 0.05
        
            # Weather condition adjustments
            if "rain" in condition:
                if "waterproof" in material or "rain" in category_type:
                    score += 0.25
                if category_type == "shoes" and "waterproof" in material:
                    score += 0.2
            
            if "snow" in condition:
                if any(mat in material for mat in ["waterproof", "insulated", "thermal"]):
                    score += 0.3
                if item.get("subcategory") in ["snow boots", "winter boots"]:
                    score += 0.2
            
            if "wind" in condition:
                if category_type in ["jacket", "coat"] and "wind" in material:
                    score += 0.15
            
            if "sun" in condition or "clear" in condition:
                if category_type in ["hat", "cap"]:
                    score += 0.1
        
        # Penalize inappropriate items
        for item in items:
            material = item.get("material", "").lower()
            category_type = item.get("category", "").lower()
            
            if category in ["hot", "warm"]:
                if any(hot in material for hot in ["wool", "fleece", "thermal"]):
                    score -= 0.1
                if category_type in ["coat", "heavy jacket"]:
                    score -= 0.15
            
            if category in ["cold", "freezing"]:
                if any(cold in material for cold in ["linen", "light cotton"]):
                    score -= 0.1
                if category_type in ["shorts", "tank", "sleeveless"]:
                    score -= 0.2
        
        return min(max(score, 0), 1)  # Ensure between 0 and 1
    
    # ============ OUTFIT SCORING ============
    
    async def score_outfit(
        self,
        outfit: Dict,
        user_id: str,
        occasion: str,
        weather_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Score an outfit on multiple dimensions"""
        try:
            items = outfit.get("items", [])
            
            # Style score (random for now, but could be based on AI analysis)
            style_score = random.uniform(0.6, 0.95)
            
            # Color coordination score
            color_score = self._calculate_color_score(items)
            
            # Occasion appropriateness
            occasion_score = self._calculate_occasion_score(items, occasion)
            
            # Weather score (if weather data provided)
            weather_score = 1.0
            if weather_data:
                weather_score = self._calculate_weather_score(items, weather_data)
            
            # Combined score
            combined_score = (style_score * 0.3 + 
                            color_score * 0.25 + 
                            occasion_score * 0.25 + 
                            weather_score * 0.2)
            
            return {
                **outfit,
                "scores": {
                    "style_score": round(style_score, 2),
                    "color_score": round(color_score, 2),
                    "occasion_score": round(occasion_score, 2),
                    "weather_score": round(weather_score, 2),
                    "combined_score": round(combined_score, 2)
                },
                "is_weather_appropriate": weather_score >= 0.6,
                "analysis": {
                    "color_coordination": "Good" if color_score > 0.7 else "Needs improvement",
                    "style_coherence": "Excellent" if style_score > 0.8 else "Good",
                    "occasion_appropriateness": "Perfect" if occasion_score > 0.8 else "Appropriate"
                }
            }
            
        except Exception as e:
            logger.error(f"Error scoring outfit: {e}")
            return {**outfit, "scores": {}, "analysis": {}}
    
    def _calculate_color_score(self, items: List[Dict]) -> float:
        """Calculate color coordination score"""
        if not items:
            return 0.5
        
        colors = [item.get("color", "").lower() for item in items if item.get("color")]
        
        if not colors:
            return 0.5
        
        # Basic color coordination rules
        neutral_colors = ["black", "white", "gray", "navy", "beige", "brown"]
        
        # Check if colors are complementary
        score = 0.5
        
        # Bonus for monochromatic
        if len(set(colors)) == 1:
            score += 0.2
        
        # Bonus for neutral base
        if any(color in neutral_colors for color in colors[:2]):  # First two items
            score += 0.1
        
        # Penalty for too many bright colors
        bright_colors = ["red", "yellow", "orange", "pink", "purple"]
        bright_count = sum(1 for color in colors if color in bright_colors)
        if bright_count > 2:
            score -= 0.1
        
        return min(max(score, 0), 1)
    
    def _calculate_occasion_score(self, items: List[Dict], occasion: str) -> float:
        """Calculate occasion appropriateness score"""
        if not items:
            return 0.5
        
        score = 0.5
        
        # Get formality levels
        formality_scores = {
            "formal": 0.9,
            "business": 0.7,
            "casual": 0.5,
            "sport": 0.3
        }
        
        # Calculate average formality
        formalities = []
        for item in items:
            formality = item.get("formality", "casual")
            formalities.append(formality_scores.get(formality, 0.5))
        
        if formalities:
            avg_formality = sum(formalities) / len(formalities)
            
            # Score based on occasion
            occasion_targets = {
                "formal": 0.8,
                "business": 0.7,
                "casual": 0.5,
                "sport": 0.3,
                "party": 0.6,
                "beach": 0.4,
                "date": 0.6
            }
            
            target = occasion_targets.get(occasion.lower(), 0.5)
            # Score is higher when formality matches target
            score = 1.0 - abs(avg_formality - target)
        
        return min(max(score, 0), 1)
    
    # ============ SEASONAL RECOMMENDATIONS ============
    
    def get_seasonal_recommendations(self, month: int = None) -> Dict[str, Any]:
        """Get recommendations based on season"""
        from datetime import datetime
        
        if month is None:
            month = datetime.now().month
        
        seasons = {
            12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "fall", 10: "fall", 11: "fall"
        }
        
        season = seasons.get(month, "spring")
        
        seasonal_colors = {
            "winter": ["navy", "burgundy", "charcoal", "ivory", "white", "black", "gray"],
            "spring": ["pastel blue", "mint", "coral", "light pink", "lavender", "yellow"],
            "summer": ["white", "light blue", "bright red", "yellow", "turquoise", "orange"],
            "fall": ["mustard", "olive", "rust", "brown", "burgundy", "dark green"]
        }
        
        seasonal_materials = {
            "winter": ["wool", "cashmere", "fleece", "down", "knit"],
            "spring": ["light cotton", "linen blend", "chambray", "denim"],
            "summer": ["linen", "cotton", "seersucker", "breathable fabrics"],
            "fall": ["wool blend", "corduroy", "tweed", "flannel"]
        }
        
        seasonal_tips = {
            "winter": [
                "Layer clothing for better insulation",
                "Protect extremities with gloves and hat",
                "Choose darker colors that absorb heat"
            ],
            "spring": [
                "Transition from heavy to light layers",
                "Bright colors reflect the spring mood",
                "Carry a light jacket for changing temperatures"
            ],
            "summer": [
                "Choose light, breathable fabrics",
                "Light colors reflect sunlight",
                "Stay hydrated and wear sunscreen"
            ],
            "fall": [
                "Perfect weather for layering",
                "Rich, warm colors match the season",
                "Have a versatile jacket ready"
            ]
        }
        
        return {
            "season": season,
            "month": month,
            "recommended_colors": seasonal_colors.get(season, []),
            "recommended_materials": seasonal_materials.get(season, []),
            "tips": seasonal_tips.get(season, []),
            "description": self._get_season_description(season)
        }
    
    def _get_season_description(self, season: str) -> str:
        """Get description for season"""
        descriptions = {
            "winter": "Cold weather season - focus on warmth and insulation",
            "spring": "Transition season - mix of light layers and brighter colors",
            "summer": "Warm season - light fabrics and breathable materials",
            "fall": "Cooling season - rich colors and comfortable layers"
        }
        return descriptions.get(season, "General fashion season")
    
    # ============ MOCK DATA ============
    
    def _get_mock_outfits(self, occasion: str, location: str, count: int) -> List[Dict]:
        """Generate mock outfit suggestions for testing"""
        outfits = []
        
        mock_items = [
            {"id": "mock_1", "item_name": "White Cotton T-Shirt", "category": "tops", "color": "white", "image_url": None},
            {"id": "mock_2", "item_name": "Blue Denim Jeans", "category": "bottoms", "color": "blue", "image_url": None},
            {"id": "mock_3", "item_name": "Black Leather Jacket", "category": "outerwear", "color": "black", "image_url": None},
            {"id": "mock_4", "item_name": "White Sneakers", "category": "shoes", "color": "white", "image_url": None},
            {"id": "mock_5", "item_name": "Beige Chinos", "category": "bottoms", "color": "brown", "image_url": None},
            {"id": "mock_6", "item_name": "Gray Hoodie", "category": "tops", "color": "gray", "image_url": None}
        ]
        
        for i in range(min(count, 3)):
            outfit_id = f"mock_outfit_{i+1}_{datetime.now().strftime('%H%M%S')}"
            
            # Create different outfit combinations
            if i == 0:
                items = [mock_items[0], mock_items[1], mock_items[3]]
                name = "Casual Streetwear"
            elif i == 1:
                items = [mock_items[0], mock_items[4], mock_items[3]]
                name = "Smart Casual"
            else:
                items = [mock_items[5], mock_items[1], mock_items[2], mock_items[3]]
                name = "Urban Style"
            
            style_score = round(random.uniform(0.7, 0.9), 2)
            color_score = round(random.uniform(0.6, 0.8), 2)
            occasion_score = round(random.uniform(0.7, 0.9), 2)
            weather_score = round(random.uniform(0.8, 1.0), 2)
            combined_score = round((style_score + color_score + occasion_score + weather_score) / 4, 2)
            
            outfits.append({
                "outfit_id": outfit_id,
                "name": f"{name} - {occasion.capitalize()}",
                "items": items,
                "occasion": occasion,
                "created_at": datetime.now().isoformat(),
                "scores": {
                    "style_score": style_score,
                    "color_score": color_score,
                    "occasion_score": occasion_score,
                    "weather_score": weather_score,
                    "combined_score": combined_score
                },
                "is_weather_appropriate": True,
                "is_mock": True,
                "analysis": {
                    "color_coordination": "Good",
                    "style_coherence": "Excellent",
                    "occasion_appropriateness": "Perfect"
                }
            })
        
        logger.info(f"Generated {len(outfits)} mock outfit suggestions")
        return outfits
    
    # ============ OUTFIT SAVING ============
    
    async def save_outfit(self, user_id: str, outfit_data: Dict, occasion: str = "casual") -> Dict[str, Any]:
        """Save an outfit combination to database"""
        try:
            db = await self._get_db()
            if db is None:
                return {"success": False, "error": "Database not available"}
            
            # Prepare outfit document
            outfit_doc = {
                "user_id": ObjectId(user_id),
                "name": outfit_data.get("name", f"My {occasion.capitalize()} Outfit"),
                "items": outfit_data.get("items", []),
                "occasion": occasion,
                "scores": outfit_data.get("scores", {}),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "weather": outfit_data.get("weather", {}),
                "tags": outfit_data.get("tags", []),
                "notes": outfit_data.get("notes", ""),
                "is_favorite": outfit_data.get("is_favorite", False),
                "outfit_id": outfit_data.get("outfit_id", str(uuid.uuid4())[:8])
            }
            
            # Add seasonal info
            season_info = self.get_seasonal_recommendations()
            outfit_doc["season"] = season_info.get("season")
            
            # Save to database
            result = await db.saved_outfits.insert_one(outfit_doc)
            
            logger.info(f"Outfit saved for user {user_id}: {outfit_doc['name']}")
            
            return {
                "success": True,
                "outfit_id": str(result.inserted_id),
                "outfit_data": {
                    "id": str(result.inserted_id),
                    "name": outfit_doc["name"],
                    "occasion": outfit_doc["occasion"],
                    "created_at": outfit_doc["created_at"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error saving outfit: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def get_saved_outfits(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get user's saved outfits"""
        try:
            db = await self._get_db()
            if db is None:
                return []
            
            outfits = await db.saved_outfits.find(
                {"user_id": ObjectId(user_id)}
            ).sort("created_at", -1).limit(limit).to_list(length=None)
            
            # Convert ObjectId to string
            for outfit in outfits:
                outfit["_id"] = str(outfit["_id"])
                outfit["user_id"] = str(outfit["user_id"])
            
            logger.info(f"Retrieved {len(outfits)} saved outfits for user {user_id}")
            return outfits
            
        except Exception as e:
            logger.error(f"Error getting saved outfits: {e}")
            return []
    
    async def delete_saved_outfit(self, user_id: str, outfit_id: str) -> Dict[str, Any]:
        """Delete a saved outfit"""
        try:
            db = await self._get_db()
            if db is None:
                return {"success": False, "error": "Database not available"}
            
            result = await db.saved_outfits.delete_one({
                "_id": ObjectId(outfit_id),
                "user_id": ObjectId(user_id)
            })
            
            if result.deleted_count > 0:
                logger.info(f"Outfit {outfit_id} deleted for user {user_id}")
                return {"success": True, "deleted_count": result.deleted_count}
            else:
                return {"success": False, "error": "Outfit not found or not authorized"}
                
        except Exception as e:
            logger.error(f"Error deleting outfit: {e}")
            return {"success": False, "error": str(e)}
    
    # ============ OTHER METHODS ============
    
    async def get_detailed_outfit_analysis(
        self,
        outfit_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get detailed analysis for a specific outfit"""
        try:
            # For now, return mock analysis
            return {
                "success": True,
                "outfit_id": outfit_id,
                "analysis": {
                    "color_coordination": "Good - neutral base with one pop of color",
                    "style_coherence": "Excellent - all pieces work well together",
                    "occasion_appropriateness": "Perfect for casual occasions",
                    "weather_suitability": "Appropriate for current conditions",
                    "improvement_suggestions": [
                        "Add a statement accessory",
                        "Consider different footwear for dressier occasions",
                        "Try layering with a light jacket"
                    ],
                    "style_tips": [
                        "This outfit works well for day-to-night transitions",
                        "The color palette is versatile and can be accessorized in multiple ways",
                        "Consider adding texture with different materials"
                    ]
                },
                "recommendations": {
                    "similar_items": ["Add a belt for definition", "Try a different shoe color"],
                    "alternative_items": ["Replace with darker jeans for evening", "Add a scarf for colder weather"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting outfit analysis: {e}")
            return {"success": False, "error": str(e)}
    
    def _has_complementary_colors(self, colors: List[str]) -> bool:
        """Check if colors are complementary"""
        if not colors or len(colors) < 2:
            return True
        
        # Simple complementary check - ensure not too many conflicting bright colors
        bright_colors = ["red", "yellow", "orange", "pink", "purple"]
        bright_count = sum(1 for color in colors if color in bright_colors)
        
        return bright_count <= 2
    
    async def generate_outfit_combinations(
        self,
        wardrobe_items: List[Dict],
        occasion: str = "casual",
        max_combinations: int = 50
    ) -> List[Dict]:
        """Generate multiple outfit combinations from wardrobe items"""
        # For now, generate a limited number of combinations
        categorized = self._categorize_items(wardrobe_items)
        combinations = []
        
        for _ in range(min(max_combinations, 10)):
            outfit = self._create_outfit_from_categories(categorized, occasion)
            if outfit and self._is_outfit_valid(outfit, occasion):
                combinations.append(outfit)
        
        return combinations


# Singleton instance
outfit_service = OutfitService()