from app import app, db, Stop

def update_stop_coordinates():
    with app.app_context():
        # Define default coordinates for different areas in Shah Alam
        default_coordinates = [
            {'latitude': 3.0733, 'longitude': 101.5185},  # Shah Alam City Centre
            {'latitude': 3.0697, 'longitude': 101.5107},  # Section 7
            {'latitude': 3.0611, 'longitude': 101.5236},  # Section 13
            {'latitude': 3.0808, 'longitude': 101.5296},  # Section 2
            {'latitude': 3.0732, 'longitude': 101.5002},  # Section 9
            {'latitude': 3.0645, 'longitude': 101.4926}   # Section 17
        ]
        
        try:
            # Get all stops
            stops = Stop.query.all()
            
            print(f"Found {len(stops)} stops to update")
            
            # Update each stop with coordinates
            for i, stop in enumerate(stops):
                # Use modulo to cycle through the coordinate list
                coord = default_coordinates[i % len(default_coordinates)]
                
                # Add a small offset to avoid all stops being in the exact same location
                offset = i * 0.0005  # Small offset for each stop
                stop.latitude = coord['latitude'] + offset
                stop.longitude = coord['longitude'] + offset
                
                print(f"Updated stop '{stop.name}' with coordinates: ({stop.latitude}, {stop.longitude})")
            
            # Commit the changes
            db.session.commit()
            print("\nSuccessfully updated coordinates for all stops")
            
        except Exception as e:
            print(f"Error updating coordinates: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    update_stop_coordinates()