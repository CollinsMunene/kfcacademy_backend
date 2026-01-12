
# Async ActionLogs creation for audit logging
from main.models import ActionLogs,Users
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

from django.template.loader import render_to_string
from celery import shared_task
from django.core.mail import get_connection,EmailMultiAlternatives
from KFCAcademy.celery import app
from jinja2 import Environment, FileSystemLoader

# Setup Jinja2 environment (once globally)
jinja_env = Environment(loader=FileSystemLoader("templates/email"))

# resend.api_key ="re_bHYJb3M6_PJdoFSCMEYKthScS2myWRkC1"
@app.task(bind=True, max_retries=3, default_retry_delay=60)  # Retry up to 3 times with a 60-second delay between retries
def send_email(self, subject, context, template, to_email):
    try:
        print(f"Preparing to send email to {to_email} with subject '{subject}' using template '{template}'")
        connection = get_connection()
        connection.timeout = 120


        msg = EmailMultiAlternatives(
            # title:
            subject="{title}".format(title=subject),
            # message:
            body="",
            # from:
            from_email='"{from_name}" <{from_email}>'.format(from_name='FPC Academy', from_email="fpc@devligence.com"),
            # to:
            to=[to_email],
            connection=connection
        )

        email_html_message = render_to_string('email/{template}'.format(template=template), context)
        msg.attach_alternative(email_html_message, "text/html")

        # Send email
        num_sent = msg.send()
        print(f"Email send function returned: {num_sent}")

        if num_sent == 1:
            print("Email sent successfully.")
        else:
            print("Unexpected number of emails sent:", num_sent)

    except Exception as e:
        print(f"Error sending email: {e}")
        self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def create_action_log_async(self, initiator_id, action, extra_details):
    try:
        ActionLogs.objects.create(
            initiator_id=Users.objects.filter(pk=initiator_id).first() if initiator_id else None,
            action=action,
            extra_details=extra_details
        )
        print(f"[CELERY] ActionLog created: {action}")
    except Exception as e:
        print(f"[CELERY][ERROR] Failed to create ActionLog: {e}")
        self.retry(exc=e)

# @app.task(bind=True, max_retries=3, default_retry_delay=60)
# def create_status_log_async(self,module_name,initiator_id, from_action, to_action, extra_details):
#     try:
#         StatusLog.objects.create(
#             module_name=module_name,
#             initiator_id=Users.objects.filter(pk=initiator_id).first() if initiator_id else None,
#             from_action=from_action,
#             to_action=to_action,
#             extra_details=extra_details
#         )
#         print(f"[CELERY] StatusLog created: {from_action} -> {to_action}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_user_image(self, user_id):
    """
    Background task to process user profile images
    """
    try:
        user = Users.objects.get(pk=user_id)
        
        if not user.image:
            return "No image to process"
        
        # Validate file size (max 10MB)
        if user.image.size > 10 * 1024 * 1024:
            return f"Image too large: {user.image.size} bytes"

        # Process image
        im = Image.open(user.image)
        im = im.convert('RGB')

        output_size = (300, 300)
        im.thumbnail(output_size)

        thumb_io = BytesIO()
        im.save(thumb_io, 'PNG', quality=85)

        # Save processed image
        user.image.save(
            user.image.name, 
            ContentFile(thumb_io.getvalue()), 
            save=False
        )
        
        # Update only the image field to avoid recursion
        Users.objects.filter(pk=user_id).update(image=user.image)
        
        print(f"[CELERY] Successfully processed image for user {user.email}")
        return f"Image processed for user {user.email}"
        
    except Users.DoesNotExist:
        print(f"[CELERY] User with id {user_id} not found")
        return f"User with id {user_id} not found"
        
    except Exception as e:
        print(f"[CELERY] Error processing image for user {user_id}: {e}")
        # Retry the task
        raise self.retry(exc=e)
#     except Exception as e:
#         print(f"[CELERY][ERROR] Failed to create StatusLog: {e}")
#         self.retry(exc=e)