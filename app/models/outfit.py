from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId
from app.models.clothing import ClothingResponse, Season, Occasion

class OutfitBase(BaseModel):
    name: Optional[str] = None
    clothing_items: List[str] = Field(..., min_items=1)  # List of clothing IDs
    occasion: Optional[Occasion] = None
    season: Optional[Season] = None
    weather_condition: Optional[str] = None  # sunny, rainy, cloudy, snowy
    temperature_range: Optional[Dict[str, float]] = None  # {"min": 15, "max": 25}

class OutfitCreate(OutfitBase):
    is_favorite: bool = False
    notes: Optional[str] = None

class OutfitUpdate(BaseModel):
    name: Optional[str] = None
    clothing_items: Optional[List[str]] = None
    occasion: Optional[Occasion] = None
    season: Optional[Season] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None

class OutfitResponse(OutfitBase):
    id: str = Field(alias="_id")
    user_id: str
    is_favorite: bool
    notes: Optional[str] = None
    times_worn: int = 0
    last_worn: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        use_enum_values = True

class OutfitWithItems(OutfitResponse):
    items: List[ClothingResponse] = []

class OutfitSuggestion(BaseModel):
    outfit: OutfitWithItems
    reason: str
    weather_info: Dict
    style_score: float = Field(ge=0, le=1)
    occasion_match: bool

class AIOutfitRequest(BaseModel):
    occasion: Optional[Occasion] = None
    weather_location: Optional[str] = None
    temperature: Optional[float] = None
    weather_condition: Optional[str] = None
    color_preference: Optional[str] = None
    style_preference: Optional[str] = None
    excluded_items: Optional[List[str]] = []

class OutfitHistory(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    outfit_id: str
    worn_date: datetime
    occasion: Optional[Occasion] = None
    weather: Optional[Dict] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}