import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, db, Admin, Driver
from werkzeug.security import check_password_hash

def verify_credentials():
    with app.app_context():
        print("\nVerifying Admin Accounts:")
        print("-" * 50)
        admins = Admin.query.all()
        
        if not admins:
            print("No admin accounts found in database.")
        else:
            for admin in admins:
                print(f"Username: {admin.username}")
                print(f"Role: {admin.role}")
                print(f"Name: {admin.name}")
                print(f"Email: {admin.email}")
                print("-" * 30)
        
        print("\nVerifying Driver Accounts:")
        print("-" * 50)
        drivers = Driver.query.all()
        
        if not drivers:
            print("No driver accounts found in database.")
        else:
            for driver in drivers:
                print(f"Username: {driver.username}")
                print(f"Name: {driver.name}")
                print(f"Email: {driver.email}")
                print("-" * 30)

if __name__ == "__main__":
    verify_credentials()