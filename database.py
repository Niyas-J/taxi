from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # e.g. Sedan, SUV, Auto
    price_per_km = db.Column(db.Float, nullable=False)
    base_fare = db.Column(db.Float, default=0.0)
    image_url = db.Column(db.String(200)) # Placeholder or path

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    vehicle_number = db.Column(db.String(50), nullable=False)
    photo_url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    # Safety Features
    agreement_accepted = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    complaint_count = db.Column(db.Integer, default=0)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    pickup_location = db.Column(db.String(200), nullable=False)
    drop_location = db.Column(db.String(200), nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    date_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending') # Pending, Confirmed, Completed, Cancelled
    special_notes = db.Column(db.Text)
    # Privacy & Safety
    privacy_mode = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=True) # Assigned driver

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Resolved, Dismissed
    date_time = db.Column(db.DateTime, default=datetime.utcnow)


def init_db(app):
    with app.app_context():
        db.create_all()
        
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('admin123') # Default password
            db.session.add(admin)
            
        # Add sample data if empty
        if not Vehicle.query.first():
            v1 = Vehicle(name="Maruti Dzire", type="Sedan", price_per_km=12, base_fare=50)
            v2 = Vehicle(name="Toyota Innova", type="SUV", price_per_km=18, base_fare=100)
            v3 = Vehicle(name="Bajaj Auto", type="Auto", price_per_km=8, base_fare=30)
            db.session.add_all([v1, v2, v3])
        
        if not Driver.query.first():
            d1 = Driver(name="Ramesh Kumar", phone="+919876543210", vehicle_number="KA-01-AB-1234", is_active=True)
            d2 = Driver(name="Suresh Singh", phone="+919876543211", vehicle_number="KA-02-CD-5678", is_active=True)
            db.session.add_all([d1, d2])

        db.session.commit()
