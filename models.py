from flask_login import UserMixin
from bson import ObjectId
# No need to import mongo here

class User(UserMixin):
    def __init__(self, user_data):
        # Ensure user_data['_id'] is handled correctly
        if user_data and '_id' in user_data:
            self.id = str(user_data['_id'])
        else:
            self.id = None # Or handle error appropriately

        self.username = user_data.get('username')
        self.email = user_data.get('email') # Added email attribute
        self.password = user_data.get('password')
        self.is_admin = user_data.get('is_admin', False)

    # Optional: Add __repr__ for easier debugging
    def __repr__(self):
        return f"<User username='{self.username}', email='{self.email}'>"