from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os

from app.config import settings
from app.database import Database
from app.routes import (
    auth,
    clothing,
    outfit,
    admin,
    ai_recommendations,
    user,
    weather,
    outfit_history,
    notifications,
    push_notifications,  # ✅ ADD THIS IMPORT
)

# Logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---------------- STARTUP ----------------
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Database connection (FAIL FAST)
    try:
        await Database.connect_db()
        logger.info("✅ Database connected successfully")
    except Exception as e:
        logger.critical(f"❌ Database startup failed: {e}")
        raise RuntimeError("Application startup aborted")

    # Start notification scheduler
    from app.tasks.notification_scheduler import notification_scheduler

    await notification_scheduler.start()
    logger.info("🔔 Notification scheduler started")

    # Create default admin (optional)
    try:
        await create_default_admin()
    except Exception as e:
        logger.warning(f"Admin creation skipped: {e}")

    yield

    # ---------------- SHUTDOWN ----------------
    logger.info("🛑 Shutting down application")

    await notification_scheduler.stop()
    logger.info("🔕 Notification scheduler stopped")

    await Database.close_db()
    logger.info("✅ Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Fashion Stylist API",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static uploads
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(clothing.router, prefix="/api/v1")
app.include_router(outfit.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(ai_recommendations.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(weather.router, prefix="/api/v1")
app.include_router(outfit_history.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(push_notifications.router, prefix="/api/v1")  # ✅ ADD THIS LINE


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    try:
        await Database.client.admin.command("ping")
        return {
            "status": "healthy",
            "database": "connected",
            "version": settings.APP_VERSION,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else "Unexpected error",
        },
    )


async def create_default_admin():
    from app.utils.auth import get_password_hash
    from datetime import datetime

    db = Database.get_database()

    admin = await db.users.find_one({"email": settings.ADMIN_EMAIL})
    if admin:
        logger.info("Admin user already exists")
        return

    logger.info("Creating default admin user")

    admin_user = {
        "email": settings.ADMIN_EMAIL,
        "full_name": "Admin User",
        "password_hash": get_password_hash(settings.ADMIN_PASSWORD[:72]),
        "is_admin": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    await db.users.insert_one(admin_user)
    logger.info(f"✅ Default admin created: {settings.ADMIN_EMAIL}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )