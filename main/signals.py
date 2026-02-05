from django.dispatch import receiver
from django.urls import reverse
from django_rest_passwordreset.signals import reset_password_token_created,post_password_reset
from django.core.mail import EmailMessage  
import asyncio

from KFCAcademy.tasks import create_action_log_async, send_email
# from compliance_tool.tasks import create_action_log_async
from main.models import ActionLogs, QuizResponses, UserModuleProgress
from django.db.models.signals import post_save, post_delete
from django.apps import apps
from django.forms.models import model_to_dict
import threading
import uuid
from django.db.models.fields.files import ImageFieldFile

# Recursive serialization for all values
from django.db.models import Model

# Helper to get current user from thread local (for DRF, middleware can set this)
_user = threading.local()
def get_current_user():
    return getattr(_user, 'value', None)

def set_current_user(user):
    _user.value = user

def serialize_value(val):
    import datetime
    if isinstance(val, uuid.UUID):
        return str(val)
    elif isinstance(val, Model):
        return getattr(val, 'pk', str(val))
    elif isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [serialize_value(v) for v in val]
    elif isinstance(val, datetime.date) or isinstance(val, datetime.datetime):
        return val.isoformat()
    elif isinstance(val, ImageFieldFile):
        return str(val.url) if val.url else None
    else:
        return val
                    
@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    email_plaintext_message = "{}?token={}".format("https://kfc-frontend-wine.vercel.app/reset-password/confirm", reset_password_token.key)
    message = "Hello "+ str(reset_password_token.user.email)+ ",You have requested a password reset for your account. Please click the button below. The link is valid for one Hour only. If you did not request a password reset, please ignore this email. Thank you."
    send_email.delay(
        subject="Password Reset for {title}".format(title="kfc Academy"),
           context={
                        "user":reset_password_token.user.email,
                        "org":"",
                        "message1":message,
                        "message2":"",
                        "message3":"",
                        "username":reset_password_token.user.email,
                        "password":"",
                        "link":email_plaintext_message
                    },
        template="email_with_button.html",
        to_email=reset_password_token.user.email
    )
    

@receiver(post_password_reset)
def post_password_reset(sender, user,*args, **kwargs):
    message = "Hello "+ str(user.email)+",Your password reset has been succesful. You can proceed to Log In. Thank you."
    
    ActionLogs.objects.create(
        initiator_id = user,
        action = f'{user.first_name} reset password successfully',  
        extra_details ={}  
    )
    
    send_email.delay(
        subject="Reset Successful for {title}".format(title="kfc Academy"),
           context={
                        "user":user.email,
                        "org":"",
                        "message1":message,
                        "message2":"",
                        "message3":"",
                        "username":user.email,
                        "password":"",
                        "link":"https://kfc-frontend-wine.vercel.app/login"
                    },
        template="email_with_button.html",
        to_email=user.email
    )

# Helper for soft delete audit logging
def log_soft_delete(instance, user=None):
    """
    Call this after setting deleted_at on an instance to log a soft delete action.
    user: the user performing the delete (if available)
    """
    data = serialize_value(model_to_dict(instance))
    extra_details = {
        'object_id': serialize_value(instance.pk),
        'data': data,
    }
    create_action_log_async.delay(
        initiator_id=getattr(user, 'pk', user) if user else None,
        action=f'delete {instance.__class__.__name__}',
        extra_details=extra_details
    )
    print(f'[SOFT DELETE LOG] ActionLog async task queued for soft_delete {instance.__class__.__name__} ({instance.pk})')

@receiver(post_save, sender=QuizResponses)
def update_module_progress(sender, instance, **kwargs):
    try:
        progress, _ = UserModuleProgress.objects.get_or_create(
            user=instance.user,
            module=instance.question.quiz.module
        )
        progress.update_quiz_progress()
    except Exception as e:
        print(f"Error updating progress: {e}")