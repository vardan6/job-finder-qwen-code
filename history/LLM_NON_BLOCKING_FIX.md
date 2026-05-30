# LLM Non-Blocking Fix - Dedicated Thread Pool

**Date:** April 10, 2026  
**Issue:** LLM operations were hanging the entire web application  
**Status:** ✅ FIXED

---

## Problem

When any LLM-related functionality was running (AI parsing, chat, testing connections), the entire web application would hang for all users. This made the app unusable during LLM operations.

### Root Cause

The code was using `asyncio.to_thread()` which relies on Python's **default thread pool**. This pool is shared across ALL async operations in FastAPI. When LLM calls (which can take 30-180 seconds) occupied threads in this pool, other requests (dashboard, candidates, health checks) would queue up waiting for available threads, causing the app to appear "hung".

---

## Solution

Created a **dedicated ThreadPoolExecutor** exclusively for LLM operations, isolating them from the default thread pool used by other application requests.

### Architecture

```
Before (BLOCKED):
┌─────────────────────────────────────────┐
│  Default Thread Pool (shared)           │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ LLM Call │ │ LLM Call │ │ Request │ │ ← All competing for same threads
│  │ (120s)   │ │ (120s)   │ │ (0.2s)  │ │
│  └──────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────────────────┘
         ↓ Requests queue and hang!

After (NON-BLOCKING):
┌──────────────────────┐  ┌──────────────────────┐
│  LLM Thread Pool     │  │  Default Thread Pool  │
│  (8 workers)         │  │  (for all requests)   │
│  ┌────────┐ ┌──────┐│  │  ┌─────────┐ ┌─────┐ │
│  │ LLM    │ │ LLM  ││  │  │ Request │ │ DB  │ │ ← Isolated, no contention
│  │ (120s) │ │(120s)││  │  │ (0.2s)  │ │(0.1s│ │
│  └────────┘ └──────┘│  │  └─────────┘ └─────┘ │
└──────────────────────┘  └──────────────────────┘
```

---

## Changes Made

### 1. New File: `backend/services/llm_executor.py`
- Creates dedicated `ThreadPoolExecutor(max_workers=8)` for LLM operations
- Provides `get_llm_executor()` function to access the pool
- Provides `shutdown_llm_executor()` for graceful shutdown

### 2. Updated: `backend/services/llm_service.py`
- Modified `_threaded_completion()` to use dedicated LLM executor
- Changed from `asyncio.to_thread()` to `loop.run_in_executor(dedicated_pool, ...)`
- Updated docstring to reflect the change

### 3. Updated: `backend/routes/llm_test.py`
- Removed local `ThreadPoolExecutor(max_workers=4)`
- Now uses shared dedicated LLM executor (8 workers)
- Added explicit 120-second timeout with `asyncio.wait_for()`

### 4. Updated: `backend/routes/llm_config.py`
- Changed `test_llm_provider()` from `asyncio.to_thread()` to dedicated executor
- Added explicit 120-second timeout
- Improved Ollama health check error handling

### 5. Updated: `backend/app.py`
- Added LLM executor initialization logging on startup
- Added LLM executor shutdown in `shutdown_event()`
- Logs thread pool size on startup

---

## Technical Details

### Thread Pool Configuration

| Pool | Workers | Purpose |
|------|---------|---------|
| **LLM Pool** | 8 | Dedicated to LLM calls only |
| **Default Pool** | Python default (CPU cores × 5) | All other async operations |

### Timeout Configuration

| Operation | Timeout | Location |
|-----------|---------|----------|
| Standard LLM calls | 120s | `LLM_TIMEOUT_SECONDS` in config |
| Chat interactions | 180s | `LLM_CHAT_TIMEOUT_SECONDS` in config |
| LLM test endpoint | 120s | Hardcoded in `llm_test.py` |
| LLM config test | 120s | Hardcoded in `llm_config.py` |

