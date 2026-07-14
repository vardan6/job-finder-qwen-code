"""
Tests for search_lock.py

Uses temporary directories so tests don't touch the real data/ folder.
"""
import json
import os
import time
import pytest

from backend.services.search_lock import GlobalSearchLock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_lock(tmp_path) -> GlobalSearchLock:
    """Return a GlobalSearchLock backed by a temp directory."""
    return GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))


# ---------------------------------------------------------------------------
# Basic acquire / release
# ---------------------------------------------------------------------------

class TestAcquireRelease:
    def test_acquire_non_blocking_succeeds_when_free(self, tmp_path):
        lock = make_lock(tmp_path)
        assert lock.acquire(blocking=False) is True
        lock.release()

    def test_double_acquire_non_blocking_fails(self, tmp_path):
        lock1 = make_lock(tmp_path)
        lock2 = make_lock(tmp_path)
        assert lock1.acquire(blocking=False) is True
        # A second instance (different fd) should fail to acquire non-blocking
        assert lock2.acquire(blocking=False) is False
        lock1.release()

    def test_release_unlocks(self, tmp_path):
        lock1 = make_lock(tmp_path)
        lock2 = make_lock(tmp_path)
        lock1.acquire(blocking=False)
        lock1.release()
        # After release, another instance should be able to acquire
        assert lock2.acquire(blocking=False) is True
        lock2.release()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_context_manager_acquires_and_releases(self, tmp_path):
        lock = make_lock(tmp_path)
        with lock:
            assert lock.is_locked() is True
        assert lock.is_locked() is False

    def test_context_manager_releases_on_exception(self, tmp_path):
        lock = make_lock(tmp_path)
        try:
            with lock:
                raise ValueError("simulated error")
        except ValueError:
            pass
        # Lock must be released even though an exception was raised
        assert lock.is_locked() is False

        # Another lock should be able to acquire now
        lock2 = make_lock(tmp_path)
        assert lock2.acquire(blocking=False) is True
        lock2.release()


# ---------------------------------------------------------------------------
# _get_lock_age_minutes / _is_stale
# ---------------------------------------------------------------------------

class TestStalenessDetection:
    def test_no_lock_file_is_not_stale(self, tmp_path):
        lock = make_lock(tmp_path)
        assert lock._is_stale() is False

    def test_fresh_lock_is_not_stale(self, tmp_path):
        lock = make_lock(tmp_path)
        lock.acquire(blocking=False)
        assert lock._is_stale(max_age_minutes=60) is False
        lock.release()

    def test_old_lock_file_is_stale(self, tmp_path):
        """A lock file with an old mtime (faked via os.utime) is stale."""
        lock = make_lock(tmp_path)
        lock.lock_file.write_text("old lock content")

        # Set mtime to 3 hours ago
        old_time = time.time() - 3 * 3600
        os.utime(str(lock.lock_file), (old_time, old_time))

        assert lock._is_stale(max_age_minutes=60) is True

    def test_get_lock_age_returns_none_when_no_file(self, tmp_path):
        lock = make_lock(tmp_path)
        assert lock._get_lock_age_minutes() is None


# ---------------------------------------------------------------------------
# acquire_with_timeout
# ---------------------------------------------------------------------------

class TestAcquireWithTimeout:
    def test_acquire_with_timeout_succeeds_when_free(self, tmp_path):
        lock = make_lock(tmp_path)
        assert lock.acquire_with_timeout(timeout_seconds=5) is True
        lock.release()

    def test_acquire_with_timeout_fails_when_held(self, tmp_path):
        """If the lock is held by another instance, acquire_with_timeout gives up."""
        lock1 = make_lock(tmp_path)
        lock2 = make_lock(tmp_path)

        lock1.acquire(blocking=False)
        # Very short timeout — should give up quickly
        result = lock2.acquire_with_timeout(timeout_seconds=1)
        assert result is False
        lock1.release()
