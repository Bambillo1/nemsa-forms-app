from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_from_directory, current_app)
from flask_login import login_required, current_user
from datetime import datetime
import os
import logging
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename # Keep this import as it's used elsewhere (e.g., in utils)
from pymongo.errors import PyMongoError
from extensions import mongo
from utils.file_utils import allowed_file, save_uploaded_file
from bson import ObjectId
from flask_wtf import FlaskForm


main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@main_bp.route('/')
def home():
    if current_user.is_authenticated:
         return redirect(url_for('main.dashboard'))
    return render_template('auth/homepage.html')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        user_obj_id = ObjectId(current_user.id)
        documents = list(mongo.db.documents.find({
            'user_id': user_obj_id
        }).sort('upload_date', -1))

        template_dir = current_app.config['TEMPLATE_DOWNLOAD_FOLDER']
        # abs_template_dir = os.path.abspath(template_dir) # Keep debug logging if needed
        # current_app.logger.debug(f"Attempting to list files from template directory: {template_dir}")
        # current_app.logger.debug(f"Resolved absolute path for template directory: {abs_template_dir}")

        try:
            all_items_in_dir = os.listdir(template_dir)
            # current_app.logger.debug(f"All items found in '{template_dir}': {all_items_in_dir}")

            template_files = [f for f in all_items_in_dir if os.path.isfile(os.path.join(template_dir, f))]
            # current_app.logger.debug(f"Filtered list (only files): {template_files}")

        except OSError as e:
            current_app.logger.error(f"Error listing template files from {template_dir}: {e}")
            template_files = []

    except Exception as e:
        current_app.logger.error(f"Database error fetching documents for user {current_user.id}: {str(e)}", exc_info=True)
        flash('Could not load documents.', 'danger')
        documents = []
        template_files = []

    return render_template('dashboard.html', documents=documents, template_files=template_files)

# Add route for downloading template files
@main_bp.route('/download_template/<filename>')
def download_template(filename):
    # Templates are public, no login required here

    template_dir = current_app.config['TEMPLATE_DOWNLOAD_FOLDER']

    # --- CORRECTED LOGIC ---
    # Do NOT use secure_filename here. Use the original filename from the URL
    # because that's the name listed by os.listdir and the name of the file on disk.
    # send_from_directory is secure and prevents path traversal by ensuring the
    # final path resolved from 'directory' and 'path' is inside 'directory'.
    # secure_filename_part = secure_filename(filename) # REMOVE THIS LINE

    # Construct the full path to the intended file using the ORIGINAL filename
    filepath = os.path.join(template_dir, filename) # USE filename directly

    # Check if the file exists at the constructed path AND is a file
    # This check still uses the path constructed with the original filename
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        flash(f"Template file not found: {filename}", 'danger')
        current_app.logger.warning(f"Attempted download of non-existent or non-file template: {filename}")
        if current_user.is_authenticated:
             return redirect(url_for('main.dashboard'))
        return redirect(url_for('main.home'))


    # Serve the file using send_from_directory
    # Pass the ORIGINAL filename as the path argument to send_from_directory.
    # send_from_directory will handle the secure resolution of this path relative to the directory.
    try:
        return send_from_directory(
            directory=template_dir,
            path=filename, # USE filename directly here
            as_attachment=True,
            download_name=filename # Use original filename for the download client side
        )
    except Exception as e:
        current_app.logger.error(f"Error serving template file {filename}: {e}", exc_info=True)
        flash("An error occurred while trying to download the template.", 'danger')
        if current_user.is_authenticated:
             return redirect(url_for('main.dashboard'))
        return redirect(url_for('main.home'))


# Keep upload and download routes as is
@main_bp.route('/upload', methods=['GET', 'POST'])
@login_required
# Remember if you are using csrf.exempt in app.py, you don't need any decorator here
def upload():
    form = FlaskForm()

    if request.method == 'POST':
        try:
            # CSRF validation is handled by Flask-WTF middleware (or exempted)

            if 'document' not in request.files:
                 raise ValueError("No file part received. Ensure you select a file.")

            file = request.files['document']

            if file.filename == '':
                raise ValueError("No selected file. Please choose a document to upload.")

            if not allowed_file(file.filename):
                allowed = ", ".join(current_app.config.get('ALLOWED_EXTENSIONS', []))
                raise ValueError(f"Invalid file type. Allowed extensions: {allowed}")

            stored_filename = save_uploaded_file(file)
            if not stored_filename:
                 raise RuntimeError("File save failed on the server.")

            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], stored_filename)
            try:
                file_size = os.path.getsize(filepath)
            except OSError as e:
                 current_app.logger.error(f"Error getting size of saved file {filepath}: {e}")
                 file_size = 0

            document = {
                'user_id': ObjectId(current_user.id),
                'filename': stored_filename,
                'original_name': file.filename,
                'upload_date': datetime.utcnow(),
                'status': 'Pending Review',
                'file_size': file_size
            }

            mongo.db.documents.insert_one(document)

            flash('Document uploaded successfully!', 'success')
            return redirect(url_for('main.dashboard'))

        except RequestEntityTooLarge:
            flash(f'File exceeds maximum size limit ({current_app.config.get("MAX_CONTENT_LENGTH", 0) // (1024*1024)}MB).', 'danger')
            return render_template('upload.html', form=form)
        except (ValueError, RuntimeError) as e:
            flash(str(e), 'danger')
            return render_template('upload.html', form=form)
        except PyMongoError as e:
            logger.error(f"Database error during upload: {str(e)}", exc_info=True)
            flash('Database error occurred while saving document metadata.', 'danger')
            if 'stored_filename' in locals() and stored_filename:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Cleaned up uploaded file {stored_filename} due to DB error.")
                except Exception as cleanup_e:
                    logger.error(f"Error cleaning up file {stored_filename} at {filepath}: {cleanup_e}")
            return render_template('upload.html', form=form)
        except Exception as e:
            logger.error(f"Unexpected error during upload: {str(e)}", exc_info=True)
            flash('An unexpected error occurred during upload.', 'danger')
            return render_template('upload.html', form=form)


    return render_template('upload.html', form=form)

@main_bp.route('/download/<filename>')
@login_required
def download(filename):
     try:
          user_obj_id = ObjectId(current_user.id)
          document = mongo.db.documents.find_one({
              'filename': filename,
              'user_id': user_obj_id
          })

          if not document:
              flash('File not found or unauthorized access', 'danger')
              current_app.logger.warning(f"Unauthorized download attempt for file {filename} by user {current_user.id}")
              return redirect(url_for('main.dashboard'))

          filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
          if not os.path.exists(filepath) or not os.path.isfile(filepath):
              flash('File content not found on server.', 'danger')
              current_app.logger.error(f"File {filename} not found on disk for document {document.get('_id')}")
              return redirect(url_for('main.dashboard'))

          return send_from_directory(
              directory=current_app.config['UPLOAD_FOLDER'],
              path=filename,
              as_attachment=True,
              download_name=document.get('original_name', filename)
          )

     except Exception as e:
         current_app.logger.error(f"Error during download for file {filename}: {str(e)}", exc_info=True)
         flash('An error occurred during download.', 'danger')
         return redirect(url_for('main.dashboard'))