import os
from dotenv import load_dotenv
load_dotenv()

# Gemini AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
TEMPERATURE = 0.8
MAX_TOKENS = 8000

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Cache Configuration
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL_DESCRIPTIONS = int(os.getenv("CACHE_TTL_DESCRIPTIONS", "2592000"))  # 30 days
CACHE_TTL_IMAGE_ANALYSIS = int(os.getenv("CACHE_TTL_IMAGE_ANALYSIS", "604800"))  # 7 days
CACHE_TTL_JOBS = int(os.getenv("CACHE_TTL_JOBS", "86400"))  # 24 hours

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "300"))  # 5 minutes
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "270"))  # 4.5 minutes

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))  # requests
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds (1 minute)
RATE_LIMIT_PREMIUM_REQUESTS = int(os.getenv("RATE_LIMIT_PREMIUM_REQUESTS", "100"))
RATE_LIMIT_PREMIUM_WINDOW = int(os.getenv("RATE_LIMIT_PREMIUM_WINDOW", "60"))

# API Configuration
ASYNC_MODE = os.getenv("ASYNC_MODE", "true").lower() == "true"  # Enable async task queue
JOB_STATUS_POLL_INTERVAL = int(os.getenv("JOB_STATUS_POLL_INTERVAL", "2"))  # seconds