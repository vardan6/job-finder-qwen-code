"""
Job Routes - Job search, listing, and management
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import DATA_DIR
from backend.models.candidate import Candidate
from backend.models.job import Job
from backend.models.llm_provider import LLMProvider
from backend.security import safe_resolve_path
from backend.services.job_search import run_job_search, SearchConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


@router.get("/", response_class=HTMLResponse)
async def list_jobs(
    request: Request,
    db: Session = Depends(get_db),
    candidate_id: int = None,
    status: str = "active",
):
    """List all jobs with filtering"""
    query = db.query(Job)
    
    if candidate_id:
        query = query.filter(Job.candidate_id == candidate_id)
    
    if status:
        query = query.filter(Job.status == status)
    
    # Order by most recent first
    query = query.order_by(Job.found_at.desc())
    
    jobs = query.all()
    
    # Get candidates for filter dropdown
    candidates = db.query(Candidate).filter(Candidate.is_active == True).all()
    
    return templates.TemplateResponse(
        "jobs/list.html",
        {
            "request": request,
            "jobs": jobs,
            "candidates": candidates,
            "selected_candidate_id": candidate_id,
            "selected_status": status,
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_jobs_form(
    request: Request,
    db: Session = Depends(get_db),
    candidate_id: int = None,
):
    """Show job search form for a candidate"""
    candidates = db.query(Candidate).filter(Candidate.is_active == True).all()
    
    # Get selected candidate
    candidate = None
    if candidate_id:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    return templates.TemplateResponse(
        "jobs/search.html",
        {
            "request": request,
            "candidates": candidates,
            "candidate": candidate,
        },
    )


@router.get("/api/candidates/{candidate_id}/search-config")
async def get_candidate_search_config(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get auto-generated search configuration for a candidate.
    
    Returns search parameters built from candidate's profile:
    - Query: Combined from active job titles
    - Location: From candidate profile
    - Platforms: Only connected/active accounts
    - AI analysis: Based on LLM provider configuration
    """
    # Get candidate
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Build query from active job titles
    job_titles = [jt.title for jt in candidate.job_titles if jt.is_active]
    
    # Fallback to current role if no job titles
    if not job_titles:
        job_titles = [candidate.current_role] if candidate.current_role else ["Software Engineer"]
    
    # Construct query - use comma-separated for broad search
    query = ", ".join(job_titles[:5])  # Limit to 5 titles to avoid URL length issues
    
    # Get location from candidate preferences or default
    location = candidate.location or "United States"
    
    # Get remote-only preference
    remote_only = False
    if candidate.preferences:
        remote_only = candidate.preferences.remote_only or False
    
    # Get connected platforms (only active accounts)
    connected_platforms = []
    platform_status = []
    
    for platform in ["linkedin", "glassdoor"]:
        account = next(
            (acc for acc in candidate.platform_accounts if acc.platform == platform and acc.status == "active"),
            None
        )
        if account:
            connected_platforms.append(platform)
            platform_status.append({
                "platform": platform,
                "connected": True,
                "status": "active",
            })
        else:
            platform_status.append({
                "platform": platform,
                "connected": False,
                "status": "disconnected",
            })
    
    # Default to all platforms if none connected (user will need to connect)
    if not connected_platforms:
        connected_platforms = ["linkedin", "glassdoor"]
    
    # Check if LLM is configured for AI analysis
    llm_configured = db.query(LLMProvider).filter(
        LLMProvider.is_global_default == True
    ).first() is not None
    
    # If no global default, check if any provider has API key
    if not llm_configured:
        llm_configured = db.query(LLMProvider).filter(
            LLMProvider.api_key_encrypted.isnot(None)
        ).first() is not None
    
    # Get skills count for AI analysis info
    enabled_skills = [s for s in candidate.skills if s.is_enabled]
    
    # Get max jobs from preferences or default
    max_jobs = 20
    if candidate.preferences:
        # Could add a max_jobs field to preferences in the future
        pass
    
    # Return HTML partial for HTMX swapping
    return templates.TemplateResponse("jobs/search_config_partial.html", {
        "request": request,
        "candidate_id": candidate_id,
        "candidate_name": candidate.name,
        "query": query,
        "location": location,
        "remote_only": remote_only,
        "platforms": connected_platforms,
        "platform_status": platform_status,
        "max_jobs": max_jobs,
        "analyze_with_ai": llm_configured,
        "llm_configured": llm_configured,
        "job_titles": job_titles,
        "job_titles_count": len(job_titles),
        "skills_count": len(enabled_skills),
        "has_active_platforms": len(connected_platforms) > 0,
    })


