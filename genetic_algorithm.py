import random
import logging
import traceback
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def optimize_user_travel(bus_data, travel_datetime, starting_point, destination, population_size=50, generations=100, mutation_rate=0.1):
    """Optimize user travel path using genetic algorithm"""
    try:
        def fitness(individual):
            """Calculate fitness score for an individual solution"""
            if individual is None:
                return 0

            route = individual['route']
            departure_time = datetime.strptime(individual['departure_time'], "%H:%M").time()
            route_stops = bus_data[route]['stops']
            
            start_index = route_stops.index(starting_point)
            end_index = route_stops.index(destination)
            
            # Calculate travel time
            travel_time = calculate_travel_time(start_index, end_index, len(route_stops))
            arrival_time = (datetime.combine(travel_datetime.date(), departure_time) + 
                        timedelta(minutes=travel_time.total_seconds() / 60)).time()

            # Calculate time difference from desired arrival
            time_diff = calculate_time_difference(arrival_time, travel_datetime.time())
            
            # Penalize late arrivals more heavily
            return 1 / (time_diff + (100 if arrival_time > travel_datetime.time() else 1))

        def create_individual():
            """Create a single individual for the genetic algorithm"""
            # Find valid routes containing both stops
            valid_routes = []
            for route_name, route_data in bus_data.items():
                if starting_point in route_data['stops'] and destination in route_data['stops']:
                    valid_routes.append(route_name)
            
            if not valid_routes:
                return None
            
            route = random.choice(valid_routes)
            day_type = get_day_type(travel_datetime.strftime('%A').lower())
            
            # Get available departure times
            departure_times = []
            for bus, schedules in bus_data[route]['buses'].items():
                if day_type in schedules:
                    departure_times.extend(schedules[day_type])
            
            if not departure_times:
                return None
            
            return {
                'route': route,
                'departure_time': random.choice(departure_times),
                'bus': random.choice(list(bus_data[route]['buses'].keys()))
            }

        # First check for direct route
        direct_route = None
        for route_name, route_data in bus_data.items():
            if starting_point in route_data['stops'] and destination in route_data['stops']:
                direct_route = route_name
                break
        
        if direct_route:
            # Evolution process
            population = [create_individual() for _ in range(population_size)]
            population = [ind for ind in population if ind is not None]

            if not population:
                return None

            for _ in range(generations):
                population = evolve_population(population, fitness, mutation_rate)
                if not population:
                    return None

            # Get best solution
            best_individual = max(population, key=fitness)
            if best_individual:
                route_stops = bus_data[best_individual['route']]['stops']
                travel_time = calculate_travel_time(
                    route_stops.index(starting_point),
                    route_stops.index(destination),
                    len(route_stops)
                )
                
                return {
                    'route_type': 'direct',
                    'route': best_individual['route'],
                    'departure_time': best_individual['departure_time'],
                    'travel_time': travel_time.total_seconds() / 60,
                    'stops': get_route_stops(route_stops, starting_point, destination)
                }
        
        # If no direct route, find alternative routes
        alternative_routes = find_alternative_routes(bus_data, starting_point, destination)
        if alternative_routes:
            best_alternative = alternative_routes[0]  # Take first alternative for now
            times = calculate_alternative_route_times(
                bus_data,
                best_alternative,
                travel_datetime,
                get_day_type(travel_datetime.strftime('%A').lower())
            )
            
            if times:
                return {
                    'route_type': 'alternative',
                    'first_route': best_alternative['first_route'],
                    'second_route': best_alternative['second_route'],
                    'transfer_stop': best_alternative['transfer_stop'],
                    'times': times
                }
        
        return None
        
    except Exception as e:
        logging.error(f"Error optimizing user travel: {str(e)}")
        logging.error(traceback.format_exc())
        return None

def get_day_type(day_of_week):
    """Determines the day type (weekdays, friday, weekends) from the day of week"""
    if day_of_week in ['monday', 'tuesday', 'wednesday', 'thursday']:
        return 'weekdays'
    elif day_of_week == 'friday':
        return 'friday'
    else:
        return 'weekends'

