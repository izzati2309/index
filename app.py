from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from functools import wraps # To create decorators for authentication
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone, time
from functools import wraps
from collections import defaultdict
from gis_simulation import update_bus_locations, GISTracker
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import asc, func
from flask_migrate import Migrate
from genetic_algorithm import find_alternative_routes, calculate_alternative_route_times, optimize_user_travel
from admin_optimizer import optimize_fleet_and_schedule, BusScheduleOptimizer
import traceback # For error handling
import json
import time # For time-related operations
import traceback, logging


# Set up logging x
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

current_time = datetime.now(timezone.utc)
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bus_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '390d89c4039f95077d15ff0b7fc2bae9179be495a2f59f95'  # To keep data secure
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Set session timeout to 30 minutes

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Define models
class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    stops = db.relationship('Stop', backref='route', lazy=True, cascade='all, delete-orphan')
    buses = db.relationship('Bus', backref='route', lazy=True, cascade='all, delete-orphan')

class Stop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)  

class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    schedules = db.relationship('Schedule', backref='bus', lazy=True, cascade='all, delete-orphan')

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=False)
    day_type = db.Column(db.String(20), nullable=False)
    departure_time = db.Column(db.Time, nullable=False)

class TripRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    desired_time = db.Column(db.DateTime, nullable=False)
    starting_point = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=True)  # Allow nullable for initial setup
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20), unique=True)
    role = db.Column(db.String(20), default='Administrator')
    last_login = db.Column(db.DateTime)
    credentials_updated_at = db.Column(db.DateTime)
    
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'))
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    ip_address = db.Column(db.String(45))

class OptimizationResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    optimization_type = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    parameters = db.Column(db.JSON)
    results = db.Column(db.JSON)
    fitness_score = db.Column(db.Float)

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # Added
    password = db.Column(db.String(256), nullable=False)  
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'))
    current_location_lat = db.Column(db.Float)
    current_location_lng = db.Column(db.Float)
    last_location_update = db.Column(db.DateTime)
    credentials_updated_at = db.Column(db.DateTime) 
    last_login = db.Column(db.DateTime) 
    route = db.relationship('Route', backref='drivers')
    current_location_lat = db.Column(db.Float)
    current_location_lng = db.Column(db.Float)
    last_location_update = db.Column(db.DateTime)

with app.app_context():
    db.create_all()

# Add this new route
@app.route('/update_bus_locations')
def get_bus_locations():
    bus_data = load_bus_data_from_db()
    updated_locations = update_bus_locations(bus_data)
    return json.dumps(updated_locations)

def load_bus_data_from_db():
    bus_data = {}
    routes = Route.query.all()
    for route in routes:
        bus_data[route.name] = {
            'stops': [stop.name for stop in route.stops],
            'buses': {}
        }
        for bus in route.buses:
            bus_data[route.name]['buses'][bus.name] = {
                'weekdays': [],
                'friday': [],
                'weekends': []
            }
            for schedule in bus.schedules:
                bus_data[route.name]['buses'][bus.name][schedule.day_type].append(
                    schedule.departure_time.strftime('%H:%M')
                )
    return bus_data


def check_schedule_availability(bus_data, route_name, day_type, desired_time, start, dest):
    """
    Check if desired time is within available schedule times
    Returns: tuple (bool, str, str) - (is_available, message, first_bus_time)
    """
    # Get route stops and calculate travel time
    route_stops = bus_data[route_name]['stops']
    start_idx = route_stops.index(start)
    end_idx = route_stops.index(dest)
    
    # Calculate travel time
    if start_idx < end_idx:
        num_stops = end_idx - start_idx
    else:
        num_stops = len(route_stops) - start_idx + end_idx
    travel_time = timedelta(minutes=(num_stops * 3.5 + min(num_stops * 0.5, 10)))
    
    # Get all schedules for this route and day type
    schedules = Schedule.query.join(Bus).join(Route).filter(
        Route.name == route_name,
        Schedule.day_type == day_type
    ).order_by(Schedule.departure_time).all()
    
    if not schedules:
        return False, f"No buses available for this route on {day_type}.", None
    
    # Get first and last bus times
    first_bus = schedules[0].departure_time
    last_bus = schedules[-1].departure_time
    
    first_departure = first_bus.strftime("%I:%M %p")
    last_departure = last_bus.strftime("%I:%M %p")
    
    # Convert user's desired time for comparison
    desired_time = desired_time.time()
    
    if desired_time > (datetime.combine(datetime.today(), last_bus) + travel_time).time():
        return False, f"Your desired arrival time ({desired_time.strftime('%I:%M %p')}) is too late. Last bus departs at {last_departure}. First bus tomorrow is at {first_departure}.", first_bus
        
    if desired_time < (datetime.combine(datetime.today(), first_bus) + travel_time).time():
        return False, f"Your desired arrival time is too early. First bus is at {first_departure}.", first_bus
        
    return True, "", first_bus

def calculate_travel_time(start_idx, end_idx, total_stops):
    """Calculates optimized travel time between stops"""
    # Calculate number of stops between start and end
    if start_idx < end_idx:
        num_stops = end_idx - start_idx
    else:
        num_stops = total_stops - start_idx + end_idx
    
    # Base time calculation: 3-4 minutes between stops with traffic consideration
    base_time = num_stops * 3.5
    
    # Add buffer based on number of stops
    buffer_time = min(num_stops * 0.8, 15)  # Maximum 15 minute buffer for long routes
    
    return timedelta(minutes=(base_time + buffer_time))

def calculate_suggested_arrival(departure_time, buffer_minutes=10):
    """Calculate when user should arrive at the starting point"""
    return departure_time - timedelta(minutes=buffer_minutes)

def find_closest_departure_time(departure_times, travel_datetime, route_stops, start, dest):
    """Finds the optimal departure time to reach destination at desired time"""
    closest_departure = None
    min_wait_time = timedelta.max
    start_idx = route_stops.index(start)
    end_idx = route_stops.index(dest)
    
    # Calculate travel time for this route
    travel_time = calculate_travel_time(start_idx, end_idx, len(route_stops))
    boarding_buffer = timedelta(minutes=10)  # Add boarding buffer
    total_journey_time = travel_time + boarding_buffer
    
    # Define ideal arrival window (5-15 minutes before desired time)
    latest_arrival = travel_datetime - timedelta(minutes=5)
    earliest_arrival = travel_datetime - timedelta(minutes=15)
    
    for dep_time in departure_times:
        # Convert departure time string to datetime
        dep_datetime = datetime.combine(
            travel_datetime.date(), 
            datetime.strptime(dep_time, "%H:%M").time()
        )
        
        # Calculate arrival time for this departure
        arrival_time = dep_datetime + total_journey_time
        
        # Check if arrival is within our ideal window
        if earliest_arrival <= arrival_time <= latest_arrival:
            wait_time = travel_datetime - arrival_time
            if abs(wait_time - timedelta(minutes=10)) < min_wait_time:
                min_wait_time = abs(wait_time - timedelta(minutes=10))
                closest_departure = dep_time
    
    # If no ideal time found, look for any departure that gets us there before desired time
    if not closest_departure:
        latest_possible = None
        min_difference = timedelta.max
        
        for dep_time in departure_times:
            dep_datetime = datetime.combine(
                travel_datetime.date(), 
                datetime.strptime(dep_time, "%H:%M").time()
            )
            arrival_time = dep_datetime + total_journey_time
            
            if arrival_time <= travel_datetime:
                difference = travel_datetime - arrival_time
                if difference < min_difference:
                    min_difference = difference
                    latest_possible = dep_time
        
        closest_departure = latest_possible
    
    return closest_departure

