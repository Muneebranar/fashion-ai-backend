from fastapi import HTTPException, UploadFile
from typing import Optional, List
import re
from pathlib import Path

class Validators:
    """Request validation utilities"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username (3-50 chars, alphanumeric + underscore)"""
        if not username or len(username) < 3 or len(username) > 50:
            return False
        pattern = r'^[a-zA-Z0-9_]+$'
        return re.match(pattern, username) is not None
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength
        Returns: (is_valid, error_message)
        """
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters long"
        
        if len(password) > 100:
            return False, "Password is too long"
        
        # Optional: Add more strength requirements
        # has_upper = any(c.isupper() for c in password)
        # has_lower = any(c.islower() for c in password)
        # has_digit = any(c.isdigit() for c in password)
        
        return True, None
    
    @staticmethod
    async def validate_image_file(
        file: UploadFile,
        max_size_mb: int = 10,
        allowed_extensions: List[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate uploaded image file
        Returns: (is_valid, error_message)
        """
        if allowed_extensions is None:
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        
        # Check file exists
        if not file or not file.filename:
            return False, "No file provided"
        
        # Check extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return False, f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
        
        # Check content type
        valid_content_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if file.content_type not in valid_content_types:
            return False, f"Invalid content type: {file.content_type}"
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return False, f"File too large. Maximum size: {max_size_mb}MB"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, None
    
    @staticmethod
    def validate_object_id(id_str: str) -> bool:
        """Validate MongoDB ObjectId format"""
        if not id_str or len(id_str) != 24:
            return False
        try:
            int(id_str, 16)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_pagination(page: int, page_size: int, max_page_size: int = 100) -> tuple[int, int]:
        """
        Validate and sanitize pagination parameters
        Returns: (sanitized_page, sanitized_page_size)
        """
        page = max(1, page)
        page_size = max(1, min(page_size, max_page_size))
        return page, page_size
    
    @staticmethod
    def validate_search_query(query: str, min_length: int = 2, max_length: int = 200) -> bool:
        """Validate search query string"""
        if not query:
            return False
        
        query = query.strip()
        return min_length <= len(query) <= max_length
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        # Remove path separators and parent directory references
        filename = Path(filename).name
        # Remove any remaining dangerous characters
        filename = re.sub(r'[^\w\s.-]', '', filename)
        return filename
    
    @staticmethod
    def validate_color(color: str) -> bool:
        """Validate color name or hex code"""
        valid_colors = {
            'black', 'white', 'gray', 'grey', 'red', 'blue', 'green',
            'yellow', 'orange', 'pink', 'purple', 'brown', 'beige',
            'navy', 'maroon', 'teal', 'olive', 'multicolor'
        }
        
        # Check if it's a valid color name
        if color.lower() in valid_colors:
            return True
        
        # Check if it's a valid hex code
        hex_pattern = r'^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
        return re.match(hex_pattern, color) is not None
    
    @staticmethod
    def validate_category(category: str) -> bool:
        """Validate clothing category"""
        valid_categories = {
            'tops', 'bottoms', 'dresses', 'outerwear', 'shoes',
            'accessories', 'bags', 'jewelry', 'other'
        }
        return category.lower() in valid_categories
    
    @staticmethod
    def validate_season(season: str) -> bool:
        """Validate season"""
        valid_seasons = {'spring', 'summer', 'fall', 'autumn', 'winter', 'all'}
        return season.lower() in valid_seasons
    
    @staticmethod
    def validate_occasion(occasion: str) -> bool:
        """Validate occasion"""
        valid_occasions = {
            'casual', 'formal', 'business', 'party', 'sport', 'workout',
            'beach', 'evening', 'wedding', 'date', 'everyday'
        }
        return occasion.lower() in valid_occasions


# Convenience function for raising validation errors
def raise_validation_error(message: str, field: Optional[str] = None):
    """Raise HTTPException with validation error"""
    detail = {"message": message}
    if field:
        detail["field"] = field
    raise HTTPException(status_code=422, detail=detail)