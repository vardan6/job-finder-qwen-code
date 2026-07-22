"""
Job Routes - Job search, listing, and management
"""
import asyncio
import csv
import json
import logging
import uuid
from datetime import datetime
from io import StringIO
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import DATA_DIR
from backend.models.candidate import Candidate
from backend.models.document import GeneratedDocument
from backend.models.job import Job, JobApplication, SearchRun, SearchRunJob
from backend.models.llm_provider import LLMProvider
from backend.models.supporting import CandidatePreferences
from backend.models.user import User
from backend.ownership import get_current_user, get_owned_candidate
from backend.security import safe_resolve_path
from backend.services.document_generation import DocumentGenerationError, generate_tailored_document
from backend.services.job_search import run_job_search, SearchConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

# R11 application pipeline: fixed five-stage progression, not a general workflow.
APPLICATION_PIPELINE_STATUSES = ("interested", "applied", "interview", "offer", "rejected")

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


def _persist_search_location(db: Session, candidate: Candidate, location: str) -> None:
    """Remember the user's edited search location so it survives the next page load.

    Written to a dedicated preferences field rather than `candidate.location`
    (the profile's home/current location) so tuning a search never silently
    rewrites profile data.
    """
    preferences = candidate.preferences
    if preferences is None:
        preferences = CandidatePreferences(candidate_id=candidate.id)
        db.add(preferences)
    preferences.last_search_location = location
    db.commit()


@router.get("/", response_class=HTMLResponse)
async def list_jobs(
    request: Request,
    db: Session = Depends(get_db),
    candidate_id: int = None,
    status: str = "active",
    sort: str = "score",
    direction: str = "desc",
    min_score: int = None,
    verified_remote_only: bool = False,
    include_dismissed: bool = False,
    application_status: str = None,
):
    """List all jobs with filtering"""
    query = db.query(Job)

    if candidate_id:
        query = query.filter(Job.candidate_id == candidate_id)

    if status:
        query = query.filter(Job.status == status)
    if not include_dismissed:
        query = query.filter(Job.is_dismissed.is_(False))
    if min_score is not None:
        min_score = max(0, min(100, min_score))
        query = query.filter(Job.deterministic_score >= min_score)
    if verified_remote_only:
        query = query.filter(Job.verified_remote_status == "fully_remote")
    if application_status in APPLICATION_PIPELINE_STATUSES:
        query = query.outerjoin(JobApplication, JobApplication.job_id == Job.id)
        if application_status == "interested":
            # No JobApplication row yet means the job is implicitly "interested".
            query = query.filter(
                (JobApplication.status == "interested") | (JobApplication.status.is_(None))
            )
        else:
            query = query.filter(JobApplication.status == application_status)

    sort_columns = {
        "title": Job.title,
        "company": Job.company,
        "location": Job.location,
        "platform": Job.platform,
        "salary": Job.salary,
        "remote": Job.verified_remote_status,
        "score": Job.deterministic_score,
        "status": Job.status,
        "found": Job.found_at,
    }
    selected_sort = sort if sort in sort_columns else "score"
    selected_direction = direction.lower() if direction.lower() in {"asc", "desc"} else "desc"
    order_column = sort_columns[selected_sort]
    order = order_column.asc() if selected_direction == "asc" else order_column.desc()

    # R5's deterministic composite remains the best-match default.  A stable
    # secondary sort prevents results with equal values from jumping around.
    query = query.order_by(order, Job.found_at.desc(), Job.id.desc())
    
    jobs = query.all()
    for job in jobs:
        try:
            job.score_details = json.loads(job.score_breakdown) if job.score_breakdown else None
        except (TypeError, json.JSONDecodeError):
            logger.warning("Job %s has invalid score breakdown JSON", job.id)
            job.score_details = None
    
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
            "selected_sort": selected_sort,
            "selected_direction": selected_direction,
            "min_score": min_score,
            "verified_remote_only": verified_remote_only,
            "include_dismissed": include_dismissed,
            "selected_application_status": application_status,
            "application_pipeline_statuses": APPLICATION_PIPELINE_STATUSES,
        },
    )