# Add this function at the top of the file, with other helper functions
def find_alternative_routes(bus_data, starting_point, destination, max_transfers=3):
    routes = []
    for route1, data1 in bus_data.items():
        for route2, data2 in bus_data.items():
            if route1 != route2:
                # Find common stops between routes
                stops1 = set(data1['stops'])
                stops2 = set(data2['stops'])
                transfer_stops = stops1.intersection(stops2)
                
                for transfer_stop in transfer_stops:
                    if starting_point in data1['stops'] and transfer_stop in data1['stops'] and \
                       transfer_stop in data2['stops'] and destination in data2['stops']:
                        # Calculate segments
                        first_route_stops = data1['stops']
                        second_route_stops = data2['stops']
                        
                        start_idx1 = first_route_stops.index(starting_point)
                        transfer_idx1 = first_route_stops.index(transfer_stop)
                        transfer_idx2 = second_route_stops.index(transfer_stop)
                        dest_idx2 = second_route_stops.index(destination)
                        
                        # Get all stops for first leg
                        if start_idx1 <= transfer_idx1:
                            first_leg_stops = first_route_stops[start_idx1:transfer_idx1 + 1]
                        else:
                            first_leg_stops = first_route_stops[start_idx1:] + first_route_stops[:transfer_idx1 + 1]
                        
                        # Get all stops for second leg
                        if transfer_idx2 <= dest_idx2:
                            second_leg_stops = second_route_stops[transfer_idx2:dest_idx2 + 1]
                        else:
                            second_leg_stops = second_route_stops[transfer_idx2:] + second_route_stops[:dest_idx2 + 1]
                        
                        # Calculate travel times
                        first_leg_time = (len(first_leg_stops) - 1) * 5  # 5 minutes between stops
                        second_leg_time = (len(second_leg_stops) - 1) * 5
                        transfer_time = 10  # 10 minutes for transfer
                        
                        routes.append({
                            'first_route': route1,
                            'second_route': route2,
                            'transfer_stop': transfer_stop,
                            'first_leg_stops': first_leg_stops,
                            'second_leg_stops': second_leg_stops,
                            'first_leg_time': first_leg_time,
                            'second_leg_time': second_leg_time,
                            'total_time': first_leg_time + second_leg_time + transfer_time
                        })
    
    return routes

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            travel_date = datetime.strptime(request.form['travel_date'], '%Y-%m-%d').date()
            desired_time = datetime.strptime(request.form['desired_time'], '%H:%M').time()
            starting_point = request.form['starting_point'].strip()
            destination = request.form['destination'].strip()

            travel_datetime = datetime.combine(travel_date, desired_time)
            desired_arrival = datetime.combine(travel_date, desired_time)

            bus_data = load_bus_data_from_db()
            logger.debug(f"Bus data: {bus_data}")

            all_stops = Stop.query.all()
            stop_names = [stop.name.strip().lower() for stop in all_stops]

            if starting_point.lower() not in stop_names:
                flash(f"Starting point '{starting_point}' not found. Please choose from the provided options.", "error")
                return redirect(url_for('home'))
            if destination.lower() not in stop_names:
                flash(f"Destination '{destination}' not found. Please choose from the provided options.", "error")
                return redirect(url_for('home'))

            # Determine day type
            day_of_week = travel_datetime.strftime('%A').lower()
            if day_of_week == 'friday':
                day_type = 'friday'
            elif day_of_week in ['saturday', 'sunday']:
                day_type = 'weekends'
            else:
                day_type = 'weekdays'

            # Find the relevant route
            relevant_route = None
            for route_name, route_data in bus_data.items():
                if starting_point in route_data['stops'] and destination in route_data['stops']:
                    relevant_route = route_name
                    break

            if relevant_route:
                # Direct route found - check schedule availability first
                is_available, message, first_bus = check_schedule_availability(
                    bus_data, 
                    relevant_route, 
                    day_type, 
                    travel_datetime,
                    starting_point,
                    destination
                )
                
                if not is_available:
                    flash(message, "error")
                    return redirect(url_for('home'))

                # Available buses check
                available_buses = []
                if relevant_route in bus_data:
                    for bus, schedules in bus_data[relevant_route]['buses'].items():
                        if day_type in schedules and schedules[day_type]:
                            available_buses.append(bus)

                if not available_buses:
                    flash(f"No buses are available for this route on {day_of_week.capitalize()}s.", "warning")
                    return redirect(url_for('home'))

                # Get route stops and calculate optimal travel time
                route_stops = bus_data[relevant_route]['stops']
                start_index = route_stops.index(starting_point)
                end_index = route_stops.index(destination)
                travel_time = calculate_travel_time(start_index, end_index, len(route_stops))

                # Get all departure times for this route
                all_departure_times = []
                for bus in available_buses:
                    if relevant_route in bus_data:
                        schedules = bus_data[relevant_route]['buses'][bus]
                        if day_type in schedules:
                            for departure_time in schedules[day_type]:
                                departure_datetime = datetime.combine(
                                    travel_date,
                                    datetime.strptime(departure_time, '%H:%M').time()
                                )
                                # Calculate travel time and estimated arrival
                                travel_time = calculate_travel_time(
                                    route_stops.index(starting_point),
                                    route_stops.index(destination),
                                    len(route_stops)
                                )
                                estimated_arrival = departure_datetime + travel_time + timedelta(minutes=10)
                                
                                # Only consider departures that get us there before or at desired time
                                if estimated_arrival <= desired_arrival:
                                    all_departure_times.append((bus, departure_time, estimated_arrival))

                    if not all_departure_times:
                        flash("No departures found that arrive before your desired time. Please try a later arrival time.", "warning")
                        return redirect(url_for('home'))

                # Sort by arrival time to find optimal departure
                all_departure_times.sort(key=lambda x: x[2])
                
                # Find the best departure time (arriving 5-15 minutes before desired time)
                suitable_departure = None
                suitable_bus = None
                final_arrival = None

                
                for bus, dep_time, arr_time in all_departure_times:
                    wait_time = desired_arrival - arr_time
                    if timedelta(minutes=5) <= wait_time <= timedelta(minutes=15):
                        suitable_bus = bus
                        suitable_departure = datetime.strptime(dep_time, '%H:%M').time()
                        final_arrival = arr_time
                        break

                # If no ideal time found, take the latest possible departure that gets us there before desired time
                if suitable_departure is None and all_departure_times:
                    suitable_bus = all_departure_times[-1][0]
                    suitable_departure = datetime.strptime(all_departure_times[-1][1], '%H:%M').time()
                    final_arrival = all_departure_times[-1][2]

                if suitable_departure is None:
                    flash("No suitable bus departures found. Please try a different time or route.", "error")
                    return redirect(url_for('home'))

                # Calculate suggested arrival time (10 minutes before departure)
                suggested_arrival = (datetime.combine(travel_date, suitable_departure) - 
                        timedelta(minutes=10))
                suggested_arrival_str = suggested_arrival.strftime('%I:%M %p')

                # Get ordered route stops
                route_stops = get_route_stops(relevant_route, starting_point, destination)

                # Record trip request
                trip_request = TripRequest(
                    desired_time=travel_datetime,
                    starting_point=starting_point,
                    destination=destination
                )
                db.session.add(trip_request)
                db.session.commit()

                return render_template('user_result.html',
                                    arrival_time=desired_arrival.strftime('%I:%M %p'),
                                    starting_point=starting_point,
                                    destination=destination,
                                    bus_group=relevant_route,
                                    bus_name=suitable_bus,
                                    optimized_plan=[suitable_departure.strftime('%I:%M %p')],
                                    actual_arrival=final_arrival.strftime('%I:%M %p'),
                                    route_stops=route_stops,
                                    is_alternative=False,
                                    suggested_arrival=suggested_arrival_str)

            else:
                # Look for alternative routes
                alternative_routes = find_alternative_routes(bus_data, starting_point, destination)
                
                if not alternative_routes:
                    flash("No direct or alternative routes found between these stops.", "error")
                    return redirect(url_for('home'))
                
                # Find best alternative route (shortest total time)
                best_alternative = min(alternative_routes, key=lambda x: x['total_time'])
                
                # Calculate departure and arrival times for first leg
                first_route = best_alternative['first_route']
                
                # Calculate day type
                day_type = 'weekdays'
                if day_of_week == 'friday':
                    day_type = 'friday'
                elif day_of_week in ['saturday', 'sunday']:
                    day_type = 'weekends'
                
                # Find available buses and departure times for first route
                first_route_buses = bus_data[first_route]['buses']
                available_departures = []
                
                for bus, schedules in first_route_buses.items():
                    if day_type in schedules and schedules[day_type]:
                        for departure_time in schedules[day_type]:
                            departure_datetime = datetime.combine(
                                travel_date,
                                datetime.strptime(departure_time, '%H:%M').time()
                            )
                            estimated_arrival = departure_datetime + timedelta(minutes=best_alternative['first_leg_time'])
                            if estimated_arrival <= desired_arrival:
                                available_departures.append((bus, departure_datetime, estimated_arrival))
                
                # If no departures found, get the earliest departure
                if not available_departures:
                    earliest_time = None
                    earliest_bus = None
                    
                    for bus, schedules in first_route_buses.items():
                        if day_type in schedules and schedules[day_type]:
                            for departure_time in schedules[day_type]:
                                time_obj = datetime.strptime(departure_time, '%H:%M').time()
                                if earliest_time is None or time_obj < earliest_time:
                                    earliest_time = time_obj
                                    earliest_bus = bus
                    
                    if earliest_time:
                        departure_datetime = datetime.combine(travel_date, earliest_time)
                        estimated_arrival = departure_datetime + timedelta(minutes=best_alternative['first_leg_time'])
                        available_departures.append((earliest_bus, departure_datetime, estimated_arrival))
                
                # If still no departures, handle no routes scenario
                if not available_departures:
                    flash("No suitable alternative routes found for your desired arrival time.", "error")
                    return redirect(url_for('home'))
                
                # Sort departures and get the best one
                available_departures.sort(key=lambda x: x[2])
                best_departure = available_departures[-1]
                
                # Calculate suggested arrival time
                suggested_arrival = best_departure[1] - timedelta(minutes=10)
                suggested_arrival_str = suggested_arrival.strftime('%I:%M %p')
                
                # Update best_alternative with timing information
                best_alternative.update({
                    'first_bus': best_departure[0],
                    'first_departure': best_departure[1].strftime('%I:%M %p'),
                    'transfer_time': (best_departure[2] + timedelta(minutes=10)).strftime('%I:%M %p')
                })
                
                # Record trip request
                trip_request = TripRequest(
                    desired_time=travel_datetime,
                    starting_point=starting_point,
                    destination=destination
                )
                db.session.add(trip_request)
                db.session.commit()
                
                # Return alternative route result
                return render_template(
                    'user_result.html',
                    arrival_time=desired_arrival.strftime('%I:%M %p'),
                    starting_point=starting_point,
                    destination=destination,
                    alternative_route=best_alternative,
                    is_alternative=True,
                    optimized_plan=[''],
                    actual_arrival='',
                    suggested_arrival=suggested_arrival_str
                )

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            print(traceback.format_exc())
            flash(f"An error occurred while processing your request: {str(e)}", "error")
            return redirect(url_for('home'))

    # GET request handling
    routes = Route.query.all()
    all_stops = Stop.query.all()
    stops = sorted(list(set([stop.name.strip() for stop in all_stops])))
    return render_template('index.html', routes=routes, stops=stops)

