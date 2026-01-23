from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.middleware.auth_middleware import get_current_user
from app.database import get_database
from app.models.user import UserResponse, UserUpdate, PasswordChange
from app.services.image_service import image_service
from app.utils.validators import Validators, raise_validation_error
from bson import ObjectId
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information (minimal)
    
    Returns basic info about the currently logged-in user.
    Use /profile for more detailed information.
    """
    try:
        return {
            "id": current_user.get("id", str(current_user.get("_id", ""))),
            "email": current_user.get("email", ""),
            "username": current_user.get("username"),
            "full_name": current_user.get("full_name"),
            "phone_number": current_user.get("phone_number"),
            "profile_photo": current_user.get("profile_photo"),
            "is_admin": current_user.get("is_admin", False),
            "is_active": current_user.get("is_active", True),
            "created_at": current_user.get("created_at"),
        }
    except Exception as e:
        logger.error(f"Error in /me endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        return UserResponse(
            id=current_user.get("id", str(current_user.get("_id", ""))),
            email=current_user.get("email", ""),
            username=current_user.get("username", ""),
            full_name=current_user.get("full_name"),
            phone_number=current_user.get("phone_number"),
            profile_photo=current_user.get("profile_photo"),
            avatar_url=current_user.get("avatar_url"),
            bio=current_user.get("bio"),
            location=current_user.get("location"),
            preferences=current_user.get("preferences", {}),
            is_active=current_user.get("is_active", True),
            is_admin=current_user.get("is_admin", False),
            created_at=current_user.get("created_at")
        )
    except Exception as e:
        logger.error(f"Error getting profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve profile")


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    try:
        db = await get_database()
        user_id = current_user["id"]
        
        # Prepare update data
        update_data = profile_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update user in database
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.warning(f"No changes made to user {user_id}")
        
        # Fetch updated user
        updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        updated_user["id"] = str(updated_user["_id"])
        
        return UserResponse(
            id=updated_user["id"],
            email=updated_user["email"],
            username=updated_user.get("username", ""),
            full_name=updated_user.get("full_name"),
            phone_number=updated_user.get("phone_number"),
            profile_photo=updated_user.get("profile_photo"),
            avatar_url=updated_user.get("avatar_url"),
            bio=updated_user.get("bio"),
            location=updated_user.get("location"),
            preferences=updated_user.get("preferences", {}),
            is_active=updated_user.get("is_active", True),
            is_admin=updated_user.get("is_admin", False),
            created_at=updated_user.get("created_at"),
            updated_at=updated_user.get("updated_at")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


@router.post("/profile-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload user profile photo"""
    try:
        # Validate image
        is_valid, error_msg = await Validators.validate_image_file(file)
        if not is_valid:
            raise_validation_error(error_msg, "file")
        
        # Save and process image
        image_path, thumbnail_path = await image_service.save_image(file)
        
        # Update user profile photo in database
        db = await get_database()
        user_id = current_user["id"]
        
        # Delete old profile photo if exists
        old_photo = current_user.get("profile_photo")
        if old_photo:
            await image_service.delete_image(old_photo)
        
        # Update profile photo URL
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"profile_photo": image_path}}
        )
        
        return {
            "success": True,
            "message": "Profile photo uploaded successfully",
            "profile_photo": image_path,
            "thumbnail_url": thumbnail_path
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading profile photo: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile photo")


@router.delete("/profile-photo")
async def delete_profile_photo(current_user: dict = Depends(get_current_user)):
    """Delete user profile photo"""
    try:
        db = await get_database()
        user_id = current_user["id"]
        
        # Get current profile photo
        profile_photo = current_user.get("profile_photo")
        
        if not profile_photo:
            raise HTTPException(status_code=404, detail="No profile photo to delete")
        
        # Delete image file
        await image_service.delete_image(profile_photo)
        
        # Remove profile photo URL from database
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"profile_photo": ""}}
        )
        
        return {
            "success": True,
            "message": "Profile photo deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting profile photo: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete profile photo")


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload user avatar (legacy endpoint - use /profile-photo instead)"""
    try:
        # Validate image
        is_valid, error_msg = await Validators.validate_image_file(file)
        if not is_valid:
            raise_validation_error(error_msg, "file")
        
        # Save and process image
        image_path, thumbnail_path = await image_service.save_image(file)
        
        # Update user avatar in database
        db = await get_database()
        user_id = current_user["id"]
        
        # Delete old avatar if exists
        old_avatar = current_user.get("avatar_url")
        if old_avatar:
            await image_service.delete_image(old_avatar)
        
        # Update avatar URL
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"avatar_url": image_path}}
        )
        
        return {
            "success": True,
            "message": "Avatar uploaded successfully",
            "avatar_url": image_path,
            "thumbnail_url": thumbnail_path
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload avatar")


@router.delete("/avatar")
async def delete_avatar(current_user: dict = Depends(get_current_user)):
    """Delete user avatar (legacy endpoint - use /profile-photo instead)"""
    try:
        db = await get_database()
        user_id = current_user["id"]
        
        # Get current avatar
        avatar_url = current_user.get("avatar_url")
        
        if not avatar_url:
            raise HTTPException(status_code=404, detail="No avatar to delete")
        
        # Delete image file
        await image_service.delete_image(avatar_url)
        
        # Remove avatar URL from database
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"avatar_url": ""}}
        )
        
        return {
            "success": True,
            "message": "Avatar deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting avatar: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete avatar")


@router.get("/stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    """Get user statistics"""
    try:
        db = await get_database()
        user_id = current_user["id"]
        
        # Count clothing items
        clothing_count = await db.clothing.count_documents({"user_id": user_id})
        
        # Count outfits
        outfit_count = await db.outfits.count_documents({"user_id": user_id})
        
        # Count favorites
        favorite_count = await db.favorites.count_documents({"user_id": user_id})
        
        # Get category breakdown
        category_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
        ]
        category_counts = await db.clothing.aggregate(category_pipeline).to_list(None)
        
        categories = {item["_id"]: item["count"] for item in category_counts}
        
        return {
            "success": True,
            "data": {
                "clothing_items": clothing_count,
                "outfits": outfit_count,
                "favorites": favorite_count,
                "categories": categories,
                "member_since": current_user.get("created_at")
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.put("/preferences")
async def update_preferences(
    preferences: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update user preferences"""
    try:
        db = await get_database()
        user_id = current_user["id"]
        
        # Update preferences
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"preferences": preferences}}
        )
        
        return {
            "success": True,
            "message": "Preferences updated successfully",
            "preferences": preferences
        }
    
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,  # ✅ Use the PasswordChange schema
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    try:
        from app.utils.auth import verify_password, get_password_hash
        
        db = await get_database()
        user_id = current_user["id"]
        
        # Fetch user from database to get password_hash
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # ✅ Check both field names for backward compatibility
        stored_password_hash = user.get("password_hash") or user.get("hashed_password")
        
        if not stored_password_hash:
            logger.error(f"No password hash found for user {user_id}")
            raise HTTPException(status_code=500, detail="Password data not found")
        
        # Verify current password
        if not verify_password(password_data.current_password, stored_password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Hash new password
        new_password_hash = get_password_hash(password_data.new_password)
        
        # ✅ Update using password_hash (standardized field name)
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {"hashed_password": ""}  # Remove old field if it exists
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update password")
        
        logger.info(f"Password changed successfully for user {user_id}")
        
        return {
            "success": True,
            "message": "Password changed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to change password")


@router.put("/privacy-settings")
async def update_privacy_settings(
    privacy_settings: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update privacy settings"""
    try:
        db = await get_database()
        user_id = current_user["id"]
        
        # Update privacy settings
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"privacy_settings": privacy_settings, "updated_at": datetime.utcnow()}}
        )
        
        return {
            "success": True,
            "message": "Privacy settings updated successfully",
            "privacy_settings": privacy_settings
        }
    
    except Exception as e:
        logger.error(f"Error updating privacy settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update privacy settings")


@router.delete("/account")
async def delete_account(
    password: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete user account (requires password confirmation)"""
    try:
        from app.utils.auth import verify_password
        
        db = await get_database()
        user_id = current_user["id"]
        
        # Fetch user from database to get password_hash
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # ✅ Check both field names for backward compatibility
        stored_password_hash = user.get("password_hash") or user.get("hashed_password")
        
        if not stored_password_hash:
            raise HTTPException(status_code=500, detail="Password data not found")
        
        # Verify password
        if not verify_password(password, stored_password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")
        
        # Delete user's profile photo if exists
        if current_user.get("profile_photo"):
            await image_service.delete_image(current_user["profile_photo"])
        
        # Delete user's avatar if exists
        if current_user.get("avatar_url"):
            await image_service.delete_image(current_user["avatar_url"])
        
        # Delete user's clothing items and outfits
        clothing_delete = await db.clothing.delete_many({"user_id": user_id})
        outfit_delete = await db.outfits.delete_many({"user_id": user_id})
        favorite_delete = await db.favorites.delete_many({"user_id": user_id})
        
        logger.info(f"Deleted {clothing_delete.deleted_count} clothing items for user {user_id}")
        logger.info(f"Deleted {outfit_delete.deleted_count} outfits for user {user_id}")
        logger.info(f"Deleted {favorite_delete.deleted_count} favorites for user {user_id}")
        
        # Mark user as inactive (soft delete)
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_active": False,
                    "deleted_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "success": True,
            "message": "Account deleted successfully",
            "deleted_items": {
                "clothing": clothing_delete.deleted_count,
                "outfits": outfit_delete.deleted_count,
                "favorites": favorite_delete.deleted_count
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete account")