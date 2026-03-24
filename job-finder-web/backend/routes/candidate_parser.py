"""
Candidate Parser Routes - AI-powered job title extraction from documents
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Dict, Optional

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.services.job_title_parser import (
    parse_all_candidate_documents,
    save_job_titles_to_candidate,
    get_candidate_job_titles_with_sources
)

router = APIRouter(tags=["Candidate Parser"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


@router.post("/{candidate_id}/parse-job-titles")
async def parse_job_titles(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    Parse all candidate documents and extract job titles using AI.
    Returns parsed results without saving to database.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Parse all documents
    success, job_titles, error = parse_all_candidate_documents(db, candidate_id)
    
    if not success:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": error,
                "job_titles": []
            }
        )
    
    return {
        "success": True,
        "message": f"Extracted {len(job_titles)} job titles from documents",
        "job_titles": job_titles,
        "warning": error  # Non-fatal warnings
    }


@router.post("/{candidate_id}/save-job-titles")
async def save_job_titles(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Save job titles to candidate profile.
    Expects JSON body with job_titles array and optional clear_existing flag.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Parse JSON body
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    job_titles_data = body.get("job_titles", [])
    clear_existing = body.get("clear_existing", False)
    
    if not job_titles_data:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No job titles provided"}
        )
    
    # Save to database
    success, count, error = save_job_titles_to_candidate(
        db, candidate_id, job_titles_data, clear_existing
    )
    
    if not success:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error}
        )
    
    return {
        "success": True,
        "message": f"Saved {count} job titles to candidate profile",
        "count": count
    }


@router.get("/{candidate_id}/job-titles")
async def get_job_titles(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """Get candidate's current job titles with source information"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job_titles = get_candidate_job_titles_with_sources(db, candidate_id)
    
    return {
        "success": True,
        "job_titles": job_titles
    }


@router.post("/{candidate_id}/job-titles")
async def add_job_title(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add a single job title manually"""
    from backend.models.supporting import CandidateJobTitle
    from sqlalchemy import func
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    title = body.get("title", "").strip()
    priority = body.get("priority", 2)
    description = body.get("description", "")
    
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    
    # Check for duplicates
    existing = db.query(CandidateJobTitle).filter(
        CandidateJobTitle.candidate_id == candidate_id,
        CandidateJobTitle.title == title
    ).first()
    
    if existing:
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": "Job title already exists"}
        )
    
    # Add new job title
    job_title = CandidateJobTitle(
        candidate_id=candidate_id,
        title=title,
        priority=priority,
        description=description,
        created_at=func.now()
    )
    db.add(job_title)
    db.commit()
    db.refresh(job_title)
    
    return {
        "success": True,
        "message": "Job title added",
        "id": job_title.id
    }


@router.put("/{candidate_id}/job-titles/bulk-save")
async def bulk_save_job_titles(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Bulk save all job titles for a candidate.
    Replaces the entire list with the provided data.
    """
    from backend.models.supporting import CandidateJobTitle
    from sqlalchemy import func
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    job_titles_data = body.get("job_titles", [])
    
    # Delete all existing job titles for this candidate
    db.query(CandidateJobTitle).filter(
        CandidateJobTitle.candidate_id == candidate_id
    ).delete()
    db.commit()
    
    # Add new job titles
    count = 0
    for title_data in job_titles_data:
        if not title_data.get("title", "").strip():
            continue
        
        job_title = CandidateJobTitle(
            candidate_id=candidate_id,
            title=title_data["title"].strip(),
            priority=title_data.get("priority", 2),
            description=title_data.get("description", ""),
            source_document_id=title_data.get("source_document_id")
        )
        db.add(job_title)
        count += 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Saved {count} job titles",
        "count": count
    }


@router.delete("/{candidate_id}/job-titles/{jt_id}")
async def delete_job_title(
    candidate_id: int,
    jt_id: int,
    db: Session = Depends(get_db)
):
    """Delete a job title"""
    from backend.models.supporting import CandidateJobTitle
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job_title = db.query(CandidateJobTitle).filter(
        CandidateJobTitle.id == jt_id,
        CandidateJobTitle.candidate_id == candidate_id
    ).first()
    
    if not job_title:
        raise HTTPException(status_code=404, detail="Job title not found")
    
    db.delete(job_title)
    db.commit()
    
    return {"success": True, "message": "Job title deleted"}


@router.put("/{candidate_id}/job-titles/{jt_id}")
async def update_job_title(
    candidate_id: int,
    jt_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a job title"""
    from backend.models.supporting import CandidateJobTitle
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job_title = db.query(CandidateJobTitle).filter(
        CandidateJobTitle.id == jt_id,
        CandidateJobTitle.candidate_id == candidate_id
    ).first()
    
    if not job_title:
        raise HTTPException(status_code=404, detail="Job title not found")
    
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Update fields
    if "title" in body:
        job_title.title = body["title"].strip()
    if "priority" in body:
        job_title.priority = body["priority"]
    if "description" in body:
        job_title.description = body["description"]

    db.commit()

    return {
        "success": True,
        "message": "Job title updated"
    }