def get_route_stops(route_name, start_stop=None, end_stop=None):
    route = Route.query.filter_by(name=route_name).first()
    if not route:
        return []

    # Retrieve the ordered list of stops from the database for the specific route
    stops = Stop.query.filter_by(route_id=route.id).order_by(asc(Stop.id)).all()
    stop_names = [stop.name.strip() for stop in stops]

    # If no start and end stops are provided, return all stops
    if not start_stop or not end_stop:
        return stop_names

    try:
        # Locate the indices of the starting point and destination in the list
        start_index = stop_names.index(start_stop.strip())
        end_index = stop_names.index(end_stop.strip())
    except ValueError:
        return []  # Return empty list if start or end stop not found
    
    # Initialize a set to track seen stops and a list for the result
    seen_stops = set()
    route_stops = []

    # Determine the direction of traversal
    current_index = start_index
    while True:
        # Add the current stop if it hasn't been seen yet
        current_stop = stop_names[current_index]
        if current_stop not in seen_stops:
            seen_stops.add(current_stop)
            route_stops.append(current_stop)

        # Break if we reach the end stop
        if current_stop == end_stop.strip():
            break

        # Move to the next index
        current_index = (current_index + 1) % len(stop_names)

        # Prevent infinite loop
        if current_index == start_index:
            break

    return route_stops

