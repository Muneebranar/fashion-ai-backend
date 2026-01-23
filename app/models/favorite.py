from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class FavoriteBase(BaseModel):
    """Base model for favorites"""
    item_type: str  # "clothing" or "outfit"
    item_id: str

class FavoriteCreate(FavoriteBase):
    """Model for creating a favorite"""
    pass

class FavoriteInDB(FavoriteBase):
    """Model for favorite in database"""
    id: str = Field(alias="_id")
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True

class FavoriteResponse(BaseModel):
    """Response model for favorite"""
    id: str
    user_id: str
    item_type: str
    item_id: str
    created_at: datetime
    
    # Populated item data (optional)
    item_data: Optional[dict] = None
    
    class Config:
        from_attributes = True

class FavoriteListResponse(BaseModel):
    """Response model for list of favorites"""
    favorites: list[FavoriteResponse]
    total: int
    page: int
    page_size: int
    
    class Config:
        from_attributes = True