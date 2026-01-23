# app/models/outfit_history.py - FIXED FOR PYDANTIC V2
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class OutfitItem(BaseModel):
    """Individual clothing item in an outfit"""
    id: str
    item_name: str
    category: str
    color: Optional[str] = None
    image_url: Optional[str] = None

class WeatherData(BaseModel):
    """Weather information when outfit was worn"""
    temperature: float
    temp_c: float
    condition: str
    humidity: Optional[int] = None
    location: str

class OutfitHistoryBase(BaseModel):
    """Base outfit history model"""
    # user_id: str
    date: datetime
    outfit_items: List[OutfitItem]
    outfit_image_urls: List[str] = []
    weather_data: Optional[WeatherData] = None
    selection_source: str  # ai or manual
    is_favorite: bool = False
    notes: Optional[str] = None
    occasion: Optional[str] = None
    rating: Optional[int] = None
    
    @field_validator('selection_source')
    @classmethod
    def validate_selection_source(cls, v):
        if v not in ['ai', 'manual']:
            raise ValueError('selection_source must be either "ai" or "manual"')
        return v
    
    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('rating must be between 1 and 5')
        return v

class OutfitHistoryCreate(OutfitHistoryBase):
    """Model for creating outfit history"""
    pass

class OutfitHistoryUpdate(BaseModel):
    """Model for updating outfit history"""
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    
    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('rating must be between 1 and 5')
        return v

class OutfitHistoryResponse(OutfitHistoryBase):
    """Model for outfit history response"""
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    wear_count: int = 1

    class Config:
        populate_by_name = True  # Changed from allow_population_by_field_name in Pydantic v2
        json_encoders = {ObjectId: str}