def find_closest_departure_time(departure_times, travel_datetime, route_stops, start, dest):
    """Finds the optimal departure time to reach destination at desired time"""
    closest_departure = None
    min_wait_time = timedelta.max
    start_idx = route_stops.index(start)
    end_idx = route_stops.index(dest)
    
    # Calculate travel time for this route
    travel_time = calculate_travel_time(start_idx, end_idx, len(route_stops))
    
    # Work backwards from desired arrival time
    desired_arrival = travel_datetime
    ideal_departure = desired_arrival - travel_time
    
    for dep_time in departure_times:
        # Convert departure time string to datetime
        dep_datetime = datetime.combine(
            travel_datetime.date(), 
            datetime.strptime(dep_time, "%H:%M").time()
        )
        
        # Calculate arrival time for this departure
        arrival_time = dep_datetime + travel_time
        
        # Check if this departure gets us there before desired time
        if arrival_time <= desired_arrival:
            wait_time = desired_arrival - arrival_time
            
            # Prioritize arrivals that are 5-15 minutes before desired time
            if timedelta(minutes=5) <= wait_time <= timedelta(minutes=15):
                if wait_time < min_wait_time:
                    min_wait_time = wait_time
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
            arrival_time = dep_datetime + travel_time
            
            if arrival_time <= desired_arrival:
                difference = desired_arrival - arrival_time
                if difference < min_difference:
                    min_difference = difference
                    latest_possible = dep_time
        
        closest_departure = latest_possible
    
    return closest_departure

def calculate_travel_time(start_idx, end_idx, total_stops):
    """Calculates optimized travel time between stops"""
    # Calculate number of stops between start and end
    if start_idx < end_idx:
        num_stops = end_idx - start_idx
    else:
        num_stops = total_stops - start_idx + end_idx
    
    # Base time calculation: 3-4 minutes between stops with traffic consideration
    base_time = num_stops * 3.5
    
    # Add buffer based on number of stops and time of day
    buffer_time = min(num_stops * 0.8, 15)  # Maximum 15 minute buffer for long routes
    
    return timedelta(minutes=(base_time + buffer_time))

def find_optimal_departure_time(travel_datetime, schedules, route_stops, start, dest, day_type):
    """Find the optimal departure time that ensures arrival before desired time"""
    travel_time = calculate_travel_time(
        route_stops.index(start),
        route_stops.index(dest),
        len(route_stops)
    )
    
    # Add 10 minutes buffer for boarding and potential delays
    total_journey_time = travel_time + timedelta(minutes=10)
    
    # Calculate ideal departure time working backwards
    ideal_departure = travel_datetime - total_journey_time
    
    # Get all available departure times for the day
    available_departures = []
    for departure_time in schedules:
        dep_time = datetime.strptime(departure_time, '%H:%M').time()
        dep_datetime = datetime.combine(travel_datetime.date(), dep_time)
        
        # Calculate estimated arrival for this departure
        est_arrival = dep_datetime + total_journey_time
        
        # Only consider departures that get us there before desired time
        if est_arrival <= travel_datetime:
            time_diff = travel_datetime - est_arrival
            # Prioritize arrivals 5-15 minutes before desired time
            if timedelta(minutes=5) <= time_diff <= timedelta(minutes=15):
                available_departures.append({
                    'departure': dep_datetime,
                    'arrival': est_arrival,
                    'wait_time': time_diff,
                    'score': abs((time_diff - timedelta(minutes=10)).total_seconds())  # Optimal: 10 min early
                })
    
    if available_departures:
        # Sort by score (closest to 10 minutes early)
        optimal_journey = min(available_departures, key=lambda x: x['score'])
        return {
            'departure_time': optimal_journey['departure'].strftime('%H:%M'),
            'arrival_time': optimal_journey['arrival'].strftime('%H:%M'),
            'suggested_arrival': (optimal_journey['departure'] - timedelta(minutes=10)).strftime('%I:%M %p'),
            'travel_time': travel_time.total_seconds() / 60
        }
    
    return None

def calculate_time_difference(time1, time2):
    """Calculates difference between two times in minutes"""
    t1_minutes = time1.hour * 60 + time1.minute
    t2_minutes = time2.hour * 60 + time2.minute
    return abs(t1_minutes - t2_minutes)

def get_route_stops(route_stops, start, dest):
    """Gets ordered list of stops between start and destination"""
    start_idx = route_stops.index(start)
    end_idx = route_stops.index(dest)
    
    if start_idx < end_idx:
        return route_stops[start_idx:end_idx + 1]
    return route_stops[start_idx:] + route_stops[:end_idx + 1]

