# config.py
import os
from dotenv import load_dotenv

# Assuming PROJECT_ROOT is set in app.py and added to sys.path
# Use a path relative to the project root if necessary
# PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # If config.py is in a subdir
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__)) # Assuming config.py is at the root

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'd4ff3ab4a1606baefa76b1bf22e19661978bf0e52cfbda9c830b4271d0eb8092')
    MONGO_URI = os.getenv('MONGO_URI')
    UPLOAD_FOLDER = 'uploads'
    # Add TEMPLATE_DOWNLOAD_FOLDER
    TEMPLATE_DOWNLOAD_FOLDER = 'templates_for_download' # Folder relative to project root

    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = False

    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/png',
        'image/jpeg',
        'image/gif'
    }

    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com') # Get from env or default
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587)) # Get from env or default
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1'] # Get from env or default
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@nemsa.gov.ng') # Get from env or default

    # Add a debug flag from .env
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1']