@router.post("/search", response_class=HTMLResponse)
async def perform_job_search(
    request: Request,
    db: Session = Depends(get_db),
    candidate_id: int = Form(...),
    query: str = Form(...),
    location: str = Form(""),
    platforms: list = Form(default_factory=lambda: ["linkedin", "glassdoor"]),
    max_jobs: int = Form(20),
    analyze: str = Form("false"),  # Comes as 'true' or 'false' string
    headless: str = Form("false"),  # Comes as 'true' or 'false' string
    remote_only: str = Form("false"),  # Comes as 'true' or 'false' string (for override)
):
    """
    Perform a job search across platforms.

    This is a long-running operation that:
    1. Acquires global search lock
    2. Checks rate limits
    3. Scrapes job platforms
    4. Deduplicates results
    5. Runs AI analysis (if enabled)
    6. Saves to database
    """
    # Parse string booleans
    analyze_bool = analyze.lower() == "true"
    headless_bool = headless.lower() == "true"
    
    # Validate candidate
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return templates.TemplateResponse(
            "components/error.html",
            {
                "request": request,
                "error": f"Candidate {candidate_id} not found",
            },
            status_code=200,
        )

    # Check if search is already running
    from backend.services.search_lock import is_search_running
    if is_search_running():
        return templates.TemplateResponse(
            "components/error.html",
            {
                "request": request,
                "error": "Another job search is already in progress. Please wait.",
            },
            status_code=200,
        )
    
    try:
        # Normalize platforms from form payload (can arrive as string, list, or empty)
        if isinstance(platforms, str):
            platforms = [platforms]
        elif not platforms:
            platforms = ["linkedin", "glassdoor"]
        else:
            platforms = [p for p in platforms if isinstance(p, str) and p.strip()]
            if not platforms:
                platforms = ["linkedin", "glassdoor"]

        logger.info(
            f"Starting job search for candidate {candidate_id}: "
            f"query='{query}', location='{location}', platforms={platforms}, "
            f"analyze={analyze_bool}, headless={headless_bool}"
        )

        # Run the search (async)
        result = await run_job_search(
            db=db,
            candidate_id=candidate_id,
            query=query,
            location=location,
            platforms=platforms,
            max_jobs=max_jobs,
            analyze=analyze_bool,
            headless=headless_bool,
        )
        
        # Prepare result summary
        summary = {
            "success": result.success,
            "total_found": result.total_found,
            "total_unique": result.total_unique,
            "total_duplicates": result.total_duplicates,
            "total_analyzed": result.total_analyzed,
            "jobs_saved": result.jobs_saved,
            "errors": result.errors,
            "platform_results": result.platform_results,
        }
        
        return templates.TemplateResponse(
            "jobs/search_result.html",
            {
                "request": request,
                "candidate": candidate,
                "query": query,
                "result": summary,
            },
        )
        
    except Exception as e:
        logger.error(f"Job search failed: {e}")
        return templates.TemplateResponse(
            "components/error.html",
            {
                "request": request,
                "error": f"Search failed: {str(e)}",
            },
            status_code=200,
        )


@router.post("/search/start")
async def start_job_search_stream(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    candidate_id: int = Form(...),
    query: str = Form(...),
    location: str = Form(""),
    platforms: list = Form(default_factory=lambda: ["linkedin", "glassdoor"]),
    max_jobs: int = Form(20),
    analyze: str = Form("false"),
    headless: str = Form("false"),
):
    """
    Start a job search and return a search_id for SSE progress streaming.
    The client should then connect to /search/stream/{search_id}.
    """
    from backend.services.search_progress import create_progress_queue
    from backend.services.search_lock import is_search_running

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return JSONResponse({"error": f"Candidate {candidate_id} not found"}, status_code=404)

    if is_search_running():
        return JSONResponse({"error": "Another search is already in progress. Please wait."}, status_code=409)

    # Normalize platforms
    if isinstance(platforms, str):
        platforms = [platforms]
    else:
        platforms = [p for p in platforms if isinstance(p, str) and p.strip()] or ["linkedin", "glassdoor"]

    analyze_bool = analyze.lower() == "true"
    headless_bool = headless.lower() == "true"

    search_id = str(uuid.uuid4())
    # Create queue BEFORE the background task starts so the SSE endpoint can connect immediately
    create_progress_queue(search_id)

    background_tasks.add_task(
        _run_search_with_progress,
        search_id,
        candidate_id,
        query,
        location,
        platforms,
        max_jobs,
        analyze_bool,
        headless_bool,
    )

    return JSONResponse({"search_id": search_id})


