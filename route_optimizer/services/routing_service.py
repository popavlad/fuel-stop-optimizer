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
            
            # Create route points with CORRECT coordinates
            route_points = []
            for point in coordinates:
                route_points.append({
                    'lat': float(point[0]),  # First value should be latitude
                    'lon': float(point[1])   # Second value should be longitude
                })
            
            # Log first point to verify format matches station
            if route_points:
                logger.info(f"First route point: {route_points[0]}")
            
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

    def _get_route_data(self, start_coords: List[float], end_coords: List[float]) -> Dict:
        """Get route data using OpenRouteService."""
        try:
            logger.info(f"Getting route data between {start_coords} and {end_coords}")
            
            response = requests.post(
                f"{self.ors_url}/v2/directions/driving-car/json",
                json={"coordinates": [start_coords, end_coords]},
                headers={
                    'Authorization': self.ors_key,
                    'Content-Type': 'application/json'
                }
            )
            
            response.raise_for_status()  # Add this to catch bad responses
            data = response.json()
            
            if not data.get('routes'):
                logger.error(f"No routes in response: {data}")
                raise ValueError("No route found in response")
                
            return {
                'routes': [{
                    'geometry': data['routes'][0]['geometry']
                }]
            }
            
        except Exception as e:
            logger.error(f"Routing failed: {str(e)}")
            raise ValueError(f"Routing failed: {str(e)}")
    
    def optimize_route(self, origin: str, destination: str, tank_size: float, current_fuel: float) -> List[Dict]:
        """For now, just get route and find nearby stations."""
        try:
            # Get route points
            route_points = self.get_route(origin, destination)
            logger.info(f"Got route with {len(route_points['points'])} points")
            
            # Find stations near route
            stations = self.fuel_data_service.get_stations_near_route(route_points['points'])
            logger.info(f"Found {len(stations)} stations near route")
            
            # For now, just return the stations we found
            return stations
            
        except Exception as e:
            logger.error(f"Route optimization failed: {str(e)}")
            raise ValueError(f"Route optimization failed: {str(e)}") 