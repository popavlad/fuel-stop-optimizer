import pandas as pd
import re
from typing import List, Dict, Tuple, Optional
from django.conf import settings
import logging
import math

logger = logging.getLogger(__name__)

class FuelDataService:
    def __init__(self):
        self.fuel_data = self._load_and_process_fuel_data()
        # Define comprehensive highway-to-state mapping
        self.highway_states = {
            'I-95': ['FL', 'GA', 'SC', 'NC', 'VA', 'MD', 'DE', 'PA', 'NJ', 'NY', 'CT', 'RI', 'MA', 'ME'],
            'I-75': ['FL', 'GA', 'TN', 'KY', 'OH', 'MI'],
            'I-10': ['FL', 'AL', 'MS', 'LA', 'TX', 'NM', 'AZ', 'CA'],
            'I-12': ['LA'],
            'I-35': ['TX', 'OK', 'KS', 'MO', 'IA', 'MN'],
            'I-80': ['NJ', 'PA', 'OH', 'IN', 'IL', 'IA', 'NE', 'WY', 'UT', 'NV', 'CA'],
            'I-70': ['UT', 'CO', 'KS', 'MO', 'IL', 'IN', 'OH', 'WV', 'PA', 'MD'],
            'I-15': ['CA', 'NV', 'AZ', 'UT', 'ID', 'MT'],
            'I-20': ['TX', 'LA', 'MS', 'AL', 'GA', 'SC'],
            'I-40': ['CA', 'AZ', 'NM', 'TX', 'OK', 'AR', 'TN', 'NC'],
            'I-78': ['PA', 'NJ', 'NY'],
            'I-94': ['MT', 'ND', 'MN', 'WI', 'IL', 'IN', 'MI'],
            'I-90': ['WA', 'ID', 'MT', 'WY', 'SD', 'MN', 'WI', 'IL', 'IN', 'OH', 'PA', 'NY', 'MA'],
            'I-84': ['OR', 'ID', 'UT', 'PA', 'NY', 'CT', 'MA'],
            'I-280': ['CA', 'IL', 'IA'],
            'I-76': ['CO', 'NE', 'OH', 'PA', 'NJ'],
            'I-410': ['TX'],
            'I-5': ['CA', 'OR', 'WA']
        }
        
        # Test I-80 stations
        test_stations = self.fuel_data[self.fuel_data['highway'] == 'I-80'].sort_values(['State', 'exit_mile'])
        print("\nI-80 stations by state and exit:")
        print(test_stations[['State', 'exit_mile', 'Truckstop Name', 'Address']].head(20))
        
    def _load_and_process_fuel_data(self) -> pd.DataFrame:
        """Load and process the fuel price data."""
        logger.info("Loading fuel price data...")
        df = pd.read_csv(settings.FUEL_PRICES_CSV)
        
        # Clean up state data
        df['State'] = df['State'].str.strip()
        
        # Extract highway and exit information from the Address field
        df['highway_info'] = df['Address'].apply(self._parse_highway_info)
        df = df.dropna(subset=['highway_info'])
        
        # Split the highway_info tuple into separate columns
        df[['highway', 'exit_mile']] = pd.DataFrame(df['highway_info'].tolist(), index=df.index)
        
        # Log some sample data for debugging
        sample_data = df[['Address', 'highway', 'exit_mile', 'State']].head(5)
        logger.info(f"Sample processed data:\n{sample_data}")
        
        return df
    
    def _parse_highway_info(self, address: str) -> Optional[Tuple[str, float]]:
        """Extract highway and mile marker from address."""
        if pd.isna(address):
            return None
        
        # Convert to uppercase and clean up the address
        address = str(address).upper().strip()
        
        # First try to find a highway number
        highway = None
        
        # Check for Interstate highways
        if 'I-' in address or 'I ' in address or 'INTERSTATE' in address:
            match = re.search(r'I[-\s]?(\d+)|INTERSTATE\s*(\d+)', address)
            if match:
                num = match.group(1) or match.group(2)
                highway = f'I-{num}'
        
        # Check for US highways
        elif 'US' in address or 'U.S.' in address:
            match = re.search(r'US[-\s]?(\d+)|U\.?S\.?(?:HWY)?\s*(\d+)', address)
            if match:
                num = match.group(1) or match.group(2)
                highway = f'US-{num}'
        
        # Find mile/exit number
        mile = 0
        if 'EXIT' in address:
            match = re.search(r'EXIT\s*(\d+)', address)
            if match:
                try:
                    mile = float(match.group(1))
                except ValueError:
                    pass
        
        return (highway, mile) if highway else None
    
    def get_stations_on_route(self, highways: List[Dict], state_info: Dict) -> pd.DataFrame:
        """Get all fuel stations along the specified highways."""
        logger.info(f"Finding stations along {len(highways)} highway segments")
        
        if not highways:
            logger.error("No highway segments provided")
            return pd.DataFrame()
        
        route_stations = []
        seen_stations = set()
        
        for highway_segment in highways:
            highway = highway_segment['highway']
            
            # Get all stations on this highway
            highway_mask = self.fuel_data['highway'].apply(self._normalize_highway_name) == self._normalize_highway_name(highway)
            highway_stations = self.fuel_data[highway_mask].copy()
            
            if highway_stations.empty:
                logger.warning(f"No stations found on highway {highway}")
                continue
            
            # Process each state segment
            for state_segment in highway_segment['state_segments']:
                state = state_segment['state']
                state_start = state_segment['start_mile']
                state_end = state_segment['end_mile']
                
                # Get stations for this state
                state_stations = highway_stations[highway_stations['State'] == state].copy()
                
                if state_stations.empty:
                    logger.warning(f"No stations found in {state} on {highway}")
                    continue
                
                # Calculate absolute position on route
                # Station's position = start of state segment + station's exit number
                state_stations.loc[:, 'distance_from_start'] = state_start + state_stations['exit_mile']
                
                # Create unique station IDs
                state_stations.loc[:, 'station_id'] = state_stations.apply(
                    lambda x: f"{highway}_{state}_{x['exit_mile']}_{x['Truckstop Name']}", 
                    axis=1
                )
                
                # Filter out stations we've already seen
                new_stations = state_stations[~state_stations['station_id'].isin(seen_stations)]
                seen_stations.update(new_stations['station_id'].tolist())
                
                if not new_stations.empty:
                    route_stations.append(new_stations)
                    logger.info(f"Added {len(new_stations)} stations from {state} on {highway} between miles {state_start:.1f}-{state_end:.1f}")
        
        if route_stations:
            result = pd.concat(route_stations)
            logger.info(f"Total stations found: {len(result)}")
            return result
        
        logger.warning("No stations found along route")
        return pd.DataFrame()
    
    def _normalize_highway_name(self, highway: str) -> str:
        """Normalize highway name for consistent matching."""
        if pd.isna(highway):
            return ''
        
        # Convert to string and uppercase
        highway = str(highway).upper().strip()
        
        # Remove any whitespace around hyphens
        highway = re.sub(r'\s*-\s*', '-', highway)
        
        # Ensure I-XX format for Interstate highways
        highway = re.sub(r'^I\s*(\d)', r'I-\1', highway)
        highway = re.sub(r'^INTERSTATE\s*(\d)', r'I-\1', highway)
        
        # Remove directional suffixes
        highway = re.sub(r'\s*[NSEW]$', '', highway)
        
        return highway
    
    def find_optimal_fuel_stops(self, route_stations: pd.DataFrame, total_distance: float) -> List[Dict]:
        """Public method to find optimal fuel stops along the route."""
        logger.info(f"Planning route of {total_distance:.1f} miles")
        logger.info(f"Found {len(route_stations)} total stations")
        
        if route_stations.empty:
            logger.warning("No stations available for optimization")
            return []
            
        # Get distance range of available stations
        if not route_stations.empty:
            min_dist = route_stations['distance_from_start'].min()
            max_dist = route_stations['distance_from_start'].max()
            logger.info(f"Station distance range: {min_dist:.1f} to {max_dist:.1f} miles")
        
        # Call the private implementation with vehicle range from settings
        return self._find_optimal_fuel_stops(
            stations_df=route_stations,
            total_distance=total_distance,
            vehicle_range=settings.VEHICLE_RANGE_MILES
        )

    def _find_optimal_fuel_stops(self, stations_df: pd.DataFrame, total_distance: float, vehicle_range: float) -> List[Dict]:
        """Find fuel stops by always picking the furthest reachable station."""
        logger.info(f"Starting station search along {total_distance:.1f} mile route")
        
        # Sort stations by distance
        stations = stations_df.sort_values('distance_from_start')
        logger.info(f"Found {len(stations)} total stations from {stations['distance_from_start'].min():.1f} to {stations['distance_from_start'].max():.1f} miles")
        
        # Just get the furthest reachable station each time
        found_stations = []
        current_pos = 0
        
        while current_pos < total_distance:
            # Get all stations we can reach with our remaining fuel
            reachable_stations = stations[
                (stations['distance_from_start'] > current_pos) & 
                (stations['distance_from_start'] <= current_pos + vehicle_range)
            ]
            
            if reachable_stations.empty:
                logger.info(f"No more reachable stations from position {current_pos:.1f}")
                break
            
            # Take the furthest one
            next_station = reachable_stations.iloc[-1]
            logger.info(f"From position {current_pos:.1f}, furthest reachable station is at {next_station['distance_from_start']:.1f} miles: {next_station['Truckstop Name']}")
            
            found_stations.append({
                'station_name': str(next_station['Truckstop Name']).strip(),
                'address': str(next_station['Address']).strip(),
                'price': float(next_station['Retail Price']),
                'highway': str(next_station['highway']).strip(),
                'exit_mile': float(next_station['exit_mile']),
                'distance_from_start': float(next_station['distance_from_start'])
            })
            
            current_pos = next_station['distance_from_start']
        
        logger.info("\nFinal station list:")
        for stop in found_stations:
            logger.info(f"Stop at {stop['distance_from_start']:.1f} miles: {stop['station_name']}")
            
        return found_stations 