from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app # Import current_app
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from bson import ObjectId
import re
import logging
from extensions import mongo
from models import User
from services.email_services import send_email # Assuming email_services exists and is functional
from flask_wtf import FlaskForm # Import FlaskForm

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# Constants
EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'
MIN_PASSWORD_LENGTH = 8

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user authentication with security checks and logging."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Instantiate a simple form for CSRF token on GET requests
    form = FlaskForm()

    if request.method == 'POST':
        # Process the form submission
        # Note: If you were using Flask-WTF for validation, you'd do form.validate_on_submit() here
        # With manual handling, you process request.form directly.
        # For CSRF, Flask-WTF's CSRFProtect initialized with app handles validation middleware on POST.
        return handle_login_request(request.form)

    # Render template for GET request, passing the form object
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration with validation and email verification."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Instantiate a simple form for CSRF token on GET requests
    form = FlaskForm()

    if request.method == 'POST':
        # Process the form submission (manual validation as before)
        return handle_registration_request(request.form)

    # Render template for GET request, passing the form object
    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
def logout():
    """Handle user logout with security notifications."""
    if current_user.is_authenticated:
        handle_logout_notification()

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# Helper functions (Keep these as they were in the previous correction)
def handle_login_request(form_data):
    """Process login form submission."""
    try:
        username = form_data.get('username', '').strip()
        password = form_data.get('password', '')

        if not username or not password:
            flash('Please fill in username and password', 'danger')
            return redirect(url_for('auth.login'))

        user_data = find_user(username)

        if not user_data:
            flash('Invalid username or password', 'danger')
            log_login_attempt(username)
            return redirect(url_for('auth.login'))

        user = User(user_data)

        if not validate_password(user.password, password):
             flash('Invalid username or password', 'danger')
             log_login_attempt(username)
             return redirect(url_for('auth.login'))

        login_user(user)
        send_login_notification(user)
        flash('Login successful!', 'success')
        return redirect(url_for('main.dashboard'))

    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}", exc_info=True) # Use current_app.logger
        flash('An error occurred during login. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

def handle_registration_request(form_data):
    """Process registration form submission."""
    try:
        username = form_data.get('username', '').strip()
        email = form_data.get('email', '').strip().lower()
        password = form_data.get('password', '')
        confirm_password = form_data.get('confirm_password', '')

        if not validate_registration(username, email, password, confirm_password):
            return redirect(url_for('auth.register'))

        if user_exists(username, email):
            flash('Username or email already exists', 'danger')
            return redirect(url_for('auth.register'))

        create_new_user(username, email, password)

        try:
             send_welcome_email(username, email)
        except Exception as e:
             current_app.logger.error(f"Failed to send welcome email to {email}: {e}") # Use current_app.logger

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    except Exception as e:
        current_app.logger.error(f"Registration error: {str(e)}", exc_info=True) # Use current_app.logger
        flash('An error occurred during registration. Please try again.', 'danger')
        return redirect(url_for('auth.register'))

def handle_logout_notification():
    """Send logout notification email safely."""
    try:
        if current_user.is_authenticated and hasattr(current_user, 'email') and current_user.email:
             send_email(
                 subject="Logout Notification - NEMSA Forms",
                 recipients=[current_user.email],
                 template="logout_alert",
                 username=current_user.username if hasattr(current_user, 'username') else 'User'
             )
    except Exception as e:
        current_app.logger.error(f"Logout email failed for user {current_user.username if hasattr(current_user, 'username') else current_user.id}: {str(e)}") # Use current_app.logger

def validate_password(hashed_password_from_db, provided_password):
    """Validates a provided password against a hashed password from the database."""
    if not hashed_password_from_db:
        return False
    return check_password_hash(hashed_password_from_db, provided_password)

# Validation functions (Keep as is)
def validate_registration(username, email, password, confirm_password):
    """Validate registration data fields."""
    errors = []

    if not all([username, email, password, confirm_password]):
        errors.append('All fields are required.')

    if password != confirm_password:
        errors.append('Passwords do not match.')

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f'Password must be at least {MIN_PASSWORD_LENGTH} characters long.')

    if email and not re.match(EMAIL_REGEX, email):
        errors.append('Invalid email format.')

    if errors:
        for error in errors:
            flash(error, 'danger')
        return False
    return True

# Database operations (Keep as is)
def find_user(username):
    """Find user in database by username (case-insensitive)."""
    if not username:
        return None
    return mongo.db.users.find_one({
        'username': {'$regex': f'^{re.escape(username)}$', '$options': 'i'}
    })

def find_user_by_email(email):
    """Find user in database by email (case-insensitive)."""
    if not email:
        return None
    return mongo.db.users.find_one({
        'email': email.lower()
    })

def user_exists(username, email):
    """Check if user already exists in database by username (case-insensitive) or email (case-insensitive)."""
    query_parts = []
    if username:
         query_parts.append({'username': {'$regex': f'^{re.escape(username)}$', '$options': 'i'}})
    if email:
         query_parts.append({'email': email.lower()})

    if not query_parts:
        return False

    return mongo.db.users.find_one({'$or': query_parts}) is not None

def create_new_user(username, email, password):
    """Create new user in database."""
    hashed_pw = generate_password_hash(password)
    user_data = {
        'username': username.strip(),
        'email': email.strip().lower(),
        'password': hashed_pw,
        'is_admin': False
    }
    result = mongo.db.users.insert_one(user_data)
    return result.inserted_id

# Email functions (Keep as is)
def send_login_notification(user):
    """Send login alert email with error handling."""
    try:
        if hasattr(user, 'email') and user.email and hasattr(user, 'username') and user.username:
             send_email(
                 subject="Login Alert - NEMSA Forms",
                 recipients=[user.email],
                 template="login_alert",
                 username=user.username
             )
        else:
             current_app.logger.warning(f"Could not send login email for user ID {user.id}: Missing email or username attribute.") # Use current_app.logger
    except Exception as e:
        current_app.logger.error(f"Login email failed for user {user.username if hasattr(user, 'username') else user.id}: {str(e)}") # Use current_app.logger

def send_welcome_email(username, email):
    """Send welcome email with error handling."""
    try:
        if email and username:
            send_email(
                subject="Welcome to NEMSA Forms",
                recipients=[email],
                template="welcome",
                username=username
            )
        else:
            current_app.logger.warning(f"Could not send welcome email: Missing email ({email}) or username ({username}).") # Use current_app.logger
    except Exception as e:
        current_app.logger.error(f"Welcome email failed for {email}: {str(e)}") # Use current_app.logger

def log_login_attempt(username):
    """Log failed login attempts by username."""
    current_app.logger.warning(f"Failed login attempt for username: {username}") # Use current_app.logger