@router.get("/lists", response_class=HTMLResponse)
async def list_search_runs(request: Request, db: Session = Depends(get_db), candidate_id: int = None, current_user=Depends(get_current_user)):
    """Show named searches that can be revisited as historical snapshots."""
    query = db.query(SearchRun).join(Candidate).filter(Candidate.user_id == current_user.id)
    if candidate_id:
        query = query.filter(SearchRun.candidate_id == candidate_id)
    runs = query.order_by(SearchRun.started_at.desc(), SearchRun.id.desc()).all()
    for search_run in runs:
        try:
            search_run.platform_names = ", ".join(json.loads(search_run.platforms))
        except (TypeError, json.JSONDecodeError):
            search_run.platform_names = "Unknown"
        search_run.new_count = sum(1 for membership in search_run.jobs if membership.first_sighting)
    candidates = db.query(Candidate).filter(Candidate.is_active == True, Candidate.user_id == current_user.id).all()
    return templates.TemplateResponse("jobs/saved_lists.html", {
        "request": request, "runs": runs, "candidates": candidates,
        "selected_candidate_id": candidate_id,
    })


def _curated_search_run_jobs(
    db: Session, search_run_id: int, min_score: int | None,
    verified_remote_only: bool, include_dismissed: bool,
):
    """Return saved-list rows using run snapshots, never current job scores."""
    query = db.query(SearchRunJob).join(Job).filter(SearchRunJob.search_run_id == search_run_id)
    if not include_dismissed:
        query = query.filter(Job.is_dismissed.is_(False))
    if min_score is not None:
        min_score = max(0, min(100, min_score))
        query = query.filter(SearchRunJob.deterministic_score >= min_score)
    if verified_remote_only:
        query = query.filter(SearchRunJob.verified_remote_status == "fully_remote")
    return query.order_by(
        SearchRunJob.deterministic_score.desc(), SearchRunJob.id.desc(),
    ).all(), min_score


def _owned_search_run(db: Session, search_run_id: int, current_user):
    search_run = db.query(SearchRun).join(Candidate).filter(
        SearchRun.id == search_run_id, Candidate.user_id == current_user.id,
    ).first()
    if search_run is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return search_run


@router.get("/lists/{search_run_id}", response_class=HTMLResponse)
async def view_search_run(
    search_run_id: int, request: Request, db: Session = Depends(get_db),
    min_score: int = None, verified_remote_only: bool = False,
    include_dismissed: bool = False, current_user=Depends(get_current_user),
):
    """Render a saved list from SearchRunJob values, never live job scores."""
    search_run = _owned_search_run(db, search_run_id, current_user)
    memberships, min_score = _curated_search_run_jobs(
        db, search_run.id, min_score, verified_remote_only, include_dismissed,
    )
    for membership in memberships:
        try:
            membership.platform_names = ", ".join(json.loads(membership.sighted_platforms))
        except (TypeError, json.JSONDecodeError):
            membership.platform_names = "Unknown"
    # "N new since last run" = count of first_sighting rows in this run (per
    # docs/design/search-runs-and-lists.md), computed over the full run, not
    # just the currently visible/curated rows.
    new_count = sum(1 for membership in search_run.jobs if membership.first_sighting)
    return templates.TemplateResponse("jobs/saved_list.html", {
        "request": request, "search_run": search_run, "memberships": memberships,
        "min_score": min_score, "verified_remote_only": verified_remote_only,
        "include_dismissed": include_dismissed, "new_count": new_count,
    })


@router.post("/lists/{search_run_id}/rerun")
async def rerun_search_run(
    search_run_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user),
):
    """Re-run a saved search with its original query/location/platforms.

    Produces a new SearchRun; "N new since last run" is simply that run's
    first_sighting count, since dedup already compares against every job the
    candidate has ever been shown (see docs/design/search-runs-and-lists.md).
    """
    prior_run = _owned_search_run(db, search_run_id, current_user)
    try:
        platforms = json.loads(prior_run.platforms)
    except (TypeError, json.JSONDecodeError):
        platforms = ["linkedin", "glassdoor"]

    result = await run_job_search(
        db=db,
        candidate_id=prior_run.candidate_id,
        query=prior_run.query,
        location=prior_run.location or "",
        platforms=platforms,
    )
    if not result.search_run_id:
        raise HTTPException(status_code=502, detail="Re-run failed to produce a saved list")
    return RedirectResponse(url=f"/jobs/lists/{result.search_run_id}", status_code=303)


