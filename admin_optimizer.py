import random
import logging
import traceback
from datetime import datetime, timedelta, time
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class BusScheduleOptimizer:
    def __init__(self, optimization_data):
        """
        Initialize the BusScheduleOptimizer with comprehensive optimization data
        
        Expected keys in optimization_data:
        - current_schedules: Current bus schedules
        - demand_patterns: Passenger demand patterns
        - fleet_data: Fleet information
        - historical_data: Historical travel data
        - trip_requests: Recent trip requests
        """
        # Ensure all required keys are present
        required_keys = [
            'current_schedules', 
            'demand_patterns', 
            'fleet_data', 
            'historical_data', 
            'trip_requests'
        ]
        for key in required_keys:
            if key not in optimization_data:
                raise ValueError(f"Missing required key: {key}")

        # Store all input data
        self.current_schedules = optimization_data['current_schedules']
        self.demand_patterns = optimization_data.get('demand_patterns', {})
        self.fleet_data = optimization_data.get('fleet_data', {})
        self.historical_data = optimization_data.get('historical_data', {})
        self.trip_requests = optimization_data.get('trip_requests', [])
        
        # Explicitly set current_fleet to ensure it exists
        self.current_fleet = self.fleet_data.get('current_fleet', {})
        
        # Determine peak hours
        self.peak_hours = set(self.demand_patterns.get('peak_hours', []))

    def _find_route(self, start, end):
        """Find route containing both start and end points"""
        for route_name, route_data in self.current_schedules.items():
            if start in route_data.get('stops', []) and end in route_data.get('stops', []):
                return route_name
        return None

    def _find_closest_departure(self, schedules, desired_time):
        """Find the closest departure time to the desired time"""
        closest_time = None
        min_diff = float('inf')
        
        for bus_schedules in schedules.values():
            for day_type, departure_times in bus_schedules.items():
                # Skip day type strings and ensure we're working with a list of times
                if not isinstance(departure_times, list):
                    continue
                
                for departure_time in departure_times:
                    try:
                        # Convert departure time to datetime for comparison
                        dep_time = datetime.strptime(str(departure_time), '%H:%M').time()
                        
                        # Calculate time difference
                        time_diff = abs(
                            (datetime.combine(datetime.today(), dep_time) - 
                             datetime.combine(datetime.today(), desired_time)).total_seconds()
                        )
                        
                        # Update closest time if this is closer
                        if time_diff < min_diff:
                            min_diff = time_diff
                            closest_time = dep_time
                    except ValueError:
                        # Skip times that can't be parsed
                        continue
        
        return closest_time

    def _generate_day_schedule(self, route, day_type):
        """Generate schedule for entire day based on demand patterns"""
        schedule = []
        operating_hours = range(5, 23)  # 5 AM to 10 PM

        for hour in operating_hours:
            route_demand = self.demand_patterns.get('route_patterns', {}).get(route, {}).get(hour, 0)
            
            # Adjust frequency based on demand
            base_frequency = 15 if hour in self.peak_hours else 30
            
            if route_demand > 0:
                demand_factor = min(route_demand / 50, 2)
                frequency = max(10, int(base_frequency / demand_factor))
            else:
                frequency = base_frequency
            
            # Generate departure times
            for minute in range(0, 60, frequency):
                schedule.append(f"{hour:02d}:{minute:02d}")
        
        return sorted(schedule)

    def _create_individual(self):
        """Create initial solution with fleet allocation and schedules"""
        individual = {
            'fleet': {},
            'schedules': defaultdict(dict),
            'fitness_metrics': {
                'waiting_time': 0,
                'utilization': 0,
                'peak_coverage': 0,
                'cost': 0
            }
        }

        for route, data in self.current_schedules.items():
            # Calculate optimal fleet size based on demand
            peak_demand = max(self.demand_patterns.get('route_patterns', {}).get(route, {}).values() or [0])
            
            # Use current fleet size or default to 1 if not found
            current_size = self.current_fleet.get(route, 1)
            
            # Suggest fleet size based on demand
            suggested_size = max(1, min(current_size + 1, int(peak_demand / 30)))
            individual['fleet'][route] = suggested_size

            # Generate optimized schedules
            for bus_id in range(suggested_size):
                # Ensure schedules are properly formatted
                bus_schedules = {}
                for day_type in ['weekdays', 'friday', 'weekends']:
                    bus_schedules[day_type] = self._generate_day_schedule(route, day_type)
                
                individual['schedules'][route][f"bus_{bus_id}"] = bus_schedules

        return individual

    def _calculate_fitness(self, individual):
        """Calculate fitness score based on multiple metrics"""
        metrics = {
            'waiting_time': self._evaluate_waiting_time(individual),
            'utilization': self._evaluate_bus_utilization(individual),
            'peak_coverage': self._evaluate_peak_coverage(individual),
            'cost': self._evaluate_cost_efficiency(individual)
        }
        
        # Add debug print to see actual values
        print("Fitness Metrics:", {k: f"{v:.2f}" for k, v in metrics.items()})
        
        individual['fitness_metrics'] = metrics
        
        # Weighted sum of metrics
        weights = {
            'waiting_time': 0.35,
            'utilization': 0.25,
            'peak_coverage': 0.25,
            'cost': 0.15
        }
        
        return sum(score * weights[metric] for metric, score in metrics.items())

    def _evaluate_waiting_time(self, individual):
        """Evaluate average passenger waiting time"""
        total_wait = 0
        request_count = 0
        
        for request in self.trip_requests:
            route = self._find_route(request.starting_point, request.destination)
            if route and route in individual['schedules']:
                desired_time = request.desired_time.time()
                closest_time = self._find_closest_departure(
                    individual['schedules'],
                    desired_time
                )
                
                if closest_time:
                    wait_time = abs((
                        datetime.combine(datetime.today(), closest_time) - 
                        datetime.combine(datetime.today(), desired_time)
                    ).total_seconds() / 60)
                    
                    total_wait += min(wait_time, 60)  # Cap at 60 minutes
                    request_count += 1
        
        return 1 - (total_wait / (request_count * 60)) if request_count > 0 else 0

    def _evaluate_bus_utilization(self, individual):
        try:
            utilization = 0
            total_routes = len(individual['fleet'])
            
            for route in individual['fleet']:
                fleet_size = individual['fleet'][route]
                
                # Calculate schedule count more carefully
                schedule_count = 0
                for bus in individual['schedules'][route].values():
                    for day_type, schedules in bus.items():
                        schedule_count += len(schedules)
                
                # Maximum possible trips: fleet size * number of day types * trips per day
                max_possible = fleet_size * 3 * 6  # 3 day types (weekdays, friday, weekends), 6 trips per day
                
                # Calculate utilization for this route
                route_utilization = min(1.0, schedule_count / max_possible) if max_possible > 0 else 0
                utilization += route_utilization
            
            # Average utilization across routes
            return utilization / total_routes if total_routes > 0 else 0
        
        except Exception as e:
            logging.error(f"Error in bus utilization calculation: {e}")
            return 0

    def _evaluate_peak_coverage(self, individual):
        """Evaluate coverage during peak hours"""
        peak_coverage = 0
        for route in individual['fleet']:
            peak_trips = 0
            total_peak_slots = len(self.peak_hours) * 4  # 4 slots per peak hour
            
            for bus in individual['schedules'][route].values():
                for schedule in bus.values():
                    peak_trips += sum(1 for time in schedule 
                                    if int(time.split(':')[0]) in self.peak_hours)
            
            peak_coverage += min(1, peak_trips / total_peak_slots)
        
        return peak_coverage / len(individual['fleet']) if individual['fleet'] else 0

    def _evaluate_cost_efficiency(self, individual):
        """Evaluate operational cost efficiency"""
        total_cost = 0
        max_cost = 0
        
        for route in individual['fleet']:
            current = self.current_fleet.get(route, 1)
            proposed = individual['fleet'][route]
            
            # Calculate cost based on fleet size difference
            cost_factor = abs(proposed - current) * 0.2
            total_cost += cost_factor
            max_cost += max(current, proposed)
        
        return 1 - (total_cost / max_cost) if max_cost > 0 else 0

    def _crossover(self, parent1, parent2):
        """Perform crossover between two parent solutions"""
        child = {
            'fleet': {},
            'schedules': defaultdict(dict)
        }
        
        for route in self.current_schedules:
            # Crossover fleet size
            if random.random() < 0.5:
                child['fleet'][route] = parent1['fleet'][route]
                child['schedules'][route] = parent1['schedules'][route].copy()
            else:
                child['fleet'][route] = parent2['fleet'][route]
                child['schedules'][route] = parent2['schedules'][route].copy()
        
        return child

    def _mutate(self, individual, mutation_rate):
        """Apply mutation to an individual"""
        if random.random() >= mutation_rate:
            return individual
        
        mutated = {
            'fleet': individual['fleet'].copy(),
            'schedules': defaultdict(dict)
        }
        
        # Select random route for mutation
        route = random.choice(list(self.current_schedules.keys()))
        
        # Mutate fleet size
        current_size = mutated['fleet'][route]
        mutated['fleet'][route] = max(1, current_size + random.choice([-1, 1]))
        
        # Regenerate schedules for mutated route
        for bus_id in range(mutated['fleet'][route]):
            mutated['schedules'][route][f"bus_{bus_id}"] = {
                'weekdays': self._generate_day_schedule(route, 'weekdays'),
                'friday': self._generate_day_schedule(route, 'friday'),
                'weekends': self._generate_day_schedule(route, 'weekends')
            }
        
        # Copy unchanged routes
        for r in self.current_schedules:
            if r != route:
                mutated['schedules'][r] = individual['schedules'][r].copy()
        
        return mutated

    def optimize(self, population_size=50, generations=30, mutation_rate=0.1):
        """Main optimization process"""
        logging.info("Starting optimization process")
        
        try:
            # Print out some debug information
            logging.info(f"Population Size: {population_size}")
            logging.info(f"Generations: {generations}")
            logging.info(f"Mutation Rate: {mutation_rate}")
            logging.info(f"Number of Routes: {len(self.current_schedules)}")
            logging.info(f"Current Fleet: {self.current_fleet}")
            logging.info(f"Number of Trip Requests: {len(self.trip_requests)}")
            
            # Initialize population
            population = [self._create_individual() for _ in range(population_size)]
            best_solution = None
            best_fitness = float('-inf')
            
            for generation in range(generations):
                # Evaluate fitness
                fitness_scores = [(ind, self._calculate_fitness(ind)) 
                                for ind in population]
                fitness_scores.sort(key=lambda x: x[1], reverse=True)
                
                # Update best solution
                if fitness_scores[0][1] > best_fitness:
                    best_fitness = fitness_scores[0][1]
                    best_solution = fitness_scores[0][0]
                
                # Selection and new population creation
                elite_size = max(2, population_size // 10)
                elite = [score[0] for score in fitness_scores[:elite_size]]
                new_population = elite.copy()
                
                while len(new_population) < population_size:
                    if random.random() < 0.7:  # 70% crossover
                        parents = random.sample(elite, 2)
                        child = self._crossover(parents[0], parents[1])
                    else:  # 30% mutation
                        parent = random.choice(elite)
                        child = self._mutate(parent, mutation_rate)
                    new_population.append(child)
                
                population = new_population
                
                # Log progress
                logging.info(f"Generation {generation}: Best fitness = {best_fitness}")
                
                # Early stopping if good solution found
                if best_fitness > 0.85:
                    logging.info(f"Good solution found at generation {generation}")
                    break

            return {
                'optimized_fleet': best_solution['fleet'],
                'optimized_schedules': best_solution['schedules'],
                'fitness_score': best_fitness,
                'fitness_metrics': best_solution['fitness_metrics']
            }
            
        except Exception as e:
            logging.error(f"Optimization error: {str(e)}")
            logging.error(traceback.format_exc())
            return None
        
def optimize_fleet_and_schedule(bus_data, trip_requests, current_fleet, population_size=50, generations=30, mutation_rate=0.1):
    """Main function to optimize fleet and schedule"""
    try:
        # Prepare optimization data
        optimization_data = {
            'current_schedules': bus_data,
            'demand_patterns': {
                'hourly_demand': {},
                'peak_hours': [],
                'route_patterns': {}
            },
            'fleet_data': {
                'current_fleet': current_fleet,
                'total_capacity': sum(current_fleet.values())
            },
            'historical_data': {},
            'trip_requests': trip_requests
        }

        # Process trip requests for demand patterns
        hourly_demand = defaultdict(int)
        route_patterns = defaultdict(lambda: defaultdict(int))

        for request in trip_requests:
            hour = request.desired_time.hour
            hourly_demand[hour] += 1

            # Find relevant route for the request
            for route_name, route_data in bus_data.items():
                if request.starting_point in route_data['stops'] and request.destination in route_data['stops']:
                    route_patterns[route_name][hour] += 1
                    break

        # Calculate peak hours (hours with demand > 120% of average)
        if hourly_demand:
            avg_demand = sum(hourly_demand.values()) / len(hourly_demand)
            peak_hours = [hour for hour, demand in hourly_demand.items() 
                    if demand > avg_demand * 1.2]
        else:
            peak_hours = []

        # Update optimization data with processed patterns
        optimization_data['demand_patterns'].update({
            'hourly_demand': dict(hourly_demand),
            'peak_hours': peak_hours,
            'route_patterns': {k: dict(v) for k, v in route_patterns.items()}
        })

        # Create optimizer instance with prepared data
        optimizer = BusScheduleOptimizer(optimization_data)

        # Run optimization
        return optimizer.optimize(population_size, generations, mutation_rate)

    except Exception as e:
        logging.error(f"Error in optimize_fleet_and_schedule: {str(e)}")
        logging.error(traceback.format_exc())
        return None