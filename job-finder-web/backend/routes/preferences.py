"""
Candidate Preferences Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import json

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.supporting import CandidatePreferences

router = APIRouter(prefix="/candidates/{candidate_id}/preferences", tags=["preferences"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


@router.get("/edit", response_class=HTMLResponse)
async def edit_preferences(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """Show preferences editing page"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get or create preferences
    preferences = db.query(CandidatePreferences).filter(
        CandidatePreferences.candidate_id == candidate_id
    ).first()
    
    if not preferences:
        preferences = CandidatePreferences(candidate_id=candidate_id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    
    return templates.TemplateResponse("preferences/edit.html", {
        "request": request,
        "candidate": candidate,
        "preferences": preferences
    })


@router.post("/save")
async def save_preferences(
    request: Request,
    candidate_id: int,
    min_score: int = Form(60),
    min_ai_remote_score: int = Form(70),
    remote_only: bool = Form(False),
    experience_levels: str = Form('["Senior", "Staff", "Principal", "Lead"]'),
    db: Session = Depends(get_db)
):
    """Save candidate preferences"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get or create preferences
    preferences = db.query(CandidatePreferences).filter(
        CandidatePreferences.candidate_id == candidate_id
    ).first()
    
    if not preferences:
        preferences = CandidatePreferences(candidate_id=candidate_id)
        db.add(preferences)
    
    try:
        # Update preferences
        preferences.min_score = min_score
        preferences.min_ai_remote_score = min_ai_remote_score
        preferences.remote_only = remote_only
        
        # Parse experience levels JSON
        try:
            exp_levels = json.loads(experience_levels)
            if isinstance(exp_levels, list):
                preferences.experience_levels = json.dumps(exp_levels)
            else:
                preferences.experience_levels = json.dumps(["Senior", "Staff", "Principal", "Lead"])
        except:
            preferences.experience_levels = json.dumps(["Senior", "Staff", "Principal", "Lead"])
        
        db.commit()
        db.refresh(preferences)
        
        # Redirect with success
        return RedirectResponse(
            url=f"/candidates/{candidate_id}/preferences/edit?success=1",
            status_code=303
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api")
async def get_preferences_api(candidate_id: int, db: Session = Depends(get_db)):
    """Get preferences as JSON"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    preferences = db.query(CandidatePreferences).filter(
        CandidatePreferences.candidate_id == candidate_id
    ).first()
    
    if not preferences:
        return JSONResponse({
            "min_score": 60,
            "min_ai_remote_score": 70,
            "remote_only": False,
            "experience_levels": ["Senior", "Staff", "Principal", "Lead"]
        })
    
    return JSONResponse({
        "min_score": preferences.min_score,
        "min_ai_remote_score": preferences.min_ai_remote_score,
        "remote_only": preferences.remote_only,
        "experience_levels": json.loads(preferences.experience_levels or "[]")
    })
