# app/services/weather_service.py - COMPLETE ENHANCED VERSION
import requests
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1"
        self.cache = {}
        self.cache_duration = 15 * 60  # 15 minutes in seconds
        
        # Temperature thresholds for outfit recommendations
        self.temperature_categories = {
            'freezing': {'min': -float('inf'), 'max': 0},
            'cold': {'min': 0, 'max': 10},
            'cool': {'min': 10, 'max': 20},
            'warm': {'min': 20, 'max': 30},
            'hot': {'min': 30, 'max': float('inf')}
        }
    
    # ==================== NEW METHODS (Add to existing class) ====================
    
    def get_temperature_category(self, temp_c: float) -> str:
        """Get temperature category name"""
        for category, bounds in self.temperature_categories.items():
            if bounds['min'] <= temp_c < bounds['max']:
                return category
        return 'moderate'
    
    def get_weather_with_category(self, location: str) -> Optional[Dict]:
        """Get weather with temperature category for outfit suggestions"""
        weather = self.get_current_weather(location)
        if weather:
            temp_c = weather.get('temperature', 20)
            weather['category'] = self.get_temperature_category(temp_c)
            weather['dress_recommendation'] = self.get_dress_recommendation(weather)
        return weather
    
    def get_dress_recommendation(self, weather: Dict) -> Dict:
        """Get detailed dress recommendations based on weather"""
        temp = weather.get('temperature', 20)
        condition = weather.get('condition', '').lower()
        category = self.get_temperature_category(temp)
        
        recommendations = {
            'layers': '',
            'outerwear': '',
            'bottom': '',
            'shoes': '',
            'accessories': ''
        }
        
        # Temperature-based recommendations
        if category == 'freezing':
            recommendations.update({
                'layers': 'Heavy layering required (3+ layers)',
                'outerwear': 'Insulated winter coat, thermal layers',
                'bottom': 'Thermal pants, heavy jeans or trousers',
                'shoes': 'Insulated waterproof boots',
                'accessories': 'Gloves, scarf, beanie, ear protection'
            })
        elif category == 'cold':
            recommendations.update({
                'layers': 'Moderate layering (2-3 layers)',
                'outerwear': 'Winter coat or heavy jacket',
                'bottom': 'Jeans with thermal layer or thick trousers',
                'shoes': 'Boots or closed shoes with insulation',
                'accessories': 'Gloves optional, scarf recommended'
            })
        elif category == 'cool':
            recommendations.update({
                'layers': 'Light layering (1-2 layers)',
                'outerwear': 'Light jacket, sweater, or cardigan',
                'bottom': 'Jeans, trousers, or light pants',
                'shoes': 'Sneakers, casual shoes, or light boots',
                'accessories': 'Optional scarf or light gloves'
            })
        elif category == 'warm':
            recommendations.update({
                'layers': 'Single layer or light layering',
                'outerwear': 'None or light cardigan/shirt',
                'bottom': 'Shorts, skirts, or light trousers',
                'shoes': 'Breathable shoes, sneakers, or sandals',
                'accessories': 'Sunglasses, hat, light scarf'
            })
        elif category == 'hot':
            recommendations.update({
                'layers': 'Minimal layers',
                'outerwear': 'None or very light cover-up',
                'bottom': 'Shorts, skirts, light dresses',
                'shoes': 'Sandals, open shoes, breathable footwear',
                'accessories': 'Sunglasses, hat, sunscreen essential'
            })
        
        # Weather condition adjustments
        if 'rain' in condition:
            recommendations['shoes'] = 'Waterproof shoes or boots'
            recommendations['accessories'] = 'Umbrella, raincoat, waterproof bag'
        
        if 'snow' in condition:
            recommendations['shoes'] = 'Waterproof snow boots with good traction'
            recommendations['accessories'] = 'Winter gloves, waterproof gloves, thermal hat'
        
        if 'wind' in condition:
            recommendations['outerwear'] = 'Wind-resistant jacket'
            recommendations['accessories'] = 'Scarf to protect face, secure hat'
        
        if 'sun' in condition:
            recommendations['accessories'] = 'Sunglasses, hat, sunscreen essential'
        
        return recommendations
    
    def get_clothing_material_recommendations(self, category: str, condition: str) -> List[str]:
        """Get recommended materials based on weather"""
        materials = []
        
        if category in ['hot', 'warm'] or 'sun' in condition:
            materials.extend(['Linen', 'Cotton', 'Rayon', 'Seersucker'])
        
        if category in ['cold', 'freezing']:
            materials.extend(['Wool', 'Fleece', 'Down', 'Cashmere'])
        
        if 'rain' in condition:
            materials.extend(['Gore-Tex', 'Nylon', 'Polyester', 'Waterproof fabrics'])
        
        if 'wind' in condition:
            materials.extend(['Windbreaker materials', 'Tightly woven fabrics'])
        
        return list(set(materials))  # Remove duplicates
    
    def get_weather_tips(self, weather: Dict) -> List[str]:
        """Get weather-specific style tips"""
        tips = []
        category = self.get_temperature_category(weather.get('temperature', 20))
        condition = weather.get('condition', '').lower()
        temp = weather.get('temperature', 20)
        
        if category in ['cold', 'freezing']:
            tips.append('Layer clothing for better insulation')
            tips.append('Protect extremities with gloves, hat, and scarf')
            tips.append('Wear thermal layers close to skin')
        
        if category in ['warm', 'hot']:
            tips.append('Choose light-colored, breathable fabrics')
            tips.append('Wear loose-fitting clothes for better airflow')
            tips.append('Stay hydrated throughout the day')
        
        if 'rain' in condition:
            tips.append('Carry a compact umbrella or wear a waterproof jacket')
            tips.append('Choose darker colors that hide water spots')
            tips.append('Wear waterproof shoes to keep feet dry')
        
        if 'sun' in condition:
            tips.append('Apply sunscreen to exposed skin')
            tips.append('Wear a hat and sunglasses for UV protection')
            tips.append('Light colors reflect heat better than dark ones')
        
        if 'wind' in condition:
            tips.append('Wear close-fitting layers to prevent heat loss')
            tips.append('Choose wind-resistant outer layers')
            tips.append('Secure accessories that might blow away')
        
        return tips
    
    # ==================== YOUR EXISTING METHODS ====================
    
    def get_coordinates(self, location: str) -> Optional[Dict]:
        """Get latitude and longitude for a location using Open-Meteo geocoding"""
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
                    "admin1": result.get("admin1"),  # State/Province
                    "timezone": result.get("timezone")
                }
                logger.info(f"Coordinates for {location}: {location_info['latitude']}, {location_info['longitude']}")
                return location_info
            
            logger.warning(f"No coordinates found for location: {location}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Geocoding API error for {location}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting coordinates for {location}: {e}")
            return None
    
    def get_current_weather(self, location: str) -> Optional[Dict]:
        """Get current weather for a location"""
        # First, get coordinates for the location
        location_info = self.get_coordinates(location)
        if not location_info:
            return None
        
        return self.get_weather_by_coordinates(
            location_info["latitude"], 
            location_info["longitude"],
            location_info
        )
    
    def get_weather_by_coordinates(self, lat: float, lon: float, location_info: Optional[Dict] = None) -> Optional[Dict]:
        """Get current weather by coordinates (latitude, longitude)"""
        try:
            # Check cache first
            cache_key = f"weather_{lat}_{lon}"
            current_time = datetime.now()
            
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if (current_time - timestamp).seconds < self.cache_duration:
                    logger.info(f"Using cached weather for ({lat}, {lon})")
                    return cached_data
            
            url = f"{self.base_url}/forecast"
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
                    "surface_pressure",
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
            
            # Map WMO weather codes to descriptions
            weather_code = current.get("weather_code", 0)
            condition, description = self._get_weather_description(weather_code)
            
            # Parse and format weather data
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
            
            # Cache the result
            self.cache[cache_key] = (weather_info, current_time)
            
            logger.info(f"Weather fetched for coordinates ({lat}, {lon}): {weather_info['temperature']}°C, {weather_info['condition']}")
            return weather_info
            
        except requests.RequestException as e:
            logger.error(f"Weather API error for coordinates ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting weather for coordinates ({lat}, {lon}): {e}")
            return None
    
    def get_forecast(self, location: str, days: int = 7) -> Optional[List[Dict]]:
        """Get weather forecast for next few days"""
        # First, get coordinates for the location
        location_info = self.get_coordinates(location)
        if not location_info:
            return None
        
        return self.get_forecast_by_coordinates(
            location_info["latitude"],
            location_info["longitude"],
            days
        )
    
    def get_forecast_by_coordinates(self, lat: float, lon: float, days: int = 7) -> Optional[List[Dict]]:
        """Get weather forecast by coordinates"""
        try:
            cache_key = f"forecast_{lat}_{lon}_{days}"
            current_time = datetime.now()
            
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if (current_time - timestamp).seconds < self.cache_duration:
                    logger.info(f"Using cached forecast for ({lat}, {lon})")
                    return cached_data
            
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "apparent_temperature_max",
                    "apparent_temperature_min",
                    "precipitation_sum",
                    "rain_sum",
                    "showers_sum",
                    "snowfall_sum",
                    "precipitation_probability_max",
                    "wind_speed_10m_max",
                    "wind_gusts_10m_max",
                    "wind_direction_10m_dominant",
                    "sunrise",
                    "sunset"
                ],
                "timezone": "auto",
                "forecast_days": min(days, 16)  # Open-Meteo supports up to 16 days
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            
            forecasts = []
            for i in range(len(dates)):
                weather_code = daily.get("weather_code", [])[i]
                condition, description = self._get_weather_description(weather_code)
                
                forecasts.append({
                    "date": dates[i],
                    "temperature_max": round(daily.get("temperature_2m_max", [])[i]),
                    "temperature_min": round(daily.get("temperature_2m_min", [])[i]),
                    "temperature": round((daily.get("temperature_2m_max", [])[i] + daily.get("temperature_2m_min", [])[i]) / 2),
                    "feels_like_max": round(daily.get("apparent_temperature_max", [])[i]),
                    "feels_like_min": round(daily.get("apparent_temperature_min", [])[i]),
                    "condition": condition,
                    "description": description,
                    "weather_code": weather_code,
                    "precipitation": round(daily.get("precipitation_sum", [])[i], 1),
                    "rain": round(daily.get("rain_sum", [])[i], 1),
                    "showers": round(daily.get("showers_sum", [])[i], 1),
                    "snowfall": round(daily.get("snowfall_sum", [])[i], 1),
                    "precipitation_probability": daily.get("precipitation_probability_max", [])[i],
                    "wind_speed": round(daily.get("wind_speed_10m_max", [])[i], 1),
                    "wind_gusts": round(daily.get("wind_gusts_10m_max", [])[i], 1),
                    "wind_direction": daily.get("wind_direction_10m_dominant", [])[i],
                    "sunrise": daily.get("sunrise", [])[i],
                    "sunset": daily.get("sunset", [])[i]
                })
            
            # Cache the result
            self.cache[cache_key] = (forecasts, current_time)
            
            logger.info(f"Forecast fetched for coordinates ({lat}, {lon}): {len(forecasts)} days")
            return forecasts
            
        except requests.RequestException as e:
            logger.error(f"Forecast API error for coordinates ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting forecast for coordinates ({lat}, {lon}): {e}")
            return None
    
    def get_hourly_forecast(self, lat: float, lon: float, hours: int = 24) -> Optional[List[Dict]]:
        """Get hourly weather forecast"""
        try:
            cache_key = f"hourly_{lat}_{lon}_{hours}"
            current_time = datetime.now()
            
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if (current_time - timestamp).seconds < self.cache_duration:
                    logger.info(f"Using cached hourly forecast for ({lat}, {lon})")
                    return cached_data
            
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation_probability",
                    "precipitation",
                    "rain",
                    "showers",
                    "snowfall",
                    "weather_code",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m"
                ],
                "timezone": "auto",
                "forecast_days": min((hours // 24) + 1, 16)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])[:hours]
            
            forecasts = []
            for i in range(len(times)):
                weather_code = hourly.get("weather_code", [])[i]
                condition, description = self._get_weather_description(weather_code)
                
                forecasts.append({
                    "time": times[i],
                    "temperature": round(hourly.get("temperature_2m", [])[i]),
                    "feels_like": round(hourly.get("apparent_temperature", [])[i]),
                    "humidity": hourly.get("relative_humidity_2m", [])[i],
                    "condition": condition,
                    "description": description,
                    "weather_code": weather_code,
                    "precipitation": round(hourly.get("precipitation", [])[i], 1),
                    "precipitation_probability": hourly.get("precipitation_probability", [])[i],
                    "rain": round(hourly.get("rain", [])[i], 1),
                    "showers": round(hourly.get("showers", [])[i], 1),
                    "snowfall": round(hourly.get("snowfall", [])[i], 1),
                    "cloud_cover": hourly.get("cloud_cover", [])[i],
                    "wind_speed": round(hourly.get("wind_speed_10m", [])[i], 1),
                    "wind_direction": hourly.get("wind_direction_10m", [])[i]
                })
            
            # Cache the result
            self.cache[cache_key] = (forecasts, current_time)
            
            return forecasts
            
        except requests.RequestException as e:
            logger.error(f"Hourly forecast API error for coordinates ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting hourly forecast: {e}")
            return None
    
    def _get_weather_description(self, code: int) -> tuple:
        """
        Convert WMO Weather interpretation codes to human-readable descriptions
        https://open-meteo.com/en/docs
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
    
    def get_clothing_recommendations(self, weather: Dict) -> Dict:
        """Get clothing recommendations based on weather"""
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
        
        # Temperature-based recommendations (using feels_like for better accuracy)
        effective_temp = feels_like
        category = self.get_temperature_category(effective_temp)
        
        if category == 'freezing':
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
        elif category == 'cold':
            recommendations["layers"] = ["Warm jacket or coat", "Long-sleeve shirt", "Sweater", "Jeans or trousers"]
            recommendations["accessories"] = ["Light scarf", "Gloves (optional)"]
            recommendations["footwear"] = ["Closed-toe shoes", "Boots", "Sneakers"]
            recommendations["materials"] = ["Wool blends", "Cotton", "Denim"]
            recommendations["colors"] = ["Neutral tones", "Earth colors"]
            recommendations["tips"] = [
                "Layer up for warmth and flexibility",
                "A jacket is essential"
            ]
        elif category == 'cool':
            recommendations["layers"] = ["Light jacket or cardigan", "Long sleeves or t-shirt", "Jeans or casual pants"]
            recommendations["accessories"] = ["Light scarf (optional)"]
            recommendations["footwear"] = ["Sneakers", "Casual shoes", "Loafers"]
            recommendations["materials"] = ["Cotton", "Linen blends", "Light denim"]
            recommendations["colors"] = ["Versatile colors", "Spring/autumn tones"]
            recommendations["tips"] = [
                "Perfect weather for layering",
                "Bring a light jacket for evening"
            ]
        elif category == 'warm':
            recommendations["layers"] = ["T-shirt or blouse", "Shorts or light pants", "Light dress"]
            recommendations["accessories"] = ["Sunglasses", "Light hat"]
            recommendations["footwear"] = ["Sandals", "Sneakers", "Casual shoes"]
            recommendations["materials"] = ["Cotton", "Linen", "Breathable fabrics"]
            recommendations["colors"] = ["Light colors", "Pastels", "Bright colors"]
            recommendations["tips"] = [
                "Stay cool and comfortable",
                "Light, breathable fabrics are best"
            ]
        else:  # 'hot'
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
        
        # Condition-based additions
        if "rain" in condition or "drizzle" in condition or "showers" in condition or precipitation > 0:
            if "Umbrella" not in recommendations["accessories"]:
                recommendations["accessories"].append("Umbrella")
            recommendations["footwear"] = ["Waterproof shoes", "Rain boots", "Water-resistant sneakers"]
            if "Bring waterproof outerwear" not in recommendations["tips"]:
                recommendations["tips"].append("Bring waterproof outerwear")
            recommendations["materials"].append("Waterproof/water-resistant fabrics")
        
        if "snow" in condition or weather.get("snowfall", 0) > 0:
            if "Insulated gloves" not in recommendations["accessories"]:
                recommendations["accessories"].extend(["Insulated gloves", "Warm winter hat"])
            recommendations["footwear"] = ["Insulated winter boots", "Waterproof snow boots"]
            recommendations["tips"].append("Watch for slippery surfaces")
            recommendations["tips"].append("Waterproof everything")
        
        if "thunderstorm" in condition:
            recommendations["tips"].append("Stay indoors during thunderstorm")
            recommendations["accessories"].append("Umbrella (avoid open areas)")
        
        # Wind adjustments
        if wind_speed > 20:
            recommendations["tips"].append("Wear wind-resistant outer layer")
            recommendations["materials"].append("Wind-resistant fabrics")
        
        # Humidity adjustments
        if humidity > 70 and effective_temp > 20:
            recommendations["tips"].append("High humidity - choose moisture-wicking fabrics")
            recommendations["materials"].append("Moisture-wicking materials")
        
        # Sun protection
        if "clear" in condition or "cloudy" in condition:
            if effective_temp > 20 and "Sunglasses" not in recommendations["accessories"]:
                recommendations["accessories"].append("Sunglasses")
            if effective_temp > 25:
                recommendations["tips"].append("Apply sunscreen (SPF 30+)")
        
        # Remove duplicates while preserving order
        for key in recommendations:
            if isinstance(recommendations[key], list):
                recommendations[key] = list(dict.fromkeys(recommendations[key]))
        
        return recommendations
    
    def generate_clothing_recommendations(self, weather: Dict) -> Dict:
        """Alias for get_clothing_recommendations for compatibility"""
        return self.get_clothing_recommendations(weather)
    
    def clear_cache(self):
        """Clear all cached weather data"""
        self.cache.clear()
        logger.info("Weather cache cleared")

# Singleton instance
weather_service = WeatherService()