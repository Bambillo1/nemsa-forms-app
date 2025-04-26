# extensions.py
from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail

# Initialize extensions, but don't link to an app yet
mongo = PyMongo(connect=False)
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()