@app.route('/get_route_stops/<route_name>/<start_stop>/<end_stop>')
def get_route_stops_route(route_name, start_stop, end_stop):
    try:
        stops = get_route_stops(route_name, start_stop, end_stop)
        return jsonify({
            'status': 'success',
            'stops': stops
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get_route_stops/<int:route_id>')
def get_route_stops_by_id(route_id):
    try:
        stops = Stop.query.filter_by(route_id=route_id).all()
        return jsonify({
            'status': 'success',
            'stops': [{
                'name': stop.name,
                'latitude': stop.latitude,
                'longitude': stop.longitude
            } for stop in stops]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('You need to be logged in as an admin to access this page.', 'warning')
            return redirect(url_for('auth_login'))
        
        # Check if the session has expired
        last_activity = session.get('last_activity', 0)
        if time.time() - last_activity > app.config['PERMANENT_SESSION_LIFETIME'].total_seconds():
            session.clear()
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('auth_login'))
        
        # Update last activity time
        session['last_activity'] = time.time()
        
        # Add cache-control headers
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function

@app.route('/update_profile', methods=['POST'])
@admin_required
def update_profile():
    try:
        admin_username = session.get('admin_username', 'admin')
        admin = Admin.query.filter_by(username=admin_username).first()
        
        # Get the form data
        new_email = request.form.get('email')
        new_phone = request.form.get('phone')
        new_name = request.form.get('fullName')

        # Validate required fields
        if not all([new_email, new_phone, new_name]):
            return jsonify({
                'status': 'error',
                'message': 'All fields are required'
            }), 400

        # Validate email uniqueness if email changed
        if new_email != admin.email:
            existing_email = Admin.query.filter(
                Admin.email == new_email,
                Admin.id != admin.id
            ).first()
            if existing_email:
                return jsonify({
                    'status': 'error',
                    'message': 'Email already exists'
                }), 400

        # Validate phone uniqueness if phone changed
        if new_phone != admin.phone:
            existing_phone = Admin.query.filter(
                Admin.phone == new_phone,
                Admin.id != admin.id
            ).first()
            if existing_phone:
                return jsonify({
                    'status': 'error',
                    'message': 'Phone number already exists'
                }), 400

        # Update admin information
        admin.email = new_email
        admin.phone = new_phone
        admin.name = new_name
        
        # Log the activity
        audit_log = AuditLog(
            admin_id=admin.id,
            action="Profile information updated",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Commit changes
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    
@app.route('/update_password', methods=['POST'])
@admin_required
def update_password():
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        # Input validation
        if not current_password or not new_password:
            return jsonify({
                'status': 'error',
                'message': 'Both current and new passwords are required'
            }), 400
        
        admin_username = session.get('admin_username')
        if not admin_username:
            return jsonify({
                'status': 'error',
                'message': 'No admin session found'
            }), 401
        
        admin = Admin.query.filter_by(username=admin_username).first()
        if not admin:
            return jsonify({
                'status': 'error',
                'message': 'Admin account not found'
            }), 404
        
        # For first-time setup or migration where password might be None
        if admin.password is None:
            if current_password == 'password':  # Default password check
                admin.password = generate_password_hash(new_password)
                admin.credentials_updated_at = datetime.now()
                db.session.commit()
                return jsonify({
                    'status': 'success',
                    'message': 'Password updated successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid current password'
                }), 400
        
        # Normal password change flow
        if not check_password_hash(admin.password, current_password):
            return jsonify({
                'status': 'error',
                'message': 'Current password is incorrect'
            }), 400
        
        admin.password = generate_password_hash(new_password)
        admin.credentials_updated_at = datetime.now()
        
        # Add audit log
        audit_log = AuditLog(
            admin_id=admin.id,
            action="Password changed",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Password updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/auth_login', methods=['GET', 'POST'])
def auth_login():
    if request.method == 'GET' and session.get('admin_logged_in'):
        session.clear()
        return redirect(url_for('auth_login', message='You have been logged out for security reasons.'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        print(f"Login attempt - Username: {username}, Role: {role}")  # Debug log

        if role.lower() == 'administrator':
            user = Admin.query.filter_by(username=username).first()
            print(f"Found admin: {user}")  # Debug log

            if user and check_password_hash(user.password, password):
                session.clear()  # Clear any existing session
                session['admin_logged_in'] = True
                session['admin_username'] = user.username
                session['role'] = 'administrator'
                session['last_activity'] = time.time()
                
                user.last_login = datetime.now()
                db.session.commit()
                print(f"Admin login successful for {username}")  # Debug log
                
                response = jsonify({'status': 'success', 'redirect': url_for('admin_dashboard')})
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
        
        elif role.lower() == 'driver':
            user = Driver.query.filter_by(username=username).first()
            print(f"Found driver: {user}")  # Debug log
            if user and check_password_hash(user.password, password):
                session.clear()  # Clear any existing session
                session['admin_logged_in'] = True
                session['admin_username'] = user.username
                session['role'] = 'driver'
                session['last_activity'] = time.time()
                
                user.last_login = datetime.now()
                db.session.commit()
                print(f"Driver login successful for {username}")  # Debug log
                
                response = jsonify({'status': 'success', 'redirect': url_for('driver_dashboard')})
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
        
        print("Login failed - Invalid credentials")  # Debug log
        return jsonify({'status': 'error', 'message': 'Invalid credentials'})
    
    # Add cache control headers to the login page
    response = make_response(render_template('auth_login.html', 
                                          success_message=request.args.get('message')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('admin_logged_in'):
                print("Session check failed: Not logged in")  # Debug log
                # Add cache control headers to the redirect
                response = make_response(redirect(url_for('auth_login')))
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
            if session.get('role').lower() not in [r.lower() for r in roles]:
                print(f"Role check failed: {session.get('role')} not in {roles}")  # Debug log
                flash('Unauthorized access', 'error')
                response = make_response(redirect(url_for('auth_login')))
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
            print(f"Access granted for role: {session.get('role')}")  # Debug log
            
            # Add cache control headers to all protected pages
            response = make_response(f(*args, **kwargs))
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        return decorated_function
    return decorator

@app.route('/admin_dashboard')
@role_required(['administrator'])
def admin_dashboard():
    total_buses = Bus.query.count()
    routes = Route.query.all()
    peak_hours = get_peak_hours()
    peak_hours_formatted = ", ".join([hour.strftime("%I%p") for hour in peak_hours])
    
    return render_template('admin_dashboard.html', 
                         buses=total_buses, 
                         routes=routes,
                         peak_hours=peak_hours_formatted)

@app.route('/driver_dashboard')
@role_required(['driver'])
def driver_dashboard():
    # Get the current driver's username from session
    username = session.get('admin_username')
    driver = Driver.query.filter_by(username=username).first()
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('auth_login'))
    
    # Get the route information if assigned
    route_info = None
    if driver.route:
        route_info = {
            'name': driver.route.name,
            'stops': [stop.name for stop in driver.route.stops]
        }
        
    return render_template('driver_dashboard.html', 
                         driver=driver,
                         route_info=route_info)


@app.route('/api/routes', methods=['GET'])
@admin_required
def get_routes():
    try:
        routes = Route.query.all()
        return jsonify([{
            'id': route.id,
            'name': route.name,
            'stops': [{'name': stop.name} for stop in route.stops]
        } for route in routes])
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/routes/<int:route_id>', methods=['GET'])
@admin_required
def get_route(route_id):
    try:
        route = Route.query.get_or_404(route_id)
        return jsonify({
            'id': route.id,
            'name': route.name,
            'stops': [{'name': stop.name} for stop in route.stops],
            'buses': [{'name': bus.name} for bus in route.buses]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/routes', methods=['POST'])
@admin_required
def create_route():
    try:
        data = request.get_json()
        route = Route(name=data['name'])
        db.session.add(route)
        db.session.flush()

        for stop_data in data['stops']:
            stop = Stop(name=stop_data['name'], route_id=route.id)
            db.session.add(stop)

        for bus_data in data['buses']:
            bus = Bus(name=bus_data['name'], route_id=route.id)
            db.session.add(bus)

        db.session.commit()
        return jsonify({'message': 'Route created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/routes/<int:route_id>', methods=['PUT'])
@admin_required
def update_route(route_id):
    try:
        route = Route.query.get_or_404(route_id)
        data = request.get_json()

        if not data.get('name') or not data.get('stops'):
            return jsonify({'error': 'Name and stops are required'}), 400

        route.name = data['name']
        
        # Delete existing stops
        Stop.query.filter_by(route_id=route.id).delete()
        
        # Add new stops
        for stop_data in data['stops']:
            stop = Stop(name=stop_data['name'], route_id=route.id)
            db.session.add(stop)
            
        # Handle buses if provided
        if 'buses' in data:
            # Delete existing buses
            Bus.query.filter_by(route_id=route.id).delete()
            
            # Add new buses
            for bus_data in data['buses']:
                bus = Bus(name=bus_data['name'], route_id=route.id)
                db.session.add(bus)

        db.session.commit()
        return jsonify({'message': 'Route updated successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating route: {str(e)}")  # Add debugging
        return jsonify({'error': str(e)}), 400

@app.route('/api/routes/<int:route_id>', methods=['DELETE']) 
@admin_required
def delete_route(route_id):
    try:
        route = Route.query.get_or_404(route_id)
        db.session.delete(route)
        db.session.commit()
        return jsonify({'message': 'Route deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/route_coordinates/<int:route_id>')
@role_required(['driver'])
def get_route_coordinates(route_id):
    try:
        route = Route.query.get_or_404(route_id)
        stops = Stop.query.filter_by(route_id=route_id).order_by(Stop.id).all()
        
        # Convert stops to coordinates (you'll need to add latitude and longitude fields to your Stop model)
        coordinates = [
            {'lat': stop.latitude, 'lng': stop.longitude}
            for stop in stops
        ]
        
        return jsonify({
            'status': 'success',
            'coordinates': coordinates
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/routes_management')
@admin_required
def routes_management():
    routes = Route.query.all()
    routes_data = [{
        'id': route.id,
        'name': route.name,
        'stops': [{'name': stop.name} for stop in route.stops]
    } for route in routes]
    return render_template('routes_management.html', routes=routes_data)

@app.route('/schedules_management', methods=['GET', 'POST'])
@app.route('/schedules_management/<int:route_id>', methods=['GET', 'POST'])
@app.route('/schedules_management/<int:route_id>/<int:bus_id>', methods=['GET', 'POST'])
@admin_required
def schedules_management(route_id=None, bus_id=None):
    if request.method == 'POST':
        print(f"Received POST request with data: {request.form}")  # Debug log
        action = request.form.get('action')
        if action == 'add':
            try:
                route_id = request.form.get('route_id')
                bus_id = request.form.get('bus_id')
                day_type = request.form.get('day_type')
                departure_time = request.form.get('departure_time')

                if not bus_id:
                    return jsonify({
                        'status': 'error',
                        'message': 'Bus ID is required'
                    })

                bus = Bus.query.get(bus_id)
                if not bus:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid bus ID'
                    })

                if not departure_time:
                    return jsonify({
                        'status': 'error',
                        'message': 'Departure time is required'
                    })

                try:
                    time_obj = datetime.strptime(departure_time, '%H:%M').time()
                except ValueError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid time format. Please use HH:MM format'
                    })

                # Check if schedule already exists
                existing_schedule = Schedule.query.filter_by(
                    bus_id=bus_id,
                    day_type=day_type,
                    departure_time=time_obj
                ).first()

                if existing_schedule:
                    return jsonify({
                        'status': 'error',
                        'message': 'This schedule already exists'
                    })

                try:
                    new_schedule = Schedule(
                        bus=bus,  # Use the bus object directly
                        day_type=day_type,
                        departure_time=time_obj
                    )
                    db.session.add(new_schedule)
                    db.session.commit()
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Schedule added successfully'
                    })
                except Exception as e:
                    db.session.rollback()
                    return jsonify({
                        'status': 'error',
                        'message': f'Error creating schedule: {str(e)}'
                    })

            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        elif action == 'edit':
            schedule_id = request.form.get('schedule_id')
            new_departure_time = request.form.get('new_departure_time')
            new_day_type = request.form.get('new_day_type')

            print(f"Received edit request - Schedule ID: {schedule_id}, New Time: {new_departure_time}, New Day Type: {new_day_type}")  # Debug print

            if not schedule_id:
                return jsonify({
                    'status': 'error',
                    'message': 'Schedule ID is required'
                })

            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return jsonify({
                    'status': 'error',
                    'message': 'Schedule not found'
                })

            try:
                if not new_departure_time:
                    return jsonify({
                        'status': 'error',
                        'message': 'New departure time is required'
                    })

                time_obj = datetime.strptime(new_departure_time, '%H:%M').time()
                schedule.departure_time = time_obj
                schedule.day_type = new_day_type
                db.session.commit()

                return jsonify({
                    'status': 'success',
                    'message': 'Schedule updated successfully',
                    'day_type': new_day_type,
                    'departure_time': new_departure_time
                })
            except ValueError as ve:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid time format: {str(ve)}'
                })
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': f'Error updating schedule: {str(e)}'
                })

        elif action == 'delete':
            try:
                schedule_id = request.form.get('schedule_id')
                
                if not schedule_id:
                    return jsonify({
                        'status': 'error',
                        'message': 'Schedule ID is required'
                    })

                schedule = Schedule.query.get(schedule_id)
                
                if not schedule:
                    return jsonify({
                        'status': 'error',
                        'message': 'Schedule not found'
                    })

                # Store schedule info before deletion for confirmation
                schedule_info = {
                    'bus_name': schedule.bus.name,
                    'day_type': schedule.day_type,
                    'departure_time': schedule.departure_time.strftime('%H:%M')
                }

                db.session.delete(schedule)
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'message': f'Schedule deleted successfully: {schedule_info["bus_name"]} - {schedule_info["day_type"]} at {schedule_info["departure_time"]}',
                    'deleted_schedule': schedule_info
                })
                
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': f'Error deleting schedule: {str(e)}'
                })

    # GET request handling
    routes = Route.query.all()
    all_buses = Bus.query.all()

    if route_id:
        selected_route = Route.query.get_or_404(route_id)
        buses = Bus.query.filter_by(route_id=route_id).all()
        
        if bus_id:
            selected_bus = Bus.query.get_or_404(bus_id)
            schedules = Schedule.query.filter_by(bus_id=bus_id)\
                .order_by(Schedule.day_type, Schedule.departure_time).all()
        else:
            selected_bus = None
            schedules = Schedule.query.join(Bus)\
                .filter(Bus.route_id == route_id)\
                .order_by(Bus.name, Schedule.day_type, Schedule.departure_time).all()
    else:
        selected_route = None
        selected_bus = None
        buses = []
        schedules = []

    # Get all unique day types from the database
    day_types = [day_type[0] for day_type in db.session.query(Schedule.day_type).distinct()]

    try:
        peak_hours = get_peak_hours()
    except Exception as e:
        print(f"Error getting peak hours: {str(e)}")
        peak_hours = []

    return render_template('schedules_management.html', 
                         routes=routes,
                         selected_route=selected_route,
                         buses=buses,
                         all_buses=all_buses,
                         selected_bus=selected_bus,
                         schedules=schedules,
                         peak_hours=peak_hours,
                         day_types=day_types)
def get_peak_hours():
    try:
        # Query most common travel times
        peak_hours_query = db.session.query(
            func.strftime('%H:00', TripRequest.desired_time).label('hour'),
            func.count().label('count')
        ).group_by('hour').order_by(func.count().desc()).limit(3)

        peak_hours = [datetime.strptime(result[0], '%H:%M').time() for result in peak_hours_query]
        return peak_hours
    except Exception as e:
        print(f"Error in get_peak_hours: {str(e)}")
        return []

@app.route('/analytics')
@admin_required
def analytics():
    try:
        # Query 1: Search Volume
        total_searches = db.session.query(func.count(TripRequest.id)).scalar()

        # Query 2: Hourly Distribution
        hourly_searches = db.session.query(
            func.strftime('%H', TripRequest.desired_time).label('hour'),
            func.count(TripRequest.id).label('count')
        ).group_by(
            func.strftime('%H', TripRequest.desired_time)
        ).order_by(
            func.strftime('%H', TripRequest.desired_time)
        ).all()

        # Query 3: Daily Distribution
        daily_searches = db.session.query(
            func.strftime('%w', TripRequest.desired_time).label('day'),
            func.count(TripRequest.id).label('count')
        ).group_by(
            func.strftime('%w', TripRequest.desired_time)
        ).all()

        day_mapping = {
            '0': 'Sunday', '1': 'Monday', '2': 'Tuesday',
            '3': 'Wednesday', '4': 'Thursday', '5': 'Friday', '6': 'Saturday'
        }

        formatted_daily = [
            {'day': day_mapping.get(str(day), 'Unknown'), 'count': count}
            for day, count in daily_searches
        ]

        # Query 4: Popular Routes
        popular_routes = db.session.query(
            TripRequest.starting_point,
            TripRequest.destination,
            func.count(TripRequest.id).label('count')
        ).group_by(
            TripRequest.starting_point,
            TripRequest.destination
        ).order_by(
            func.count(TripRequest.id).desc()
        ).limit(10).all()

        # Query 5: Time Window Analysis
        def get_time_window(hour):
            try:
                hour = int(hour)
                peak_hours = [h.hour for h in get_peak_hours()]
                if hour in peak_hours:
                    return 'Peak Hours'
                elif 6 <= hour < 10:
                    return 'Morning (6-10)'
                elif 10 <= hour < 16:
                    return 'Mid-day (10-16)'
                elif 16 <= hour < 20:
                    return 'Evening (16-20)'
                else:
                    return 'Night (20-6)'
            except (ValueError, TypeError):
                return 'Unknown'

        time_windows = defaultdict(int)
        for hour, count in hourly_searches:
            window = get_time_window(hour)
            time_windows[window] += count

        total_window_searches = sum(time_windows.values()) or 1
        time_windows_data = [
            {
                'window': window,
                'count': count,
                'percentage': round((count / total_window_searches * 100), 2)
            }
            for window, count in time_windows.items()
        ]

        # Query 6: Recent Trends
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_trends = db.session.query(
            func.date(TripRequest.created_at).label('date'),
            func.count(TripRequest.id).label('count')
        ).filter(
            TripRequest.created_at >= seven_days_ago
        ).group_by(
            func.date(TripRequest.created_at)
        ).all()

        # Get peak hours
        peak_hours = get_peak_hours()
        peak_hours_formatted = [hour.strftime("%I:%M %p") for hour in peak_hours]

        # Summary statistics
        summary_stats = {
            'total_searches': total_searches,
            'busiest_day': (
                f"{max(formatted_daily, key=lambda x: x['count'])['day']} "
                f"({max(formatted_daily, key=lambda x: x['count'])['count']} searches)"
            ) if formatted_daily else "No data",
            'busiest_route': (
                f"{popular_routes[0][0]} to {popular_routes[0][1]} "
                f"({popular_routes[0][2]} searches)"
            ) if popular_routes else "No data",
            'busiest_window': (
                f"{max(time_windows_data, key=lambda x: x['count'])['window']} "
                f"({max(time_windows_data, key=lambda x: x['count'])['count']} searches)"
            ) if time_windows_data else "No data",
            'peak_hours': peak_hours_formatted
        }

        # Analytics data
        analytics_data = {
            'hourly': {
                'data': [
                    {'hour': f"{int(hour):02d}:00", 'count': count}
                    for hour, count in hourly_searches
                ],
                'peak_hours': peak_hours_formatted
            },
            'daily': {'data': formatted_daily},
            'popular_routes': [
                {
                    'starting_point': start,
                    'destination': dest,
                    'count': count
                }
                for start, dest, count in popular_routes
            ],
            'time_windows': time_windows_data,
            'recent_trends': [
                {
                    'date': str(date),
                    'count': count
                }
                for date, count in recent_trends
            ]
        }

        return render_template(
            'analytics.html',
            analytics=analytics_data,
            summary=summary_stats
        )

    except Exception as e:
        logging.error(f"Error in analytics: {str(e)}")
        logging.error(traceback.format_exc())
        flash(f"Error generating analytics: {str(e)}", 'error')
        return render_template('analytics.html', 
                             analytics={}, 
                             summary={}, 
                             error=str(e))
    
@app.route('/test_analytics')
@admin_required
def test_analytics():
    try:
        total_searches = db.session.query(func.count(TripRequest.id)).scalar()
        return jsonify({
            'status': 'success',
            'total_searches': total_searches
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        })

@app.route('/api/system_status')
@admin_required
def get_system_status():
    try:
        # Get total fleet size
        total_fleet = Bus.query.count()
        
        # Get number of active routes
        active_routes = Route.query.count()
        
        # Get peak hours
        peak_hours = get_peak_hours()
        peak_hours_formatted = ", ".join([hour.strftime("%I%p") for hour in peak_hours])
        
        # Calculate average daily trips
        last_week = datetime.now() - timedelta(days=7)
        avg_trips = db.session.query(func.count(TripRequest.id) / 7).filter(
            TripRequest.created_at >= last_week
        ).scalar()
        
        return jsonify({
            'total_fleet': total_fleet,
            'active_routes': active_routes,
            'peak_hours': peak_hours_formatted,
            'avg_daily_trips': round(avg_trips if avg_trips else 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
def collect_optimization_data():
    """Collect all necessary data for optimization"""
    try:
        # 1. Current Bus Schedules
        current_schedules = {}
        routes = Route.query.all()
        for route in routes:
            current_schedules[route.name] = {
                'buses': {},
                'stops': [stop.name for stop in route.stops]
            }
            for bus in route.buses:
                current_schedules[route.name]['buses'][bus.name] = {
                    'weekdays': [],
                    'friday': [],
                    'weekends': []
                }
                for schedule in bus.schedules:
                    current_schedules[route.name]['buses'][bus.name][schedule.day_type].append(
                        schedule.departure_time.strftime('%H:%M')
                    )

        # 2. Passenger Demand Trends
        demand_patterns = analyze_demand_patterns()

        # 3. Bus Capacity and Fleet
        fleet_data = {
            'current_fleet': {route.name: len(route.buses) for route in routes},
            'total_capacity': sum(len(route.buses) for route in routes)
        }

        # 4. Historical Travel Patterns
        historical_data = analyze_historical_patterns()

        return {
            'current_schedules': current_schedules,
            'demand_patterns': demand_patterns,
            'fleet_data': fleet_data,
            'historical_data': historical_data
        }
    except Exception as e:
        logging.error(f"Error collecting optimization data: {str(e)}")
        raise

def analyze_demand_patterns():
    """Analyze passenger demand patterns"""
    try:
        # Query trip requests for the last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        trip_requests = TripRequest.query.filter(
            TripRequest.created_at >= thirty_days_ago
        ).all()

        # Analyze hourly patterns
        hourly_demand = defaultdict(int)
        for request in trip_requests:
            hour = request.desired_time.hour
            hourly_demand[hour] += 1

        # Calculate peak hours (hours with demand > 120% of average)
        avg_demand = sum(hourly_demand.values()) / len(hourly_demand) if hourly_demand else 0
        peak_hours = {hour for hour, demand in hourly_demand.items() 
                     if demand > avg_demand * 1.2}

        # Analyze route-specific patterns
        route_patterns = defaultdict(lambda: defaultdict(int))
        for request in trip_requests:
            route = find_route_for_request(request)
            if route:
                hour = request.desired_time.hour
                route_patterns[route.name][hour] += 1

        return {
            'hourly_demand': dict(hourly_demand),
            'peak_hours': list(peak_hours),
            'route_patterns': {k: dict(v) for k, v in route_patterns.items()}
        }
    except Exception as e:
        logging.error(f"Error analyzing demand patterns: {str(e)}")
        return {}

def analyze_historical_patterns():
    """Analyze historical travel patterns"""
    try:
        # Get historical data for the last 90 days
        ninety_days_ago = datetime.now() - timedelta(days=90)
        historical_requests = TripRequest.query.filter(
            TripRequest.created_at >= ninety_days_ago
        ).all()

        patterns = {
            'daily_patterns': defaultdict(int),
            'weekly_patterns': defaultdict(int),
            'route_popularity': defaultdict(int)
        }

        for request in historical_requests:
            # Daily patterns
            hour = request.desired_time.hour
            patterns['daily_patterns'][hour] += 1

            # Weekly patterns
            day = request.desired_time.strftime('%A')
            patterns['weekly_patterns'][day] += 1

            # Route popularity
            route = find_route_for_request(request)
            if route:
                patterns['route_popularity'][route.name] += 1

        return {k: dict(v) for k, v in patterns.items()}
    except Exception as e:
        logging.error(f"Error analyzing historical patterns: {str(e)}")
        return {}

@app.route('/optimization', methods=['GET', 'POST'])
@admin_required
def optimize_system():
    if request.method == 'GET':
        try:
            # Load initial data for the page
            routes = Route.query.all()
            
            # Get current system status
            total_fleet = Bus.query.count()
            active_routes = Route.query.count()
            peak_hours = get_peak_hours()
            peak_hours_formatted = ", ".join([hour.strftime("%I%p") for hour in peak_hours])
            
            # Get optimization history
            recent_optimizations = OptimizationResult.query.order_by(
                OptimizationResult.timestamp.desc()
            ).limit(5).all()
            
            # Get current performance metrics
            performance_metrics = calculate_current_performance()
            
            return render_template(
                'optimization.html',
                routes=routes,
                total_fleet=total_fleet,
                active_routes=active_routes,
                peak_hours=peak_hours_formatted,
                recent_optimizations=recent_optimizations,
                current_metrics=performance_metrics
            )
            
        except Exception as e:
            logging.error(f"Error loading optimization page: {str(e)}")
            flash('Error loading optimization page', 'error')
            return redirect(url_for('admin_dashboard'))

    # POST request handling
    try:
        # Validate parameters
        population_size = int(request.form.get('population_size', 50))
        generations = int(request.form.get('generations', 30))
        mutation_rate = float(request.form.get('mutation_rate', 0.1))

        # Collect optimization data
        optimization_data = collect_optimization_data()
        
        if not optimization_data['current_schedules']:
            return jsonify({
                'status': 'error',
                'message': 'No current schedules found. Please set up routes and schedules first.'
            }), 400

        # Initialize optimizer with collected data
        optimizer = BusScheduleOptimizer(optimization_data)
        
        # Run optimization
        result = optimizer.optimize(
            population_size=population_size,
            generations=generations,
            mutation_rate=mutation_rate
        )

        if not result:
            return jsonify({
                'status': 'error',
                'message': 'Optimization failed to produce valid results'
            }), 500

        # Save optimization result
        optimization_record = OptimizationResult(
            optimization_type='fleet_schedule',
            parameters={
                'population_size': population_size,
                'generations': generations,
                'mutation_rate': mutation_rate
            },
            results=result,
            fitness_score=result['fitness_score']
        )
        db.session.add(optimization_record)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=session.get('admin_id'),
            action="Ran schedule optimization",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()

        return jsonify({
            'status': 'success',
            'result': result
        })

    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': f'Invalid parameter values: {str(e)}'
        }), 400
    except Exception as e:
        logging.error(f"Optimization error: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Error during optimization: {str(e)}'
        }), 500
    
@app.route('/optimize_travel', methods=['POST'])
def optimize_travel():
    try:
        # Get input parameters
        data = request.get_json()
        travel_datetime = datetime.strptime(data['travel_datetime'], '%Y-%m-%d %H:%M')
        starting_point = data['starting_point']
        destination = data['destination']

        # Load bus data
        bus_data = load_bus_data_from_db()

        # Run optimization
        result = optimize_user_travel(bus_data, travel_datetime, starting_point, destination)

        if result:
            return jsonify({
                'status': 'success',
                'result': result
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No suitable route found'
            }), 404

    except Exception as e:
        logging.error(f"Error in travel optimization: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/optimize_fleet', methods=['POST'])
@admin_required
def optimize_fleet():
    global request  # Add this line to access request from outer scope
    try:
        data = request.get_json()
        if not data:
            data = {}
            
        population_size = int(data.get('population_size', 50))
        generations = int(data.get('generations', 30))
        mutation_rate = float(data.get('mutation_rate', 0.1))

        # Load bus data
        bus_data = load_bus_data_from_db()
        
        # Get recent trip requests and calculate demand patterns
        thirty_days_ago = datetime.now() - timedelta(days=30)
        trip_requests = TripRequest.query.filter(
            TripRequest.created_at >= thirty_days_ago
        ).order_by(TripRequest.desired_time).all()

        # Calculate hourly demand patterns
        hourly_demand = [0] * 24
        for request_obj in trip_requests:  # Changed variable name to avoid conflict
            hour = request_obj.desired_time.hour
            hourly_demand[hour] += 1

        # Get current fleet data
        current_fleet = {route.name: len(route.buses) for route in Route.query.all()}

        # Run optimization
        result = optimize_fleet_and_schedule(
            bus_data, 
            trip_requests, 
            current_fleet, 
            population_size, 
            generations, 
            mutation_rate
        )

        if result is None:
            return jsonify({
                'status': 'error',
                'message': 'Optimization failed to produce results'
            }), 500

        response_data = {
            'status': 'success',
            'result': {
                'optimized_fleet': result.get('optimized_fleet', {}),
                'optimized_schedules': result.get('optimized_schedules', {}),
                'fitness_score': result.get('fitness_score', 0),
                'fitness_metrics': result.get('fitness_metrics', {}),
                'current_fleet': current_fleet,
                'demand_patterns': hourly_demand
            }
        }

        logging.info(f"Demand patterns: {hourly_demand}")
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Optimization error: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/optimization_metrics', methods=['GET'])
@admin_required
def get_optimization_metrics():
    try:
        # Get latest optimization result
        latest_result = OptimizationResult.query.order_by(
            OptimizationResult.timestamp.desc()
        ).first()

        if not latest_result:
            # If no optimization results, create a default one
            return jsonify({
                'status': 'success',
                'metrics': {
                    'fitness_score': 0,
                    'optimization_type': 'default',
                    'parameters': {},
                    'results': {},
                    'demand_patterns': [0] * 24  # Default empty demand pattern
                }
            })

        # Get demand patterns
        demand_patterns = calculate_demand_patterns()

        return jsonify({
            'status': 'success',
            'metrics': {
                'fitness_score': latest_result.fitness_score or 0,
                'optimization_type': latest_result.optimization_type or 'default',
                'parameters': latest_result.parameters or {},
                'results': latest_result.results or {},
                'demand_patterns': demand_patterns
            }
        })

    except Exception as e:
        logging.error(f"Error fetching optimization metrics: {str(e)}")
        return jsonify({
            'status': 'success',
            'metrics': {
                'fitness_score': 0,
                'optimization_type': 'error',
                'parameters': {},
                'results': {},
                'demand_patterns': [0] * 24
            }
        })

def find_route_for_request(request):
    """Find route containing both starting point and destination"""
    try:
        start_stop = Stop.query.filter_by(name=request.starting_point).first()
        end_stop = Stop.query.filter_by(name=request.destination).first()
        
        if not start_stop or not end_stop:
            return None
            
        # First check for direct routes
        direct_route = Route.query.filter(
            Route.id == start_stop.route_id,
            Route.id == end_stop.route_id
        ).first()
        
        if direct_route:
            return direct_route
            
        # If no direct route, find first route that contains either stop
        return Route.query.filter(
            (Route.id == start_stop.route_id) | 
            (Route.id == end_stop.route_id)
        ).first()
        
    except Exception as e:
        logging.error(f"Error finding route for request: {str(e)}")
        return None
    
def calculate_current_performance():
    """Calculate current system performance metrics"""
    try:
        metrics = {
            'average_wait_time': 0,
            'bus_utilization': 0,
            'peak_coverage': 0,
            'operational_efficiency': 0
        }
        
        # Calculate average wait time
        current_time = datetime.now()  # Use datetime instead of time
        recent_requests = TripRequest.query.order_by(
            TripRequest.created_at.desc()
        ).limit(100).all()
        
        if recent_requests:
            total_wait_time = 0
            count = 0
            for request in recent_requests:
                route = find_route_for_request(request)
                if route:
                    bus_schedules = Schedule.query.join(Bus).filter(
                        Bus.route_id == route.id
                    ).all()
                    if bus_schedules:
                        closest_time = min(
                            abs((schedule.departure_time.hour * 60 + schedule.departure_time.minute) -
                                (request.desired_time.hour * 60 + request.desired_time.minute))
                            for schedule in bus_schedules
                        )
                        total_wait_time += closest_time
                        count += 1
            
            if count > 0:
                metrics['average_wait_time'] = total_wait_time / count

        return metrics
    except Exception as e:
        logging.error(f"Error calculating performance metrics: {str(e)}")
        return {
            'average_wait_time': 0,
            'bus_utilization': 0,
            'peak_coverage': 0,
            'operational_efficiency': 0
        }
    
def calculate_demand_patterns(trip_requests=None):
    """Calculate hourly demand patterns"""
    try:
        # If no trip_requests provided, fetch recent requests
        if trip_requests is None:
            trip_requests = TripRequest.query.filter(
                TripRequest.created_at >= datetime.now() - timedelta(days=30)
            ).all()
        
        # Initialize demand array for 24 hours
        hourly_demand = [0] * 24
        
        if not trip_requests:
            return hourly_demand
            
        # Count requests for each hour
        for request in trip_requests:
            if request.desired_time:  # Check if desired_time exists
                hour = request.desired_time.hour
                hourly_demand[hour] += 1
                
        # Normalize the data to get ratios
        max_demand = max(hourly_demand) if max(hourly_demand) > 0 else 1
        normalized_demand = [round(count / max_demand, 2) for count in hourly_demand]
        
        logging.info(f"Calculated demand patterns: {normalized_demand}")
        return normalized_demand
        
    except Exception as e:
        logging.error(f"Error calculating demand patterns: {str(e)}")
        return [0] * 24

@app.route('/api/drivers', methods=['GET'])
@admin_required
def get_drivers():
    drivers = Driver.query.all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'phone': d.phone,
        'email': d.email,
        'license_number': d.license_number,
        'route_id': d.route_id,
        'route_name': Route.query.get(d.route_id).name if d.route_id else 'Unassigned'
    } for d in drivers])

