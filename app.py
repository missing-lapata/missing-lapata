import os
import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from sqlalchemy import cast, String

# Allowed image file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_recaptcha(response_token):
    """Verify Google reCAPTCHA response"""
    secret_key = app.config.get('RECAPTCHA_SECRET_KEY')
    if not secret_key:
        return True  # Skip verification if not configured
    payload = {
        'secret': secret_key,
        'response': response_token
    }
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload)
    result = r.json()
    return result.get('success', False)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mahakhub.db'
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong secret key for production!
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
# RECAPTCHA configuration – replace these with your actual keys from Google
app.config['RECAPTCHA_SITE_KEY'] = 'GoogleRecaptcha'
app.config['RECAPTCHA_SECRET_KEY'] = '6Lf-ZcoqAAAAAPslFLKqkI8PmcXYxuOaLgvrveXG'

db = SQLAlchemy(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Updated Person model includes a callback number, location photo, and uses the ID as a serial.
class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Serial Number
    name = db.Column(db.String(100), nullable=False)
    callback_number = db.Column(db.String(20))  # Contact number for coordination
    picture = db.Column(db.String(200))
    location_photo = db.Column(db.String(200))  # Photo for location (optional)
    age = db.Column(db.Integer)
    dob = db.Column(db.String(20))  # Format: YYYY-MM-DD
    birth_mark = db.Column(db.String(200))
    missing_from = db.Column(db.String(200))  # Last location where the person was missing
    current_location = db.Column(db.String(200))
    wearing = db.Column(db.String(200))       # What they were wearing last time
    home_city = db.Column(db.String(100))
    address = db.Column(db.String(200))
    additional_info = db.Column(db.Text)
    status = db.Column(db.String(50))         # e.g., Missing, Found, Dead, Sighted, Updated
    comment = db.Column(db.Text)

# Index route: Display a gallery with optional status filtering (via tabs) and pagination.
@app.route('/')
def index():
    status_filter = request.args.get('status', 'All')
    page = request.args.get('page', 1, type=int)
    query = Person.query
    if status_filter != 'All':
        query = query.filter_by(status=status_filter)
    pagination = query.order_by(Person.id.desc()).paginate(page=page, per_page=12, error_out=False)
    persons = pagination.items
    return render_template('index.html', persons=persons, pagination=pagination, status_filter=status_filter)

# Global search route (supports English/Hindi)
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_term = request.form.get('search_term')
        results = Person.query.filter(
            (Person.name.ilike(f"%{search_term}%")) |
            (Person.address.ilike(f"%{search_term}%")) |
            (Person.home_city.ilike(f"%{search_term}%")) |
            (Person.current_location.ilike(f"%{search_term}%")) |
            (Person.missing_from.ilike(f"%{search_term}%")) |
            (Person.dob.ilike(f"%{search_term}%")) |
            (Person.birth_mark.ilike(f"%{search_term}%")) |
            (cast(Person.age, String).ilike(f"%{search_term}%"))
        ).all()
        return render_template('search_results.html', persons=results, search_term=search_term)
    return render_template('search.html')

# Detail view: Show full information along with Google Maps links.
@app.route('/person/<int:person_id>')
def person_detail(person_id):
    person = Person.query.get_or_404(person_id)
    return render_template('person_detail.html', person=person)

# Create route: Add a new missing person. It performs a duplicate check (based on name, dob, and birth mark)
# and includes reCAPTCHA verification.
@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_response = request.form.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            flash('Captcha verification failed. कृपया कैप्चा सत्यापन करें।', 'danger')
            return redirect(url_for('create'))
        
        name = request.form.get('name')
        dob = request.form.get('dob')
        birth_mark = request.form.get('birth_mark')
        # Duplicate check: If a record with matching Name, DOB, and Birth Mark exists, show a confirmation.
        duplicates = Person.query.filter_by(name=name, dob=dob, birth_mark=birth_mark).all()
        if duplicates and request.form.get('confirm_duplicate') != 'yes':
            return render_template('confirm_duplicate.html',
                                   duplicates=duplicates,
                                   form_data=request.form,
                                   recaptcha_site_key=app.config['RECAPTCHA_SITE_KEY'])
        
        # Process the main picture upload with a unique filename.
        file = request.files.get('picture')
        picture_filename = None
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            picture_filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], picture_filename))
        
        # Process the location photo upload.
        loc_file = request.files.get('location_photo')
        location_photo_filename = None
        if loc_file and allowed_file(loc_file.filename):
            ext = loc_file.filename.rsplit('.', 1)[1].lower()
            location_photo_filename = f"{uuid.uuid4().hex}.{ext}"
            loc_file.save(os.path.join(app.config['UPLOAD_FOLDER'], location_photo_filename))
        
        new_person = Person(
            name=name,
            callback_number=request.form.get('callback_number'),
            picture=picture_filename,
            location_photo=location_photo_filename,
            age=request.form.get('age'),
            dob=dob,
            birth_mark=birth_mark,
            missing_from=request.form.get('missing_from'),
            current_location=request.form.get('current_location'),
            wearing=request.form.get('wearing'),
            home_city=request.form.get('home_city'),
            address=request.form.get('address'),
            additional_info=request.form.get('additional_info')
        )
        db.session.add(new_person)
        db.session.commit()
        flash('New person added successfully! / नया व्यक्ति सफलतापूर्वक जोड़ा गया!', 'success')
        return redirect(url_for('index'))
    return render_template('create.html', recaptcha_site_key=app.config['RECAPTCHA_SITE_KEY'])

# Update status and comment route: Includes reCAPTCHA verification.
@app.route('/update_status/<int:person_id>', methods=['GET', 'POST'])
def update_status(person_id):
    person = Person.query.get_or_404(person_id)
    if request.method == 'POST':
        recaptcha_response = request.form.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            flash('Captcha verification failed. कृपया कैप्चा सत्यापन करें।', 'danger')
            return redirect(url_for('update_status', person_id=person.id))
        person.status = request.form.get('status')
        person.comment = request.form.get('comment')
        db.session.commit()
        flash('Status and comment updated successfully! / स्थिति और टिप्पणी सफलतापूर्वक अपडेट हुई!', 'success')
        return redirect(url_for('person_detail', person_id=person.id))
    return render_template('update_status.html', person=person, recaptcha_site_key=app.config['RECAPTCHA_SITE_KEY'])

if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('mahakhub.db'):
            db.create_all()
    app.run(debug=True)
