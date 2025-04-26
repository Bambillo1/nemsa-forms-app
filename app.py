'''
import os
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask
# Import extensions *from* extensions.py
from extensions import mongo, login_manager, csrf, mail 
# Import User model from models.py
from models import User
from config import Config
from bson import ObjectId
from pymongo import ASCENDING
import logging
from dateutil import parser
from config import Config # Ensure Config is imported


# Set project root and Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

# Initialize extensions outside app factory (as before, defining them)
# mongo = PyMongo(connect=False) # REMOVE THIS - already done in extensions.py
# login_manager = LoginManager() # REMOVE THIS - already done in extensions.py
# csrf = CSRFProtect()           # REMOVE THIS - already done in extensions.py
# mail = Mail()                  # REMOVE THIS - already done in extensions.py


def create_app(test_config=None):
    """Application factory function"""
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Load configuration with environment check
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    # Verify MONGO_URI is set before initialization
    if not app.config.get('MONGO_URI'):
        raise ValueError("MONGO_URI not configured in environment or Config")

    # Initialize extensions *with the app instance*
    # Call init_app *on the imported extensions*
    mongo.init_app(app) # connect=False is default now, or set to True if needed immediately
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)


    # Configure template filter (keep as is)
    @app.template_filter('datetimeformat')
    def datetimeformat(value, fmt='%Y-%m-%d %H:%M:%S'):
        if isinstance(value, datetime):
            return value.strftime(fmt)
        try:
            # Handle potential timezone info if present
            if value.endswith('Z'): # ISO 8601 UTC
                 value = value[:-1] # Remove Z
            # Consider using a more robust parsing library like dateutil
            
            dt_obj = parser.parse(value)
            return dt_obj.strftime(fmt)
        except (TypeError, ValueError, AttributeError):
            return '' # Return empty string or a default

    # Database initialization with explicit connection (keep this, but it should work better now)
    with app.app_context():
        try:
            # Force connection establishment (optional, but good for testing)
            mongo.cx.server_info()
            print("✅ MongoDB connection successful")

            # Index creation with improved checks (keep as is)
            def safe_create_index(collection, keys, **kwargs):
                """Create index only if it doesn't exist with same key pattern"""
                existing_indexes = collection.index_information()

                # Check for existing index with same keys
                # Note: This check is basic. More robust checks would compare options.
                for index in existing_indexes.values():
                    if index.get('key') == keys:
                        print(f"⚠️ Index for {keys} already exists.")
                        return list(index.keys()) # Return something indicating it was found

                try:
                     index_name = collection.create_index(keys, **kwargs)
                     print(f"🆕 Created index: {index_name} for {keys}")
                     return index_name
                except Exception as e:
                     print(f"❌ Failed to create index for {keys}: {e}")
                     return None


            # Initialize collections if needed (keep as is)
            required_collections = {'users', 'documents'}
            existing_collections = set(mongo.db.list_collection_names())

            for coll in required_collections - existing_collections:
                mongo.db.create_collection(coll)
                print(f"🆕 Created collection: {coll}")

            # Create indexes with proper order constants (keep as is)
            documents_index = safe_create_index(
                mongo.db.documents,
                [('user_id', ASCENDING), ('status', ASCENDING)],
                name='user_status_idx',
                background=True
            )
            # print(f"🔑 Documents index: {documents_index}") # Already printed in safe_create_index

            users_index = safe_create_index(
                mongo.db.users,
                [('email', ASCENDING)],
                name='unique_email_idx',
                unique=True,
                partialFilterExpression={'email': {'$exists': True}},
                background=True
            )
            # print(f"📧 Users index: {users_index}") # Already printed in safe_create_index


        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            app.logger.error(error_msg, exc_info=True)
            print(f"❌ {error_msg}")
            # Re-raise the exception or handle it - for a production app you might log and exit gracefully
            # raise RuntimeError("Database connection failed") from e
            # For development, perhaps just log and continue, although DB errors are critical
            pass # Allow app to start even if DB init fails, errors will occur on DB access


    # Configure user loader with connection safety (keep as is, corrected import)
    @login_manager.user_loader
    def load_user(user_id):
        try:
             # Ensure user_id is valid ObjectId string before conversion
             if not ObjectId.is_valid(user_id):
                 app.logger.warning(f"Invalid user_id format: {user_id}")
                 return None

             # Check if mongo.db is available. It should be in request context after init_app.
             if mongo.db is None:
                 app.logger.error("User loader called but mongo.db is None")
                 return None

             user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
             # Pass user_data dictionary to User model constructor
             return User(user_data) if user_data else None
        except Exception as e:
            app.logger.error(f"User load error for ID {user_id}: {str(e)}", exc_info=True)
            return None


    # Register blueprints after DB initialization (keep as is)
    register_blueprints(app)
     # --- Exempt the upload route from CSRF *after* blueprint is registered ---
    # Import the specific view function after its blueprint is known to the app
    from routes.main import upload # Import the function
    csrf.exempt(upload) # Call the exempt method on the csrf instance
    print("✅ Upload route exempted from CSRF using csrf.exempt().")
    # --- End exemption ---

    # Ensure upload directory exists (keep as is)
    upload_dir = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    app.logger.info(f"Upload directory: {upload_dir}")
    
    # Ensure template download directory exists (create if it doesn't)
    template_download_dir = app.config['TEMPLATE_DOWNLOAD_FOLDER']
    os.makedirs(template_download_dir, exist_ok=True)
    app.logger.info(f"Template download directory: {template_download_dir}")


    return app

# Keep register_blueprints and the __main__ block as is
def register_blueprints(app):
    """Register Flask blueprints with late imports"""
    # Import blueprints locally to avoid import issues before app is fully configured
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.admin import admin_bp
    
    print("Attempting to register auth blueprint...")
    app.register_blueprint(auth_bp, url_prefix='/auth')
    print("Auth blueprint registered.")

    print("Attempting to register main blueprint...")
    app.register_blueprint(main_bp)
    print("Main blueprint registered.")

    print("Attempting to register admin blueprint...")
    app.register_blueprint(admin_bp, url_prefix='/admin')
    print("Admin blueprint registered.")


    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')


if __name__ == "__main__":
    # Configure logging for the main script
    logging.basicConfig(level=logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=app.config.get('DEBUG', False), # Use DEBUG config
        # use_reloader=app.config.get('DEBUG', False) # use_reloader handled by debug=True
    )
    '''
    