@app.route('/api/drivers', methods=['POST'])
@admin_required
def add_driver():
    try:
        data = request.form
        
        # Validate required fields
        required_fields = ['username', 'password', 'name', 'phone', 'email', 'license', 'route_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'{field} is required'
                }), 400
        
        # Check if username already exists
        existing_driver = Driver.query.filter_by(username=data['username']).first()
        if existing_driver:
            return jsonify({
                'status': 'error',
                'message': 'Username already exists'
            }), 400
            
        # Create new driver
        new_driver = Driver(
            username=data['username'],
            password=generate_password_hash(data['password']),
            name=data['name'],
            phone=data['phone'],
            email=data['email'],
            license_number=data['license'],
            route_id=data['route_id'],
            credentials_updated_at=datetime.now(timezone.utc)
        )
        
        db.session.add(new_driver)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Driver added successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@app.route('/api/drivers/<int:id>', methods=['GET'])
@admin_required
def get_driver(id):
    driver = Driver.query.get_or_404(id)
    return jsonify({
        'id': driver.id,
        'name': driver.name,
        'phone': driver.phone,
        'email': driver.email,
        'license_number': driver.license_number,
        'route_id': driver.route_id
    })

@app.route('/api/drivers/<int:id>', methods=['PUT'])
@admin_required
def update_driver(id):
    try:
        driver = Driver.query.get_or_404(id)
        data = request.form
        
        driver.name = data['name']
        driver.phone = data['phone']
        driver.email = data['email']
        driver.license_number = data['license']
        driver.route_id = data['route_id']
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Driver updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/drivers/<int:id>', methods=['DELETE'])
@admin_required
def delete_driver(id):
    try:
        driver = Driver.query.get_or_404(id)
        db.session.delete(driver)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Driver deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/driver_management')
