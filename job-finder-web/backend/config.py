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

# Ensure data directories exist (quick check)
for subdir in ["candidates", "cookies", "backups", "archive"]:
    dir_path = DATA_DIR / subdir
    if not dir_path.exists():
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except:
            pass

# Security
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Auto-generate encryption key if missing (first-run only)
if not ENCRYPTION_KEY:
    try:
        from cryptography.fernet import Fernet
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        print("=" * 60)
        print("⚠️  AUTO-GENERATED ENCRYPTION KEY (FIRST RUN)")
        print("=" * 60)
        print(f"ENCRYPTION_KEY={ENCRYPTION_KEY}")
        print("=" * 60)
        print("📝 Add this to your .env file to persist it:")
        print(f"   ENCRYPTION_KEY={ENCRYPTION_KEY}")
        print("=" * 60)
    except Exception as e:
        print(f"❌ CRITICAL: Cannot generate encryption key: {e}")
        ENCRYPTION_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # Dummy key to prevent crash

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# LLM Configuration (just read env vars, no validation yet)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "ollama/llama3")

# App Configuration
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 9002))  # Changed from 8000 to 9002
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Yerevan")

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
