# Route Optimizer with Fuel Stops

A Django API that finds optimal fuel stops along a route, optimizing for lowest total fuel cost.

## Features

- Finds cheapest fuel stops along any US route
- Takes into account:
  - 500-mile tank range
  - 10 MPG fuel consumption
- Ensures truck never runs out of fuel
- Calculates total cost and savings

## Setup

1. Install dependencies:

```bash
pip install django==3.2.23
pip install requests
pip install python-dotenv
```

2. Add OpenRouteService API key to .env:

```
ORS_API_KEY=your_key_here
```

3. Run server:

```bash
python manage.py runserver
```

## API Usage

Send POST request to `/api/optimize/`:

```json
{
  "start": "Miami, FL",
  "end": "Seattle, WA"
}
```

Response example:

```json
{
  "success": true,
  "total_distance": 3456.7,
  "fuel_stops": [
    {
      "Truckstop Name": "FLYING J #123",
      "City": "Houston",
      "State": "TX",
      "Retail Price": "3.249",
      "route_distance": 350.5
    }
  ],
  "total_fuel_cost": 839.23,
  "average_price_per_gallon": 3.066,
  "route_average_price": 3.275,
  "total_gallons": 273.4,
  "total_savings_based_on_average_price_for_route": 57.23,
  "number_of_stops": 6
}
```

## Requirements

- Python 3.8+
- Django 3.2.23
- Other dependencies listed in requirements.txt

## Setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following:

   ```
   ORS_API_KEY=your_openrouteservice_api_key_here
   VEHICLE_MPG=10.0
   VEHICLE_RANGE_MILES=500.0
   FUEL_PRICES_CSV=fuel-prices-for-be-assessment.csv
   ```

4. Get an API key from [OpenRouteService](https://openrouteservice.org/) and add it to your `.env` file.

5. Run migrations:

   ```bash
   python manage.py migrate
   ```

6. Start the development server:
   ```bash
   python manage.py runserver
   ```

## API Usage

### Optimize Route

**Endpoint:** `POST /api/optimize/`

**Request Body:**

```json
{
  "start": "New York, NY",
  "end": "Los Angeles, CA"
}
```

**Response:**

```json
{
    "route": {
        "start": "New York, NY",
        "end": "Los Angeles, CA",
        "total_distance": 2789.45,
        "coordinates": [[lat1, lon1], [lat2, lon2], ...]
    },
    "fuel_stops": [
        {
            "station_name": "Example Station",
            "address": "I-80, EXIT 123",
            "price": 3.25,
            "highway": "I-80",
            "exit_number": 123,
            "distance_from_start": 450.5
        },
        ...
    ],
    "total_cost": 875.50,
    "total_gallons": 278.95
}
```

## Performance Considerations

- The API uses pre-processed fuel price data for quick lookups
- Route optimization is done using highway segments to minimize API calls
- Results are cached where possible to improve response times
- The API makes only one external API call per request to OpenRouteService

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- 400: Bad Request (invalid input)
- 500: Internal Server Error (unexpected errors)

Error responses include a descriptive message in the response body.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
