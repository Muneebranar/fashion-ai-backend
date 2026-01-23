import io 
import os
import uuid
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import boto3
from botocore.exceptions import ClientError
from app.config import settings
import logging
import io

logger = logging.getLogger(__name__)

class ImageService:
    def __init__(self):
        self.s3_client = None
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
    
    def validate_image(self, file: UploadFile) -> bool:
        """Validate image file"""
        # FIXED: Better file extension validation
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        # Get file extension (case-insensitive)
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Define allowed extensions with dot prefix
        ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
        
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Check file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        max_size = getattr(settings, 'MAX_FILE_SIZE', 10 * 1024 * 1024)  # Default 10MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {max_size / (1024*1024)}MB"
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        return True
    
    async def save_image(self, file: UploadFile, folder: str = "profile") -> Tuple[str, str]:
        """
        Save image and create thumbnail (compatible with user routes)
        
        Args:
            file: Uploaded file
            folder: Folder to store the image
            
        Returns:
            Tuple of (image_url, thumbnail_url)
        """
        try:
            self.validate_image(file)
            
            # Generate unique filename
            file_ext = os.path.splitext(file.filename)[1].lower()
            unique_id = uuid.uuid4()
            image_filename = f"{folder}/{unique_id}{file_ext}"
            thumbnail_filename = f"{folder}/thumbnails/{unique_id}_thumb{file_ext}"
            
            # Read file content
            file_content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Upload main image
            if self.s3_client:
                image_url = await self._upload_to_s3_bytes(file_content, image_filename, file.content_type)
                thumbnail_url = await self._create_and_upload_thumbnail_s3(file_content, thumbnail_filename, file.content_type)
            else:
                image_url = await self._upload_local_bytes(file_content, image_filename)
                thumbnail_url = await self._create_and_upload_thumbnail_local(file_content, thumbnail_filename)
            
            logger.info(f"Image and thumbnail saved: {image_url}")
            return image_url, thumbnail_url
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in save_image: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save image"
            )
    
    async def _upload_to_s3_bytes(self, content: bytes, key: str, content_type: str) -> str:
        """Upload bytes to S3"""
        try:
            self.s3_client.put_object(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=key,
                Body=content,
                ContentType=content_type
            )
            
            url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
            return url
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise
    
    async def _create_and_upload_thumbnail_s3(
        self, 
        content: bytes, 
        key: str, 
        content_type: str,
        size: Tuple[int, int] = (200, 200)
    ) -> str:
        """Create thumbnail and upload to S3"""
        try:
            # Create thumbnail
            img = Image.open(io.BytesIO(content))
            
            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            thumb_buffer = io.BytesIO()
            img.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
            thumb_buffer.seek(0)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=key,
                Body=thumb_buffer.getvalue(),
                ContentType='image/jpeg'
            )
            
            url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
            return url
        except Exception as e:
            logger.error(f"Thumbnail S3 upload error: {e}")
            raise
    
    async def _upload_local_bytes(self, content: bytes, relative_path: str) -> str:
        """Upload bytes to local storage"""
        try:
            # Create directory if not exists
            upload_dir = settings.UPLOAD_DIR
            file_path = os.path.join(upload_dir, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Optimize image
            self._optimize_image(file_path)
            
            # Return relative URL
            url = f"/uploads/{relative_path}"
            return url
        except Exception as e:
            logger.error(f"Local upload error: {e}")
            raise
    
    async def _create_and_upload_thumbnail_local(
        self,
        content: bytes,
        relative_path: str,
        size: Tuple[int, int] = (200, 200)
    ) -> str:
        """Create thumbnail and save locally"""
        try:
            # Create directory if not exists
            upload_dir = settings.UPLOAD_DIR
            file_path = os.path.join(upload_dir, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Create thumbnail
            img = Image.open(io.BytesIO(content))
            
            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save thumbnail
            img.save(file_path, quality=85, optimize=True)
            
            # Return relative URL
            url = f"/uploads/{relative_path}"
            return url
        except Exception as e:
            logger.error(f"Thumbnail local save error: {e}")
            raise
    
    async def upload_to_s3(self, file: UploadFile, folder: str = "clothing") -> str:
        """Upload image to AWS S3"""
        try:
            self.validate_image(file)
            
            # Generate unique filename
            file_ext = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"{folder}/{uuid.uuid4()}{file_ext}"
            
            # Upload to S3 (FIXED: Removed ACL)
            self.s3_client.upload_fileobj(
                file.file,
                settings.AWS_BUCKET_NAME,
                unique_filename,
                ExtraArgs={
                    'ContentType': file.content_type
                    # Removed: 'ACL': 'public-read'  - ACLs disabled on bucket
                }
            )
            
            # Generate URL
            url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
            
            logger.info(f"Image uploaded to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"S3 upload failed: {str(e)}"
            )
    
    async def upload_local(self, file: UploadFile, folder: str = "clothing") -> str:
        """Upload image to local storage (fallback)"""
        try:
            self.validate_image(file)
            
            # Create directory if not exists
            upload_path = os.path.join(settings.UPLOAD_DIR, folder)
            os.makedirs(upload_path, exist_ok=True)
            
            # Generate unique filename
            file_ext = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(upload_path, unique_filename)
            
            # Save file
            with open(file_path, "wb") as buffer:
                contents = await file.read()
                buffer.write(contents)
            
            # Optimize image
            self._optimize_image(file_path)
            
            # Return relative URL
            url = f"/uploads/{folder}/{unique_filename}"
            logger.info(f"Image uploaded locally: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Local upload error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload image"
            )
    
    def _optimize_image(self, file_path: str, max_size: tuple = (800, 800)):
        """Optimize image size and quality"""
        try:
            with Image.open(file_path) as img:
                # Convert RGBA to RGB if necessary
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Resize if larger than max_size
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save with optimization
                img.save(file_path, optimize=True, quality=85)
                
        except Exception as e:
            logger.warning(f"Image optimization failed: {e}")
    
    async def upload_image(self, file: UploadFile, folder: str = "clothing") -> str:
        """Upload image (S3 if available, local otherwise)"""
        if self.s3_client:
            return await self.upload_to_s3(file, folder)
        else:
            return await self.upload_local(file, folder)
    
    async def delete_image(self, image_url: str) -> bool:
        """Delete image from storage"""
        try:
            if not image_url:
                return True
            
            if image_url.startswith('http'):
                # S3 deletion
                if self.s3_client:
                    key = image_url.split('.com/')[-1]
                    self.s3_client.delete_object(
                        Bucket=settings.AWS_BUCKET_NAME,
                        Key=key
                    )
                    
                    # Try to delete thumbnail as well
                    if '/thumbnails/' not in key:
                        # Construct thumbnail key
                        path_parts = key.rsplit('/', 1)
                        if len(path_parts) == 2:
                            folder, filename = path_parts
                            name, ext = os.path.splitext(filename)
                            thumbnail_key = f"{folder}/thumbnails/{name}_thumb{ext}"
                            try:
                                self.s3_client.delete_object(
                                    Bucket=settings.AWS_BUCKET_NAME,
                                    Key=thumbnail_key
                                )
                            except:
                                pass  # Thumbnail might not exist
            else:
                # Local deletion
                file_path = os.path.join(os.getcwd(), image_url.lstrip('/'))
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Try to delete thumbnail as well
                if '/thumbnails/' not in file_path:
                    path_parts = file_path.rsplit('/', 1)
                    if len(path_parts) == 2:
                        folder, filename = path_parts
                        name, ext = os.path.splitext(filename)
                        thumbnail_path = f"{folder}/thumbnails/{name}_thumb{ext}"
                        if os.path.exists(thumbnail_path):
                            os.remove(thumbnail_path)
            
            logger.info(f"Image deleted: {image_url}")
            return True
            
        except Exception as e:
            logger.error(f"Image deletion error: {e}")
            return False

# Singleton instance
image_service = ImageService()