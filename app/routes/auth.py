from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from app.database import get_database
from app.models.user import UserCreate, UserLogin, UserResponse, Token
from app.utils.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


# -----------------------------
# Models
# -----------------------------

class FirebaseTokenRequest(BaseModel):
    firebase_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# -----------------------------
# Email Utility
# -----------------------------

async def send_password_reset_email(email: str, reset_token: str):
    """Send password reset email to user"""
    try:
        # Create reset link (update with your actual frontend URL)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        # Email content
        subject = "Reset Your FashionAI Password"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #000; color: #fff; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .button {{ 
                    display: inline-block; 
                    padding: 15px 30px; 
                    background-color: #000; 
                    color: #fff; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 20px 0;
                }}
                .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                .token-box {{
                    background-color: #f0f0f0;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: monospace;
                    font-size: 14px;
                    margin: 20px 0;
                    word-break: break-all;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎨 FashionAI</h1>
                </div>
                <div class="content">
                    <h2>Reset Your Password</h2>
                    <p>We received a request to reset your password. Use the reset token below in the app:</p>
                    <div class="token-box">
                        {reset_token}
                    </div>
                    <p>Or click the button below if you're using a web browser:</p>
                    <p style="text-align: center;">
                        <a href="{reset_link}" class="button">Reset Password</a>
                    </p>
                    <p><strong>This token will expire in 1 hour.</strong></p>
                    <p>If you didn't request a password reset, you can safely ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2024 FashionAI. All rights reserved.</p>
                    <p>This is an automated message, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Reset Your FashionAI Password
        
        We received a request to reset your password. Use this reset token in the app:
        
        {reset_token}
        
        Or use this link:
        {reset_link}
        
        This token will expire in 1 hour.
        
        If you didn't request a password reset, you can safely ignore this email.
        
        © 2024 FashionAI. All rights reserved.
        """
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = email
        
        # Attach both text and HTML versions
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Send email via SMTP
        logger.info(f"Attempting to send email to {email}")
        logger.info(f"SMTP Config: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.set_debuglevel(1)  # Enable debug output
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        
        logger.info(f"Email sent successfully to {email}")
        return True
    except Exception as e:
        logger.error(f"Error sending email to {email}: {str(e)}")
        logger.exception(e)
        return False


# -----------------------------
# Register
# -----------------------------

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db=Depends(get_database)):
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    password_hash = await run_in_threadpool(
        get_password_hash,
        user_data.password
    )

    user_dict = {
        "email": user_data.email,
        "full_name": user_data.full_name,
        "phone": user_data.phone,
        "password_hash": password_hash,
        "profile_image": None,
        "location": None,
        "style_preferences": [],
        "notification_enabled": True,
        "is_admin": False,
        "firebase_token": None,
        "last_login": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await db.users.insert_one(user_dict)
    user_dict["_id"] = str(result.inserted_id)

    access_token = create_access_token(
        data={"sub": user_dict["_id"], "email": user_dict["email"]}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**user_dict)
    )


# -----------------------------
# Login
# -----------------------------

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db=Depends(get_database)):
    user = await db.users.find_one({"email": credentials.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    password_valid = await run_in_threadpool(
        verify_password,
        credentials.password,
        user["password_hash"]
    )

    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    user["_id"] = str(user["_id"])

    access_token = create_access_token(
        data={"sub": user["_id"], "email": user["email"]}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**user)
    )


# -----------------------------
# Forgot Password
# -----------------------------

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_database)
):
    """
    Send password reset email to user
    """
    logger.info(f"Password reset requested for email: {request.email}")
    
    user = await db.users.find_one({"email": request.email})
    
    # Don't reveal if email exists or not for security
    if not user:
        logger.warning(f"Password reset requested for non-existent email: {request.email}")
        return {
            "success": True,
            "message": "If an account exists with this email, you will receive password reset instructions."
        }
    
    # Generate secure random token
    reset_token = secrets.token_urlsafe(32)
    
    # Store reset token in database with expiration (1 hour)
    reset_token_data = {
        "reset_token": reset_token,
        "reset_token_expires": datetime.utcnow() + timedelta(hours=1),
        "updated_at": datetime.utcnow()
    }
    
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": reset_token_data}
    )
    
    logger.info(f"Reset token generated for {request.email}")
    
    # Send email in background
    background_tasks.add_task(send_password_reset_email, request.email, reset_token)
    
    return {
        "success": True,
        "message": "If an account exists with this email, you will receive password reset instructions."
    }


# -----------------------------
# Verify Reset Token (Optional - for validation before reset)
# -----------------------------

@router.post("/verify-reset-token")
async def verify_reset_token(
    token: str,
    db=Depends(get_database)
):
    """
    Verify if reset token is valid
    """
    user = await db.users.find_one({
        "reset_token": token,
        "reset_token_expires": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {
        "success": True,
        "message": "Token is valid",
        "email": user["email"]
    }


# -----------------------------
# Reset Password
# -----------------------------

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db=Depends(get_database)
):
    """
    Reset password using reset token
    """
    # Find user with valid reset token
    user = await db.users.find_one({
        "reset_token": request.token,
        "reset_token_expires": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Validate new password
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    # Hash new password
    new_password_hash = await run_in_threadpool(
        get_password_hash,
        request.new_password
    )
    
    # Update password and remove reset token
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "reset_token": "",
                "reset_token_expires": ""
            }
        }
    )
    
    logger.info(f"Password reset successful for user: {user['email']}")
    
    return {
        "success": True,
        "message": "Password has been reset successfully. You can now login with your new password."
    }


# -----------------------------
# Change Password (for logged-in users)
# -----------------------------

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Change password for authenticated user
    """
    # Verify current password
    password_valid = await run_in_threadpool(
        verify_password,
        request.current_password,
        current_user["password_hash"]
    )
    
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    # Hash new password
    new_password_hash = await run_in_threadpool(
        get_password_hash,
        request.new_password
    )
    
    # Update password
    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$set": {
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {
        "success": True,
        "message": "Password changed successfully"
    }


# -----------------------------
# Refresh Token
# -----------------------------

@router.post("/refresh-token", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    access_token = create_access_token(
        data={"sub": str(current_user["_id"]), "email": current_user["email"]}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**current_user)
    )


# -----------------------------
# Get Current User
# -----------------------------

@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(
    current_user: dict = Depends(get_current_user)
):
    return UserResponse(**current_user)


# -----------------------------
# Logout
# -----------------------------

@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}


# -----------------------------
# Firebase Token
# -----------------------------

@router.post("/firebase-token")
async def update_firebase_token(
    data: FirebaseTokenRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"firebase_token": data.firebase_token}}
    )
    return {"message": "Firebase token updated successfully"}


# -----------------------------
# Create Test User (DEV ONLY)
# -----------------------------

@router.post("/create-test-user")
async def create_test_user(db=Depends(get_database)):
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden"
        )

    existing = await db.users.find_one({"email": "test@fashionai.com"})
    if existing:
        return {
            "success": True,
            "message": "Test user already exists",
            "user_id": str(existing["_id"])
        }

    password_hash = await run_in_threadpool(
        get_password_hash,
        "Test123!"
    )

    test_user = {
        "email": "test@fashionai.com",
        "full_name": "Test User",
        "password_hash": password_hash,
        "is_admin": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = await db.users.insert_one(test_user)

    access_token = create_access_token(
        data={"sub": str(result.inserted_id), "email": test_user["email"]}
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "_id": str(result.inserted_id),
            "email": test_user["email"],
            "full_name": test_user["full_name"]
        }
    }