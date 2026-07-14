"""
Search Progress Store

In-memory asyncio.Queue store for streaming job search progress to SSE clients.
"""
import asyncio
from typing import Dict, Optional

_progress_queues: Dict[str, asyncio.Queue] = {}


def create_progress_queue(search_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _progress_queues[search_id] = q
    return q


def get_progress_queue(search_id: str) -> Optional[asyncio.Queue]:
    return _progress_queues.get(search_id)


def remove_progress_queue(search_id: str) -> None:
    _progress_queues.pop(search_id, None)