@admin_required
def driver_management():
    routes = Route.query.all()
    return render_template('driver_management.html', routes=routes)

@app.route('/accounts')
@admin_required
def accounts():
    # Get the admin username from the session
    admin_username = session.get('admin_username', 'admin')  # Default to 'admin' if not found
    
    # Query the admin from database
    admin = Admin.query.filter_by(username=admin_username).first()
    
    # If admin doesn't exist in database yet, create a default admin object
    if not admin:
        admin = {
            'name': 'Administrator',
            'email': '',
            'phone': '',
            'username': admin_username,
            'role': 'Administrator'
        }
    
    # Get recent audit logs (last 10 entries)
    audit_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    # Format the audit logs
    formatted_logs = []
    if audit_logs:
        for log in audit_logs:
            formatted_logs.append({
                'action': log.action,
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })
    
    # If no logs exist, add a default entry
    if not formatted_logs:
        formatted_logs = [{
            'action': 'Account page accessed',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }]

    return render_template('accounts.html', 
                         admin=admin, 
                         audit_log=formatted_logs)


@app.route('/admin_logout')
def admin_logout():
    session.clear()  # Clear all session data
    response = make_response(redirect(url_for('auth_login', message='You have been logged out.')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/driver_logout')
def driver_logout():
    session.clear()  # Clear all session data
    response = make_response(redirect(url_for('auth_login', message='You have been logged out.')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/check_session')
def check_session():
    is_logged_in = 'admin_logged_in' in session and 'role' in session
    response = jsonify({'logged_in': is_logged_in, 'role': session.get('role') if is_logged_in else None})
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/debug_stops')
def debug_stops():
    stops = Stop.query.all()
    return ', '.join([stop.name for stop in stops])


def get_day_type(day_of_week):
    if day_of_week in ['monday', 'tuesday', 'wednesday', 'thursday']:
        return 'weekdays'
    elif day_of_week == 'friday':
        return 'friday'
    else:
        return 'weekends'

def load_bus_data_from_db():
    """Load bus data from database in the format required by optimization"""
    bus_data = {}
    routes = Route.query.all()
    
    for route in routes:
        bus_data[route.name] = {
            'stops': [stop.name for stop in route.stops],
            'buses': {}
        }
        for bus in route.buses:
            bus_data[route.name]['buses'][bus.name] = {
                'weekdays': [],
                'friday': [],
                'weekends': []
            }
            for schedule in bus.schedules:
                bus_data[route.name]['buses'][bus.name][schedule.day_type].append(
                    schedule.departure_time.strftime('%H:%M')
                )
    
    return bus_data

@app.route('/update_driver_location', methods=['POST'])
@role_required(['driver'])
def update_driver_location():
    try:
        data = request.get_json()
        
        # Get current driver
        username = session.get('admin_username')
        driver = Driver.query.filter_by(username=username).first()
        
        if not driver:
            return jsonify({
                'status': 'error',
                'message': 'Driver not found'
            }), 404

        # Create GIS tracker instance
        tracker = GISTracker()

        # Get previous location if exists
        previous_location = None
        if driver.current_location_lat and driver.current_location_lng and driver.last_location_update:
            previous_location = {
                'lat': driver.current_location_lat,
                'lng': driver.current_location_lng,
                'timestamp': driver.last_location_update
            }

        # Process location update
        timestamp = datetime.fromtimestamp(data['timestamp'] / 1000.0, timezone.utc)
        result = tracker.process_location_update(
            driver_id=driver.id,
            lat=data['lat'],
            lng=data['lng'],
            accuracy=data['accuracy'],
            timestamp=timestamp,
            previous_location=previous_location
        )

        if result['status'] == 'error':
            return jsonify(result), 400

        # Update driver location in database
        driver.current_location_lat = data['lat']
        driver.current_location_lng = data['lng']
        driver.last_location_update = timestamp
        
        db.session.commit()
        
        return jsonify(result)
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Location update error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    
@app.route('/get_active_buses', methods=['GET'])
def get_active_buses():
    try:
        # Get all active drivers/buses
        active_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        active_drivers = Driver.query.filter(
            Driver.last_location_update >= active_threshold,
            Driver.current_location_lat.isnot(None),
            Driver.current_location_lng.isnot(None)
        ).all()
        
        buses = []
        for driver in active_drivers:
            buses.append({
                'driver_id': driver.id,
                'route_name': driver.route.name if driver.route else None,
                'location': {
                    'lat': driver.current_location_lat,
                    'lng': driver.current_location_lng,
                    'last_update': driver.last_location_update.isoformat()
                }
            })
            
        return jsonify({
            'status': 'success',
            'buses': buses
        })
        
    except Exception as e:
        logging.error(f"Error getting active buses: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


    
@app.route('/check_driver_location')
@role_required(['driver', 'administrator'])
def check_driver_location():
    try:
        username = session.get('admin_username')
        driver = Driver.query.filter_by(username=username).first()
        
        if not driver:
            return jsonify({
                'status': 'error',
                'message': 'Driver not found'
            })
            
        return jsonify({
            'status': 'success',
            'data': {
                'driver_name': driver.name,
                'current_lat': driver.current_location_lat,
                'current_lng': driver.current_location_lng,
                'last_update': driver.last_location_update.strftime('%Y-%m-%d %H:%M:%S') if driver.last_location_update else None
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })
    
@app.route('/driver_account')
@role_required(['driver'])
def driver_account():
    username = session.get('admin_username')
    driver = Driver.query.filter_by(username=username).first()
    
    if not driver:
        flash('Driver not found', 'error')
        return redirect(url_for('auth_login'))
    
    return render_template('driver_account.html', driver=driver)

@app.route('/update_driver_password', methods=['POST'])
@role_required(['driver'])
def update_driver_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'status': 'error',
                'message': 'Both current and new password are required'
            }), 400
        
        # Get the current driver
        username = session.get('admin_username')
        driver = Driver.query.filter_by(username=username).first()
        
        if not driver:
            return jsonify({
                'status': 'error',
                'message': 'Driver not found'
            }), 404
        
        # Verify current password
        if not check_password_hash(driver.password, current_password):
            return jsonify({
                'status': 'error',
                'message': 'Current password is incorrect'
            }), 400
        
        # Update password
        driver.password = generate_password_hash(new_password)
        driver.credentials_updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Password updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    
@app.route('/test_gis')
def test_gis():
    try:
        # Get all drivers
        drivers = Driver.query.all()
        print(f"Found {len(drivers)} drivers")  # Debug print
        
        results = []
        for driver in drivers:
            # Debug print for each driver
            print(f"Driver: {driver.name}")
            print(f"Location: {driver.current_location_lat}, {driver.current_location_lng}")
            print(f"Last update: {driver.last_location_update}")
            print(f"Route: {driver.route.name if driver.route else 'No route'}")
            
            results.append({
                'name': driver.name,
                'lat': driver.current_location_lat,
                'lng': driver.current_location_lng,
                'last_update': driver.last_location_update,
                'route': driver.route.name if driver.route else None
            })
        
        # Debug print final results
        print(f"Returning results: {results}")
        return jsonify(results)
    except Exception as e:
        print(f"Error in test_gis: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)