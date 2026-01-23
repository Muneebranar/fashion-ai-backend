from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime
from typing import Optional
from app.config import settings
from app.database import get_database
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Verify JWT token and return payload
    
    Raises HTTPException if token is invalid or expired
    """
    try:
        token = credentials.credentials
        
        # Decode JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract user info
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "is_admin": payload.get("is_admin", False)
        }
    
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )

async def get_current_user(
    token_data: dict = Depends(verify_token)
) -> dict:
    """
    Get current authenticated user from database
    
    Returns user document or raises HTTPException if not found
    """
    try:
        db = await get_database()  # ✅ FIXED: Added await
        user_id = token_data["user_id"]
        
        # Fetch user from database
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=403,
                detail="User account is disabled"
            )
        
        # Convert ObjectId to string
        user["id"] = str(user["_id"])
        
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching current user: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve user information"
        )

async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current active user (alias for get_current_user)
    """
    return current_user

async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Require admin privileges
    
    Raises HTTPException if user is not admin
    """
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    return current_user

async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[dict]:
    """
    Optional authentication - returns user data if token is valid, None otherwise
    
    Useful for endpoints that work both with and without authentication
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "is_admin": payload.get("is_admin", False)
        }
    except:
        return None