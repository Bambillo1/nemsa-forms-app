from flask import Blueprint, render_template, redirect, request, flash, url_for, current_app
from flask_login import login_required, current_user
from bson import ObjectId
from extensions import mongo
from services.email_services import send_email # Assuming email_services exists and is functional
from pymongo.errors import PyMongoError # Import PyMongoError

admin_bp = Blueprint('admin', __name__)

# CORRECTED ROUTE PATH: Removed the leading /admin
@admin_bp.route('/documents')
@login_required
def manage_documents():
    if not current_user.is_admin:
        flash('Unauthorized access', 'danger')
        current_app.logger.warning(f"Unauthorized admin access attempt by user {current_user.id}")
        return redirect(url_for('main.dashboard'))

    try:
        documents = list(mongo.db.documents.find())
    except Exception as e:
        current_app.logger.error(f"Database error fetching all documents: {str(e)}", exc_info=True)
        flash('Could not load documents for admin view.', 'danger')
        documents = []

    return render_template('admin/documents.html', documents=documents)

# CORRECTED ROUTE PATH: Removed the leading /admin
@admin_bp.route('/notify', methods=['GET', 'POST'])
@login_required
def notify_user():
    if not current_user.is_admin:
        flash('Unauthorized access', 'danger')
        current_app.logger.warning(f"Unauthorized admin notify attempt by user {current_user.id}")
        return redirect(url_for('main.dashboard'))

    if request.method == 'GET':
         try:
             documents = list(mongo.db.documents.find())
         except Exception as e:
             current_app.logger.error(f"Database error fetching documents for notify page: {str(e)}", exc_info=True)
             flash('Could not load documents.', 'danger')
             documents = []
         return render_template('admin/notify.html', documents=documents)

    if request.method == 'POST':
        try:
            document_id_str = request.form.get('document')
            message = request.form.get('message')
            new_status = request.form.get('status')

            if not document_id_str or not ObjectId.is_valid(document_id_str):
                 flash('Invalid document selected.', 'danger')
                 current_app.logger.warning(f"Admin tried to notify with invalid doc ID format: {document_id_str}")
                 return redirect(url_for('admin.notify_user'))
            if not message or not new_status:
                 flash('Message and Status are required.', 'danger')
                 return redirect(url_for('admin.notify_user'))

            document_id = ObjectId(document_id_str)

            update_result = mongo.db.documents.update_one(
                {'_id': document_id},
                {'$set': {'status': new_status}}
            )

            if update_result.matched_count == 0:
                 flash('Document not found.', 'danger')
                 current_app.logger.warning(f"Admin tried to update non-existent doc ID: {document_id_str}")
                 return redirect(url_for('admin.notify_user'))

            document = mongo.db.documents.find_one({'_id': document_id})
            if not document or 'user_id' not in document or not ObjectId.is_valid(str(document['user_id'])):
                 flash('Could not find user associated with document.', 'danger')
                 current_app.logger.error(f"Document {document_id} missing user_id or user_id invalid.")
                 return redirect(url_for('admin.manage_documents'))

            user_id = ObjectId(document['user_id'])
            user = mongo.db.users.find_one({'_id': user_id})

            if not user or 'email' not in user or 'username' not in user:
                 flash('Could not find user details for notification.', 'danger')
                 current_app.logger.error(f"User {user_id} not found or missing email/username for document {document_id}.")
                 return redirect(url_for('admin.manage_documents'))

            # Send status update email
            send_email(
                subject=f"Document Status Update: {new_status}",
                recipients=[user.get('email')],
                template="status_update",
                username=user.get('username'),
                document_name=document.get('original_name', document.get('filename', 'Document')),
                new_status=new_status,
                admin_message=message
            )

            flash('Notification sent successfully', 'success')
            return redirect(url_for('admin.manage_documents'))

        except PyMongoError as e:
            current_app.logger.error(f"Database error during admin notify: {str(e)}", exc_info=True)
            flash('Database error occurred during notification.', 'danger')
            return redirect(url_for('admin.notify_user'))
        except Exception as e:
            current_app.logger.error(f"Unexpected error during admin notify: {str(e)}", exc_info=True)
            flash('An unexpected error occurred during notification.', 'danger')
            return redirect(url_for('admin.notify_user'))

    flash('Invalid request method.', 'warning')
    return redirect(url_for('admin.manage_documents'))