@router.get("/lists/{search_run_id}/export")
async def export_search_run(
    search_run_id: int, db: Session = Depends(get_db), min_score: int = None,
    verified_remote_only: bool = False, include_dismissed: bool = False,
    current_user=Depends(get_current_user),
):
    """Export the visible historical snapshot rows as a CSV file."""
    search_run = _owned_search_run(db, search_run_id, current_user)
    memberships, _ = _curated_search_run_jobs(
        db, search_run.id, min_score, verified_remote_only, include_dismissed,
    )
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "title", "company", "location", "platforms_sighted", "salary",
        "verified_remote_status", "score", "first_sighting", "url",
    ])
    for membership in memberships:
        try:
            platforms = ", ".join(json.loads(membership.sighted_platforms))
        except (TypeError, json.JSONDecodeError):
            platforms = ""
        writer.writerow([
            membership.job.title, membership.job.company, membership.job.location or "",
            platforms, membership.salary or "", membership.verified_remote_status or "unknown",
            membership.deterministic_score if membership.deterministic_score is not None else "",
            "yes" if membership.first_sighting else "no", membership.job.original_url or "",
        ])
    filename = f"saved-search-{search_run.id}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })


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
    
    # Get location from the last search the user edited, then candidate
    # profile, then a hard default; the profile value is only used the first
    # time nothing has been saved yet, so a corrected location persists.
    location = (
        (candidate.preferences.last_search_location if candidate.preferences else None)
        or candidate.location
        or "United States"
    )
    
    # Get remote-only preference
    remote_only = False
    if candidate.preferences:
        remote_only = candidate.preferences.remote_only or False
    
    # Get connected platforms (only active accounts)
    connected_platforms = []
    platform_status = []
    
    from backend.routes.platform_accounts import _account_guidance

    for platform in ["linkedin", "glassdoor"]:
        account = next(
            (acc for acc in candidate.platform_accounts if acc.platform == platform),
            None
        )
        if account and account.status == "active":
            connected_platforms.append(platform)
            platform_status.append({
                "platform": platform,
                "label": platform.capitalize(),
                "connected": True,
                "selectable": True,
                "status": "active",
                "account_id": account.id,
            })
        else:
            guidance = _account_guidance(account)
            platform_status.append({
                "platform": platform,
                "label": platform.capitalize(),
                "connected": False,
                "selectable": False,
                "status": account.status if account else "not_connected",
                "detail": guidance["label"],
                "account_id": account.id if account else None,
            })

    # WWR is wired through the common adapter path, but live navigation is
    # deliberately unavailable until the maintainer records authorization and
    # completes manual validation.  Keep it visible and selectable so a
    # requested search receives the explicit fail-closed result from the
    # service instead of being mistaken for an unknown platform.
    platform_status.append({
        "platform": "we_work_remotely",
        "label": "We Work Remotely",
        "connected": False,
        "selectable": True,
        "status": "policy_gated",
        "detail": "Live search is awaiting maintainer authorization and manual validation.",
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
    location: str = Form(...),
    platforms: list = Form(default_factory=lambda: ["linkedin", "glassdoor"]),
    max_jobs: int = Form(20),
    analyze: str = Form("false"),  # Comes as 'true' or 'false' string
    headless: str = Form("false"),  # Comes as 'true' or 'false' string
    remote_only: str = Form("false"),  # Comes as 'true' or 'false' string (for override)
    list_name: str = Form(""),
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

    if not location.strip():
        return templates.TemplateResponse(
            "components/error.html",
            {
                "request": request,
                "error": "Location is required for job search.",
            },
            status_code=200,
        )

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

    _persist_search_location(db, candidate, location)

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
            run_name=list_name,
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
            "search_run_id": result.search_run_id,
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
    location: str = Form(...),
    platforms: list = Form(default_factory=lambda: ["linkedin", "glassdoor"]),
    max_jobs: int = Form(20),
    analyze: str = Form("false"),
    headless: str = Form("false"),
    list_name: str = Form(""),
):
    """
    Start a job search and return a search_id for SSE progress streaming.
    The client should then connect to /search/stream/{search_id}.
    """
    from backend.services.search_progress import create_progress_queue
    from backend.services.search_lock import is_search_running

    if not location.strip():
        return JSONResponse({"error": "Location is required for job search."}, status_code=400)

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return JSONResponse({"error": f"Candidate {candidate_id} not found"}, status_code=404)

    _persist_search_location(db, candidate, location)

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
        list_name,
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
    list_name: str,
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
            run_name=list_name,
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
    location: str = Form(...),
    platforms: list = Form(default_factory=lambda: ["linkedin", "glassdoor"]),
    max_jobs: int = Form(20),
    analyze: bool = Form(False),
    headless: bool = Form(False),
):
    """
    Start an asynchronous job search (non-blocking).

    Returns immediately with a search ID, then runs the search in the background.
    """
    if not location.strip():
        return {"error": "Location is required for job search."}

    # Validate candidate
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return {"error": f"Candidate {candidate_id} not found"}

    _persist_search_location(db, candidate, location)

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
    
    # Existing tailored documents for this job (R11), keyed by document_type
    generated_documents = {
        doc.document_type: doc
        for doc in db.query(GeneratedDocument).filter(GeneratedDocument.job_id == job.id).all()
    }

    return templates.TemplateResponse(
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "description": description,
            "ai_analysis": ai_analysis,
            "generated_documents": generated_documents,
        },
    )


