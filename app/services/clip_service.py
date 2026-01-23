"""
CLIP Service - Image & Text Embeddings
Handles CLIP model for visual similarity search
"""

import torch
import clip
from PIL import Image
import numpy as np
from typing import List, Dict, Optional
import logging
from pathlib import Path
import io
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class CLIPService:
    """CLIP-based AI service for fashion embeddings and similarity"""
    
    def __init__(self, model_name: str = "ViT-B/32", device: str = None):
        """
        Initialize CLIP model
        
        Args:
            model_name: CLIP model variant ("ViT-B/32" or "ViT-L/14")
            device: Device to run model on ("cpu" or "cuda")
        """
        try:
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"Loading CLIP model {model_name} on {self.device}")
            
            self.model, self.preprocess = clip.load(model_name, device=self.device)
            self.model.eval()
            
            logger.info("CLIP model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise
    
    def encode_image(self, image_path: str) -> np.ndarray:
        """
        Generate CLIP embedding for an image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            Normalized embedding vector (512 dimensions for ViT-B/32)
        """
        try:
            image = Image.open(image_path).convert('RGB')
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                # Normalize for cosine similarity
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy().flatten()
        
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            raise
    
    def encode_image_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """
        Generate CLIP embedding from image bytes
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Normalized embedding vector
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            return image_features.cpu().numpy().flatten()
        
        except Exception as e:
            logger.error(f"Error encoding image from bytes: {e}")
            raise
    
    def get_image_embedding(self, image_source: str) -> Optional[np.ndarray]:
        """
        Universal method to get image embedding from URL or local path
        
        Automatically detects if source is:
        - HTTP/HTTPS URL (downloads and processes)
        - S3 URL (downloads and processes)
        - Local file path (processes directly)
        
        Args:
            image_source: URL or local file path
            
        Returns:
            Normalized embedding vector or None if failed
        """
        try:
            # Check if it's a URL
            parsed = urlparse(image_source)
            is_url = parsed.scheme in ('http', 'https', 's3')
            
            if is_url:
                # Download image from URL
                logger.info(f"Downloading image from URL: {image_source}")
                response = requests.get(image_source, timeout=10)
                response.raise_for_status()
                
                # Process from bytes
                return self.encode_image_from_bytes(response.content)
            else:
                # Process local file
                logger.info(f"Processing local image: {image_source}")
                return self.encode_image(image_source)
                
        except requests.RequestException as e:
            logger.error(f"Failed to download image from {image_source}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting image embedding from {image_source}: {e}")
            return None
    
    def encode_text(self, text: str) -> np.ndarray:
        """
        Generate CLIP embedding for text query
        
        Args:
            text: Text description (e.g., "red formal dress")
            
        Returns:
            Normalized embedding vector
        """
        try:
            text_input = clip.tokenize([text]).to(self.device)
            
            with torch.no_grad():
                text_features = self.model.encode_text(text_input)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            return text_features.cpu().numpy().flatten()
        
        except Exception as e:
            logger.error(f"Error encoding text '{text}': {e}")
            raise
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0 to 1)
        """
        try:
            # Ensure embeddings are normalized
            emb1 = embedding1 / np.linalg.norm(embedding1)
            emb2 = embedding2 / np.linalg.norm(embedding2)
            
            similarity = np.dot(emb1, emb2)
            return float(similarity)
        
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def batch_compute_similarity(
        self,
        query_embedding: np.ndarray,
        item_embeddings: List[np.ndarray]
    ) -> np.ndarray:
        """
        Compute similarities between query and multiple items efficiently
        
        Args:
            query_embedding: Query embedding vector
            item_embeddings: List of item embedding vectors
            
        Returns:
            Array of similarity scores
        """
        try:
            # Stack embeddings into matrix
            embeddings_matrix = np.stack(item_embeddings)
            
            # Normalize query
            query_norm = query_embedding / np.linalg.norm(query_embedding)
            
            # Normalize items
            embeddings_norm = embeddings_matrix / np.linalg.norm(
                embeddings_matrix, axis=1, keepdims=True
            )
            
            # Compute all similarities at once
            similarities = np.dot(embeddings_norm, query_norm)
            
            return similarities
        
        except Exception as e:
            logger.error(f"Error in batch similarity computation: {e}")
            return np.zeros(len(item_embeddings))
    
    def find_similar_items(
        self,
        query_embedding: np.ndarray,
        wardrobe_items: List[Dict],
        top_k: int = 10,
        min_similarity: float = 0.2
    ) -> List[Dict]:
        """
        Find similar clothing items using CLIP embeddings
        
        Args:
            query_embedding: Query embedding (from text or image)
            wardrobe_items: List of clothing items with 'embedding' field
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of items sorted by similarity score
        """
        try:
            similarities = []
            
            for item in wardrobe_items:
                if item.get('embedding') is not None:
                    embedding = np.array(item['embedding'])
                    similarity = self.compute_similarity(query_embedding, embedding)
                    
                    if similarity >= min_similarity:
                        similarities.append({
                            **item,
                            'similarity_score': round(float(similarity), 3)
                        })
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return similarities[:top_k]
        
        except Exception as e:
            logger.error(f"Error finding similar items: {e}")
            return []


# ============= SINGLETON PATTERN =============
# Lazy loading - model only initialized when first accessed

_clip_service_instance: Optional[CLIPService] = None


def get_clip_service(model_name: str = "ViT-B/32", device: str = None) -> CLIPService:
    """
    Get or create CLIP service singleton
    
    Args:
        model_name: CLIP model variant
        device: Device to run on
        
    Returns:
        CLIPService instance
    """
    global _clip_service_instance
    
    if _clip_service_instance is None:
        logger.info("Initializing CLIP service...")
        _clip_service_instance = CLIPService(model_name, device)
    
    return _clip_service_instance