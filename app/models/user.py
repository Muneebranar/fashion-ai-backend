from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
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
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = None
    
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordChange(BaseModel):
    """Schema for changing user password"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    location: Optional[str] = None
    style_preferences: Optional[List[str]] = None
    notification_enabled: Optional[bool] = None

class UserResponse(UserBase):
    id: str = Field(alias="_id")
    profile_image: Optional[str] = None
    location: Optional[str] = None
    style_preferences: List[str] = []
    notification_enabled: bool = True
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "full_name": "John Doe",
                "phone": "+1234567890",
                "location": "New York, NY",
                "style_preferences": ["casual", "formal"],
                "notification_enabled": True
            }
        }

class UserInDB(UserResponse):
    password_hash: str  # ✅ Keep this as password_hash
    hashed_password: Optional[str] = None  # ✅ Add alias for backward compatibility
    firebase_token: Optional[str] = None
    last_login: Optional[datetime] = None
    
    def __init__(self, **data):
        # Handle both password_hash and hashed_password
        if 'hashed_password' in data and 'password_hash' not in data:
            data['password_hash'] = data.pop('hashed_password')
        super().__init__(**data)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None