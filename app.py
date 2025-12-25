from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
# Import helper functions from new database.py
from database import (
    Booking, Driver, Vehicle, Complaint, User,
    get_all_vehicles, get_active_drivers, get_all_drivers, get_driver_by_phone, get_driver_by_id, update_driver,
    add_booking, get_all_bookings, update_booking_status, add_complaint, get_all_complaints
)
import urllib.parse
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Use a consistent secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Simple Admin User for Auth (ID=1)
# Password: admin123
ADMIN_PASS_HASH = generate_password_hash('admin123')

@login_manager.user_loader
def load_user(user_id):
    if user_id == '1':
        return User(id=1, username='admin', password_hash=ADMIN_PASS_HASH)
    return None

# --- Public Routes ---

@app.route('/')
def index():
    vehicles = get_all_vehicles()
    active_drivers = get_active_drivers()
    return render_template('index.html', vehicles=vehicles, active_drivers=active_drivers)

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        pickup = request.form.get('pickup')
        drop = request.form.get('drop')
        date_str = request.form.get('date') 
        vehicle_type = request.form.get('vehicle')
        privacy_mode = True if request.form.get('privacy_mode') else False
        
        # Format Date
        try:
             # Just store as object or string for Firestore
             if date_str:
                 date_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
             else:
                 date_obj = datetime.now()
        except ValueError:
            date_obj = datetime.now()

        booking_data = {
            'customer_name': name,
            'phone': phone,
            'pickup_location': pickup,
            'drop_location': drop,
            'vehicle_type': vehicle_type,
            'date_time': date_obj, # Firestore handles datetime
            'status': 'Pending',
            'privacy_mode': privacy_mode,
            'special_notes': '',
            'is_completed': False
        }
        
        add_booking(booking_data)

        # WhatsApp Integration
        msg = f"New Booking Request!\nName: {name}\nFrom: {pickup}\nTo: {drop}\nVehicle: {vehicle_type}\nTime: {date_str}"
        if privacy_mode:
            msg = f"🔒 PRIVACY MODE REQUESTED\n" + msg + "\n(Driver: Do not ask personal questions. Minimal interaction.)"
        
        phone_number = "919876543210" 
        encoded_msg = urllib.parse.quote(msg)
        wa_link = f"https://wa.me/{phone_number}?text={encoded_msg}"
        
        if 'whatsapp' in request.form:
             return redirect(wa_link)
        
        flash('Booking submitted successfully! We will call you shortly.', 'success')
        return redirect(url_for('index'))

    vehicles = get_all_vehicles()
    return render_template('book.html', vehicles=vehicles)

@app.route('/vehicles')
def vehicles():
    vehicles = get_all_vehicles()
    return render_template('vehicles.html', vehicles=vehicles)

@app.route('/drivers')
def drivers():
    drivers = get_active_drivers()
    return render_template('drivers.html', drivers=drivers)

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/driver-agreement', methods=['GET', 'POST'])
def driver_agreement():
    if request.method == 'GET':
        return render_template('driver_agreement.html')
    return redirect(url_for('index')) 

@app.route('/driver-agreement/submit', methods=['POST'])
def driver_agreement_submit():
    phone = request.form.get('driver_phone')
    driver = get_driver_by_phone(phone)
    if driver:
        update_driver(driver.id, {'agreement_accepted': True})
        flash('Thank you for pledging to safety!', 'success')
    else:
        # For prototype, maybe auto-create driver? Or just fail.
        flash('Driver number not found. Please contact admin.', 'error')
    return redirect(url_for('index'))

@app.route('/report', methods=['GET', 'POST'])
def report_issue():
    if request.method == 'GET':
        drivers = get_all_drivers()
        return render_template('report.html', drivers=drivers)
    return redirect(url_for('index'))

@app.route('/report/submit', methods=['POST'])
def submit_complaint():
    driver_id = request.form.get('driver_id')
    reason_type = request.form.get('reason_type')
    details = request.form.get('details')
    full_reason = f"{reason_type}: {details}"

    complaint_data = {
        'driver_id': driver_id,
        'reason': full_reason,
        'status': 'Pending',
        'date_time': datetime.now()
    }
    add_complaint(complaint_data)
    
    # Auto-ban logic
    driver = get_driver_by_id(driver_id)
    if driver:
        new_count = driver.complaint_count + 1
        updates = {'complaint_count': new_count}
        if new_count >= 3:
            updates['is_banned'] = True
            updates['is_active'] = False
            flash('Complaint recorded. Driver has been auto-banned due to repeated complaints.', 'warning')
        else:
             flash('Complaint submitted successfully. We will take action.', 'success')
        update_driver(driver_id, updates)
    
    return redirect(url_for('index'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

# --- Admin Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Check against single admin
        if username == 'admin' and check_password_hash(ADMIN_PASS_HASH, password):
            user = User(id=1, username='admin', password_hash=ADMIN_PASS_HASH)
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    bookings = get_all_bookings()
    drivers = get_all_drivers()
    complaints = get_all_complaints()
    return render_template('admin.html', bookings=bookings, drivers=drivers, complaints=complaints)

@app.route('/admin/driver/<id>/toggle-ban', methods=['POST'])
@login_required
def toggle_ban(id):
    driver = get_driver_by_id(id)
    if driver:
        new_ban_status = not driver.is_banned
        updates = {
            'is_banned': new_ban_status,
            'is_active': False if new_ban_status else True
        }
        update_driver(id, updates)
        status = "Banned" if new_ban_status else "Unbanned"
        flash(f"Driver {driver.name} has been {status}.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/booking/<id>/status', methods=['POST'])
@login_required
def update_booking_status_route(id):
    new_status = request.form.get('status')
    if new_status:
        update_booking_status(id, new_status)
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