def evolve_population(population, fitness_func, mutation_rate):
    """Evolves a population for user travel optimization"""
    fitness_scores = [fitness_func(ind) for ind in population]
    parents = random.choices(population, weights=fitness_scores, k=len(population))
    new_population = []
    
    for i in range(0, len(parents), 2):
        parent1, parent2 = parents[i], parents[min(i+1, len(parents)-1)]
        child1 = crossover_individuals(parent1, parent2)
        child2 = crossover_individuals(parent2, parent1)
        new_population.extend([
            mutate_individual(child1, mutation_rate),
            mutate_individual(child2, mutation_rate)
        ])
    
    return [ind for ind in new_population if ind is not None]

def crossover_individuals(parent1, parent2):
    """Performs crossover for user travel optimization"""
    if parent1 is None or parent2 is None:
        return parent1 if parent1 is not None else parent2
    
    child = parent1.copy()
    if random.random() < 0.5:
        child['bus'] = parent2['bus']
    if random.random() < 0.5:
        child['departure_time'] = parent2['departure_time']
    return child

def mutate_individual(individual, mutation_rate):
    """Mutates an individual for user travel optimization"""
    if individual is None or random.random() >= mutation_rate:
        return individual
    
    new_individual = individual.copy()
    if random.random() < 0.5:
        new_individual['departure_time'] = str(
            random.randint(0, 23)).zfill(2) + ':' + str(random.randint(0, 59)).zfill(2)
    return new_individual

def find_alternative_routes(bus_data, starting_point, destination, travel_datetime=None):
    """
    Find alternative routes with optimized timing when direct route is not available.
    """
    alternative_routes = []
    
    # Find all routes containing the starting point
    start_routes = []
    for route_name, route_data in bus_data.items():
        if starting_point in route_data['stops']:
            start_routes.append(route_name)
    
    # Find all routes containing the destination
    dest_routes = []
    for route_name, route_data in bus_data.items():
        if destination in route_data['stops']:
            dest_routes.append(route_name)
    
    # Find valid transfer combinations
    for start_route in start_routes:
        start_stops = set(bus_data[start_route]['stops'])
        
        for dest_route in dest_routes:
            if start_route == dest_route:
                continue
                
            dest_stops = set(bus_data[dest_route]['stops'])
            transfer_stops = start_stops.intersection(dest_stops)
            
            for transfer_stop in transfer_stops:
                if is_valid_transfer_path(
                    bus_data, 
                    start_route, 
                    dest_route, 
                    starting_point, 
                    transfer_stop, 
                    destination
                ):
                    alternative_routes.append({
                        'first_route': start_route,
                        'second_route': dest_route,
                        'transfer_stop': transfer_stop,
                        'starting_point': starting_point,
                        'destination': destination
                    })
    
    return alternative_routes

def is_valid_transfer_path(bus_data, start_route, dest_route, start_stop, transfer_stop, dest_stop):
    """
    Check if the transfer path is valid and efficient
    """
    try:
        # Get stop indices for first route
        first_route_stops = bus_data[start_route]['stops']
        start_idx = first_route_stops.index(start_stop)
        transfer_idx_first = first_route_stops.index(transfer_stop)
        
        # Get stop indices for second route
        second_route_stops = bus_data[dest_route]['stops']
        transfer_idx_second = second_route_stops.index(transfer_stop)
        dest_idx = second_route_stops.index(dest_stop)
        
        # Check first route segment
        if start_route == dest_route:
            return False
        
        # For circular routes, handle wraparound
        if start_idx > transfer_idx_first:
            transfer_idx_first += len(first_route_stops)
        if transfer_idx_second > dest_idx:
            dest_idx += len(second_route_stops)
        
        # Check total journey length is reasonable
        first_leg_time = calculate_travel_time(start_idx, transfer_idx_first, len(first_route_stops))
        second_leg_time = calculate_travel_time(transfer_idx_second, dest_idx, len(second_route_stops))
        total_time = first_leg_time + second_leg_time + timedelta(minutes=10)  # Including transfer time
        
        # Return true only if total journey time is reasonable (e.g., less than 2 hours)
        return total_time <= timedelta(hours=2)
        
    except (ValueError, IndexError):
        return False

