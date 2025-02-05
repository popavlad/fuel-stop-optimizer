import pandas as pd
from typing import List, Dict
import logging
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)

class FuelDataService:
    def __init__(self):
        df = pd.read_csv('fuel_prices_with_coords.csv')
        self.stations = df.dropna(subset=['latitude', 'longitude']).to_dict('records')
        logger.info(f"Loaded {len(self.stations)} stations from CSV")
        
        # Log a sample station to verify data format
        if self.stations:
            logger.info(f"Sample station data: {self.stations[0]}")

        # Pre-calculate float values to avoid repeated conversions
        for station in self.stations:
            station['latitude'] = float(station['latitude'])
            station['longitude'] = float(station['longitude'])
            station['Retail Price'] = float(station['Retail Price'])

    def _calculate_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two points in miles."""
        R = 6371  # Earth's radius in km
        
        lat1, lon1 = float(lat1), float(lon1)
        lat2, lon2 = float(lat2), float(lon2)
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c * 0.621371  # Convert km to miles

    def get_all_route_stations(self, route_points: List[Dict], total_distance: float) -> List[Dict]:
        """Find all stations near the route and calculate their route distances."""
        logger.info(f"Starting station search along {total_distance} mile route")
        all_stations = {}
        
        # More aggressive sampling of route points
        step = max(1, len(route_points) // 500)  # Reduced from 1500 to 500 points
        sampled_points = route_points[::step]
        
        # Pre-calculate route point coordinates as floats
        route_coords = [(point['lat'], point['lon']) for point in sampled_points]
        
        # Calculate rough bounding box for quick filtering
        min_lat = min(lat for lat, _ in route_coords) - 0.2  # About 10-15 miles
        max_lat = max(lat for lat, _ in route_coords) + 0.2
        min_lon = min(lon for _, lon in route_coords) - 0.2
        max_lon = max(lon for _, lon in route_coords) + 0.2
        
        # Quick filter stations within bounding box
        filtered_stations = [
            station for station in self.stations
            if min_lat <= station['latitude'] <= max_lat
            and min_lon <= station['longitude'] <= max_lon
        ]
        
        logger.info(f"Filtered to {len(filtered_stations)} stations within bounding box")
        
        # Process stations in chunks for better performance
        chunk_size = 100
        for i in range(0, len(filtered_stations), chunk_size):
            station_chunk = filtered_stations[i:i + chunk_size]
            
            for station in station_chunk:
                # Quick distance check to nearest point
                min_distance = float('inf')
                closest_point_index = 0
                
                # Check every 5th point first for rough estimate
                for i in range(0, len(route_coords), 5):
                    distance = self._calculate_distance(
                        station['latitude'],
                        station['longitude'],
                        route_coords[i][0],
                        route_coords[i][1]
                    )
                    if distance < min_distance:
                        min_distance = distance
                        closest_point_index = i
                
                # If rough estimate is promising, do detailed check around that area
                if min_distance <= 15:  # Slightly larger initial filter
                    start_idx = max(0, closest_point_index - 10)
                    end_idx = min(len(route_coords), closest_point_index + 10)
                    
                    for i in range(start_idx, end_idx):
                        distance = self._calculate_distance(
                            station['latitude'],
                            station['longitude'],
                            route_coords[i][0],
                            route_coords[i][1]
                        )
                        if distance < min_distance:
                            min_distance = distance
                            closest_point_index = i
                
                # If station is within reasonable distance of route
                if min_distance <= 10:
                    station_id = station['OPIS Truckstop ID']
                    if station_id not in all_stations:
                        # Approximate route distance based on index
                        route_distance = (closest_point_index / len(route_coords)) * total_distance
                        
                        station_copy = station.copy()
                        station_copy['route_distance'] = round(route_distance, 1)
                        station_copy['highway_distance'] = round(min_distance, 1)
                        all_stations[station_id] = station_copy

        unique_stations = list(all_stations.values())
        unique_stations.sort(key=lambda x: x['route_distance'])
        
        return unique_stations

    def find_optimal_fuel_stops(self, route_stations: List[Dict], total_distance: float) -> List[Dict]:
        """Find optimal fuel stops along route."""
        TANK_SIZE = 50  # Gallons
        MPG = 10  # Miles per gallon
        TANK_RANGE = TANK_SIZE * MPG  # 500 miles on full tank
        SEARCH_START = TANK_RANGE * 0.7  # Start looking at 70% tank depletion (350 miles)
        SAFETY_BUFFER = 150  # Look for stations within next 150 miles
        
        # Log station distribution first
        logger.info("\nStation distribution along route:")
        for i in range(0, int(total_distance), 100):
            stations_in_range = [s for s in route_stations 
                               if i <= s['route_distance'] < i + 100]
            if stations_in_range:
                logger.info(f"Mile {i}-{i+100}: {len(stations_in_range)} stations " +
                           f"(cheapest: ${min(float(s['Retail Price']) for s in stations_in_range):.3f}, " +
                           f"{min(s['highway_distance'] for s in stations_in_range):.1f} miles from highway)")
        
        logger.info(f"\nStarting with full tank ({TANK_SIZE} gallons, {TANK_RANGE} mile range)")
        
        fuel_stops = []
        next_search_at = SEARCH_START  # Start searching at 350 miles
        
        while next_search_at < total_distance:
            remaining_range = TANK_RANGE
            if fuel_stops:
                # Calculate remaining range from last stop
                distance_since_last = total_distance - fuel_stops[-1]['route_distance']
                remaining_range = TANK_RANGE - distance_since_last
            
            if remaining_range >= (total_distance - next_search_at):
                logger.info(f"\nCan reach destination with remaining fuel ({round(remaining_range)} miles range left)")
                break
            
            search_window = []
            for station in route_stations:
                if next_search_at <= station['route_distance'] <= next_search_at + SAFETY_BUFFER:
                    search_window.append(station)
            
            if search_window:
                cheapest = min(search_window, key=lambda x: float(x['Retail Price']))
                fuel_stops.append(cheapest)
                gallons_needed = TANK_SIZE  # Full tank refill
                fuel_cost = float(cheapest['Retail Price']) * gallons_needed
                logger.info(f"\nFuel stop {len(fuel_stops)}: ${cheapest['Retail Price']}/gal - {cheapest['Truckstop Name']} " +
                           f"at mile {cheapest['route_distance']} ({gallons_needed:.1f} gal = ${fuel_cost:.2f})")
                next_search_at = cheapest['route_distance'] + SEARCH_START  # Next search after 350 miles
            else:
                logger.warning(f"No stations found between mile {next_search_at} and {next_search_at + SAFETY_BUFFER}")
                next_search_at += SAFETY_BUFFER
        
        return fuel_stops 