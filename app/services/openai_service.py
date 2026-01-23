"""
OpenAI Service - Intelligent Ranking & Explanation

Purpose:
- Rank outfit suggestions intelligently
- Generate natural language explanations
- Provide styling tips

NOT used for image understanding (that's CLIP's job)
"""

from openai import OpenAI
from typing import List, Dict, Optional
import logging
import json

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    OpenAI service for outfit ranking and explanation generation
    """
    
    def __init__(self, api_key: str):
        """
        Initialize OpenAI service
        
        Args:
            api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # Cost-effective for text tasks
    
    def rank_and_explain_outfits(
        self,
        outfits: List[Dict],
        weather: Optional[Dict] = None,
        occasion: Optional[str] = None,
        user_preferences: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Use OpenAI to intelligently rank outfits and provide explanations
        
        Args:
            outfits: List of outfit dictionaries from OutfitGenerator
            weather: Current weather data
            occasion: Target occasion
            user_preferences: User style preferences
            
        Returns:
            Ranked outfits with enhanced explanations
        """
        try:
            # Prepare context for OpenAI
            context = self._build_context(weather, occasion, user_preferences)
            
            # Prepare outfit data (remove embeddings to save tokens)
            simplified_outfits = []
            for i, outfit in enumerate(outfits):
                simplified = {
                    'outfit_id': i,
                    'items': [
                        {
                            'name': item.get('item_name', 'Item'),
                            'category': item.get('category'),
                            'color': item.get('color'),
                            'brand': item.get('brand')
                        }
                        for item in outfit['items']
                    ],
                    'coherence_score': outfit.get('coherence_score', 0.5),
                    'initial_reason': outfit.get('reason', '')
                }
                simplified_outfits.append(simplified)
            
            # Create prompt
            prompt = self._create_ranking_prompt(context, simplified_outfits)
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional fashion stylist AI. Analyze outfits and provide expert fashion advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse response
            result = self._parse_ranking_response(
                response.choices[0].message.content,
                outfits
            )
            
            return result
        
        except Exception as e:
            logger.error(f"OpenAI ranking failed: {e}")
            # Fallback: return outfits with original ordering
            return outfits
    
    def generate_styling_tips(
        self,
        outfit: Dict,
        weather: Optional[Dict] = None,
        occasion: Optional[str] = None
    ) -> str:
        """
        Generate personalized styling tips for an outfit
        
        Args:
            outfit: Outfit dictionary
            weather: Weather data
            occasion: Occasion
            
        Returns:
            Styling tips as string
        """
        try:
            # Prepare outfit description
            items_desc = ", ".join([
                f"{item.get('color', '')} {item.get('category', 'item')}"
                for item in outfit['items']
            ])
            
            # Create prompt
            prompt = f"""
            Generate 3-4 concise styling tips for this outfit:
            
            Items: {items_desc}
            Weather: {weather.get('temperature', 'N/A')}°C, {weather.get('condition', 'N/A') if weather else 'N/A'}
            Occasion: {occasion or 'General wear'}
            
            Format as bullet points. Keep tips practical and specific.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fashion stylist providing practical outfit advice."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Styling tips generation failed: {e}")
            return "• Mix and match with confidence\n• Pay attention to fit and proportion\n• Accessorize to elevate your look"
    
    def _build_context(
        self,
        weather: Optional[Dict],
        occasion: Optional[str],
        user_preferences: Optional[List[str]]
    ) -> str:
        """Build context string for OpenAI prompt"""
        context_parts = []
        
        if weather:
            context_parts.append(
                f"Weather: {weather.get('temperature', 'N/A')}°C, "
                f"{weather.get('condition', 'N/A')}"
            )
        
        if occasion:
            context_parts.append(f"Occasion: {occasion}")
        
        if user_preferences:
            context_parts.append(f"User preferences: {', '.join(user_preferences)}")
        
        return " | ".join(context_parts) if context_parts else "General outfit selection"
    
    def _create_ranking_prompt(
        self,
        context: str,
        outfits: List[Dict]
    ) -> str:
        """Create prompt for outfit ranking"""
        prompt = f"""
Context: {context}

I have {len(outfits)} outfit combinations. Each has a visual coherence score (0-1) from CLIP embeddings.

Outfits:
{json.dumps(outfits, indent=2)}

Please:
1. Rank these outfits from best to worst (considering context, coherence, and fashion sense)
2. For each outfit, provide a brief explanation (max 40 words) of why it's appropriate or what makes it work

Respond in JSON format:
{{
    "rankings": [
        {{
            "outfit_id": 0,
            "rank": 1,
            "explanation": "Brief explanation here",
            "style_score": 0.85
        }},
        ...
    ]
}}
"""
        return prompt
    
    def _parse_ranking_response(
        self,
        response_text: str,
        original_outfits: List[Dict]
    ) -> List[Dict]:
        """Parse OpenAI response and merge with original outfits"""
        try:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON found in OpenAI response")
                return original_outfits
            
            json_str = response_text[start_idx:end_idx]
            parsed = json.loads(json_str)
            
            rankings = parsed.get('rankings', [])
            
            # Create mapping of outfit_id to ranking info
            ranking_map = {
                r['outfit_id']: r
                for r in rankings
            }
            
            # Merge rankings with original outfits
            for i, outfit in enumerate(original_outfits):
                if i in ranking_map:
                    outfit['ai_rank'] = ranking_map[i].get('rank', i + 1)
                    outfit['ai_explanation'] = ranking_map[i].get('explanation', outfit.get('reason', ''))
                    outfit['ai_style_score'] = ranking_map[i].get('style_score', outfit.get('coherence_score', 0.5))
                else:
                    outfit['ai_rank'] = i + 1
                    outfit['ai_explanation'] = outfit.get('reason', '')
                    outfit['ai_style_score'] = outfit.get('coherence_score', 0.5)
            
            # Sort by AI ranking
            original_outfits.sort(key=lambda x: x.get('ai_rank', 999))
            
            return original_outfits
        
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            return original_outfits


# ============= SINGLETON PATTERN =============

_openai_service_instance: Optional[OpenAIService] = None


def get_openai_service(api_key: str) -> OpenAIService:
    """
    Get or create OpenAI service singleton
    
    Args:
        api_key: OpenAI API key
        
    Returns:
        OpenAIService instance
    """
    global _openai_service_instance
    
    if _openai_service_instance is None:
        logger.info("Initializing OpenAI service...")
        _openai_service_instance = OpenAIService(api_key)
    
    return _openai_service_instance