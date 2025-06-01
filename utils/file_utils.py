    
import os
import uuid
import logging
from werkzeug.utils import secure_filename
from flask import current_app
import mimetypes # Optional: for checking MIME types as well

logger = logging.getLogger(__name__)


def allowed_file(filename):
    """
    Checks if the file extension is in the allowed set.
    Note: This is a basic check based on extension only.
    """
    if '.' not in filename:
        return False
    # Get the extension after the last dot, convert to lowercase
    ext = filename.rsplit('.', 1)[1].lower()
    is_allowed = ext in current_app.config.get('ALLOWED_EXTENSIONS', set())

    # Optional: Log the result of this initial check
    # logger.debug(f"Initial allowed_file check for '{filename}': Extension '{ext}' is_allowed={is_allowed}")

    return is_allowed


def save_uploaded_file(file):
    """
    Securely saves an uploaded file with collision prevention and validation.
    Includes a second check against allowed extensions after securing.
    Returns: stored_filename or None on failure.
    """
    try:
        if not file or file.filename.strip() == '':
            logger.warning("No file or empty filename provided to save_uploaded_file")
            return None

        original_filename = file.filename
        # Split original filename into name and extension part
        filename_part, extension_part = os.path.splitext(original_filename) # extension_part includes the dot, e.g., '.png'

        # Secure the filename part (before the dot)
        secure_name = secure_filename(filename_part)
        if not secure_name:
             # If securing results in an empty string, use a UUID as the base name
             secure_name = str(uuid.uuid4())

        # Secure the extension part (including the dot) and ensure lowercase
        secure_ext = secure_filename(extension_part.lower())

        # Ensure the secured extension starts with a dot and handle cases like "filename."
        if not secure_ext.startswith('.'):
             # This shouldn't typically happen if os.path.splitext provided an extension_part,
             # but secure_filename might change things or handle edge cases.
             if secure_ext: # If there's a secured extension string, add a dot
                 secure_ext = '.' + secure_ext
             # If secure_ext is empty, it means no extension was found/secured, handle below


        # Check if a valid secured extension exists
        if not secure_ext or secure_ext == '.':
            logger.warning(f"File missing valid extension after securing filename '{original_filename}'. Secured extension part: '{secure_ext}'")
            # This catches files like "filename." or files with no extension or only unsafe chars in extension
            return None

        # --- Add detailed logging before the second extension check ---
        actual_extension_without_dot = secure_ext[1:] # Get the extension string without the leading dot
        allowed_extensions_set = current_app.config.get('ALLOWED_EXTENSIONS', set()) # Get the allowed set safely

        logger.debug(f"Save check: Original='{original_filename}', Secured Name='{secure_name}', Secured Ext='{secure_ext}'")
        logger.debug(f"Save check: Ext without dot='{actual_extension_without_dot}'")
        logger.debug(f"Save check: Allowed Extensions Set: {allowed_extensions_set}")
        logger.debug(f"Save check: Is '{actual_extension_without_dot}' IN {allowed_extensions_set}? --> {actual_extension_without_dot in allowed_extensions_set}")
        # --- End logging ---


        # Validate against allowed extensions *again* after securing
        # This checks if the extracted/secured extension (without the dot) is in the allowed set.
        if actual_extension_without_dot not in allowed_extensions_set:
            # This condition is TRUE if the extension is NOT allowed
            # The warning message should now include the exact extension being checked
            logger.warning(f"Invalid file extension '{actual_extension_without_dot}' after securing. Allowed: {allowed_extensions_set}")
            return None # Return None if extension is not allowed


        # Optional: Validate MIME type as well for added security
        # mimetype, _ = mimetypes.guess_type(original_filename)
        # allowed_mimetypes = current_app.config.get('ALLOWED_MIME_TYPES', set())
        # if mimetype and mimetype not in allowed_mimetypes:
        #    logger.warning(f"Invalid MIME type '{mimetype}' for file '{original_filename}'. Allowed: {allowed_mimetypes}")
        #    return None
        # elif not mimetype:
        #    logger.warning(f"Could not determine MIME type for file '{original_filename}'")
        #    # Decide if you want to reject files with unknown MIME types


        # Generate a unique filename to prevent collision
        base_name_for_final = secure_name # Use the secured filename part
        final_filename = f"{base_name_for_final}{secure_ext}" # Append the secured extension

        upload_folder = current_app.config['UPLOAD_FOLDER']

        # Ensure the upload directory exists
        os.makedirs(upload_folder, exist_ok=True)
        # Consider setting permissions: os.chmod(upload_folder, 0o755) # Permissions might vary based on OS/deployment needs

        # Prevent overwrites by adding a counter if a file with the same name exists
        counter = 1
        check_filename = final_filename
        while os.path.exists(os.path.join(upload_folder, check_filename)):
            # Construct the next filename attempt with a counter
            check_filename = f"{base_name_for_final}_{counter}{secure_ext}"
            counter += 1
        final_filename = check_filename # Use the final unique name

        # Construct the full path where the file will be saved
        file_path = os.path.join(upload_folder, final_filename)

        # Save the file to disk
        file.save(file_path)

        # Verify that the file was successfully written (basic check)
        if not os.path.exists(file_path):
            logger.error(f"File save verification failed: file does not exist after saving at {file_path}")
            # Raise an error or return None if verification fails
            return None

        # Consider setting permissions on the saved file: os.chmod(file_path, 0o644) # Permissions might vary

        logger.info(f"File saved successfully: Stored as '{final_filename}' (Original: '{original_filename}')")
        return final_filename # Return the unique stored filename

    except Exception as e:
        # Log any exceptions that occur during the save process
        logger.error(f"File save failed for original file '{file.filename if file else 'N/A'}': {str(e)}", exc_info=True)
        # Attempt to clean up the partially written file if file_path was defined before the error
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
             try:
                 os.remove(file_path)
                 logger.info(f"Cleaned up partially saved file: {file_path}")
             except Exception as cleanup_e:
                 logger.error(f"Error during cleanup of failed upload file {file_path}: {cleanup_e}")
        return None # Indicate failure by returning None