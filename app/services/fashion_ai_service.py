
import os
import uuid
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from io import BytesIO

# FastAPI & File handling
from fastapi import UploadFile, HTTPException, status
from PIL import Image

# AWS S3
import boto3
from botocore.exceptions import ClientError

# AI & ML
import torch
import clip
import numpy as np

# HTTP requests
import requests

# Configuration (assumes settings object)
from app.config import settings

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# UNIFIED FASHION AI SERVICE
# ============================================================================
class FashionAIService:
    """
    Unified service for Fashion AI application.
    Handles image processing, AI embeddings, weather data, and recommendations.
    """
    
    def __init__(self):
        """Initialize all sub-services"""
        logger.info("Initializing Fashion AI Service...")
        
        # Initialize S3 client (if credentials available)
        self.s3_client = self._init_s3()
        
        # Initialize CLIP model (lazy loading - only when needed)
        self.clip_model = None
        self.clip_preprocess = None
        self.clip_device = None
        
        # Weather API URLs
        self.weather_base_url = "https://api.open-meteo.com/v1"
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1"
        
        logger.info("Fashion AI Service initialized successfully")
    
    # ========================================================================
    # S3 INITIALIZATION
    # ========================================================================
    def _init_s3(self) -> Optional[boto3.client]:
     
        try:
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
                logger.info("S3 client initialized successfully")
                return client
            else:
                logger.warning("AWS credentials not found. Using local storage fallback.")
                return None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            return None
    
    # ========================================================================
    # CLIP MODEL INITIALIZATION (LAZY LOADING)
    # ========================================================================
    def _init_clip_model(self):
        """
        Initialize CLIP model (lazy loading - only when first needed).
        This prevents loading the model on service startup.
        """
        if self.clip_model is None:
            try:
                logger.info("Loading CLIP model...")
                self.clip_device = "cuda" if torch.cuda.is_available() else "cpu"
                # vision transformer nase size model 32 
                model_name = getattr(settings, 'CLIP_MODEL_NAME', 'ViT-B/32')
                self.clip_model, self.clip_preprocess = clip.load(
                    model_name, 
                    device=self.clip_device
                )
                self.clip_model.eval()
                
                logger.info(f"CLIP model loaded on {self.clip_device}")
            except Exception as e:
                logger.error(f"Failed to load CLIP model: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="AI model initialization failed"
                )
    
    # ========================================================================
    # IMAGE VALIDATION
    # ========================================================================
    def validate_image(self, file: UploadFile) -> bool:
        """
        Validate uploaded image file.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            bool: True if valid
            
        Raises:
            HTTPException: If validation fails
        """
        # Check filename exists
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
        
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        max_size = getattr(settings, 'MAX_FILE_SIZE', 10 * 1024 * 1024)  # 10MB default
        
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
        
        logger.info(f"Image validated: {file.filename} ({file_size} bytes)")
        return True
    
    # ========================================================================
    # IMAGE OPTIMIZATION
    # ========================================================================
    def optimize_image(self, image_bytes: bytes, max_size: Tuple[int, int] = (800, 800)) -> bytes:
        """
        Optimize image: resize, compress, convert format.
        
        Args:
            image_bytes: Raw image bytes
            max_size: Maximum dimensions (width, height)
            
        Returns:
            bytes: Optimized image bytes
        """
        try:
            # Open image
            img = Image.open(BytesIO(image_bytes))
            
            # Convert RGBA to RGB if needed
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Resize if larger than max_size
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image to bytes
            output = BytesIO()
            img.save(output, format='JPEG', optimize=True, quality=85)
            optimized_bytes = output.getvalue()
            
            logger.info(f"Image optimized: {len(image_bytes)} -> {len(optimized_bytes)} bytes")
            return optimized_bytes
            
        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            # Return original if optimization fails
            return image_bytes
    
    # ========================================================================
    # IMAGE UPLOAD (S3 or Local)
    # ========================================================================
    async def upload_image(
        self, 
        file: UploadFile, 
        folder: str = "clothing",
        optimize: bool = True
    ) -> str:
        """
        Upload image to S3 (if available) or local storage.
        
        Args:
            file: FastAPI UploadFile object
            folder: Storage folder/prefix
            optimize: Whether to optimize image before upload
            
        Returns:
            str: Public URL of uploaded image
            
        Raises:
            HTTPException: If upload fails
        """
        try:
            # Validate image
            self.validate_image(file)
            
            # Read file bytes
            file_bytes = await file.read()
            
            # Optimize if requested
            if optimize:
                file_bytes = self.optimize_image(file_bytes)
            
            # Generate unique filename
            file_ext = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"{folder}/{uuid.uuid4()}{file_ext}"
            
            # Upload to S3 if available
            if self.s3_client:
                return await self._upload_to_s3(file_bytes, unique_filename, file.content_type)
            else:
                return await self._upload_to_local(file_bytes, unique_filename)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Image upload failed"
            )
    
    async def _upload_to_s3(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Upload to AWS S3"""
        try:
            self.s3_client.put_object(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=filename,
                Body=file_bytes,
                ContentType=content_type
            )
            
            url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
            logger.info(f"Image uploaded to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 upload failed"
            )
    
    async def _upload_to_local(self, file_bytes: bytes, filename: str) -> str:
        """Upload to local storage (fallback)"""
        try:
            # Create directory
            upload_dir = getattr(settings, 'UPLOAD_DIR', 'uploads')
            file_path = os.path.join(upload_dir, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
            
            url = f"/uploads/{filename}"
            logger.info(f"Image uploaded locally: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Local upload error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Local upload failed"
            )
    
    # ========================================================================
    # CLIP EMBEDDING GENERATION
    # ========================================================================
    def generate_embedding(self, image_bytes: bytes) -> np.ndarray:
        """
        Generate CLIP embedding for image.
        
        Args:
            image_bytes: Image file bytes
            
        Returns:
            np.ndarray: Normalized embedding vector (512 dimensions)
            
        Raises:
            HTTPException: If embedding generation fails
        """
        try:
            # Lazy load CLIP model
            self._init_clip_model()
            
            # Open and preprocess image
            image = Image.open(BytesIO(image_bytes)).convert('RGB')
            image_input = self.clip_preprocess(image).unsqueeze(0).to(self.clip_device)
            
            # Generate embedding
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_input)
                # Normalize for cosine similarity
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            embedding = image_features.cpu().numpy().flatten()
            logger.info(f"Embedding generated: shape {embedding.shape}")
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI embedding generation failed"
            )
    
    # ========================================================================
    # WEATHER DATA FETCHING
    # ========================================================================
    def get_coordinates(self, location: str) -> Optional[Dict]:
        """
        Get latitude and longitude for a location.
        
        Args:
            location: City name (e.g., "New York", "London")
            
        Returns:
            dict: Location info with lat, lon, name, country, timezone
        """
        try:
            url = f"{self.geocoding_url}/search"
            params = {
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                location_info = {
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "name": result.get("name"),
                    "country": result.get("country"),
                    "admin1": result.get("admin1"),
                    "timezone": result.get("timezone")
                }
                logger.info(f"Coordinates found: {location_info['name']}, {location_info['country']}")
                return location_info
            
            logger.warning(f"No coordinates found for: {location}")
            return None
            
        except Exception as e:
            logger.error(f"Geocoding error for {location}: {e}")
            return None
    
    def get_current_weather(self, lat: float, lon: float, location_info: Optional[Dict] = None) -> Optional[Dict]:
        """
        Get current weather by coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
            location_info: Optional location metadata
            
        Returns:
            dict: Weather data with temperature, condition, humidity, wind, etc.
        """
        try:
            url = f"{self.weather_base_url}/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "rain",
                    "showers",
                    "snowfall",
                    "weather_code",
                    "cloud_cover",
                    "pressure_msl",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "wind_gusts_10m"
                ],
                "timezone": "auto"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            weather_code = current.get("weather_code", 0)
            condition, description = self._parse_weather_code(weather_code)
            
            weather_info = {
                "location": location_info.get("name") if location_info else f"Lat: {lat}, Lon: {lon}",
                "country": location_info.get("country") if location_info else None,
                "latitude": lat,
                "longitude": lon,
                "timezone": data.get("timezone"),
                "temperature": round(current.get("temperature_2m", 0)),
                "feels_like": round(current.get("apparent_temperature", 0)),
                "humidity": current.get("relative_humidity_2m", 0),
                "pressure": round(current.get("pressure_msl", 0)),
                "condition": condition,
                "description": description,
                "weather_code": weather_code,
                "wind_speed": round(current.get("wind_speed_10m", 0), 1),
                "wind_direction": current.get("wind_direction_10m", 0),
                "wind_gusts": round(current.get("wind_gusts_10m", 0), 1),
                "cloud_cover": current.get("cloud_cover", 0),
                "precipitation": current.get("precipitation", 0),
                "rain": current.get("rain", 0),
                "showers": current.get("showers", 0),
                "snowfall": current.get("snowfall", 0),
                "timestamp": current.get("time")
            }
            
            logger.info(f"Weather fetched: {weather_info['location']} - {weather_info['temperature']}°C, {weather_info['condition']}")
            return weather_info
            
        except Exception as e:
            logger.error(f"Weather fetch error: {e}")
            return None
    
    def _parse_weather_code(self, code: int) -> Tuple[str, str]:
        """
        Convert WMO weather code to readable condition and description.
        
        Args:
            code: WMO weather code
            
        Returns:
            tuple: (condition, description)
        """
        weather_codes = {
            0: ("Clear", "Clear sky"),
            1: ("Mainly Clear", "Mainly clear sky"),
            2: ("Partly Cloudy", "Partly cloudy"),
            3: ("Overcast", "Overcast"),
            45: ("Fog", "Foggy"),
            48: ("Fog", "Depositing rime fog"),
            51: ("Drizzle", "Light drizzle"),
            53: ("Drizzle", "Moderate drizzle"),
            55: ("Drizzle", "Dense drizzle"),
            56: ("Freezing Drizzle", "Light freezing drizzle"),
            57: ("Freezing Drizzle", "Dense freezing drizzle"),
            61: ("Rain", "Slight rain"),
            63: ("Rain", "Moderate rain"),
            65: ("Rain", "Heavy rain"),
            66: ("Freezing Rain", "Light freezing rain"),
            67: ("Freezing Rain", "Heavy freezing rain"),
            71: ("Snow", "Slight snow fall"),
            73: ("Snow", "Moderate snow fall"),
            75: ("Snow", "Heavy snow fall"),
            77: ("Snow", "Snow grains"),
            80: ("Showers", "Slight rain showers"),
            81: ("Showers", "Moderate rain showers"),
            82: ("Showers", "Violent rain showers"),
            85: ("Snow Showers", "Slight snow showers"),
            86: ("Snow Showers", "Heavy snow showers"),
            95: ("Thunderstorm", "Thunderstorm"),
            96: ("Thunderstorm", "Thunderstorm with slight hail"),
            99: ("Thunderstorm", "Thunderstorm with heavy hail")
        }
        return weather_codes.get(code, ("Unknown", "Unknown condition"))
    
    # ========================================================================
    # CLOTHING RECOMMENDATIONS
    # ========================================================================
    def generate_clothing_recommendations(self, weather: Dict) -> Dict:
        """
        Generate smart clothing recommendations based on weather.
        
        Args:
            weather: Weather data dictionary
            
        Returns:
            dict: Recommendations with layers, footwear, accessories, materials, colors, tips
        """
        temp = weather.get("temperature", 20)
        feels_like = weather.get("feels_like", temp)
        condition = weather.get("condition", "Clear").lower()
        humidity = weather.get("humidity", 50)
        wind_speed = weather.get("wind_speed", 0)
        precipitation = weather.get("precipitation", 0)
        
        recommendations = {
            "layers": [],
            "accessories": [],
            "footwear": [],
            "materials": [],
            "colors": [],
            "tips": []
        }
        
        # Temperature-based recommendations
        effective_temp = feels_like
        
        if effective_temp < 0:
            recommendations["layers"] = ["Heavy winter coat", "Thermal underwear", "Thick sweater", "Wool pants"]
            recommendations["accessories"] = ["Insulated gloves", "Wool scarf", "Winter beanie", "Thermal socks"]
            recommendations["footwear"] = ["Insulated winter boots", "Waterproof boots"]
            recommendations["materials"] = ["Wool", "Down", "Fleece", "Thermal fabrics"]
            recommendations["colors"] = ["Dark colors (retain heat)"]
            recommendations["tips"] = [
                "Dress in multiple layers for insulation",
                "Cover all exposed skin to prevent frostbite",
                "Avoid cotton - it retains moisture"
            ]
        elif effective_temp < 10:
            recommendations["layers"] = ["Warm jacket or coat", "Long-sleeve shirt", "Sweater", "Jeans or trousers"]
            recommendations["accessories"] = ["Light scarf", "Gloves (optional)"]
            recommendations["footwear"] = ["Closed-toe shoes", "Boots", "Sneakers"]
            recommendations["materials"] = ["Wool blends", "Cotton", "Denim"]
            recommendations["colors"] = ["Neutral tones", "Earth colors"]
            recommendations["tips"] = ["Layer up for warmth and flexibility", "A jacket is essential"]
        elif effective_temp < 20:
            recommendations["layers"] = ["Light jacket or cardigan", "Long sleeves or t-shirt", "Jeans or casual pants"]
            recommendations["accessories"] = ["Light scarf (optional)"]
            recommendations["footwear"] = ["Sneakers", "Casual shoes", "Loafers"]
            recommendations["materials"] = ["Cotton", "Linen blends", "Light denim"]
            recommendations["colors"] = ["Versatile colors", "Spring/autumn tones"]
            recommendations["tips"] = ["Perfect weather for layering", "Bring a light jacket for evening"]
        elif effective_temp < 28:
            recommendations["layers"] = ["T-shirt or blouse", "Shorts or light pants", "Light dress"]
            recommendations["accessories"] = ["Sunglasses", "Light hat"]
            recommendations["footwear"] = ["Sandals", "Sneakers", "Casual shoes"]
            recommendations["materials"] = ["Cotton", "Linen", "Breathable fabrics"]
            recommendations["colors"] = ["Light colors", "Pastels", "Bright colors"]
            recommendations["tips"] = ["Stay cool and comfortable", "Light, breathable fabrics are best"]
        else:  # 28°C+
            recommendations["layers"] = ["Light breathable t-shirt", "Shorts", "Tank top", "Light dress"]
            recommendations["accessories"] = ["Sunglasses", "Wide-brim hat", "Sunscreen"]
            recommendations["footwear"] = ["Sandals", "Flip-flops", "Breathable sneakers"]
            recommendations["materials"] = ["Light cotton", "Linen", "Moisture-wicking fabrics"]
            recommendations["colors"] = ["White", "Light colors (reflect heat)", "Pastels"]
            recommendations["tips"] = [
                "Stay hydrated throughout the day",
                "Avoid dark colors - they absorb heat",
                "Seek shade during peak sun hours"
            ]
        
        # Weather condition adjustments
        if "rain" in condition or "drizzle" in condition or "showers" in condition or precipitation > 0:
            if "Umbrella" not in recommendations["accessories"]:
                recommendations["accessories"].append("Umbrella")
            recommendations["footwear"] = ["Waterproof shoes", "Rain boots", "Water-resistant sneakers"]
            recommendations["tips"].append("Bring waterproof outerwear")
            recommendations["materials"].append("Waterproof/water-resistant fabrics")
        
        if "snow" in condition or weather.get("snowfall", 0) > 0:
            recommendations["accessories"].extend(["Insulated gloves", "Warm winter hat"])
            recommendations["footwear"] = ["Insulated winter boots", "Waterproof snow boots"]
            recommendations["tips"].extend(["Watch for slippery surfaces", "Waterproof everything"])
        
        if "thunderstorm" in condition:
            recommendations["tips"].append("Stay indoors during thunderstorm")
        
        if wind_speed > 20:
            recommendations["tips"].append("Wear wind-resistant outer layer")
            recommendations["materials"].append("Wind-resistant fabrics")
        
        if humidity > 70 and effective_temp > 20:
            recommendations["tips"].append("High humidity - choose moisture-wicking fabrics")
            recommendations["materials"].append("Moisture-wicking materials")
        
        if "clear" in condition or "cloudy" in condition:
            if effective_temp > 20 and "Sunglasses" not in recommendations["accessories"]:
                recommendations["accessories"].append("Sunglasses")
            if effective_temp > 25:
                recommendations["tips"].append("Apply sunscreen (SPF 30+)")
        
        # Remove duplicates
        for key in recommendations:
            if isinstance(recommendations[key], list):
                recommendations[key] = list(dict.fromkeys(recommendations[key]))
        
        logger.info("Clothing recommendations generated")
        return recommendations
    
    # ========================================================================
    # SIMILARITY SEARCH (Find Similar Items)
    # ========================================================================
    def find_similar_items(
        self, 
        query_embedding: np.ndarray, 
        wardrobe_items: List[Dict],
        top_k: int = 5,
        min_similarity: float = 0.2
    ) -> List[Dict]:
        """
        Find similar clothing items using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            wardrobe_items: List of items with 'embedding' field
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            list: Sorted list of similar items with similarity scores
        """
        try:
            similarities = []
            
            for item in wardrobe_items:
                if item.get('embedding') is not None:
                    embedding = np.array(item['embedding'])
                    
                    # Cosine similarity (embeddings are already normalized)
                    similarity = float(np.dot(query_embedding, embedding))
                    
                    if similarity >= min_similarity:
                        similarities.append({
                            **item,
                            'similarity_score': round(similarity, 3)
                        })
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            logger.info(f"Found {len(similarities)} similar items (top {top_k} returned)")
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    # ========================================================================
    # UNIFIED UPLOAD & ANALYZE
    # ========================================================================
    async def upload_and_analyze(
        self, 
        file: UploadFile, 
        location: Optional[str] = None,
        wardrobe_items: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Unified method: Upload image, generate embedding, fetch weather, recommend outfits.
        
        Args:
            file: Image file to upload
            location: User's location (city name)
            wardrobe_items: User's existing wardrobe (for similarity search)
            
        Returns:
            dict: Complete analysis with image URL, embedding, weather, recommendations, similar items
        """
        try:
            # Step 1: Upload image
            logger.info("Step 1: Uploading image...")
            image_url = await self.upload_image(file, folder="clothing", optimize=True)
            
            # Step 2: Generate embedding
            logger.info("Step 2: Generating AI embedding...")
            file.file.seek(0)  # Reset file pointer
            file_bytes = await file.read()
            embedding = self.generate_embedding(file_bytes)
            
            # Step 3: Fetch weather (if location provided)
            weather = None
            recommendations = None
            if location:
                logger.info(f"Step 3: Fetching weather for {location}...")
                location_info = self.get_coordinates(location)
                if location_info:
                    weather = self.get_current_weather(
                        location_info["latitude"],
                        location_info["longitude"],
                        location_info
                    )
                    if weather:
                        recommendations = self.generate_clothing_recommendations(weather)
            
            # Step 4: Find similar items (if wardrobe provided)
            similar_items = []
            if wardrobe_items:
                logger.info("Step 4: Finding similar items...")
                similar_items = self.find_similar_items(
                    embedding,
                    wardrobe_items,
                    top_k=5
                )
            
            # Build response
            response = {
                "success": True,
                "image_url": image_url,
                "embedding": embedding.tolist(),
                "embedding_dimension": len(embedding)
            }
            
            if weather:
                response["weather"] = weather
            
            if recommendations:
                response["recommendations"] = recommendations
            
            if similar_items:
                response["similar_items"] = similar_items
            
            logger.info("Upload and analysis completed successfully")
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Upload and analysis failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis failed: {str(e)}"
            )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
_fashion_ai_service = None

def get_fashion_ai_service() -> FashionAIService:
    """
    Get or create singleton instance of FashionAIService.
    Lazy loading pattern - service is only initialized when first called.
    
    Returns:
        FashionAIService: Singleton service instance
    """
    global _fashion_ai_service
    if _fashion_ai_service is None:
        _fashion_ai_service = FashionAIService()
    return _fashion_ai_service