# app/config.py
from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Fashion AI API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # MongoDB
    MONGODB_URL: str
    DATABASE_NAME: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # OpenAI (Optional - keeping for potential text generation)
    OPENAI_API_KEY: Optional[str] = None
    
    # CLIP Model Configuration
    CLIP_MODEL_NAME: str = "ViT-B/32"  # or "ViT-L/14" for better quality
    CLIP_DEVICE: str = "cpu"  # or "cuda" if GPU available
    GENERATE_EMBEDDINGS_ON_UPLOAD: bool = True
    EMBEDDING_DIMENSION: int = 512  # ViT-B/32 produces 512-dim vectors
    
    # Weather
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_API_URL: str = "https://api.openweathermap.org/data/2.5/weather"
    
    # AWS S3
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    
    # Email/SMTP Settings for Password Reset
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "FashionAI"
    SMTP_USE_TLS: bool = True
    
    # Frontend URL (for password reset links)
    FRONTEND_URL: str = "http://localhost:19006"
    
    # Admin
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".webp"]
    
    # Image Processing
    IMAGE_MAX_WIDTH: int = 1024
    IMAGE_MAX_HEIGHT: int = 1024
    THUMBNAIL_SIZE: tuple = (300, 300)
    
    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:19006",
        "*"  # Remove in production
    ]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Password Reset Token Expiry
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

settings = Settings()





# 