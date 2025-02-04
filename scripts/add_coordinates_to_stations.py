import pandas as pd
import requests
import time
import logging
from tqdm import tqdm
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_address(address: str, city: str, state: str) -> list:
    """Return multiple address variants to try."""
    addresses = []
    
    # Clean the original address
    address = address.strip()
    
    # Handle Interstate highways
    if 'I-' in address or 'Interstate' in address:
        # Extract exit number if present
        exit_match = re.search(r'EXIT\s+(\d+[A-Z]?)', address, re.IGNORECASE)
        if exit_match:
            exit_num = exit_match.group(1)
            # Try with mile marker
            addresses.append(f"Interstate {address.split('I-')[1].split()[0]} mile {exit_num}, {city}, {state}")
            # Try just the Interstate
            addresses.append(f"Interstate {address.split('I-')[1].split()[0]}, {city}, {state}")
    
    # Handle US Routes
    if 'US-' in address or 'US ' in address:
        route_match = re.search(r'US-?\s*(\d+)', address)
        if route_match:
            route_num = route_match.group(1)
            addresses.append(f"US Route {route_num}, {city}, {state}")
    
    # Handle State Routes
    if 'SR-' in address or 'SR ' in address:
        route_match = re.search(r'SR-?\s*(\d+)', address)
        if route_match:
            route_num = route_match.group(1)
            addresses.append(f"State Route {route_num}, {city}, {state}")
    
    # Always try city center as fallback
    addresses.append(f"{city}, {state}")
    
    return addresses

def get_coordinates(address: str, city: str, state: str) -> tuple:
    """Get coordinates using Nominatim with multiple attempts."""
    try:
        # Get all possible address variants
        address_variants = clean_address(address, city, state)
        
        # Try each variant
        for search_address in address_variants:
            coords = try_geocode(search_address)
            if coords:
                return coords
        
        logger.warning(f"No coordinates found for any variant of: {address}, {city}, {state}")
        return None, None
        
    except Exception as e:
        logger.error(f"Error getting coordinates for {address}: {str(e)}")
        return None, None

def try_geocode(search_address: str) -> tuple:
    """Try to geocode a single address."""
    headers = {
        'User-Agent': 'FuelStationLocator/1.0'
    }
    
    time.sleep(0.2)
    
    response = requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={
            'q': search_address,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'us'
        },
        headers=headers
    )
    
    if response.status_code == 200:
        results = response.json()
        if results:
            return float(results[0]['lat']), float(results[0]['lon'])
    return None

def main():
    # Load the CSV
    input_file = 'fuel-prices-for-be-assessment.csv'
    df = pd.read_csv(input_file)
    
    logger.info(f"Starting geocoding for {len(df)} stations...")
    
    # Add coordinates columns if they don't exist
    if 'latitude' not in df.columns:
        df['latitude'] = None
    if 'longitude' not in df.columns:
        df['longitude'] = None
    
    # Process only rows without coordinates
    missing_coords = df[df['latitude'].isna()].index
    
    try:
        for idx in tqdm(missing_coords):
            address = df.loc[idx, 'Address']
            city = df.loc[idx, 'City']
            state = df.loc[idx, 'State']
            
            lat, lon = get_coordinates(address, city, state)
            
            if lat and lon:
                df.loc[idx, 'latitude'] = lat
                df.loc[idx, 'longitude'] = lon
            
            # Save progress every 100 stations
            if idx % 100 == 0:
                df.to_csv('fuel_prices_with_coords_partial.csv', index=False)
                logger.info(f"Progress saved - completed {idx} stations")
    
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user - saving progress...")
        df.to_csv('fuel_prices_with_coords_partial.csv', index=False)
        return
    
    # Save final results
    output_file = 'fuel_prices_with_coords.csv'
    df.to_csv(output_file, index=False)
    
    # Print stats
    total = len(df)
    with_coords = len(df.dropna(subset=['latitude', 'longitude']))
    logger.info(f"Added coordinates to {with_coords} out of {total} stations")
    logger.info(f"Saved enriched data to {output_file}")

if __name__ == '__main__':
    main() 