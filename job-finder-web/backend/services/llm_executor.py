"""
Dedicated Thread Pool for LLM Operations

This module provides a separate ThreadPoolExecutor exclusively for LLM calls,
isolating them from the default thread pool used by FastAPI's asyncio.to_thread().

This prevents LLM operations (which can take 30-180 seconds) from starving
other async operations that need the default thread pool.
"""
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Dedicated thread pool for LLM operations
# - max_workers=8 allows multiple concurrent LLM calls without blocking the app
# - This is separate from Python's default thread pool used by asyncio.to_thread()
llm_executor = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="llm-worker"
)


def get_llm_executor() -> ThreadPoolExecutor:
    """Get the dedicated LLM thread pool executor."""
    return llm_executor


def shutdown_llm_executor():
    """Shutdown the LLM thread pool gracefully."""
    logger.info("Shutting down LLM thread pool...")
    llm_executor.shutdown(wait=True)
    logger.info("LLM thread pool shut down complete")
