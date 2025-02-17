import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, db, Admin, Driver, Route
from werkzeug.security import generate_password_hash
from datetime import datetime

def manage_users():
    with app.app_context():
        while True:
            print("\nUser Management System")
            print("-" * 50)
            print("1. View Users")
            print("2. Add New User")
            print("3. Delete User")
            print("4. Exit")
            
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == '1':
                view_users()
            elif choice == '2':
                add_new_user()
            elif choice == '3':
                delete_user()
            elif choice == '4':
                print("Exiting...")
                break
            else:
                print("Invalid choice. Please try again.")

def view_users():
    print("\nAdmin Accounts")
    print("=" * 120)
    admins = Admin.query.all()
    print(f"{'ID':<5} | {'Username':<15} | {'Name':<20} | {'Email':<25} | {'Role':<15} | {'Last Login':<20}")
    print("-" * 120)
    
    for admin in admins:
        last_login = admin.last_login.strftime('%Y-%m-%d %H:%M') if admin.last_login else 'Never'
        print(f"{admin.id:<5} | {admin.username:<15} | {admin.name or 'N/A':<20} | {admin.email or 'N/A':<25} | {admin.role:<15} | {last_login:<20}")
    print("-" * 120)
    
    print("\nDriver Accounts")
    print("=" * 120)
    drivers = Driver.query.all()
    print(f"{'ID':<5} | {'Name':<20} | {'Phone':<15} | {'Email':<25} | {'License':<15} | {'Route':<15}")
    print("-" * 120)
    
    for driver in drivers:
        route_name = driver.route.name if driver.route else 'Unassigned'
        print(f"{driver.id:<5} | {driver.name:<20} | {driver.phone:<15} | {driver.email:<25} | {driver.license_number:<15} | {route_name:<15}")
    print("-" * 120)
    print()

def add_new_user():
    print("\nAdd New User")
    print("-" * 50)
    
    user_type = input("Enter user type (admin/driver): ").lower().strip()
    
    if user_type == 'admin':
        add_admin()
    elif user_type == 'driver':
        add_driver()
    else:
        print("Invalid user type. Please enter 'admin' or 'driver'.")

def add_admin():
    username = input("Enter username: ").strip()
    if not username or Admin.query.filter_by(username=username).first():
        print(f"Error: Username empty or already exists!")
        return
        
    password = input("Enter password: ").strip()
    if not password or password != input("Confirm password: ").strip():
        print("Error: Invalid password or passwords don't match!")
        return
        
    name = input("Enter full name: ").strip()
    email = input("Enter email: ").strip()
    phone = input("Enter phone number: ").strip()
    
    try:
        new_admin = Admin(
            username=username,
            password=generate_password_hash(password),
            name=name,
            email=email,
            phone=phone,
            role='Administrator',
            credentials_updated_at=datetime.now()
        )
        db.session.add(new_admin)
        db.session.commit()
        print(f"\nSuccess: Admin '{username}' created successfully!")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin: {str(e)}")

def add_driver():
    # Get login credentials
    username = input("Enter username: ").strip()
    if not username or Driver.query.filter_by(username=username).first():
        print(f"Error: Username empty or already exists!")
        return
        
    password = input("Enter password: ").strip()
    if not password or password != input("Confirm password: ").strip():
        print("Error: Invalid password or passwords don't match!")
        return

    # Get driver details    
    name = input("Enter full name: ").strip()
    if not name:
        print("Error: Name cannot be empty")
        return
        
    phone = input("Enter phone number: ").strip()
    email = input("Enter email: ").strip()
    license_number = input("Enter license number: ").strip()
    
    # Get route assignment
    routes = Route.query.all()
    if routes:
        print("\nAvailable Routes:")
        for route in routes:
            print(f"ID: {route.id}, Name: {route.name}")
        route_id = input("Enter route ID (or press Enter to skip): ").strip()
        route_id = int(route_id) if route_id else None
    else:
        print("No routes available.")
        route_id = None
    
    try:
        new_driver = Driver(
            username=username,
            password=generate_password_hash(password),
            name=name,
            phone=phone,
            email=email,
            license_number=license_number,
            route_id=route_id,
            credentials_updated_at=datetime.now()
        )
        db.session.add(new_driver)
        db.session.commit()
        print(f"\nSuccess: Driver account for '{username}' created successfully!")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating driver account: {str(e)}")

def delete_user():
    print("\nDelete User")
    print("-" * 50)
    print("1. Delete Admin")
    print("2. Delete Driver")
    print("3. Back to Main Menu")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        delete_admin()
    elif choice == '2':
        delete_driver()
    elif choice == '3':
        return
    else:
        print("Invalid choice. Please try again.")

def delete_admin():
    print("\nDeleting Admin Account")
    print("-" * 50)
    
    # Get all admins except the default admin
    admins = Admin.query.filter(Admin.username != 'admin').all()
    
    if not admins:
        print("No additional admin accounts found.")
        return
        
    print("\nCurrent Admins:")
    print("-" * 80)
    print(f"{'ID':<5} | {'Username':<15} | {'Name':<20} | {'Email':<25}")
    print("-" * 80)
    
    for admin in admins:
        print(f"{admin.id:<5} | {admin.username:<15} | {admin.name or 'N/A':<20} | {admin.email or 'N/A':<25}")
    
    try:
        admin_id = input("\nEnter admin ID to delete (or 'q' to quit): ").strip()
        if admin_id.lower() == 'q':
            return
            
        admin_id = int(admin_id)
        admin = Admin.query.get(admin_id)
        
        if not admin:
            print(f"Error: No admin found with ID {admin_id}")
            return
            
        if admin.username == 'admin':
            print("Error: Cannot delete the default admin account")
            return
            
        confirm = input(f"\nAre you sure you want to delete admin '{admin.username}'? (y/n): ").lower()
        if confirm != 'y':
            print("Deletion cancelled.")
            return
        
        db.session.delete(admin)
        db.session.commit()
        print(f"\nSuccess: Admin '{admin.username}' deleted successfully!")
        
    except ValueError:
        print("Error: Please enter a valid ID number")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting admin: {str(e)}")

def delete_driver():
    print("\nDeleting Driver Account")
    print("-" * 50)
    
    drivers = Driver.query.all()
    if not drivers:
        print("No drivers found.")
        return
        
    print("\nCurrent Drivers:")
    print("-" * 100)
    print(f"{'ID':<5} | {'Name':<20} | {'Phone':<15} | {'Email':<25} | {'Route':<15}")
    print("-" * 100)
    
    for driver in drivers:
        route_name = driver.route.name if driver.route else 'Unassigned'
        print(f"{driver.id:<5} | {driver.name:<20} | {driver.phone:<15} | {driver.email:<25} | {route_name:<15}")
    
    try:
        driver_id = input("\nEnter driver ID to delete (or 'q' to quit): ").strip()
        if driver_id.lower() == 'q':
            return
            
        driver_id = int(driver_id)
        driver = Driver.query.get(driver_id)
        
        if not driver:
            print(f"Error: No driver found with ID {driver_id}")
            return
            
        confirm = input(f"\nAre you sure you want to delete driver '{driver.name}'? (y/n): ").lower()
        if confirm != 'y':
            print("Deletion cancelled.")
            return
        
        db.session.delete(driver)
        db.session.commit()
        print(f"\nSuccess: Driver '{driver.name}' deleted successfully!")
        
    except ValueError:
        print("Error: Please enter a valid ID number")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting driver: {str(e)}")

if __name__ == "__main__":
    manage_users()