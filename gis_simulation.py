from typing import Dict, List, Tuple
from datetime import datetime, timezone, timedelta
import math
import logging
from sqlalchemy import and_

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GISTracker:
    def __init__(self):
        self.MIN_LAT = 2.9  # Shah Alam southern boundary
        self.MAX_LAT = 3.2  # Shah Alam northern boundary
        self.MIN_LNG = 101.4  # Shah Alam western boundary
        self.MAX_LNG = 101.7  # Shah Alam eastern boundary
        self.INDOOR_ACCURACY = self.ACCURACY_THRESHOLDS['indoor']['max']  # 100
        self.OUTDOOR_ACCURACY = self.ACCURACY_THRESHOLDS['outdoor']['max']  # 50
        # Update accuracy thresholds
        self.ACCURACY_THRESHOLDS = {
            'initial': 100,     # More lenient for initial positioning
            'indoor': {
                'warning': 50,
                'max': 100
            },
            'outdoor': {
                'warning': 30,
                'max': 50
            }
        }
        self.MIN_SPEED = 0  # Minimum speed in km/h
        self.MAX_SPEED = 100  # Maximum speed in km/h
        
    def detect_environment(self, accuracy: float, speed: float = None) -> bool:
        """Determine if location is likely indoor based on accuracy and speed"""
        # First check speed if available
        if speed is not None and speed > 5:
            return False  # Definitely outdoor if moving

        # Then check accuracy thresholds
        if accuracy <= self.ACCURACY_THRESHOLDS['outdoor']['max']:
            return False  # Good accuracy indicates outdoor
        elif accuracy > self.ACCURACY_THRESHOLDS['indoor']['warning']:
            return True  # Poor accuracy suggests indoor

        # For borderline cases, assume outdoor
        return False
    
    # Modify process_location_update method
    def process_location_update(self, driver_id: int, lat: float, lng: float, 
                              accuracy: float, timestamp: datetime,
                              previous_location: Dict = None) -> Dict:
        try:
            # Basic validation remains the same
            if not all(isinstance(x, (int, float)) for x in [lat, lng, accuracy]):
                return {
                    'status': 'error',
                    'message': 'Invalid data types for location parameters'
                }

            # Location bounds check
            if not self.is_valid_location(lat, lng):
                return {
                    'status': 'error',
                    'message': 'Location outside service area'
                }

            # Determine environment and accuracy status
            is_indoor = self.detect_environment(accuracy)
            thresholds = self.ACCURACY_THRESHOLDS['indoor' if is_indoor else 'outdoor']
            
            accuracy_status = 'good'
            if accuracy > thresholds['max']:
                accuracy_status = 'poor'
            elif accuracy > thresholds['warning']:
                accuracy_status = 'warning'

            # Calculate speed and bearing
            speed = 0.0
            bearing = 0.0
            if previous_location:
                speed = self.calculate_speed(
                    previous_location['lat'],
                    previous_location['lng'],
                    previous_location['timestamp'],
                    lat,
                    lng,
                    timestamp
                )
                bearing = self.calculate_bearing(
                    previous_location['lat'],
                    previous_location['lng'],
                    lat,
                    lng
                )

            # Prepare location data
            location_data = {
                'driver_id': driver_id,
                'lat': lat,
                'lng': lng,
                'accuracy': accuracy,
                'accuracy_status': accuracy_status,
                'speed': speed,
                'bearing': bearing,
                'timestamp': timestamp.isoformat(),
                'environment': 'indoor' if is_indoor else 'outdoor',
                'valid': True
            }

            return {
                'status': 'success',
                'location': location_data
            }

        except Exception as e:
            logger.error(f"Error processing location update: {str(e)}")
            return {
                'status': 'error',
                'message': f'Internal error processing location: {str(e)}'
            }

    def is_valid_location(self, lat: float, lng: float) -> bool:
        """Validate if coordinates are within Shah Alam bounds"""
        return (self.MIN_LAT <= lat <= self.MAX_LAT and 
                self.MIN_LNG <= lng <= self.MAX_LNG)

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        try:
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
                 math.cos(lat1_rad) * math.cos(lat2_rad) *
                 math.sin(delta_lon/2) * math.sin(delta_lon/2))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            return R * c
        except Exception as e:
            logger.error(f"Error calculating distance: {str(e)}")
            return 0.0

    def calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing between two points in degrees"""
        try:
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lon = math.radians(lon2 - lon1)
            
            y = math.sin(delta_lon) * math.cos(lat2_rad)
            x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
                 math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
            
            bearing = math.atan2(y, x)
            return math.degrees(bearing)
        except Exception as e:
            logger.error(f"Error calculating bearing: {str(e)}")
            return 0.0

    def calculate_speed(self, 
                       lat1: float, lon1: float, timestamp1: datetime,
                       lat2: float, lon2: float, timestamp2: datetime) -> float:
        """Calculate speed in km/h between two points"""
        try:
            distance = self.calculate_distance(lat1, lon1, lat2, lon2)  # in meters
            time_diff = (timestamp2 - timestamp1).total_seconds()  # in seconds
            
            if time_diff <= 0:
                return 0.0
                
            speed_mps = distance / time_diff
            speed_kmh = speed_mps * 3.6  # Convert to km/h
            
            # Validate speed is within reasonable bounds
            if speed_kmh < self.MIN_SPEED or speed_kmh > self.MAX_SPEED:
                logger.warning(f"Unusual speed detected: {speed_kmh} km/h")
                return 0.0
                
            return speed_kmh
        except Exception as e:
            logger.error(f"Error calculating speed: {str(e)}")
            return 0.0


    def find_nearest_stop(self, lat: float, lng: float, stops: List[Dict]) -> Dict:
        """Find the nearest bus stop to given coordinates"""
        try:
            nearest_stop = None
            min_distance = float('inf')
            
            for stop in stops:
                distance = self.calculate_distance(lat, lng, stop['latitude'], stop['longitude'])
                if distance < min_distance:
                    min_distance = distance
                    nearest_stop = stop
                    
            return {
                'stop': nearest_stop,
                'distance': min_distance
            }
        except Exception as e:
            logger.error(f"Error finding nearest stop: {str(e)}")
            return {'stop': None, 'distance': 0.0}

def update_bus_locations(db, Driver, Route, Stop):
    """Update and retrieve current bus locations"""
    try:
        # Get all active drivers (updated within last 5 minutes)
        active_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        active_drivers = Driver.query.filter(
            and_(
                Driver.last_location_update >= active_threshold,
                Driver.current_location_lat.isnot(None),
                Driver.current_location_lng.isnot(None)
            )
        ).all()
        
        bus_locations = {}
        for driver in active_drivers:
            if driver.route:
                route_name = driver.route.name
                if route_name not in bus_locations:
                    bus_locations[route_name] = {
                        'buses': {},
                        'stops': []
                    }
                    
                # Add bus location
                bus_locations[route_name]['buses'][f"Bus_{driver.id}"] = {
                    'lat': driver.current_location_lat,
                    'lng': driver.current_location_lng,
                    'last_update': driver.last_location_update.isoformat(),
                    'driver_name': driver.name
                }
                
                # Add route stops if not already added
                if not bus_locations[route_name]['stops']:
                    stops = Stop.query.filter_by(route_id=driver.route.id).all()
                    bus_locations[route_name]['stops'] = [
                        {
                            'name': stop.name,
                            'lat': stop.latitude,
                            'lng': stop.longitude
                        }
                        for stop in stops
                    ]
        
        return {
            'status': 'success',
            'locations': bus_locations,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating bus locations: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }