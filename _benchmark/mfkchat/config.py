"""应用配置。"""

import os

DB_URL = os.getenv("MFKCHAT_DB_URL", "sqlite:///./mfkchat.db")
PAGE_SIZE = int(os.getenv("MFKCHAT_PAGE_SIZE", 20))
MAX_PAGE_SIZE = int(os.getenv("MFKCHAT_MAX_PAGE_SIZE", 100))
MEMORY_LIMIT = int(os.getenv("MFKCHAT_MEMORY_LIMIT", 30))
CONTEXT_WINDOW = int(os.getenv("MFKCHAT_CONTEXT_WINDOW", 8000))
DEBUG = os.getenv("MFKCHAT_DEBUG", "1") == "1"