import os
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, current_app # Import current_app
from flask_mail import Mail
from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from bson import ObjectId
from pymongo import ASCENDING
import logging
from dateutil import parser # Ensure dateutil is installed (pip install python-dateutil)
from extensions import mongo, login_manager, csrf, mail
from models import User
# Import Config from config.py
from config import Config

# Import blueprint objects from their respective files AT THE TOP LEVEL
from routes.auth import auth_bp
from routes.main import main_bp
from routes.admin import admin_bp # <<< Ensure this import is correct


# Set project root and Python path (Keep these if you were using them)
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

# Initialize extensions outside app factory (defining them)
# These should be imported from extensions.py as you have done later
# Remove commented out lines if they were attempts to redefine:
# mongo = PyMongo(connect=False)
# login_manager = LoginManager()
# csrf = CSRFProtect()
# mail = Mail()


def create_app(test_config=None):
    """Application factory function"""
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Load configuration with environment check
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    # Verify MONGO_URI is set before initialization
    if not app.config.get('MONGO_URI'):
        raise ValueError("MONGO_URI not configured in environment or Config")

    # Initialize extensions *with the app instance*
    # Call init_app *on the imported extensions*
    mongo.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)


    # Configure template filter (keep as is)
    @app.template_filter('datetimeformat')
    def datetimeformat(value, fmt='%Y-%m-%d %H:%M:%S'):
        if isinstance(value, datetime):
            return value.strftime(fmt)
        try:
            if isinstance(value, str): # Only attempt to parse strings
                # Handle potential timezone info if present
                if value.endswith('Z'): # ISO 8601 UTC
                     value = value[:-1] # Remove Z

                dt_obj = parser.parse(value)
                # Ensure dt_obj is timezone-aware if needed, or convert to UTC
                # For simple display, naive datetime might be okay
                return dt_obj.strftime(fmt)
            else:
                 current_app.logger.warning(f"Attempted to format non-string value as datetime: {value}")
                 return ''
        except (TypeError, ValueError, AttributeError, parser.ParserError): # Add ParserError
             # Log the error when parsing fails, but return empty string
             current_app.logger.warning(f"Failed to parse datetime value '{value}' for template filter.")
             return ''


    # Database initialization with explicit connection (keep this)
    with app.app_context():
        try:
            # Force connection establishment (optional, but good for testing)
            mongo.cx.server_info()
            print("✅ MongoDB connection successful")

            # Index creation with improved checks (keep as is)
            def safe_create_index(collection, keys, **kwargs):
                """Create index only if it doesn't exist with same key pattern"""
                existing_indexes = collection.index_information()

                for index in existing_indexes.values():
                    if index.get('key') == keys:
                        print(f"⚠️ Index for {keys} already exists.")
                        return list(index.keys())

                try:
                     index_name = collection.create_index(keys, **kwargs)
                     print(f"🆕 Created index: {index_name} for {keys}")
                     return index_name
                except Exception as e:
                     print(f"❌ Failed to create index for {keys}: {e}")
                     return None


            # Initialize collections if needed (keep as is)
            required_collections = {'users', 'documents'}
            existing_collections = set(mongo.db.list_collection_names())

            for coll in required_collections - existing_collections:
                mongo.db.create_collection(coll)
                print(f"🆕 Created collection: {coll}")

            # Create indexes with proper order constants (keep as is)
            documents_index = safe_create_index(
                mongo.db.documents,
                [('user_id', ASCENDING), ('status', ASCENDING)],
                name='user_status_idx',
                background=True
            )

            users_index = safe_create_index(
                mongo.db.users,
                [('email', ASCENDING)],
                name='unique_email_idx',
                unique=True,
                partialFilterExpression={'email': {'$exists': True}},
                background=True
            )


        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            app.logger.error(error_msg, exc_info=True)
            print(f"❌ {error_msg}")
            pass


    # Configure user loader with connection safety (keep as is)
    @login_manager.user_loader
    def load_user(user_id):
        try:
             if not ObjectId.is_valid(user_id):
                 app.logger.warning(f"Invalid user_id format: {user_id}")
                 return None

             if mongo.db is None:
                 app.logger.error("User loader called but mongo.db is None")
                 return None

             user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
             return User(user_data) if user_data else None
        except Exception as e:
            app.logger.error(f"User load error for ID {user_id}: {str(e)}", exc_info=True)
            return None


    # Register blueprints (Call the function)
    register_blueprints(app)

    # Exempt the upload route from CSRF (Keep this, it fixed the 400)
    # This import must happen AFTER main_bp is registered with the app
    # because the blueprint object is needed to reference the view function.
    # Since blueprints are now imported at the top, main_bp exists.
    # The upload function itself needs to be imported from routes.main.
    # This import can stay here or be moved if preferred, but it works here.
    from routes.main import upload # Import the specific view function
    csrf.exempt(upload) # Call the exempt method on the csrf instance
    print("✅ Upload route exempted from CSRF using csrf.exempt().")

    # --- Add TEMPORARY exemption for admin notify route for testing ---
    # This import must happen AFTER admin_bp is registered with the app
    from routes.admin import notify_user # Import the notify_user function
    csrf.exempt(notify_user) # Call the exempt method on the csrf instance
    print("✅ Admin notify route TEMPORARILY exempted from CSRF for debugging.")
    # >>> REMEMBER TO REMOVE THIS LINE AFTER TESTING! <<<
    # --- End Temporary Exemption ---

    # Ensure upload and template download directories exist (keep as is)
    upload_dir = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    app.logger.info(f"Upload directory: {upload_dir}")

    template_download_dir = app.config['TEMPLATE_DOWNLOAD_FOLDER']
    os.makedirs(template_download_dir, exist_ok=True)
    app.logger.info(f"Template download directory: {template_download_dir}")

    # --- Temporary Debug Route to Inspect URL Map ---
    # Add this block just before the 'return app' line
    @app.route('/debug/routes')
    def debug_routes():
        output = []
        # Loop through all registered URL rules (routes)
        for rule in app.url_map.iter_rules():
            # Get the methods allowed for this rule (e.g., GET, POST)
            methods = ','.join(rule.methods) if rule.methods else 'ANY'
            # Format the output line: endpoint name, methods, and the URL rule pattern
            line = f"{rule.endpoint}: {methods} {rule.rule}"
            output.append(line)

        # Return the list of routes formatted as pre-formatted text
        # Sort alphabetically for easier reading
        return "<pre>" + "\n".join(sorted(output)) + "</pre>"
    # --- End Temporary Debug Route ---

    return app

