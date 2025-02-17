from app import app, db, Route, Stop, Bus, Schedule
from datetime import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def seed_database():
    with app.app_context():
        try:
            logging.info("Starting database seeding...")

            # Clear existing data
            logging.info("Clearing existing data...")
            db.drop_all()
            db.create_all()

            # Define routes and their stops
            routes_data = {
            'A': {
                'name': 'Route A',
                'stops': ['Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Hentian Anggerik', 'Hentian Perindu', 'Hentian Seroja',
                          'Hentian FSKM', 'Hentian FKPM (MASCOM)', 'Hentian Mawar (DC)']
            },
            'B': {
                'name': 'Route B',
                'stops': ['Hentian Baiduri', 'Hentian Unisel', 'Hentian Balai Polis Seksyen 6', 'Hentian Bas Seksyen 2', 'Hentian FSKM', 
                          'Hentian FKPM (MASCOM)', 'Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Hentian Anggerik', 'Hentian Perindu', 
                          'Hentian Seroja', 'Hentian Baiduri', 'Hentian Unisel', 'Hentian Balai Polis Seksyen 6', 'Hentian Bas Seksyen 2']
            },
            'C': {
                'name': 'Route C',
                'stops': ['Hentian Pusat Komersial Sek.7', 'Hentian Flat PKNS', 'Hentian Masjid Jalan Kristal', 
                          'Hentian Palpero', 'Hentian Tasik', 'Hentian Hospital Shah Alam', 'Hentian Anggerik', 
                          'Hentian Perindu', 'Hentian Seroja', 'Hentian FSKM', 'Hentian FKPM (MASCOM)', 
                          'Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Hentian Pusat Komersial Sek.7', 
                          'Hentian Flat PKNS', 'Hentian Masjid Jalan Kristal', 'Hentian Palpero', 'Hentian Tasik',
                          'Hentian Hospital Shah Alam']
            },
            'D': {
                'name': 'Route D',
                'stops': ['Dataran Bas I-SOHO', 'Hentian Masjid Jalan Kristal', 'Hentian Palpero', 'Hentian Tasik', 
                          'Hentian Hospital Shah Alam', 'Hentian Anggerik', 'Hentian Perindu', 'Hentian Seroja', 'Hentian FSKM',
                          'Hentian FKPM (MASCOM)', 'Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Hentian Pusat Komersial Sek.7',
                          'Dataran Bas I-SOHO']
            },
            'E': {
                'name': 'Route E',
                'stops': ['Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Hentian Anggerik', 'Hentian Perindu', 'Hentian Seroja', 
                          'Hentian Bas Seksyen 2', 'INTEC Sek 17', 'Hentian Bas Seksyen 2', 'Hentian FSKM','Hentian FKPM (MASCOM)', 
                          'Hentian Mawar (DC)']
            },
            'F': {
                'name': 'Route F',
                'stops': ['Apart. Palm Garden (B. B. KLANG)', 'Hentian Anggerik', 'Hentian Perindu', 'Hentian Seroja', 'Hentian FSKM',
                          'Hentian FKPM (MASCOM)', 'Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Apart. Palm Garden (B. B. KLANG)']
            },
            'G': {
                'name': 'Route G',
                'stops': ['Hentian Suria Jaya', 'Hentian KTM Padang Jawa', 'Hentian Ken Rimba', 'Hentian Anggerik',
                          'Hentian Perindu', 'Hentian Seroja', 'Hentian FSKM', 'Hentian FKPM (MASCOM)', 
                          'Hentian Mawar (DC)', 'Hentian Pusat Kesihatan (PK)', 'Hentian Suria Jaya', 'Hentian KTM Padang Jawa',
                          'Hentian Ken Rimba']
            },
        }

            # Add routes and stops to the database
            logging.info("Adding routes and stops...")
            for route_key, route_info in routes_data.items():
                route = Route(name=route_info['name'])
                db.session.add(route)
                db.session.flush()  # Flush to get the route ID

                for stop_name in route_info['stops']:
                    stop = Stop(name=stop_name, route_id=route.id)
                    db.session.add(stop)

            # Commit changes
            logging.info("Committing changes...")
            db.session.commit()

            # Define bus schedules
            schedules = {
            'A': {
                'Bus 1': {
                    'weekdays': ['07:00', '07:15', '07:30', '07:45', '08:00', '08:15', '08:30', '09:00',
                                 '11:30', '12:45', '13:45', '16:30', '17:30', '20:00', '21:00'],
                    'friday': ['07:00', '07:15', '07:30', '08:00', '08:15', '08:30', '09:00','11:30', '14:30',
                                '16:30', '17:30', '20:00', '21:00'],
                    'weekends': [],
                },
                'Bus 2': {
                    'weekdays': ['07:00', '07:15', '07:30', '07:45', '08:00', '08:15', '08:30', '09:00',
                                 '12:00', '13:00', '14:00', '16:45', '17:45', '20:15', '21:30'],
                    'friday': ['07:00', '07:15', '07:30', '08:00', '08:15', '08:30', '09:00','11:45', '14:45',
                                '16:45', '17:45', '20:15', '21:30'],
                    'weekends': [],
                },
                'Bus 3': {
                    'weekdays': ['07:00', '07:15', '07:30', '07:45', '08:00', '08:15', '08:30', '09:00',
                                 '12:15', '13:15', '14:15', '17:00', '18:00', '20:30', '22:00'],
                    'friday': ['07:00', '07:15', '07:30', '08:00', '08:15', '08:30', '09:00','12:00', '15:00',
                                '17:00', '18:00', '20:30', '22:00'],
                    'weekends': [],
                },
                'Bus 4': {
                    'weekdays': ['07:00', '07:15', '07:30', '07:45', '08:00', '08:15', '08:30', '09:00',
                                 '12:30', '13:30', '14:30', '17:15', '18:30', '20:45', '22:30'],
                    'friday': ['07:00', '07:15', '07:30', '08:00', '08:15', '08:30', '09:00','12:15', '15:15',
                                '17:15', '18:30', '20:45', '22:30'],
                    'weekends': [],
                }
            },
            'B': {
                'Bus 1': {
                    'weekdays': ['07:00', '08:15', '09:00', '11:30', '12:40', '14:00', '17:00', '18:00', '20:00', '21:30'],
                    'friday': ['07:00', '08:15', '09:00', '11:30', '14:30', '17:00', '18:00','20:00', '21:30'],
                    'weekends': ['07:00', '08:15', '09:00', '11:30', '12:40', '14:00', '17:00', '18:00'],
                },
                'Bus 2': {
                    'weekdays': ['07:30', '08:35', '09:30', '07:45', '12:00', '13:20', '14:30', '17:30',
                                 '18:30', '21:00', '22:30'],
                    'friday': ['07:30', '08:35', '09:30', '12:00', '14:30', '17:30', '18:30','21:00', '22:30'],
                    'weekends': ['07:30', '08:35', '09:30', '12:00', '13:20', '14:30', '17:30', '18:30'],
                },
            },
            'C': {
                'Bus 1': {
                    'weekdays': ['07:00', '08:00', '11:30', '12:45', '13:45', '16:30', '17:30', '20:00', '21:00'],
                    'friday': ['07:00', '08:00', '11:15', '14:30', '16:30', '17:30', '20:00','21:00'],
                    'weekends': ['07:00', '08:15', '09:00', '11:30', '12:40', '14:00', '17:00', '18:00'],
                },
                'Bus 2': {
                    'weekdays': ['07:15', '08:15', '12:00', '13:00', '14:00', '16:45', '17:45', '20:15', '21:30'],
                    'friday': ['07:15', '08:15', '11:30', '14:30', '16:45', '17:45','20:15', '21:30'],
                    'weekends': ['07:30', '08:35', '09:30', '12:00', '13:20', '14:30', '17:30', '18:30'],
                },
                'Bus 3': {
                    'weekdays': ['07:30', '08:30', '12:15', '13:15', '14:15', '17:00', '18:00', '20:30', '22:00'],
                    'friday': ['07:30', '08:30', '11:45', '15:00', '17:00', '18:00','20:30', '22:00'],
                    'weekends': [],
                },
                'Bus 4': {
                    'weekdays': ['07:45',  '09:00', '12:30', '13:30', '14:30', '17:15', '18:30', '20:45', '22:30'],
                    'friday': ['07:45', '09:00', '12:00', '15:30', '17:15', '18:30','20:45', '22:30'],
                'weekends': [],
                },  
            },
            'D': {
                'Bus 1': {
                    'weekdays': ['07:00', '08:15', '09:00', '12:00', '13:00', '14:00', '17:00', '18:00', '20:00', '21:30'],
                    'friday': ['07:00', '08:15', '09:00', '11:30', '14:30', '17:00', '18:00', '20:00','21:30'],
                    'weekends': [],
                },
                'Bus 2': {
                    'weekdays': ['07:30', '08:35', '09:30', '12:30', '13:30', '14:30', '17:30', '18:30', '21:00', '22:30'],
                    'friday': ['07:30', '08:35', '09:30', '12:00', '14:30', '17:30', '18:30', '21:00', '22:30'],
                    'weekends': [],
                },
            },
            'E': {
                'Bus 1': {
                    'weekdays': ['07:00', '08:15', '09:00', '12:00', '13:00', '14:00', '17:00', '18:00', '20:00', '21:30'],
                    'friday': ['07:00', '08:15', '09:00', '11:30', '14:30', '17:00', '18:00', '20:00','21:30'],
                    'weekends': [],
                },
                'Bus 2': {
                    'weekdays': ['07:30', '08:35', '09:30', '12:30', '13:30', '14:30', '17:30', '18:30', '21:00', '22:30'],
                    'friday': ['07:30', '08:35', '09:30', '12:00', '15:00', '17:30', '18:30', '21:00', '22:30'],
                    'weekends': [],
                },
            },
            'F': {
                'Bus 1': {
                    'weekdays': ['07:00', '08:15', '09:00', '12:00', '13:00', '14:00', '17:00', '18:00', '20:00', '21:30'],
                    'friday': ['07:00', '08:15', '09:00', '11:30', '14:30', '17:00', '18:00', '20:00','21:30'],
                    'weekends': [],
                },
                'Bus 2': {
                    'weekdays': ['07:30', '08:35', '09:30', '12:30', '13:30', '14:30', '17:30', '18:30', '21:00', '22:30'],
                    'friday': ['07:30', '08:35', '09:30', '12:00', '14:30', '17:30', '18:30', '21:00', '22:30'],
                    'weekends': [],
                },
            },
            'G': {
                'Bus 1': {
                    'weekdays': ['07:00', '08:30', '11:30', '13:20', '16:00', '17:30', '20:00', '21:30'],
                    'friday': ['07:00', '08:30', '11:00', '14:30', '16:00', '17:30', '18:00', '20:00','21:30'],
                    'weekends': [],
                },
                'Bus 2': {
                    'weekdays': ['07:30', '09:00', '12:00', '13:50', '16:30', '18:00', '20:30', '22:00'],
                    'friday': ['07:30', '09:00', '11:30', '14:30', '16:30', '18:00', '20:30', '22:00'],
                    'weekends': [],
                },
                'Bus 3': {
                    'weekdays': ['08:00', '09:30', '12:30', '14:30', '17:00', '18:30', '21:00', '22:30'],
                    'friday': ['08:00', '09:30', '12:00', '15:00', '17:00', '18:30', '21:00', '22:30'],
                    'weekends': [],
                },
            },
        }

            # Add buses and schedules
            logging.info("Adding buses and schedules...")
            for route_key, buses in schedules.items():
                route = Route.query.filter_by(name=f'Route {route_key}').first()
                if route:
                    for bus_name, schedule in buses.items():
                        bus = Bus(name=bus_name, route_id=route.id)
                        db.session.add(bus)
                        db.session.flush()

                        for day_type, times in schedule.items():
                            for t in times:
                                schedule_entry = Schedule(bus_id=bus.id, day_type=day_type, departure_time=time.fromisoformat(t))
                                db.session.add(schedule_entry)

            # Final commit
            logging.info("Committing final changes...")
            db.session.commit()

            # Verify seeded data
            logging.info("Verifying seeded data...")
            routes = Route.query.all()
            stops = Stop.query.all()
            buses = Bus.query.all()
            schedules = Schedule.query.all()
            logging.info(f"Seeded {len(routes)} routes, {len(stops)} stops, {len(buses)} buses, and {len(schedules)} schedules.")

            for route in routes:
                logging.info(f"Route {route.name}: {len(route.stops)} stops, {len(route.buses)} buses")

            logging.info("Database seeding complete.")

        except Exception as e:
            logging.error(f"An error occurred during database seeding: {str(e)}")
            db.session.rollback()
        finally:
            db.session.close()

if __name__ == "__main__":
    seed_database()
                  