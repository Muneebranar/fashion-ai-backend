from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from enum import Enum

class ClothingCategory(str, Enum):
    TOPS = "tops"
    BOTTOMS = "bottoms"
    DRESSES = "dresses"
    SHOES = "shoes"
    ACCESSORIES = "accessories"
    OUTERWEAR = "outerwear"
    BAGS = "bags"
    JEWELRY = "jewelry"

class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"

class Occasion(str, Enum):
    CASUAL = "casual"
    WORK = "work"
    FORMAL = "formal"
    PARTY = "party"
    SPORT = "sport"
    BEACH = "beach"

class Condition(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"

class ClothingBase(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=100)
    category: ClothingCategory
    color: Optional[str] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    seasons: List[Season] = []
    occasions: List[Occasion] = []
    tags: List[str] = []
    notes: Optional[str] = None

class ClothingCreate(ClothingBase):
    price: Optional[float] = None
    purchase_date: Optional[str] = None
    condition: Condition = Condition.EXCELLENT
    times_worn: int = 0
    is_favorite: bool = False

class ClothingUpdate(BaseModel):
    item_name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[ClothingCategory] = None
    color: Optional[str] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    seasons: Optional[List[Season]] = None
    occasions: Optional[List[Occasion]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    price: Optional[float] = None
    purchase_date: Optional[str] = None
    condition: Optional[Condition] = None
    times_worn: Optional[int] = None
    is_favorite: Optional[bool] = None

class ClothingResponse(ClothingBase):
    id: str = Field(alias="_id")
    user_id: str
    image_url: Optional[str] = None
    price: Optional[float] = None
    purchase_date: Optional[str] = None
    condition: Condition
    times_worn: int
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    # CLIP similarity score (only for search results)
    similarity_score: Optional[float] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        use_enum_values = True

class ClothingInDB(ClothingResponse):
    # CLIP embedding vector (512 dimensions for ViT-B/32)
    embedding: Optional[List[float]] = None

class ClothingStats(BaseModel):
    total_items: int
    by_category: dict
    by_season: dict
    by_occasion: dict
    favorites_count: int
    most_worn: List[ClothingResponse]
    least_worn: List[ClothingResponse]
    total_value: float