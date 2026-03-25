# Non-Blocking LLM Implementation

## Problem

LLM calls (Ollama, NVIDIA, OpenAI, etc.) are **synchronous and blocking** operations that can take 30-90 seconds. When these calls run in the main FastAPI event loop, they:

- **Block all other requests** - Other pages become unresponsive
- **Cause timeout errors** - HTMX requests may timeout
- **Create poor UX** - Users can't navigate or interact with the app

## Solution: Thread Pool Executor

We use Python's `concurrent.futures.ThreadPoolExecutor` via FastAPI's `asyncio.run_in_executor()` to run LLM calls in background threads.

### How It Works

```python
# BEFORE (blocking)
@router.post("/parse")
async def parse_something():
    result = call_llm(db, model, prompt)  # ❌ Blocks event loop
    return {"result": result}

# AFTER (non-blocking)
@router.post("/parse")
async def parse_something():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # Use default thread pool
        lambda: call_llm(db, model, prompt)  # ✅ Runs in background thread
    )
    return {"result": result}
```

### Benefits

✅ **Other requests processed** - Event loop remains free to handle other users/pages  
✅ **No timeout errors** - Background thread can take as long as needed  
✅ **Better UX** - Users can navigate away, check status, or start other tasks  
✅ **Concurrent LLM calls** - Multiple LLM requests can run in parallel (up to thread pool limit)

## Files Modified

### 1. Core Services

| File | Changes |
|------|---------|
| `backend/services/llm_service.py` | Added `call_llm_async()`, `extract_skills_from_text_async()` |
| `backend/services/job_title_parser.py` | Added async wrappers for all parse functions |
| `backend/services/document_parser.py` | Added `parse_document_content_async()` |
| `backend/utils/async_llm_helper.py` | **NEW** - Centralized async helpers |

### 2. Routes

| File | Changes |
|------|---------|
| `backend/routes/chat.py` | Updated `/api/chat` to use `run_in_executor` |
| `backend/routes/skills.py` | Updated `/parse` to use `extract_skills_from_text_async()` |
| `backend/routes/candidate_parser.py` | Updated `/parse-job-titles` to use async parse functions |

## Thread Pool Configuration

The default thread pool allows **10 concurrent LLM calls**:

```python
# backend/utils/async_llm_helper.py
_llm_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="llm_worker")
```

This means:
- Up to 10 LLM requests can run simultaneously
- Additional requests queue up (don't block the event loop)
- Prevents resource exhaustion from too many concurrent LLM calls

## Usage Examples

### Example 1: Chat Route

```python
from backend.routes.chat import chat

# The chat endpoint now uses:
loop = asyncio.get_event_loop()
response = await loop.run_in_executor(
    None,
    lambda: completion(**kwargs)  # LiteLLM call in background
)
```

### Example 2: Skills Parsing

```python
from backend.services.llm_service import extract_skills_from_text_async

# In your route:
@router.post("/parse")
async def parse_skills():
    skills = await extract_skills_from_text_async(content, db)
    return {"skills": skills}
```

### Example 3: Job Title Parsing

```python
from backend.services.job_title_parser import parse_all_candidate_documents_async

# In your route:
@router.post("/parse-job-titles")
async def parse_job_titles(candidate_id: int):
    success, titles, error = await parse_all_candidate_documents_async(db, candidate_id)
    return {"job_titles": titles}
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Event Loop                        │
│  (Handles HTTP requests, responses, routing)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├─ Request 1: Chat → Queue to Thread Pool
                            ├─ Request 2: Parse Skills → Queue to Thread Pool
                            ├─ Request 3: Parse Job Titles → Queue to Thread Pool
                            ├─ Request 4: Dashboard → Processed immediately ✅
                            └─ Request 5: Candidate List → Processed immediately ✅
                            │
                            ▼
                ┌──────────────────────────┐
                │   ThreadPoolExecutor     │
                │   (max_workers=10)       │
                │                          │
                │  Thread 1: LLM Call 1    │
                │  Thread 2: LLM Call 2    │
                │  Thread 3: LLM Call 3    │
                │  ...                     │
                │  Thread 10: LLM Call 10  │
                └──────────────────────────┘
                            │
                            ▼
                  LLM API (Ollama, NVIDIA, etc.)
                  (30-90 seconds response time)
```

## Testing

### Test Concurrent Requests

1. Start the app: `python run.py`
2. Open two browser tabs:
   - Tab 1: Go to a candidate page and click "Parse from Files" (takes 30-90s)
   - Tab 2: Navigate to Dashboard, Settings, other candidates
3. **Expected**: Tab 2 loads instantly while Tab 1 is processing

### Test Chat Non-Blocking

1. Open AI Chat page
2. Send a message (takes 5-30s depending on model)
3. While waiting, open another tab and navigate to any page
4. **Expected**: Other pages load instantly

## Migration Guide

### For Existing Code

If you have routes that call LLM functions directly:

**Before:**
```python
from backend.services.llm_service import call_llm

@router.post("/analyze")
async def analyze():
    result = call_llm(db, model, prompt)  # Blocking!
    return {"result": result}
```

**After:**
```python
from backend.services.llm_service import call_llm_async

@router.post("/analyze")
async def analyze():
    result = await call_llm_async(db, model, prompt)  # Non-blocking!
    return {"result": result}
```

### For New Code

Always use the `_async` versions:
- `call_llm_async()` instead of `call_llm()`
- `extract_skills_from_text_async()` instead of `extract_skills_from_text()`
- `parse_all_candidate_documents_async()` instead of `parse_all_candidate_documents()`

## Limitations

1. **Database Session Thread Safety**: SQLAlchemy sessions are passed to threads. This works because:
   - We use SQLite with proper isolation
   - Each request gets its own session via `Depends(get_db)`
   - Threads complete before the request ends

2. **Thread Pool Size**: Limited to 10 concurrent LLM calls. If you need more:
   - Adjust `max_workers` in `async_llm_helper.py`
   - Consider Redis queue for heavy workloads (Phase 5)

3. **Not True Async**: LiteLLM doesn't support native async, so we use threads. For true async:
   - Would require async HTTP client (aiohttp)
   - LiteLLM would need async support
   - Future enhancement if needed

## Future Enhancements (Phase 5)

For production deployment with high concurrency:

1. **Celery + Redis Queue**
   - Offload LLM jobs to background workers
   - Progress tracking via WebSocket
   - Retry logic for failed calls

2. **WebSocket Progress Updates**
   - Real-time progress during parsing
   - "Your job is 50% complete..."
   - Cancel long-running jobs

3. **Request Prioritization**
   - User-facing requests (chat) get priority
   - Background parsing runs at lower priority

## References

- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Python ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)
- [Asyncio run_in_executor](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor)

---

**Implementation Date:** March 25, 2026  
**Status:** ✅ Complete  
**Tested:** Pending user verification
