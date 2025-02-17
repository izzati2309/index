from app import app, Route, Bus, Schedule

def view_schedules():
    with app.app_context():
        print("\nUBUS Schedule Database")
        print("=" * 100)
        
        # Get all routes
        routes = Route.query.order_by(Route.name).all()
        
        for route in routes:
            print(f"\nRoute: {route.name}")
            print("-" * 100)
            print(f"{'Bus':<15} | {'Day Type':<15} | {'Time':<10}")
            print("-" * 100)
            
            buses = Bus.query.filter_by(route_id=route.id).order_by(Bus.name).all()
            
            for bus in buses:
                schedules = Schedule.query.filter_by(bus_id=bus.id)\
                    .order_by(Schedule.day_type, Schedule.departure_time).all()
                
                if schedules:
                    for schedule in schedules:
                        print(f"{bus.name:<15} | {schedule.day_type:<15} | {schedule.departure_time.strftime('%H:%M')}")
            
            print("-" * 100)
            print()

if __name__ == "__main__":
    print("\nViewing Database Contents...")
    view_schedules()