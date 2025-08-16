from celery import Celery
from app import create_app
import os

def make_celery(app):
    """Create Celery instance with Flask app context"""
    celery = Celery(
        app.import_name,
        backend=app.config['REDIS_URL'],
        broker=app.config['REDIS_URL']
    )
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Create Flask app and Celery instance
flask_app = create_app()
celery = make_celery(flask_app)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,
    result_expires=3600,  # 1 hour
    task_routes={
        'workers.download_worker.*': {'queue': 'downloads'},
        'workers.transfer_worker.*': {'queue': 'transfers'},
    },
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
)









