import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from datetime import datetime

# Initialize Firebase
# Expects 'FIREBASE_CREDENTIALS' env var to be the JSON content of the service account
cred_json = os.environ.get('FIREBASE_CREDENTIALS')
if cred_json:
    try:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db_client = firestore.client()
        print("Firebase initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        db_client = None
else:
    print("WARNING: FIREBASE_CREDENTIALS env var not found. Database operations will fail.")
    db_client = None

# --- Wrapper Classes for Compatibility ---
# These mimic the SQLAlchemy models so app.py needs fewer changes.

class Booking:
    def __init__(self, id, customer_name, phone, pickup_location, drop_location, vehicle_type, date_time, status='Pending', special_notes=None, privacy_mode=False, is_completed=False, driver_id=None):
        self.id = id
        self.customer_name = customer_name
        self.phone = phone
        self.pickup_location = pickup_location
        self.drop_location = drop_location
        self.vehicle_type = vehicle_type
        self.date_time = date_time
        self.status = status
        self.special_notes = special_notes
        self.privacy_mode = privacy_mode
        self.is_completed = is_completed
        self.driver_id = driver_id

class Driver:
    def __init__(self, id, name, phone, vehicle_number, photo_url=None, is_active=True, agreement_accepted=False, is_banned=False, complaint_count=0):
        self.id = id
        self.name = name
        self.phone = phone
        self.vehicle_number = vehicle_number
        self.photo_url = photo_url
        self.is_active = is_active
        self.agreement_accepted = agreement_accepted
        self.is_banned = is_banned
        self.complaint_count = complaint_count

class Vehicle:
    def __init__(self, name, type, price_per_km, base_fare, image_url=None):
        self.name = name
        self.type = type
        self.price_per_km = price_per_km
        self.base_fare = base_fare
        self.image_url = image_url

class Complaint:
    def __init__(self, id, driver_id, reason, status='Pending', date_time=None, booking_id=None):
        self.id = id
        self.driver_id = driver_id
        self.reason = reason
        self.status = status
        self.date_time = date_time
        self.booking_id = booking_id

class User: # For Admin Auth
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    
    @property
    def is_authenticated(self):
        return True
    @property
    def is_active(self):
        return True
    @property
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.id)


# --- Helper Functions ---

def get_all_vehicles():
    # Hardcoding vehicles for simplicity as they don't change often, or fetch from Firestore 'vehicles' collection
    # Return list of Vehicle objects
    return [
        Vehicle("Maruti Dzire", "Sedan", 12, 50),
        Vehicle("Toyota Innova", "SUV", 18, 100),
        Vehicle("Bajaj Auto", "Auto", 8, 30)
    ]

def get_active_drivers():
    if not db_client: return []
    docs = db_client.collection('drivers').where('is_active', '==', True).where('is_banned', '==', False).stream()
    drivers = []
    for doc in docs:
        d = doc.to_dict()
        drivers.append(Driver(id=doc.id, **d))
    return drivers

def get_all_drivers():
    if not db_client: return []
    docs = db_client.collection('drivers').stream()
    drivers = []
    for doc in docs:
        d = doc.to_dict()
        drivers.append(Driver(id=doc.id, **d))
    return drivers

def get_driver_by_phone(phone):
    if not db_client: return None
    docs = db_client.collection('drivers').where('phone', '==', phone).stream()
    for doc in docs:
        return Driver(id=doc.id, **doc.to_dict())
    return None

def get_driver_by_id(driver_id):
    if not db_client: return None
    doc = db_client.collection('drivers').document(str(driver_id)).get()
    if doc.exists:
        return Driver(id=doc.id, **doc.to_dict())
    return None

def update_driver(driver_id, data):
    if not db_client: return
    db_client.collection('drivers').document(str(driver_id)).update(data)

def add_booking(data):
    if not db_client: return
    # Transform datetime to string or timestamp for Firestore
    # Here keeping it simple
    db_client.collection('bookings').add(data)

def get_all_bookings():
    if not db_client: return []
    docs = db_client.collection('bookings').order_by('date_time', direction=firestore.Query.DESCENDING).stream()
    bookings = []
    for doc in docs:
        d = doc.to_dict()
        # Convert timestamp back to datetime if needed, or handle in template
        # Assuming we store it as string or generic
        # For this prototype, let's assume 'date_time' is stored compatible
        bookings.append(Booking(id=doc.id, **d))
    return bookings

def update_booking_status(booking_id, status):
    if not db_client: return
    db_client.collection('bookings').document(str(booking_id)).update({'status': status})

def add_complaint(data):
    if not db_client: return
    db_client.collection('complaints').add(data)

def get_all_complaints():
    if not db_client: return []
    docs = db_client.collection('complaints').order_by('date_time', direction=firestore.Query.DESCENDING).stream()
    complaints = []
    for doc in docs:
        d = doc.to_dict()
        complaints.append(Complaint(id=doc.id, **d))
    return complaints


# --- Admin ---
# Using a simple hardcoded admin for this layer, or fetch from 'users' collection
from werkzeug.security import generate_password_hash, check_password_hash
# Admin: admin / admin123
ADMIN_HASH = "scrypt:32768:8:1$..." # Placeholder, we'll use a simple check in app.py or fetch from DB
# Actually let's just stick to the simple check_password which app.py uses.
# We'll create a dummy User object 
