from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from database import db, init_db, User, Vehicle, Driver, Booking, Complaint
import urllib.parse
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taxi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Public Routes ---

@app.route('/')
def index():
    vehicles = Vehicle.query.all()
    drivers = Driver.query.filter_by(is_active=True, is_banned=False).all()
    return render_template('index.html', vehicles=vehicles, active_drivers=drivers)

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        pickup = request.form.get('pickup')
        drop = request.form.get('drop')
        date_str = request.form.get('date') # Expected format from HTML date-local input
        vehicle_type = request.form.get('vehicle')
        privacy_mode = True if request.form.get('privacy_mode') else False
        
        # Save to DB
        try:
            date_time = datetime.strptime(date_str, '%Y-%m-%dT%H:%M') if date_str else datetime.now()
        except ValueError:
            date_time = datetime.now()

        new_booking = Booking(
            customer_name=name,
            phone=phone,
            pickup_location=pickup,
            drop_location=drop,
            vehicle_type=vehicle_type,
            date_time=date_time,
            privacy_mode=privacy_mode
        )
        db.session.add(new_booking)
        db.session.commit()

        # WhatsApp Integration
        # Format: "New Booking! Name: ..., Pickup: ..., Drop: ..."
        msg = f"New Booking Request!\nName: {name}\nFrom: {pickup}\nTo: {drop}\nVehicle: {vehicle_type}\nTime: {date_str}"
        if privacy_mode:
            msg = f"🔒 PRIVACY MODE REQUESTED\n" + msg + "\n(Driver: Do not ask personal questions. Minimal interaction.)"
        
        phone_number = "919876543210" # Replace with actual taxi service number
        encoded_msg = urllib.parse.quote(msg)
        wa_link = f"https://wa.me/{phone_number}?text={encoded_msg}"
        
        # If user clicked "Book via WhatsApp", we assume the frontend handles the redirection to WA
        # If standard submit, we show success page or redirect with success
        
        if 'whatsapp' in request.form:
             return redirect(wa_link)
        
        flash('Booking submitted successfully! We will call you shortly.', 'success')
        return redirect(url_for('index'))

    vehicles = Vehicle.query.all()
    return render_template('book.html', vehicles=vehicles)

@app.route('/vehicles')
def vehicles():
    vehicles = Vehicle.query.all()
    return render_template('vehicles.html', vehicles=vehicles)

@app.route('/drivers')
def drivers():
    drivers = Driver.query.filter_by(is_active=True, is_banned=False).all()
    return render_template('drivers.html', drivers=drivers)

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/driver-agreement', methods=['GET', 'POST'])
def driver_agreement():
    if request.method == 'GET':
        return render_template('driver_agreement.html')
    return redirect(url_for('index')) # Fallback

@app.route('/driver-agreement/submit', methods=['POST'])
def driver_agreement_submit():
    phone = request.form.get('driver_phone')
    driver = Driver.query.filter_by(phone=phone).first()
    if driver:
        driver.agreement_accepted = True
        db.session.commit()
        flash('Thank you for pledging to safety!', 'success')
    else:
        flash('Driver number not found. Please contact admin.', 'error')
    return redirect(url_for('index'))

@app.route('/report', methods=['GET', 'POST'])
def report_issue():
    if request.method == 'GET':
        drivers = Driver.query.all()
        return render_template('report.html', drivers=drivers)
    return redirect(url_for('index'))

@app.route('/report/submit', methods=['POST'])
def submit_complaint():
    driver_id = request.form.get('driver_id')
    reason_type = request.form.get('reason_type')
    details = request.form.get('details')
    full_reason = f"{reason_type}: {details}"

    complaint = Complaint(driver_id=driver_id, reason=full_reason)
    db.session.add(complaint)
    
    # Auto-ban logic
    driver = Driver.query.get(driver_id)
    if driver:
        driver.complaint_count += 1
        if driver.complaint_count >= 3:
            driver.is_banned = True
            driver.is_active = False # Remove from active list
            flash('Complaint recorded. Driver has been auto-banned due to repeated complaints.', 'warning')
        else:
             flash('Complaint submitted successfully. We will take action.', 'success')
    
    db.session.commit()
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
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
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
    bookings = Booking.query.order_by(Booking.date_time.desc()).all()
    drivers = Driver.query.all()
    complaints = Complaint.query.order_by(Complaint.date_time.desc()).all()
    return render_template('admin.html', bookings=bookings, drivers=drivers, complaints=complaints)

@app.route('/admin/driver/<int:id>/toggle-ban', methods=['POST'])
@login_required
def toggle_ban(id):
    driver = Driver.query.get_or_404(id)
    driver.is_banned = not driver.is_banned
    # If banned, also deactive
    if driver.is_banned:
        driver.is_active = False
    else:
        driver.is_active = True
        
    db.session.commit()
    status = "Banned" if driver.is_banned else "Unbanned"
    flash(f"Driver {driver.name} has been {status}.", 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/booking/<int:id>/status', methods=['POST'])
@login_required
def update_booking_status(id):
    booking = Booking.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status:
        booking.status = new_status
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

# Application Start
if __name__ == '__main__':
    init_db(app)
    app.run(debug=True, host='0.0.0.0', port=5000)
