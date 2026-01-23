"""
Helper utilities for Fashion AI
"""

from datetime import datetime, timedelta
import json
import hashlib
import re
from typing import Any, Dict, List, Optional, Union
from bson import ObjectId

class Helpers:
    """Utility helper class"""
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format datetime to string"""
        return dt.strftime(format_str)
    
    @staticmethod
    def parse_datetime(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
        """Parse string to datetime"""
        try:
            return datetime.strptime(date_str, format_str)
        except ValueError:
            return None
    
    @staticmethod
    def time_ago(dt: datetime) -> str:
        """Convert datetime to human-readable time ago format"""
        now = datetime.utcnow()
        diff = now - dt
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    
    @staticmethod
    def generate_id() -> str:
        """Generate unique ID"""
        return str(ObjectId())
    
    @staticmethod
    def validate_object_id(id_str: str) -> bool:
        """Validate MongoDB ObjectId"""
        try:
            ObjectId(id_str)
            return True
        except:
            return False
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input"""
        if not text:
            return ""
        
        # Remove dangerous characters
        text = re.sub(r'[<>"\']', '', text)
        # Trim whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """Truncate text with ellipsis"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension from filename"""
        return filename.split('.')[-1].lower() if '.' in filename else ""
    
    @staticmethod
    def calculate_age(birth_date: datetime) -> int:
        """Calculate age from birth date"""
        today = datetime.utcnow()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    @staticmethod
    def dict_to_json(data: Dict) -> str:
        """Convert dict to JSON string"""
        return json.dumps(data, default=str)
    
    @staticmethod
    def json_to_dict(json_str: str) -> Dict:
        """Convert JSON string to dict"""
        try:
            return json.loads(json_str)
        except:
            return {}
    
    @staticmethod
    def hash_string(text: str) -> str:
        """Create hash of string"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def get_season(date: datetime = None) -> str:
        """Get season based on date"""
        if not date:
            date = datetime.utcnow()
        
        month = date.month
        
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"
    
    @staticmethod
    def extract_colors(text: str) -> List[str]:
        """Extract color names from text"""
        colors = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'gray', 
                  'pink', 'purple', 'orange', 'brown', 'beige', 'navy', 'maroon']
        
        found = []
        text_lower = text.lower()
        
        for color in colors:
            if color in text_lower:
                found.append(color)
        
        return found
    
    @staticmethod
    def get_temperature_range(temp: float) -> str:
        """Get temperature range description"""
        if temp < 0:
            return "freezing"
        elif temp < 10:
            return "cold"
        elif temp < 20:
            return "cool"
        elif temp < 28:
            return "warm"
        else:
            return "hot"
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate simple text similarity (0-1)"""
        if not text1 or not text2:
            return 0.0
        
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def format_price(amount: float, currency: str = "USD") -> str:
        """Format price with currency symbol"""
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "PKR": "₨"
        }
        
        symbol = symbols.get(currency.upper(), currency)
        return f"{symbol}{amount:,.2f}"
    
    @staticmethod
    def get_clothing_size_range(category: str) -> List[str]:
        """Get size range for clothing category"""
        sizes = {
            "tops": ["XS", "S", "M", "L", "XL", "XXL"],
            "bottoms": ["28", "30", "32", "34", "36", "38"],
            "shoes": ["6", "7", "8", "9", "10", "11", "12"],
            "dresses": ["XS", "S", "M", "L", "XL"],
            "accessories": ["One Size"],
            "outerwear": ["S", "M", "L", "XL", "XXL"]
        }
        
        return sizes.get(category.lower(), ["One Size"])
    
    @staticmethod
    def generate_outfit_name(items: List[str]) -> str:
        """Generate outfit name from items"""
        if not items:
            return "Untitled Outfit"
        
        # Get first 3 items
        first_items = items[:3]
        
        if len(items) == 1:
            return f"{items[0]} Outfit"
        elif len(items) <= 3:
            return " & ".join(first_items)
        else:
            return f"{', '.join(first_items)} +{len(items) - 3} more"
    
    @staticmethod
    def estimate_outfit_price(items: List[Dict]) -> float:
        """Estimate total price of outfit"""
        total = 0.0
        
        for item in items:
            if isinstance(item, dict) and "price" in item:
                try:
                    total += float(item["price"])
                except (ValueError, TypeError):
                    continue
        
        return round(total, 2)


# Export singleton instance
helpers = Helpers()