@router.get("/search/stream/{search_id}")
async def stream_search_progress(search_id: str, request: Request):
    """
    SSE endpoint that streams real-time progress for a running job search.
    Connect immediately after POST /search/start.
    """
    from backend.services.search_progress import get_progress_queue, remove_progress_queue

    # Brief wait in case the background task hasn't registered the queue yet
    queue = get_progress_queue(search_id)
    if not queue:
        await asyncio.sleep(0.3)
        queue = get_progress_queue(search_id)

    if not queue:
        return JSONResponse({"error": "Search not found"}, status_code=404)

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    # SSE keepalive comment (browsers ignore lines starting with ':')
                    yield ": keepalive\n\n"
                    continue

                if msg is None:
                    # Sentinel: search finished
                    yield "data: [DONE]\n\n"
                    break

                if isinstance(msg, dict):
                    yield f"data: {json.dumps(msg)}\n\n"
                else:
                    yield f"data: {json.dumps({'msg': str(msg)})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            remove_progress_queue(search_id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _run_search_with_progress(
    search_id: str,
    candidate_id: int,
    query: str,
    location: str,
    platforms: list,
    max_jobs: int,
    analyze: bool,
    headless: bool,
):
    """Background task: run the search and push progress messages to the SSE queue."""
    from backend.services.search_progress import get_progress_queue
    from backend.database import SessionLocal

    queue = get_progress_queue(search_id)

    def push(msg: str) -> None:
        if queue:
            queue.put_nowait({"msg": msg})

    db = SessionLocal()
    result_dict = None
    try:
        result = await run_job_search(
            db=db,
            candidate_id=candidate_id,
            query=query,
            location=location,
            platforms=platforms,
            max_jobs=max_jobs,
            analyze=analyze,
            headless=headless,
            progress_callback=push,
        )
        result_dict = result.to_dict()
    except Exception as e:
        logger.error(f"Streamed search {search_id} failed: {e}")
        push(f"Fatal error: {e}")
    finally:
        db.close()
        # Push result summary then sentinel
        if queue:
            queue.put_nowait({"done": True, "result": result_dict})
            queue.put_nowait(None)  # sentinel to close the SSE stream


@router.post("/search/async")
async def start_async_job_search(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    candidate_id: int = Form(...),
    query: str = Form(...),
    location: str = Form(""),
    platforms: list = Form(default_factory=lambda: ["linkedin", "glassdoor"]),
    max_jobs: int = Form(20),
    analyze: bool = Form(False),
    headless: bool = Form(False),
):
    """
    Start an asynchronous job search (non-blocking).
    
    Returns immediately with a search ID, then runs the search in the background.
    """
    # Validate candidate
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return {"error": f"Candidate {candidate_id} not found"}
    
    # Generate search ID
    import uuid
    search_id = str(uuid.uuid4())
    
    # Add to background tasks
    background_tasks.add_task(
        _run_async_search,
        db,
        search_id,
        candidate_id,
        query,
        location,
        platforms,
        max_jobs,
        analyze,
        headless,
    )
    
    return {
        "search_id": search_id,
        "status": "started",
        "message": "Search started in background",
    }


async def _run_async_search(
    db: Session,
    search_id: str,
    candidate_id: int,
    query: str,
    location: str,
    platforms: list,
    max_jobs: int,
    analyze: bool,
    headless: bool,
):
    """Run job search in background"""
    try:
        from backend.database import get_db
        
        # Get fresh DB session for background task
        db_session = next(get_db())
        
        result = await run_job_search(
            db=db_session,
            candidate_id=candidate_id,
            query=query,
            location=location,
            platforms=platforms,
            max_jobs=max_jobs,
            analyze=analyze,
            headless=headless,
        )
        
        # Store result (could use Redis or file-based storage)
        # For now, just log it
        logger.info(f"Async search {search_id} completed: {result.to_dict()}")
        
        db_session.close()
        
    except Exception as e:
        logger.error(f"Async search {search_id} failed: {e}")


@router.get("/{job_id}", response_class=HTMLResponse)
async def view_job(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
):
    """View job details"""
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        return templates.TemplateResponse(
            "components/error.html",
            {"request": request, "error": "Job not found"},
            status_code=404,
        )
    
    # Load description from file if available
    description = None
    if job.description_path:
        try:
            desc_path = safe_resolve_path(job.description_path, DATA_DIR)
            if desc_path.exists():
                description = desc_path.read_text()
        except ValueError:
            description = None
    if not description and job.description_snippet:
        description = job.description_snippet
    
    # Get AI analysis if available
    ai_analysis = None
    if job.ai_remote_score:
        ai_analysis = {
            "remote_score": job.ai_remote_score,
            "custom_fit_score": job.custom_fit_score,
        }
    
    return templates.TemplateResponse(
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "description": description,
            "ai_analysis": ai_analysis,
        },
    )


@router.post("/{job_id}/status")
async def update_job_status(
    request: Request,
    job_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    """Update job status (active, applied, interview, etc.)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        return {"error": "Job not found"}
    
    job.status = status
    db.commit()
    
    return {"success": True, "job_id": job_id, "status": status}


@router.delete("/{job_id}")
async def delete_job(
    request: Request,
    job_id: int,
    db: Session = Depends(get_db),
):
    """Delete a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        return {"error": "Job not found"}
    
    db.delete(job)
    db.commit()
    
    return {"success": True, "job_id": job_id}


@router.get("/api/rate-limit-status")
async def get_rate_limit_status(
    platform: str,
    db: Session = Depends(get_db),
):
    """Get rate limit status and scraper health for a platform"""
    from backend.services.rate_limiter import get_rate_limiter
    from backend.services.scraper_health import get_platform_health

    rate_limiter = get_rate_limiter()
    status = rate_limiter.get_status(platform)

    # Attach scraper health data so callers can see zero-result streaks
    health = get_platform_health(platform)
    status["scraper_health"] = health  # None if platform has never been scraped

    return status


@router.get("/api/scraper-health")
async def get_all_scraper_health(
    db: Session = Depends(get_db),
):
    """Get health summary for all scraped platforms"""
    from backend.services.scraper_health import get_health_summary
    return get_health_summary()