@router.post("/{job_id}/generate-document/{document_type}", response_class=HTMLResponse)
async def generate_job_document(
    request: Request,
    job_id: int,
    document_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or regenerate) a tailored resume/cover letter for this job (R11)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    candidate = get_owned_candidate(db, current_user, job.candidate_id)

    error = None
    generated = None
    try:
        generated = await generate_tailored_document(db, candidate, job, document_type)
    except DocumentGenerationError as e:
        error = str(e)

    return templates.TemplateResponse(
        "jobs/_generated_document.html",
        {
            "request": request,
            "job": job,
            "document_type": document_type,
            "generated": generated,
            "error": error,
        },
        status_code=400 if error else 200,
    )


@router.get("/{job_id}/generated-document/{document_type}/download")
async def download_generated_document(
    job_id: int,
    document_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a previously generated tailored document (R11)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    get_owned_candidate(db, current_user, job.candidate_id)  # ownership check only

    generated = (
        db.query(GeneratedDocument)
        .filter(GeneratedDocument.job_id == job_id, GeneratedDocument.document_type == document_type)
        .first()
    )
    if not generated:
        raise HTTPException(status_code=404, detail="Generated document not found")

    filename = f"{document_type}-job-{job_id}.md"
    return Response(
        content=generated.content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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


@router.post("/{job_id}/application-status")
async def update_application_status(
    request: Request,
    job_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update the R11 application-pipeline status (interested/applied/interview/offer/rejected).

    This tracks JobApplication.status, distinct from Job.status (the posting's
    own lifecycle). Creates the JobApplication row on first status change.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    get_owned_candidate(db, current_user, job.candidate_id)

    if status not in APPLICATION_PIPELINE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid application status")

    application = job.application
    if application is None:
        application = JobApplication(job_id=job.id, status=status)
        db.add(application)
    else:
        application.status = status
    if status == "applied" and application.applied_date is None:
        application.applied_date = datetime.utcnow()
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(request.headers.get("referer", "/jobs/"), status_code=303)


@router.post("/{job_id}/dismiss")
async def dismiss_job(
    request: Request, job_id: int, db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Hide a posting without deleting it or altering saved-list snapshots."""
    job = db.query(Job).join(Candidate).filter(
        Job.id == job_id, Candidate.user_id == current_user.id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_dismissed = True
    db.commit()
    # This endpoint is used by ordinary forms so the user lands back on the
    # filtered result/list view they curated.
    from fastapi.responses import RedirectResponse
    return RedirectResponse(request.headers.get("referer", "/jobs/"), status_code=303)


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