### Why 8 Workers?

- Allows multiple concurrent LLM calls without blocking
- Prevents thread pool exhaustion (default is usually CPU cores × 5)
- Sufficient for typical usage patterns (1-3 simultaneous LLM operations)
- Can be adjusted in `llm_executor.py` if needed

---

## Verification

### Before Fix
```
Dashboard during LLM call: 30-120+ seconds (HUNG)
Health check during LLM: 30-120+ seconds (HUNG)
Other requests: Queued indefinitely
```

### After Fix
```
Dashboard during LLM call: 0.2 seconds ✓
Health check during LLM: 0.003 seconds ✓
Other requests: Always responsive ✓
```

### Test Results
```bash
# Concurrent health checks (all fast)
Request 1: 0.004s
Request 2: 0.003s
Request 3: 0.005s
Request 4: 0.005s
Request 5: 0.005s

# Dashboard load time
0.209 seconds ✓
```

---

## How It Works

### Old Flow (BLOCKING)
```python
# In llm_service.py
async def _threaded_completion(timeout, **kwargs):
    return await asyncio.wait_for(
        asyncio.to_thread(_sync_completion, **kwargs),  # ← Uses DEFAULT pool
        timeout=timeout,
    )

# Problem: asyncio.to_thread() uses Python's default executor
# which is shared by ALL async operations in FastAPI
```

### New Flow (NON-BLOCKING)
```python
# In llm_service.py
async def _threaded_completion(timeout, **kwargs):
    from backend.services.llm_executor import get_llm_executor
    
    loop = asyncio.get_event_loop()
    executor = get_llm_executor()  # ← DEDICATED pool
    
    return await asyncio.wait_for(
        loop.run_in_executor(executor, _sync_completion, **kwargs),
        timeout=timeout,
    )

# Solution: Uses separate ThreadPoolExecutor
# LLM operations cannot starve other async operations
```

---

## Benefits

1. **No More Hanging:** Web app remains responsive during all LLM operations
2. **Isolation:** LLM operations cannot block database queries, file I/O, etc.
3. **Scalability:** Can handle multiple concurrent LLM calls without degrading UI
4. **Timeout Protection:** All LLM calls have explicit timeouts to prevent indefinite waits
5. **Graceful Shutdown:** LLM thread pool shuts down cleanly on app exit
6. **Monitoring:** Startup logs show thread pool initialization

---

## Files Modified

| File | Changes | Lines Changed |
|------|---------|---------------|
| `backend/services/llm_executor.py` | **NEW** - Dedicated thread pool | +29 |
| `backend/services/llm_service.py` | Use dedicated executor | ~15 |
| `backend/routes/llm_test.py` | Use dedicated executor + timeout | ~20 |
| `backend/routes/llm_config.py` | Use dedicated executor + timeout | ~15 |
| `backend/app.py` | Add shutdown + logging | ~8 |

**Total:** 5 files, ~87 lines changed/added

---

## Future Improvements

1. **Metrics:** Add monitoring for LLM queue depth and wait times
2. **Dynamic Sizing:** Adjust thread pool size based on load
3. **Request Prioritization:** Prioritize user-facing LLM calls over background tasks
4. **Circuit Breaker:** Temporarily disable LLM calls if provider is down
5. **Queue Limits:** Reject requests when all 8 LLM workers are busy

---

## Rollback Instructions

If issues arise, revert these commits:
```bash
# Check git log for the commit
git log --oneline | grep "LLM.*thread"

# Revert (if needed)
git revert <commit-hash>
```

Or manually:
1. Delete `backend/services/llm_executor.py`
2. Change `asyncio.to_thread()` back in all LLM service files
3. Remove LLM executor imports from `app.py`

---

## References

- [Python ThreadPoolExecutor Docs](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor)
- [FastAPI Async Guidelines](https://fastapi.tiangolo.com/async/)
- [asyncio.run_in_executor](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor)
