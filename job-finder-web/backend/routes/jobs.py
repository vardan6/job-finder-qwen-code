"""
Job Routes - Job search, listing, and management
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.job import Job
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


@router.post("/search", response_class=HTMLResponse)
async def perform_job_search(
    request: Request,
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
    Perform a job search across platforms.
    
    This is a long-running operation that:
    1. Acquires global search lock
    2. Checks rate limits
    3. Scrapes job platforms
    4. Deduplicates results
    5. Runs AI analysis (if enabled)
    6. Saves to database
    """
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
            f"query='{query}', location='{location}', platforms={platforms}"
        )
        
        # Run the search (async)
        result = await run_job_search(
            db=db,
            candidate_id=candidate_id,
            query=query,
            location=location,
            platforms=platforms,
            max_jobs=max_jobs,
            analyze=analyze,
            headless=headless,
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
    if job.description_path and Path(job.description_path).exists():
        description = Path(job.description_path).read_text()
    elif job.description_snippet:
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
    """Get rate limit status for a platform"""
    from backend.services.rate_limiter import get_rate_limiter
    
    rate_limiter = get_rate_limiter()
    status = rate_limiter.get_status(platform)
    
    return status
