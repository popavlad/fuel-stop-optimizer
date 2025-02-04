from .services.routing_service import RoutingService
from .services.fuel_data_service import FuelDataService
import logging
from django.http import JsonResponse
from django.views import View
import json

logger = logging.getLogger(__name__)


class OptimizeRouteView(View):
    def __init__(self):
        self.routing_service = RoutingService()
        self.fuel_data_service = FuelDataService()
        
    def post(self, request):
        try:
            data = json.loads(request.body)
            origin = data.get('start')
            destination = data.get('end')
            
            if not origin or not destination:
                return JsonResponse({
                    'success': False,
                    'error': 'start and end locations required'
                })
            
            # Get route with distance
            route_data = self.routing_service.get_route(origin, destination)
            
            # Get all stations along route
            route_stations = self.fuel_data_service.get_all_route_stations(
                route_points=route_data['points'],
                total_distance=route_data['total_distance']
            )
            
            # Find optimal fuel stops
            fuel_stops = self.fuel_data_service.find_optimal_fuel_stops(
                route_stations=route_stations,
                total_distance=route_data['total_distance']
            )
            
            # Calculate costs
            MPG = 10
            total_gallons = 0
            total_cost = 0
            
            for i in range(len(fuel_stops)):
                current_stop = fuel_stops[i]
                if i < len(fuel_stops) - 1:
                    next_stop = fuel_stops[i + 1]
                    distance_to_next = next_stop['route_distance'] - current_stop['route_distance']
                else:
                    distance_to_next = route_data['total_distance'] - current_stop['route_distance']
                
                gallons_needed = distance_to_next / MPG
                cost = float(current_stop['Retail Price']) * gallons_needed
                total_gallons += gallons_needed
                total_cost += cost
            
            # Calculate savings
            route_avg_price = sum(float(station['Retail Price']) for station in route_stations) / len(route_stations)
            avg_fuel_price = sum(float(stop['Retail Price']) for stop in fuel_stops) / len(fuel_stops)
            total_savings = (route_avg_price * total_gallons) - total_cost
            
            return JsonResponse({
                'success': True,
                'route': {
                    'points': route_data['points'],  # All route waypoints for drawing
                    'total_distance': round(route_data['total_distance'], 1)
                },
                'fuel_stops': [{
                    'name': stop['Truckstop Name'],
                    'city': stop['City'],
                    'state': stop['State'],
                    'price': float(stop['Retail Price']),
                    'location': {
                        'lat': float(stop['latitude']),
                        'lon': float(stop['longitude'])
                    },
                    'route_distance': stop['route_distance']
                } for stop in fuel_stops],
                'total_fuel_cost': round(total_cost, 2),
                'average_price_per_gallon': round(avg_fuel_price, 3),
                'route_average_price': round(route_avg_price, 3),
                'total_gallons': round(total_gallons, 1),
                'total_savings_based_on_average_price_for_route': round(total_savings, 2),
                'number_of_stops': len(fuel_stops)
            })
            
        except Exception as e:
            logger.error(f"Failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
