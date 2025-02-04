import pandas as pd
from typing import List, Dict
import logging
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)

class FuelDataService:
    def __init__(self):
        # Load stations with coordinates
        df = pd.read_csv('fuel_prices_with_coords.csv')
        self.stations = df.dropna(subset=['latitude', 'longitude']).to_dict('records')
        logger.info(f"Loaded {len(self.stations)} stations with coordinates")
        
        # Pre-calculate station regions
        self.station_regions = {}
        for station in self.stations:
            lat_region = int(2 * float(station['latitude'])) / 2
            lon_region = int(2 * float(station['longitude'])) / 2
            key = (lat_region, lon_region)
            if key not in self.station_regions:
                self.station_regions[key] = []
            self.station_regions[key].append(station)

    def find_stations_near_route(self, route_points: List[Dict], max_distance: float = 2) -> List[Dict]:
        """Find stations near route points efficiently."""
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

    def get_cheapest_stations(self, route_points: List[Dict], num_stations: int = 5) -> List[Dict]:
        """Get cheapest stations near the route."""
        nearby_stations = self.find_stations_near_route(route_points)
        
        # Sort by price and distance
        sorted_stations = sorted(
            nearby_stations,
            key=lambda x: (float(x['Retail Price']), x['distance'])
        )
        
        return sorted_stations[:num_stations]

    def find_fuel_stops(self, route_points: List[Dict], total_distance: float) -> List[Dict]:
        """Find optimal fuel stops along route."""
        TANK_RANGE = 500  # miles
        RESERVE_RANGE = 150  # miles
        SEARCH_RANGE = 150  # miles to look ahead for stations
        
        fuel_stops = []
        distance_covered = 0
        range_left = TANK_RANGE
        last_point = None
        
        for current_point in route_points:
            # Calculate distance from last point
            if last_point:
                distance = self._calculate_distance(
                    last_point['lat'], last_point['lon'],
                    current_point['lat'], current_point['lon']
                )
                distance_covered += distance
                range_left -= distance
                
                # Check if we need to look for gas (at 350 miles)
                if range_left <= RESERVE_RANGE:
                    # Get points for next SEARCH_RANGE miles
                    search_points = []
                    search_distance = 0
                    
                    # Collect points within SEARCH_RANGE
                    for point in route_points[route_points.index(current_point):]:
                        search_points.append(point)
                        if len(search_points) > 1:
                            search_distance += self._calculate_distance(
                                search_points[-2]['lat'], search_points[-2]['lon'],
                                search_points[-1]['lat'], search_points[-1]['lon']
                            )
                            if search_distance > SEARCH_RANGE:
                                break
                    
                    # Find stations in search range
                    stations = self.find_stations_near_route(search_points, max_distance=5)
                    
                    if stations:
                        # Log all available stations
                        logger.info(f"\nLooking for stations after {round(distance_covered, 1)} miles:")
                        for station in sorted(stations, key=lambda x: float(x['Retail Price'])):
                            # Calculate actual distance to station from route start
                            station_distance = distance_covered - (search_distance / 2)  # Approximate station position
                            logger.info(f"  ${station['Retail Price']} - {station['Truckstop Name']} ({station['City']}, {station['State']}) at {round(station_distance, 1)} miles")
                        
                        # Get cheapest station
                        cheapest = min(stations, key=lambda x: float(x['Retail Price']))
                        station_distance = distance_covered - (search_distance / 2)  # Use actual station position
                        
                        fuel_stops.append({
                            'station': cheapest,
                            'distance_from_start': round(station_distance, 1)
                        })
                        # Reset range based on where we actually found the station
                        range_left = TANK_RANGE - (distance_covered - station_distance)
                        logger.info(f"Selected: ${cheapest['Retail Price']} - {cheapest['Truckstop Name']} at {round(station_distance, 1)} miles")
            
            last_point = current_point
        
        logger.info(f"\nFound {len(fuel_stops)} fuel stops for {round(total_distance)} mile route")
        return fuel_stops

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