import os
from config import Config
from flask import current_app
import magic


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
           
def validate_file(file):
    # Basic extension check
    if not allowed_file(file.filename):
        return False
    
    # MIME type validation
    mime = magic.Magic(mime=True)
    detected_type = mime.from_buffer(file.stream.read(1024))
    file.stream.seek(0)
    
    allowed_mime = current_app.config['ALLOWED_MIME_TYPES']
    return detected_type in allowed_mime