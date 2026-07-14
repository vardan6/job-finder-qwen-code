"""
Scraper Health Monitor

Tracks per-platform scraping outcomes to surface persistent failures early.
Data is stored in data/scraper_health.json and updated after every search run.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from backend.config import DATA_DIR

HEALTH_FILE = DATA_DIR / "scraper_health.json"
# After this many consecutive zero-result searches, log an error-level alert
ZERO_STREAK_ALERT_THRESHOLD = 2


def _load() -> Dict:
    """Load health data from disk, returning empty structure on any error."""
    try:
        if HEALTH_FILE.exists():
            return json.loads(HEALTH_FILE.read_text())
    except Exception as e:
        logger.warning(f"Could not read scraper health file: {e}")
    return {}


def _save(data: Dict) -> None:
    """Persist health data to disk."""
    try:
        HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        HEALTH_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning(f"Could not write scraper health file: {e}")


def record_search_result(platform: str, result_count: int, captcha_detected: bool = False) -> None:
    """
    Record the outcome of a scraping run for a platform.

    Emits a warning if zero results are returned, and escalates to an error
    if zero-result runs exceed ZERO_STREAK_ALERT_THRESHOLD.
    """
    data = _load()
    entry = data.get(platform, {})

    prev_zero_streak = entry.get("consecutive_zero_count", 0)
    new_zero_streak = prev_zero_streak + 1 if result_count == 0 else 0

    entry.update({
        "last_search_timestamp": datetime.now().isoformat(),
        "last_result_count": result_count,
        "consecutive_zero_count": new_zero_streak,
        "total_searches": entry.get("total_searches", 0) + 1,
    })
    if captcha_detected:
        entry["last_captcha_timestamp"] = datetime.now().isoformat()

    data[platform] = entry
    _save(data)

    # Emit health log messages
    if result_count == 0:
        if new_zero_streak >= ZERO_STREAK_ALERT_THRESHOLD:
            logger.error(
                f"[HEALTH] {platform}: {new_zero_streak} consecutive searches returned 0 results. "
                "Possible causes: CAPTCHA, login wall, DOM selector change, or IP block. "
                "Check logs and review scraper selectors."
            )
        else:
            logger.warning(
                f"[HEALTH] {platform}: 0 results returned. "
                "Possible causes: CAPTCHA, login wall, rate limit, or no matches for query."
            )
    elif prev_zero_streak > 0:
        logger.info(f"[HEALTH] {platform}: Scraper recovered — {result_count} results after {prev_zero_streak} zero-result run(s).")


def get_health_summary() -> Dict:
    """Return health data for all tracked platforms, enriched with status flags."""
    data = _load()
    summary = {}
    for platform, entry in data.items():
        zero_streak = entry.get("consecutive_zero_count", 0)
        summary[platform] = {
            **entry,
            "status": (
                "error" if zero_streak >= ZERO_STREAK_ALERT_THRESHOLD
                else "warning" if zero_streak > 0
                else "ok"
            ),
        }
    return summary


def get_platform_health(platform: str) -> Optional[Dict]:
    """Return health data for a single platform, or None if never scraped."""
    data = _load()
    entry = data.get(platform)
    if entry is None:
        return None
    zero_streak = entry.get("consecutive_zero_count", 0)
    return {
        **entry,
        "status": (
            "error" if zero_streak >= ZERO_STREAK_ALERT_THRESHOLD
            else "warning" if zero_streak > 0
            else "ok"
        ),
    }
