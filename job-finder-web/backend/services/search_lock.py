"""
File-based Global Search Lock

Ensures only one job search runs at a time across the entire application.
Prevents resource contention and reduces detection risk.
"""
import fcntl
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GlobalSearchLock:
    """
    File-based lock to ensure only one search runs at a time.
    Uses flock for cross-process locking.
    """
    
    def __init__(self, lock_file: str = "data/search.lock"):
        self.lock_file = Path(lock_file)
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_fd: Optional[int] = None
        self._locked = False
    
    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the global search lock.
        
        Args:
            blocking: If True, wait for lock. If False, return immediately.
        
        Returns:
            True if lock acquired, False otherwise.
        """
        try:
            self._lock_fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT)
            
            flags = fcntl.LOCK_EX  # Exclusive lock
            if not blocking:
                flags |= fcntl.LOCK_NB  # Non-blocking
            
            fcntl.flock(self._lock_fd, flags)
            self._locked = True
            
            # Write lock info
            lock_info = f"Locked at {datetime.now().isoformat()}\nPID: {os.getpid()}\n"
            os.ftruncate(self._lock_fd, 0)
            os.write(self._lock_fd, lock_info.encode())
            
            logger.info("Global search lock acquired")
            return True
            
        except BlockingIOError:
            # Non-blocking and lock is held
            os.close(self._lock_fd)
            self._lock_fd = None
            logger.debug("Global search lock is held by another process")
            return False
        except Exception as e:
            logger.error(f"Failed to acquire global search lock: {e}")
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            return False
    
    def release(self):
        """Release the global search lock"""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                logger.info("Global search lock released")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
            finally:
                self._lock_fd = None
                self._locked = False
    
    def is_locked(self) -> bool:
        """Check if we currently hold the lock"""
        return self._locked
    
    def is_locked_by_other(self) -> bool:
        """Check if lock is held by another process"""
        if self._locked:
            return False
        
        try:
            lock_fd = os.open(str(self.lock_file), os.O_RDWR)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # We got the lock, so it wasn't held
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                return False
            except BlockingIOError:
                # Lock is held by another process
                return True
            finally:
                os.close(lock_fd)
        except FileNotFoundError:
            # No lock file exists
            return False
        except Exception as e:
            logger.error(f"Error checking lock status: {e}")
            return False
    
    def get_lock_info(self) -> Optional[dict]:
        """Get information about the current lock"""
        if not self.lock_file.exists():
            return None
        
        try:
            content = self.lock_file.read_text()
            info = {}
            for line in content.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            return info
        except Exception as e:
            logger.error(f"Error reading lock info: {e}")
            return None
    
    def __enter__(self):
        """Context manager entry"""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - always release lock"""
        self.release()
        return False  # Don't suppress exceptions


# Global instance
_search_lock: Optional[GlobalSearchLock] = None


def get_search_lock() -> GlobalSearchLock:
    """Get or create the global search lock instance"""
    global _search_lock
    if _search_lock is None:
        _search_lock = GlobalSearchLock()
    return _search_lock


def is_search_running() -> bool:
    """Convenience function to check if a search is currently running"""
    lock = get_search_lock()
    return lock.is_locked() or lock.is_locked_by_other()
