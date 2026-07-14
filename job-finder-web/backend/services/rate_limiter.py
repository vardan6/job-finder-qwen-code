"""
SQLite-backed Rate Limiter - Persistent across restarts

Ultra-conservative rate limiting to protect accounts:
- LinkedIn: 8-15s delay, max 20/hour, 100/day
- Glassdoor: 10-20s delay, max 10/hour, 50/day
- Operating hours: 8 AM - 10 PM only
- Cooldown on failure: 60 min
- Cooldown on CAPTCHA: 120 min
"""
import logging
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# Ultra-conservative rate limits
RATE_LIMITS = {
    "linkedin": {
        "delay_between_requests": (8, 15),  # seconds
        "max_requests_per_hour": 20,
        "max_requests_per_day": 100,
    },
    "glassdoor": {
        "delay_between_requests": (10, 20),  # seconds
        "max_requests_per_hour": 10,
        "max_requests_per_day": 50,
    },
}

OPERATING_HOURS_START = 8  # 8 AM
OPERATING_HOURS_END = 22   # 10 PM

COOLDOWN_ON_FAILURE_MINUTES = 60
COOLDOWN_ON_CAPTCHA_MINUTES = 120  # 2 hours


class RateLimiter:
    """SQLite-backed rate limiter for job platform scraping"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            from backend.config import DATA_DIR
            self.db_path = DATA_DIR / "rate_limits.db"
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    @contextmanager
    def _db(self):
        """Context manager for database connections"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize rate limit tracking tables"""
        with self._db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    reason TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL UNIQUE,
                    until DATETIME NOT NULL,
                    reason TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_counts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    date DATE NOT NULL,
                    count INTEGER DEFAULT 0,
                    UNIQUE(platform, date)
                )
            """)
            # Index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_log_platform_time 
                ON request_log(platform, timestamp)
            """)
            logger.debug(f"Rate limiter DB initialized at {self.db_path}")
    
    def log_request(self, platform: str, success: bool = True, reason: Optional[str] = None):
        """Log a request attempt"""
        with self._db() as conn:
            conn.execute(
                "INSERT INTO request_log (platform, timestamp, success, reason) VALUES (?, ?, ?, ?)",
                (platform, datetime.now().isoformat(), 1 if success else 0, reason)
            )
            logger.debug(f"Logged {platform} request: success={success}, reason={reason}")
    
    def set_cooldown(self, platform: str, minutes: int, reason: str):
        """Set a cooldown period for a platform"""
        until = datetime.now() + timedelta(minutes=minutes)
        with self._db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cooldowns (platform, until, reason) 
                   VALUES (?, ?, ?)""",
                (platform, until.isoformat(), reason)
            )
            logger.warning(f"Set {platform} cooldown until {until}: {reason}")
    
    def get_cooldown_remaining(self, platform: str) -> Optional[int]:
        """Get remaining cooldown seconds, or None if no cooldown"""
        with self._db() as conn:
            cursor = conn.execute(
                "SELECT until, reason FROM cooldowns WHERE platform = ?",
                (platform,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            until = datetime.fromisoformat(row["until"])
            now = datetime.now()
            
            if now >= until:
                # Cooldown expired, remove it
                conn.execute("DELETE FROM cooldowns WHERE platform = ?", (platform,))
                return None
            
            remaining = int((until - now).total_seconds())
            logger.debug(f"{platform} cooldown: {remaining}s remaining ({row['reason']})")
            return remaining
    
    def get_request_count(self, platform: str, window: str) -> int:
        """Get request count for a time window ('hour' or 'day')"""
        with self._db() as conn:
            if window == "hour":
                cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
            elif window == "day":
                cutoff = (datetime.now() - timedelta(days=1)).isoformat()
            else:
                raise ValueError(f"Invalid window: {window}")
            
            cursor = conn.execute(
                """SELECT COUNT(*) FROM request_log 
                   WHERE platform = ? AND timestamp > ?""",
                (platform, cutoff)
            )
            count = cursor.fetchone()[0]
            return count
    
    def get_daily_count(self, platform: str) -> int:
        """Get today's request count"""
        today = datetime.now().date().isoformat()
        with self._db() as conn:
            cursor = conn.execute(
                "SELECT count FROM daily_counts WHERE platform = ? AND date = ?",
                (platform, today)
            )
            row = cursor.fetchone()
            return row["count"] if row else 0
    
    def increment_daily_count(self, platform: str):
        """Increment today's request count"""
        today = datetime.now().date().isoformat()
        with self._db() as conn:
            conn.execute(
                """INSERT INTO daily_counts (platform, date, count) 
                   VALUES (?, ?, 1)
                   ON CONFLICT(platform, date) DO UPDATE SET count = count + 1""",
                (platform, today)
            )
    
    def check_rate_limit(self, platform: str) -> Tuple[bool, str]:
        """
        Check if we can make a request to the platform.
        Returns (allowed, reason) tuple.
        """
        # Check cooldown first
        cooldown_remaining = self.get_cooldown_remaining(platform)
        if cooldown_remaining:
            return False, f"Cooldown active ({cooldown_remaining}s remaining)"
        
        # Check operating hours
        now = datetime.now()
        if now.hour < OPERATING_HOURS_START or now.hour >= OPERATING_HOURS_END:
            return False, f"Outside operating hours ({OPERATING_HOURS_START}:00-{OPERATING_HOURS_END}:00)"
        
        # Check hourly limit
        hourly_count = self.get_request_count(platform, "hour")
        hourly_limit = RATE_LIMITS.get(platform, {}).get("max_requests_per_hour", 20)
        if hourly_count >= hourly_limit:
            return False, f"Hourly limit reached ({hourly_count}/{hourly_limit})"
        
        # Check daily limit
        daily_count = self.get_daily_count(platform)
        daily_limit = RATE_LIMITS.get(platform, {}).get("max_requests_per_day", 100)
        if daily_count >= daily_limit:
            return False, f"Daily limit reached ({daily_count}/{daily_limit})"
        
        # Check delay between requests
        last_request = self._get_last_request_time(platform)
        if last_request:
            delay_range = RATE_LIMITS.get(platform, {}).get("delay_between_requests", (8, 15))
            min_delay = delay_range[0]
            elapsed = (datetime.now() - last_request).total_seconds()
            if elapsed < min_delay:
                wait_time = int(min_delay - elapsed) + 1
                return False, f"Rate limit delay ({wait_time}s)"
        
        return True, "OK"
    
    def _get_last_request_time(self, platform: str) -> Optional[datetime]:
        """Get timestamp of last request"""
        with self._db() as conn:
            cursor = conn.execute(
                """SELECT timestamp FROM request_log 
                   WHERE platform = ? 
                   ORDER BY timestamp DESC LIMIT 1""",
                (platform,)
            )
            row = cursor.fetchone()
            if row:
                return datetime.fromisoformat(row["timestamp"])
            return None
    
    def get_next_allowed_time(self, platform: str) -> Optional[datetime]:
        """Get the next time a request will be allowed"""
        # Check cooldown
        cooldown_remaining = self.get_cooldown_remaining(platform)
        if cooldown_remaining:
            return datetime.now() + timedelta(seconds=cooldown_remaining)
        
        # Check operating hours
        now = datetime.now()
        if now.hour >= OPERATING_HOURS_END:
            # Next day at OPERATING_HOURS_START
            tomorrow = now.replace(hour=OPERATING_HOURS_START, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return tomorrow
        elif now.hour < OPERATING_HOURS_START:
            # Today at OPERATING_HOURS_START
            return now.replace(hour=OPERATING_HOURS_START, minute=0, second=0, microsecond=0)
        
        # Check hourly limit
        hourly_count = self.get_request_count(platform, "hour")
        hourly_limit = RATE_LIMITS.get(platform, {}).get("max_requests_per_hour", 20)
        if hourly_count >= hourly_limit:
            # Find when the oldest request in the hour window expires
            cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
            with self._db() as conn:
                cursor = conn.execute(
                    """SELECT timestamp FROM request_log 
                       WHERE platform = ? AND timestamp > ?
                       ORDER BY timestamp ASC LIMIT 1""",
                    (platform, cutoff)
                )
                row = cursor.fetchone()
                if row:
                    oldest = datetime.fromisoformat(row["timestamp"])
                    return oldest + timedelta(hours=1)
        
        # Check daily limit
        daily_count = self.get_daily_count(platform)
        daily_limit = RATE_LIMITS.get(platform, {}).get("max_requests_per_day", 100)
        if daily_count >= daily_limit:
            # Tomorrow at OPERATING_HOURS_START
            tomorrow = now.replace(hour=OPERATING_HOURS_START, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return tomorrow
        
        # Check delay between requests
        last_request = self._get_last_request_time(platform)
        if last_request:
            delay_range = RATE_LIMITS.get(platform, {}).get("delay_between_requests", (8, 15))
            min_delay = delay_range[0]
            elapsed = (datetime.now() - last_request).total_seconds()
            if elapsed < min_delay:
                return last_request + timedelta(seconds=min_delay)
        
        return None
    
    def get_status(self, platform: str) -> dict:
        """Get current rate limit status for a platform"""
        allowed, reason = self.check_rate_limit(platform)
        next_time = self.get_next_allowed_time(platform) if not allowed else None
        
        return {
            "platform": platform,
            "allowed": allowed,
            "reason": reason,
            "next_allowed": next_time.isoformat() if next_time else None,
            "hourly_count": f"{self.get_request_count(platform, 'hour')}/{RATE_LIMITS.get(platform, {}).get('max_requests_per_hour', 20)}",
            "daily_count": f"{self.get_daily_count(platform)}/{RATE_LIMITS.get(platform, {}).get('max_requests_per_day', 100)}",
            "cooldown_remaining": self.get_cooldown_remaining(platform),
        }
    
    def _get_wait_time(self, platform: str) -> float:
        """Return how many seconds to wait before the next request, or 0 if no wait needed."""
        last_request = self._get_last_request_time(platform)
        if last_request:
            delay_range = RATE_LIMITS.get(platform, {}).get("delay_between_requests", (8, 15))
            min_delay, max_delay = delay_range
            elapsed = (datetime.now() - last_request).total_seconds()
            if elapsed < min_delay:
                actual_delay = random.uniform(min_delay, max_delay)
                return max(0.0, actual_delay - elapsed)
        return 0.0

    def wait_if_needed(self, platform: str) -> bool:
        """
        Wait the required delay if needed (synchronous). Returns True if waited.
        Use check_rate_limit() first to ensure request is allowed.
        NOTE: Do not call from async code — use async_wait_if_needed() instead.
        """
        wait_time = self._get_wait_time(platform)
        if wait_time > 0:
            import time as _time
            logger.info(f"Waiting {wait_time:.1f}s for {platform} rate limit...")
            _time.sleep(wait_time)
            return True
        return False

    async def async_wait_if_needed(self, platform: str) -> bool:
        """
        Async-safe version of wait_if_needed(). Uses asyncio.sleep() to avoid
        blocking the event loop. Call from async scrapers/services.
        """
        import asyncio
        wait_time = self._get_wait_time(platform)
        if wait_time > 0:
            logger.info(f"Waiting {wait_time:.1f}s for {platform} rate limit...")
            await asyncio.sleep(wait_time)
            return True
        return False
    
    def record_failure(self, platform: str, reason: str):
        """Record a failed request and potentially set cooldown"""
        self.log_request(platform, success=False, reason=reason)
        
        # Set cooldown for serious failures
        if any(keyword in reason.lower() for keyword in ["captcha", "blocked", "ban", "suspicious"]):
            self.set_cooldown(platform, COOLDOWN_ON_CAPTCHA_MINUTES, f"Failure detected: {reason}")
        elif "rate limit" in reason.lower():
            self.set_cooldown(platform, COOLDOWN_ON_FAILURE_MINUTES, f"Rate limit hit: {reason}")
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up request logs older than specified days"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._db() as conn:
            conn.execute("DELETE FROM request_log WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM daily_counts WHERE date < ?", (datetime.now().date().isoformat(),))
            logger.info(f"Cleaned up rate limit data older than {days} days")


# Global instance (lazy initialization)
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
