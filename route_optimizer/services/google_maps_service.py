from typing import Dict, List
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class GoogleMapsService:
    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_SERVER_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"

    def get_route(self, start_location: str, end_location: str) -> Dict:
        """Get route between two locations using Google Maps Directions API."""
        try:
            logger.info(f"Getting route from {start_location} to {end_location}")
            logger.info(f"Using Google Maps API key: {self.api_key[:10]}...")
            
            response = requests.get(
                self.base_url,
                params={
                    "origin": start_location,
                    "destination": end_location,
                    "key": self.api_key
                }
            )
            
            data = response.json()
            logger.info(f"Raw route data: {data}")
            
            if data.get('status') != 'OK':
                raise Exception(f"Route API failed: {data.get('status')} - {data.get('error_message', 'No error message')}")

            route = data['routes'][0]
            points = []
            
            # Decode polyline points
            for leg in route['legs']:
                for step in leg['steps']:
                    decoded = self._decode_polyline(step['polyline']['points'])
                    logger.info(f"Decoded points from step: {decoded[:2]}...")
                    points.extend(decoded)
            
            return {
                'points': points,
                'total_distance': route['legs'][0]['distance']['value'] * 0.000621371  # Convert meters to miles
            }
            
        except Exception as e:
            logger.error(f"Route failed: {str(e)}")
            raise

    def _decode_polyline(self, polyline: str) -> List[Dict[str, float]]:
        """Decode Google's polyline format into lat/lon points."""
        coords = []
        index = 0
        lat = 0
        lng = 0
        
        while index < len(polyline):
            for i, target in enumerate([lat, lng]):
                shift = 0
                result = 0
                
                while True:
                    byte = ord(polyline[index]) - 63
                    index += 1
                    result |= (byte & 0x1F) << shift
                    shift += 5
                    if not byte >= 0x20:
                        break
                
                if result & 1:
                    result = ~(result >> 1)
                else:
                    result = result >> 1
                    
                if i == 0:  # latitude
                    lat += result / 100000.0
                else:      # longitude
                    lng += result / 100000.0
                    coords.append({'lat': lat, 'lon': lng})
        
        return coords 