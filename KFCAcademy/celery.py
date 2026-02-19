# myproject/celery.py
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KFCAcademy.settings')
app = Celery('KFCAcademy')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# app.conf.enable_utc = False
# app.conf.timezone = 'Africa/Nairobi'


if settings.DEBUG:
    broker_url = "redis://:statusString123@localhost:6379/0"
    app.conf.timezone = 'Africa/Nairobi'
    app.conf.enable_utc = True
    app.conf.task_routes = {
        'KFCAcademy.tasks.*': {'queue': 'kfc_queue'},
    }
    app.conf.task_default_queue = 'kfc_queue'
else:
    broker_url='redis://:StrongSudo483@localhost:6379/0'
    
app.conf.update(
    broker_url=broker_url,
    broker_connection_retry_on_startup=True,  # Add this line
    task_soft_time_limit=300,
)