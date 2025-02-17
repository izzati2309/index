import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, db

def migrate_driver_table():
    with app.app_context():
        try:
            # Drop existing Driver table
            db.engine.execute('DROP TABLE IF EXISTS driver')
            
            # Recreate tables
            db.create_all()
            
            print("Migration completed successfully. Driver table has been updated with new columns.")
            
        except Exception as e:
            print(f"Error during migration: {str(e)}")

def migrate_tables():
    with app.app_context():
        try:
            # Drop existing tables
            db.engine.execute('DROP TABLE IF EXISTS driver')
            db.engine.execute('DROP TABLE IF EXISTS admin')
            
            # Recreate tables
            db.create_all()
            
            # Add password handling for admin accounts
            from app import Admin
            from werkzeug.security import generate_password_hash
            
            admins = Admin.query.all()
            for admin in admins:
                if admin.password is None:
                    admin.password = generate_password_hash('password')  # Set default password
                    db.session.add(admin)
            
            db.session.commit()
            
            print("Migration completed successfully. Tables have been updated with new columns and constraints.")
            
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            db.session.rollback()

def migrate_admin_table():
    with app.app_context():
        try:
            # Create tables if they don't exist
            db.create_all()
            
            # Get all admins and ensure they have a password
            from app import Admin
            from werkzeug.security import generate_password_hash
            
            admins = Admin.query.all()
            for admin in admins:
                if admin.password is None:
                    admin.password = generate_password_hash('password')  # Set default password
                    db.session.add(admin)
            
            db.session.commit()
            print("Admin table migration completed successfully")
            
        except Exception as e:
            print(f"Error during admin table migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    migrate_driver_table()
    migrate_tables()
    migrate_admin_table()