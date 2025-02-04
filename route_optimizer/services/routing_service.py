import requests
import polyline
from typing import Dict, List
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class RoutingService:
    def __init__(self):
        self.ors_url = "https://api.openrouteservice.org"
        self.ors_key = settings.ORS_API_KEY
    
    def get_route(self, start_location: str, end_location: str) -> Dict:
        """Get route points and total distance between two locations."""
        try:
            # Get coordinates
            start_coords = self._geocode_location(start_location)
            end_coords = self._geocode_location(end_location)
            
            # Get route
            response = requests.post(
                f"{self.ors_url}/v2/directions/driving-car/json",
                json={"coordinates": [start_coords, end_coords]},
                headers={
                    'Authorization': self.ors_key,
                    'Content-Type': 'application/json'
                }
            )
            
            data = response.json()
            coordinates = polyline.decode(data['routes'][0]['geometry'])
            
            # Get total distance in miles (ORS returns meters)
            total_distance = data['routes'][0]['summary']['distance'] / 1609.34
            
            # Create route points
            route_points = []
            for point in coordinates:
                route_points.append({
                    'lat': float(point[0]),
                    'lon': float(point[1])
                })
            
            return {
                'points': route_points,
                'total_distance': round(total_distance, 2)
            }
            
        except Exception as e:
            logger.error(f"Route failed: {str(e)}")
            raise
    
    def _geocode_location(self, location: str) -> List[float]:
        """Get coordinates for a location."""
        response = requests.get(
            f"{self.ors_url}/geocode/search",
            params={'text': location},
            headers={'Authorization': self.ors_key}
        )
        
        data = response.json()
        return data['features'][0]['geometry']['coordinates']

   