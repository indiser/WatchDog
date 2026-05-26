import os
from curl_cffi import requests
from celery import Celery
from celery.schedules import crontab
from app import app, db, TargetURL
from datetime import datetime, timedelta

# Initialize Celery
# If you are running locally without Docker yet, ensure Redis is running on localhost
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
celery = Celery('tasks', broker=redis_url)

# The Scheduler (Celery Beat)
# This wakes up every 1 minute to check if any URLs need to be queued
celery.conf.beat_schedule = {
    'check-urls-every-minute': {
        'task': 'tasks.queue_due_pings',
        'schedule': crontab(minute='*'), # Runs every minute
    },
}

@celery.task
def queue_due_pings():
    """Reads the database and spawns individual ping tasks only if they are due."""
    with app.app_context():
        active_targets = TargetURL.query.filter_by(is_active=True).all()
        now = datetime.utcnow()
        queued_count = 0
        
        for target in active_targets:
            # If it has never been pinged, OR if enough time has passed since the last ping
            if target.last_pinged_at is None or now >= (target.last_pinged_at + timedelta(minutes=target.interval_minutes)):
                
                # Send it to the worker queue
                ping_url.delay(target.url)
                
                # Update the timestamp immediately so it doesn't get queued again next minute
                target.last_pinged_at = now
                queued_count += 1
                
        # Commit the timestamp updates to the database
        db.session.commit()
        return f"Queued {queued_count} URLs for pinging."

@celery.task(bind=True, max_retries=3)
def ping_url(self, url):
    """The actual worker task that makes the HTTP request."""
    try:
        # Timeout is critical. Never let a worker hang forever on a dead proxy.
        response = requests.get(url, timeout=10, impersonate="chrome")
        print(f"[SUCCESS] Pinged {url} - Status: {response.status_code}")
        return response.status_code
    except requests.exceptions.RequestException as exc:
        print(f"[FAILED] Could not reach {url}. Retrying...")
        # If the request fails, tell Celery to put it back in the queue
        raise self.retry(exc=exc, countdown=15)