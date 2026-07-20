"""
Job Finder Web App - Configuration

Optimized for fast loading - minimal imports
"""
import os
from pathlib import Path

# Load environment variables (lightweight)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed yet, use environment variables

# Base directories
BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR.parent / "data"))
AI_SETTINGS_PATH = Path(os.getenv("AI_SETTINGS_PATH", DATA_DIR / "ai-settings.json"))
LLM_SECRETS_DB_PATH = Path(os.getenv("LLM_SECRETS_DB_PATH", DATA_DIR / "llm-secrets.sqlite3"))
AI_SESSIONS_DB_PATH = Path(os.getenv("AI_SESSIONS_DB_PATH", DATA_DIR / "ai-sessions.sqlite3"))

# Ensure data directories exist (quick check)
for subdir in ["candidates", "cookies", "backups", "archive"]:
    dir_path = DATA_DIR / subdir
    if not dir_path.exists():
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

# Security
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Auto-generate encryption key if missing (first-run only)
if not ENCRYPTION_KEY:
    from cryptography.fernet import Fernet
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    # Write to .env so the key persists across restarts
    _env_path = BASE_DIR.parent / ".env"
    try:
        with open(_env_path, "a") as f:
            f.write(f"\nENCRYPTION_KEY={ENCRYPTION_KEY}\n")
    except OSError:
        pass
    import logging as _log
    _log.getLogger(__name__).warning(
        "ENCRYPTION_KEY was not set. A new key has been generated and saved to .env. "
        "Back up this key — losing it means all encrypted data becomes unrecoverable."
    )

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# LLM Configuration (just read env vars, no validation yet)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "ollama/llama3")

# App Configuration
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 9004))  # Changed from 8000 to 9002
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Yerevan")

# Deterministic R5 title-match aliases.  They are deliberately config rather
# than scoring-code constants so the curated vocabulary can evolve without
# changing the matching algorithm.
TITLE_MATCH_ALIASES = {
    "software engineer": ("swe", "software developer", "software development engineer"),
    "data scientist": ("data science specialist",),
}

# R5 deterministic composite scoring.  Keep these as application configuration
# rather than request parameters: a stored score records a fingerprint of this
# vocabulary and weighting, so old search results remain explainable.
JOB_SCORING_WEIGHTS = {
    "title_similarity": 0.60,
    "skills_overlap": 0.40,
}
SKILL_MATCH_ALIASES = {
    "amazon web services": ("aws",),
    "artificial intelligence": ("ai",),
    "continuous delivery": ("cd",),
    "continuous integration": ("ci",),
    "google cloud platform": ("gcp", "google cloud"),
    "javascript": ("js", "ecmascript"),
    "machine learning": ("ml",),
    "microsoft azure": ("azure",),
    "node js": ("node", "nodejs"),
    "postgresql": ("postgres", "psql"),
    "react": ("react js", "reactjs"),
    "typescript": ("ts",),
}

# R5's LLM stage is deliberately opt-in and bounded.  The deterministic score
# remains the default ordering even when these refinements are available.
JOB_LLM_REFINEMENT_TOP_N = int(os.getenv("JOB_LLM_REFINEMENT_TOP_N", "20"))
JOB_LLM_REFINEMENT_PROMPT_VERSION = "r5-llm-refinement-v1"

# LLM Timeouts (seconds) - prevents hangs when LLM is slow/unresponsive
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT", "120"))       # 2 min for most LLM calls
LLM_CHAT_TIMEOUT_SECONDS = int(os.getenv("LLM_CHAT_TIMEOUT", "180"))  # 3 min for interactive chat

# Playwright
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

# Queue Backend
QUEUE_BACKEND = os.getenv("QUEUE_BACKEND", "thread")
REDIS_URL = os.getenv("REDIS_URL")

# Anti-Detection Defaults
class AntiDetectionConfig:
    """Conservative rate limiting defaults"""
    LINKEDIN_DELAY_BETWEEN_REQUESTS = (8, 15)
    LINKEDIN_MAX_REQUESTS_PER_HOUR = 20
    LINKEDIN_MAX_REQUESTS_PER_DAY = 100
    GLASSDOOR_DELAY_BETWEEN_REQUESTS = (10, 20)
    GLASSDOOR_MAX_REQUESTS_PER_HOUR = 10
    GLASSDOOR_MAX_REQUESTS_PER_DAY = 50
    OPERATING_HOURS_START = 8
    OPERATING_HOURS_END = 22
    COOLDOWN_ON_FAILURE_MINUTES = 60
    COOLDOWN_ON_CAPTCHA_MINUTES = 120
