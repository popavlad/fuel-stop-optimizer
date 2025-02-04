import pandas as pd

# Create a single test station in New York (near the start of our test route)
test_station = {
    'OPIS Truckstop ID': 1,
    'Truckstop Name': 'TEST STATION NYC',
    'Address': 'Test Address',
    'City': 'New York',
    'State': 'NY',
    'Rack ID': 1,
    'Retail Price': 3.50,
    'latitude': 40.7128,    # Correct NYC latitude
    'longitude': -74.0060   # Correct NYC longitude
}

# Create DataFrame and save
df = pd.DataFrame([test_station])
df.to_csv('test_stations.csv', index=False)
print("Created test station file") 