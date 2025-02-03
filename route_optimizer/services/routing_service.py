import requests
import polyline
from typing import Dict, List, Tuple, Optional
from django.conf import settings
import re
import logging
import time

logger = logging.getLogger(__name__)

class RoutingService:
    def __init__(self):
        self.osrm_url = "https://router.project-osrm.org"
        self.photon_url = "https://photon.komoot.io"  # Public Photon instance
        self.cache = {}
        
    def get_route(self, start_location: str, end_location: str) -> Tuple[List[Dict], float, List[List[float]], Dict]:
        """
        Get route information between two locations.
        Returns: (highway_segments, total_distance, route_coordinates, state_info)
        """
        # First, geocode the locations
        logger.info(f"Geocoding locations: start={start_location}, end={end_location}")
        start_coords, start_state = self._geocode_location(start_location)
        end_coords, end_state = self._geocode_location(end_location)
        
        if not start_coords or not end_coords:
            raise ValueError("Could not geocode locations")
        
        logger.info(f"Coordinates found: start={start_coords} ({start_state}), end={end_coords} ({end_state})")
        
        # Get the route
        route_data = self._get_route_data(start_coords, end_coords)
        
        # Extract route information
        route_geometry = route_data['routes'][0]['geometry']
        total_distance = route_data['routes'][0]['distance'] / 1000.0 * 0.621371  # Convert meters to miles
        
        # Decode the route geometry
        route_coordinates = polyline.decode(route_geometry)
        
        # Extract highway segments from the route steps
        highway_segments = self._extract_highway_segments(route_data['routes'][0]['legs'][0]['steps'])
        
        # Create state info dictionary
        state_info = {
            'start_state': start_state,
            'end_state': end_state
        }
        
        return highway_segments, total_distance, route_coordinates, state_info
    
    def _geocode_location(self, location: str) -> Tuple[List[float], str]:
        """Geocode a location string to coordinates using Photon."""
        try:
            logger.info(f"Geocoding location: {location}")
            # Clean up the location string - remove extra spaces and commas
            location = location.strip().replace(" ,", ",").replace(", ", ",")
            
            response = requests.get(
                f"{self.photon_url}/api",  # Use /api for geocoding
                params={
                    'q': location,
                    'limit': 1,
                    'lang': 'en'
                },
                timeout=5
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('features'):
                feature = data['features'][0]
                coordinates = feature['geometry']['coordinates']
                state = feature['properties'].get('state', '')
                logger.info(f"Found location in state: {state}")
                return coordinates, state
            
            raise ValueError(f"No results found for location: {location}")
            
        except Exception as e:
            logger.error(f"Geocoding failed for {location}: {str(e)}")
            raise ValueError(f"Geocoding failed for {location}")
    
    def _get_route_data(self, start_coords: List[float], end_coords: List[float]) -> Dict:
        """Get route data using OSRM."""
        try:
            # Format coordinates for OSRM (lon,lat format)
            coords = f"{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}"
            
            logger.info(f"Requesting route between {start_coords} and {end_coords}")
            response = requests.get(
                f"{self.osrm_url}/route/v1/driving/{coords}",
                params={
                    'overview': 'full',
                    'steps': 'true',
                    'annotations': 'true',
                    'geometries': 'polyline',
                    'alternatives': 'false',
                    'continue_straight': 'default'
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('routes'):
                route = data['routes'][0]
                steps = route['legs'][0]['steps']
                
                # Log the first few steps to see what data we get
                logger.info("Sample steps from OSRM:")
                for i, step in enumerate(steps[:5]):
                    logger.info(f"Step {i}: ref={step.get('ref', 'None')}, name={step.get('name', 'None')}")
                
                return {
                    'routes': [{
                        'geometry': route['geometry'],
                        'distance': route['distance'],
                        'legs': [{
                            'steps': steps
                        }]
                    }]
                }
            else:
                raise ValueError("No route found in OSRM response")
            
        except Exception as e:
            logger.error(f"Routing failed: {str(e)}")
            raise ValueError(f"Routing failed: {str(e)}")
    
    def _extract_highways(self, step: Dict) -> List[str]:
        """Extract highway names from step ref field."""
        ref = step.get('ref', '')
        if not ref:
            return []
        
        # Split on semicolons or slashes for multiple refs
        highways = []
        refs = [r.strip() for r in ref.replace('/', ';').split(';')]
        
        for r in refs:
            # Normalize the ref format
            r = r.upper().replace('I ', 'I-')
            if r.startswith('I-') or r.startswith('US-'):
                highways.append(r)
            
        return highways
    
    def _extract_highway_segments(self, steps: List[Dict]) -> List[Dict]:
        """Extract highway segments from route steps."""
        highway_segments = []
        current_distance = 0
        current_state = None
        current_state_start = 0
        
        logger.info(f"Processing {len(steps)} route steps")
        
        current_highway = None
        segment_start = 0
        
        for step in steps:
            distance = step['distance'] * 0.000621371  # Convert meters to miles
            
            # Decode polyline to get coordinates
            coords_str = step['geometry']
            coords_list = polyline.decode(coords_str)
            
            # Check state at start of step
            if coords_list:
                state = self._get_state_for_coords(coords_list[0])
                if state != current_state:
                    if current_state:
                        # Record state segment
                        state_segment = {
                            'state': current_state,
                            'start_mile': current_state_start,
                            'end_mile': current_distance
                        }
                        if current_highway:
                            segment = {
                                'highway': current_highway,
                                'start_mile': segment_start,
                                'end_mile': current_distance,
                                'state_segments': [state_segment]
                            }
                            highway_segments.append(segment)
                            segment_start = current_distance
                    
                    logger.info(f"State change at {current_distance:.1f} miles: {current_state} -> {state}")
                    current_state = state
                    current_state_start = current_distance
            
            # Extract highways from step
            highways = self._extract_highways(step)
            
            if highways:
                logger.info(f"Found highways {highways} at distance {current_distance:.1f} in state {current_state}")
                
                # If this is a new highway
                if not current_highway or highways[0] != current_highway:
                    # Close out the previous segment if it exists
                    if current_highway:
                        state_segment = {
                            'state': current_state,
                            'start_mile': current_state_start,
                            'end_mile': current_distance
                        }
                        segment = {
                            'highway': current_highway,
                            'start_mile': segment_start,
                            'end_mile': current_distance,
                            'state_segments': [state_segment]
                        }
                        logger.info(f"Adding segment: {segment}")
                        highway_segments.append(segment)
                    
                    # Start a new segment
                    current_highway = highways[0]
                    segment_start = current_distance
                    current_state_start = current_distance
            
            current_distance += distance
        
        # Close out the final segment if it exists
        if current_highway:
            state_segment = {
                'state': current_state,
                'start_mile': current_state_start,
                'end_mile': current_distance
            }
            segment = {
                'highway': current_highway,
                'start_mile': segment_start,
                'end_mile': current_distance,
                'state_segments': [state_segment]
            }
            logger.info(f"Adding final segment: {segment}")
            highway_segments.append(segment)
        
        return highway_segments
    
    def _get_state_for_coords(self, coords: List[float]) -> Optional[str]:
        """Get state for coordinates using Photon."""
        try:
            url = f"{self.photon_url}/reverse"
            params = {
                'lat': coords[0],
                'lon': coords[1]
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('features'):
                properties = data['features'][0]['properties']
                state = properties.get('state')
                if state:
                    # Convert full state names and abbreviations to standard 2-letter codes
                    state_map = {
                        'Florida': 'FL', 'FL': 'FL',
                        'Louisiana': 'LA', 'LA': 'LA',
                        'Texas': 'TX', 'TX': 'TX',
                        'Arizona': 'AZ', 'AZ': 'AZ',
                        'California': 'CA', 'CA': 'CA',
                        'New Mexico': 'NM', 'NM': 'NM',
                        'Mississippi': 'MS', 'MS': 'MS',
                        'Alabama': 'AL', 'AL': 'AL'
                    }
                    return state_map.get(state, state)
        except Exception as e:
            logger.warning(f"Failed to get state for coordinates {coords}: {str(e)}")
        
        return None 