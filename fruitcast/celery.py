# your_project_name/celery.py
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fruitcast.settings')

# Create an instance of the Celery application.
app = Celery('fruitcast')

# Load task modules from all registered Django app configs.
# This tells Celery to look for 'tasks.py' files in your apps.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')