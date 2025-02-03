from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services.routing_service import RoutingService
from .services.fuel_data_service import FuelDataService
import logging
import traceback

logger = logging.getLogger(__name__)

# Create your views here.

class OptimizeRouteView(APIView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.routing_service = RoutingService()
            self.fuel_service = FuelDataService()
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}\n{traceback.format_exc()}")
            raise
    
    def post(self, request):
        """
        Optimize route with fuel stops between start and end locations.
        
        Request body:
        {
            "start": "New York, NY",
            "end": "Los Angeles, CA"
        }
        """
        try:
            # Validate input
            start = request.data.get('start')
            end = request.data.get('end')
            
            logger.info(f"Received request with start={start}, end={end}")
            
            if not start or not end:
                return Response(
                    {"error": "Both start and end locations are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get route information with state info
            try:
                highway_segments, total_distance, route_coordinates, state_info = self.routing_service.get_route(start, end)
            except Exception as e:
                logger.error(f"Routing error: {str(e)}\n{traceback.format_exc()}")
                return Response(
                    {"error": f"Routing error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Get fuel stations along the route, now including state info
            try:
                route_stations = self.fuel_service.get_stations_on_route(highway_segments, state_info)
            except Exception as e:
                logger.error(f"Fuel station error: {str(e)}\n{traceback.format_exc()}")
                return Response(
                    {"error": f"Fuel station error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Find optimal fuel stops
            try:
                fuel_stops = self.fuel_service.find_optimal_fuel_stops(route_stations, total_distance)
            except Exception as e:
                logger.error(f"Optimization error: {str(e)}\n{traceback.format_exc()}")
                return Response(
                    {"error": f"Optimization error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Calculate total fuel cost
            total_gallons = total_distance / settings.VEHICLE_MPG
            total_cost = sum(stop['price'] * (settings.VEHICLE_RANGE_MILES / settings.VEHICLE_MPG) 
                           for stop in fuel_stops[:-1])
            
            # Add remaining fuel needed for last segment
            if fuel_stops:
                remaining_distance = total_distance - fuel_stops[-1]['distance_from_start']
                remaining_gallons = remaining_distance / settings.VEHICLE_MPG
                total_cost += fuel_stops[-1]['price'] * remaining_gallons
            
            return Response({
                'route': {
                    'start': start,
                    'end': end,
                    'total_distance': round(total_distance, 2),
                    'coordinates': route_coordinates
                },
                'fuel_stops': fuel_stops,
                'total_cost': round(total_cost, 2),
                'total_gallons': round(total_gallons, 2)
            })
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
