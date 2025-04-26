# services/email_services.py
from flask_mail import Message
from flask import render_template, current_app
from extensions import mail # Import the mail instance initialized in extensions.py
import logging

logger = logging.getLogger(__name__)

def send_email(subject, recipients, template, **kwargs):
    """
    Sends an email using Flask-Mail with templated body.

    Args:
        subject (str): The subject of the email.
        recipients (list): A list of recipient email addresses.
        template (str): The base name of the template file (e.g., "status_update").
                        Expects template files like template.txt and template.html
                        in the "emails" subdirectory of your templates folder.
        **kwargs: Context variables to pass to the template.
    """
    try:
        if not recipients:
            logger.warning(f"Attempted to send email '{subject}' with no recipients.")
            return False

        # Render email body from templates
        text_body = render_template(f'emails/{template}.txt', **kwargs)
        html_body = render_template(f'emails/{template}.html', **kwargs)

        msg = Message(subject,
                      sender=current_app.config['MAIL_DEFAULT_SENDER'],
                      recipients=recipients)
        msg.body = text_body
        msg.html = html_body

        mail.send(msg)
        logger.info(f"Email '{subject}' sent successfully to {recipients}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email '{subject}' to {recipients}: {e}", exc_info=True)
        # Depending on requirements, you might re-raise or return False
        return False

# You will need corresponding email template files in templates/emails/
# e.g., templates/emails/status_update.txt and templates/emails/status_update.html
# and templates/emails/welcome.txt, templates/emails/welcome.html
# and templates/emails/login_alert.txt, templates/emails/login_alert.html
# and templates/emails/logout_alert.txt, templates/emails/logout_alert.html