def calculate_alternative_route_times(bus_data, route_combo, travel_datetime, day_type):
    """
    Calculate optimized timings for alternative routes working backwards from desired arrival time
    with improved buffer and transfer time calculations
    """
    first_route = route_combo['first_route']
    second_route = route_combo['second_route']
    transfer_stop = route_combo['transfer_stop']
    desired_arrival = travel_datetime
    
    # Get route stops and calculate travel times
    first_route_stops = bus_data[first_route]['stops']
    second_route_stops = bus_data[second_route]['stops']
    
    # Calculate leg times with more precise buffers
    start_idx = first_route_stops.index(route_combo['starting_point'])
    transfer_idx = first_route_stops.index(transfer_stop)
    first_leg_time = calculate_travel_time(start_idx, transfer_idx, len(first_route_stops))
    
    transfer_idx_second = second_route_stops.index(transfer_stop)
    dest_idx = second_route_stops.index(route_combo['destination'])
    second_leg_time = calculate_travel_time(transfer_idx_second, dest_idx, len(second_route_stops))
    
    # Define buffer times more precisely
    boarding_buffer = timedelta(minutes=5)  # Time to board the first bus
    transfer_buffer = timedelta(minutes=8)  # Transfer time between buses
    arrival_buffer = timedelta(minutes=5)   # Buffer before desired arrival time
    
    # Get all departure times
    first_route_times = []
    second_route_times = []
    
    # Collect all departure times for both routes
    for bus, schedules in bus_data[first_route]['buses'].items():
        if day_type in schedules:
            first_route_times.extend(schedules[day_type])
    for bus, schedules in bus_data[second_route]['buses'].items():
        if day_type in schedules:
            second_route_times.extend(schedules[day_type])
    
    # Sort and remove duplicates
    first_route_times = sorted(list(set(first_route_times)))
    second_route_times = sorted(list(set(second_route_times)))
    
    # Work backwards from desired arrival time
    best_combination = None
    min_total_wait = timedelta(hours=24)
    
    # Convert desired arrival to datetime
    desired_arrival_dt = datetime.combine(desired_arrival.date(), desired_arrival.time())
    ideal_arrival = desired_arrival_dt - arrival_buffer
    
    # Find suitable second leg departure that gets us to destination on time
    for second_dep in second_route_times:
        second_dep_time = datetime.strptime(second_dep, "%H:%M").time()
        second_dep_dt = datetime.combine(desired_arrival.date(), second_dep_time)
        second_arrival = second_dep_dt + second_leg_time
        
        # Check if this arrival time is suitable
        if second_arrival <= ideal_arrival:
            # Calculate required transfer arrival time
            required_transfer_time = second_dep_dt - transfer_buffer
            
            # Find suitable first leg departure
            for first_dep in first_route_times:
                first_dep_time = datetime.strptime(first_dep, "%H:%M").time()
                first_dep_dt = datetime.combine(desired_arrival.date(), first_dep_time)
                first_arrival = first_dep_dt + first_leg_time
                
                # Check if this gets us to transfer point on time
                if first_arrival <= required_transfer_time:
                    transfer_wait = required_transfer_time - first_arrival
                    total_wait = (ideal_arrival - second_arrival) + transfer_wait
                    
                    # Update best combination if this timing is better
                    if total_wait < min_total_wait and transfer_wait >= timedelta(minutes=5):
                        min_total_wait = total_wait
                        
                        # Calculate suggested arrival time (5 minutes before first departure)
                        suggested_arrival = first_dep_dt - boarding_buffer
                        
                        best_combination = {
                            'first_route_times': [first_dep],
                            'second_route_times': [second_dep],
                            'first_departure': first_dep,
                            'transfer_time': first_arrival.strftime("%H:%M"),
                            'second_departure': second_dep,
                            'final_arrival': second_arrival.strftime("%H:%M"),
                            'first_leg_time': first_leg_time.total_seconds() / 60,
                            'second_leg_time': second_leg_time.total_seconds() / 60,
                            'total_time': (first_leg_time + transfer_buffer + second_leg_time).total_seconds() / 60,
                            'suggested_arrival': suggested_arrival.strftime("%I:%M %p"),
                            'buffers': {
                                'boarding': boarding_buffer.total_seconds() / 60,
                                'transfer': transfer_buffer.total_seconds() / 60,
                                'arrival': arrival_buffer.total_seconds() / 60
                            }
                        }
    
    # If no ideal combination found, return available times
    if not best_combination:
        return {
            'first_route_times': first_route_times,
            'second_route_times': second_route_times
        }
    
    return best_combination