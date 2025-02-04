import pandas as pd
from typing import List, Dict
import logging
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)

class FuelDataService:
    def __init__(self):
        df = pd.read_csv('fuel_prices_with_coords.csv')
        self.stations = df.dropna(subset=['latitude', 'longitude']).to_dict('records')
        
        self.station_regions = {}
        for station in self.stations:
            lat_region = int(2 * float(station['latitude'])) / 2
            lon_region = int(2 * float(station['longitude'])) / 2
            key = (lat_region, lon_region)
            if key not in self.station_regions:
                self.station_regions[key] = []
            self.station_regions[key].append(station)

    def find_stations_near_route(self, route_points: List[Dict], max_distance: float = 2) -> List[Dict]:
        nearby_stations = []
        seen = set()
        
        for point in route_points:
            point_lat = int(2 * float(point['lat'])) / 2
            point_lon = int(2 * float(point['lon'])) / 2
            
            for lat_offset in [-0.5, 0, 0.5]:
                for lon_offset in [-0.5, 0, 0.5]:
                    region_key = (point_lat + lat_offset, point_lon + lon_offset)
                    if region_key in self.station_regions:
                        for station in self.station_regions[region_key]:
                            if station['OPIS Truckstop ID'] not in seen:
                                distance = self._calculate_distance(
                                    point['lat'], point['lon'],
                                    station['latitude'], station['longitude']
                                )
                                if distance <= max_distance:
                                    seen.add(station['OPIS Truckstop ID'])
                                    station['distance'] = round(distance, 2)
                                    nearby_stations.append(station)
        return nearby_stations

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
        """Get all stations along the route with their actual positions."""
        all_stations = {}
        distance_covered = 0
        last_point = None
        
        step = max(1, len(route_points) // 1500)
        sampled_points = route_points[::step]
        logger.info(f"Sampling {len(sampled_points)} points from {len(route_points)} total points")
        
        for current_point in sampled_points:
            if last_point:
                distance = self._calculate_distance(
                    last_point['lat'], last_point['lon'],
                    current_point['lat'], current_point['lon']
                )
                distance_covered += distance
                
                stations = self.find_stations_near_route([current_point], max_distance=7)
                
                for station in stations:
                    station_id = station['OPIS Truckstop ID']
                    if station_id not in all_stations:
                        station['route_distance'] = round(distance_covered, 1)
                        all_stations[station_id] = station
            
            last_point = current_point
        
        unique_stations = list(all_stations.values())
        unique_stations.sort(key=lambda x: x['route_distance'])
        
        logger.info(f"\nFound {len(unique_stations)} unique stations along {round(total_distance)} mile route")
        return unique_stations

    def find_optimal_fuel_stops(self, route_stations: List[Dict], total_distance: float) -> List[Dict]:
        """Find optimal fuel stops along route."""
        TANK_RANGE = 500  # Total range on full tank (miles)
        SEARCH_START = 350  # Start looking for stations at 350 miles
        SAFETY_BUFFER = 150  # Don't let tank go below 150 miles of range
        
        fuel_stops = []
        next_search_at = SEARCH_START
        
        while next_search_at < total_distance:
            if fuel_stops and (total_distance - fuel_stops[-1]['route_distance']) <= TANK_RANGE:
                logger.info(f"\nCan reach destination from last stop ({round(total_distance - fuel_stops[-1]['route_distance'])} miles remaining)")
                break
            
            search_window = []
            for station in route_stations:
                if next_search_at <= station['route_distance'] <= next_search_at + SAFETY_BUFFER:
                    search_window.append(station)
            
            if search_window:
                cheapest = min(search_window, key=lambda x: float(x['Retail Price']))
                fuel_stops.append(cheapest)
                logger.info(f"\nFuel stop {len(fuel_stops)}: ${cheapest['Retail Price']} - {cheapest['Truckstop Name']} at mile {cheapest['route_distance']}")
                next_search_at = cheapest['route_distance'] + 350
            else:
                logger.warning(f"No stations found between mile {next_search_at} and {next_search_at + SAFETY_BUFFER}")
                
                next_viable_stations = []
                for station in route_stations:
                    if station['route_distance'] > next_search_at + SAFETY_BUFFER:
                        stations_after = [s for s in route_stations 
                                        if station['route_distance'] + 350 <= s['route_distance'] <= station['route_distance'] + 500]
                        if stations_after:
                            next_viable_stations.append(station)
                            break
                
                if next_viable_stations:
                    next_viable = next_viable_stations[0]
                    logger.info(f"Found next viable station at mile {next_viable['route_distance']}")
                    
                    last_stop_distance = fuel_stops[-1]['route_distance'] if fuel_stops else 0
                    gap_stations = []
                    
                    for station in route_stations:
                        if last_stop_distance < station['route_distance'] < next_search_at:
                            distance_to_next_viable = next_viable['route_distance'] - station['route_distance']
                            if distance_to_next_viable <= TANK_RANGE:
                                gap_stations.append(station)
                    
                    if gap_stations:
                        best_station = min(gap_stations, key=lambda x: float(x['Retail Price']))
                        fuel_stops.append(best_station)
                        logger.info(f"\nFuel stop {len(fuel_stops)} (before gap): ${best_station['Retail Price']} - {best_station['Truckstop Name']} at mile {best_station['route_distance']}")
                        next_search_at = best_station['route_distance'] + 350
                    else:
                        next_search_at += SAFETY_BUFFER
                else:
                    next_search_at += SAFETY_BUFFER
        
        return fuel_stops 