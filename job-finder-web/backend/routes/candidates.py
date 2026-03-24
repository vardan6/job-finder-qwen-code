"""
Candidate Routes - CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path
import uuid

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.supporting import CandidateJobTitle, CandidateSkill, CandidatePreferences
from backend.models.document import CandidateDocument
from backend.config import DATA_DIR

router = APIRouter()

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


@router.get("/", response_class=HTMLResponse)
async def list_candidates(request: Request, db: Session = Depends(get_db)):
    """List all candidates"""
    candidates = db.query(Candidate).filter(Candidate.is_active == True).all()
    return templates.TemplateResponse("candidates/list.html", {"request": request, "candidates": candidates})


@router.get("/new", response_class=HTMLResponse)
async def new_candidate_form(request: Request):
    """Show form to create new candidate"""
    return templates.TemplateResponse("candidates/edit.html", {"request": request, "candidate": None, "action": "Create"})


@router.post("/")
async def create_candidate(
    request: Request,
    name: str = Form(...),
    email: Optional[str] = Form(None),
    location: str = Form("Armenia"),
    timezone: str = Form("Asia/Yerevan"),
    experience_years: Optional[int] = Form(None),
    current_role: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Create a new candidate"""
    try:
        # Generate UUID and folder path
        candidate_uuid = str(uuid.uuid4())
        folder_path = DATA_DIR / "candidates" / candidate_uuid
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Create candidate
        candidate = Candidate(
            name=name,
            email=email,
            location=location,
            timezone=timezone,
            experience_years=experience_years,
            current_role=current_role,
            folder_path=str(folder_path),
            uuid=candidate_uuid
        )
        
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        # Create default preferences
        preferences = CandidatePreferences(
            candidate_id=candidate.id
        )
        db.add(preferences)
        db.commit()
        
        # Redirect with success message
        return RedirectResponse(url="/candidates?success=created", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{candidate_id}", response_class=HTMLResponse)
async def view_candidate(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """View candidate details"""
    from sqlalchemy.orm import joinedload
    from backend.models.supporting import CandidateSkill, CandidateJobTitle
    from backend.models.document import CandidateDocument, LLMFunctionMapping

    # Eager load relationships
    candidate = db.query(Candidate).options(
        joinedload(Candidate.skills),
        joinedload(Candidate.job_titles),
        joinedload(Candidate.documents)
    ).filter(Candidate.id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Get current model configurations for AI functions
    job_title_parser_mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "job_title_parser",
        LLMFunctionMapping.is_active == True
    ).first()
    skill_extractor_mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "skill_extractor",
        LLMFunctionMapping.is_active == True
    ).first()

    return templates.TemplateResponse("candidates/detail.html", {
        "request": request,
        "candidate": candidate,
        "job_title_parser_model_id": job_title_parser_mapping.model_id if job_title_parser_mapping else None,
        "skill_extractor_model_id": skill_extractor_mapping.model_id if skill_extractor_mapping else None
    })


@router.get("/{candidate_id}/edit", response_class=HTMLResponse)
async def edit_candidate_form(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """Show form to edit candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    return templates.TemplateResponse("candidates/edit.html", {"request": request, "candidate": candidate, "action": "Update"})


@router.post("/{candidate_id}")
async def update_candidate(
    request: Request,
    candidate_id: int,
    name: str = Form(...),
    email: Optional[str] = Form(None),
    location: str = Form("Armenia"),
    timezone: str = Form("Asia/Yerevan"),
    experience_years: Optional[int] = Form(None),
    current_role: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Update an existing candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    try:
        # Update fields
        candidate.name = name
        candidate.email = email
        candidate.location = location
        candidate.timezone = timezone
        candidate.experience_years = experience_years
        candidate.current_role = current_role
        
        db.commit()
        db.refresh(candidate)
        
        # Redirect with success message
        return RedirectResponse(url=f"/candidates/{candidate_id}?success=updated", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{candidate_id}/delete")
async def delete_candidate(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """Delete a candidate (soft delete)"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    try:
        # Soft delete - mark as inactive
        candidate.is_active = False
        
        db.commit()
        
        # Redirect with success message
        return RedirectResponse(url="/candidates?success=deleted", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