# Define the register_blueprints function
# Blueprint objects are imported AT THE TOP LEVEL now
def register_blueprints(app):
    """Register Flask blueprints"""
    # No need to import blueprints inside this function anymore
    # from routes.auth import auth_bp
    # from routes.main import main_bp
    # from routes.admin import admin_bp

    print("--- Blueprint Registration Start ---")
    # Print blueprint objects to confirm they are imported
    print(f"Auth blueprint object: {auth_bp}")
    print(f"Main blueprint object: {main_bp}")
    print(f"Admin blueprint object: {admin_bp}")


    print("Attempting to register auth blueprint...")
    # Use the blueprint objects imported at the top
    app.register_blueprint(auth_bp, url_prefix='/auth')
    print("Auth blueprint registered.")

    print("Attempting to register main blueprint...")
    # Use the blueprint objects imported at the top
    app.register_blueprint(main_bp)
    print("Main blueprint registered.")

    print("Attempting to register admin blueprint...")
    # Use the blueprint objects imported at the top
    # This is the crucial line for admin routes
    app.register_blueprint(admin_bp, url_prefix='/admin')
    print("Admin blueprint registered.")
    print("--- Blueprint Registration End ---")

app = create_app()
# __main__ block (Keep as is)
if __name__ == "__main__":
    # Configure logging. Only the first basicConfig call takes effect.
    # Set level to DEBUG to see the blueprint registration prints and other debug messages.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    
    # Running with debug=True enables the reloader and sets logging to DEBUG by default
    # If you set debug=False in config, explicitly set level in basicConfig
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        #debug=app.config.get('DEBUG', False), # Use DEBUG config flag
    )