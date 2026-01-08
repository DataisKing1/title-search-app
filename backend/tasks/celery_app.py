"""Celery application configuration"""
from celery import Celery
from kombu import Queue
import os

# Check if we're in eager/test mode (no broker needed)
CELERY_EAGER_MODE = os.getenv("CELERY_TASK_ALWAYS_EAGER", "").lower() == "true"

# Get broker URL from environment
if CELERY_EAGER_MODE:
    # Use memory backend for testing without Redis
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
else:
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Create Celery application
celery_app = Celery(
    "title_search",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "tasks.search_tasks",
        "tasks.scraping_tasks",
        "tasks.ai_tasks",
        "tasks.report_tasks",
    ]
)

# Enable eager mode if set
if CELERY_EAGER_MODE:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task queues
    task_queues=(
        Queue("high_priority", routing_key="high"),
        Queue("default", routing_key="default"),
        Queue("scraping", routing_key="scraping"),
        Queue("ai_analysis", routing_key="ai"),
        Queue("report_generation", routing_key="report"),
    ),

    # Default queue
    task_default_queue="default",
    task_default_routing_key="default",

    # Task routing
    task_routes={
        "tasks.search_tasks.orchestrate_search": {"queue": "default"},
        "tasks.scraping_tasks.*": {"queue": "scraping"},
        "tasks.ai_tasks.*": {"queue": "ai_analysis"},
        "tasks.report_tasks.*": {"queue": "report_generation"},
    },

    # Rate limiting for scraping tasks
    task_annotations={
        "tasks.scraping_tasks.scrape_county_records": {"rate_limit": "10/m"},
        "tasks.scraping_tasks.download_document": {"rate_limit": "20/m"},
        "tasks.ai_tasks.analyze_document": {"rate_limit": "30/m"},
    },

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result settings
    result_expires=86400,  # 24 hours

    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit

    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "check-county-health": {
        "task": "tasks.scraping_tasks.check_county_health",
        "schedule": 3600.0,  # Every hour
    },
    "cleanup-old-tasks": {
        "task": "tasks.search_tasks.cleanup_stale_searches",
        "schedule": 86400.0,  # Every 24 hours
    },
}
