"""
Skills Management Routes - CRUD, toggle, AI parsing
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from pathlib import Path
import json

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.supporting import CandidateSkill, CandidatePreferences
from backend.models.document import CandidateDocument, LLMFunctionMapping
from backend.services.llm_service import extract_skills_from_text

router = APIRouter(prefix="/candidates/{candidate_id}/skills", tags=["skills"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


@router.get("/modal", response_class=HTMLResponse)
async def skills_modal(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """Render skills management modal"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Get all active skills
    skills = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.is_active == True
    ).order_by(CandidateSkill.category, CandidateSkill.skill_name).all()

    # Get current model configuration for skill extractor
    skill_extractor_mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "skill_extractor",
        LLMFunctionMapping.is_active == True
    ).first()

    return templates.TemplateResponse("skills/modal.html", {
        "request": request,
        "candidate": candidate,
        "skills": skills,
        "skill_extractor_model_id": skill_extractor_mapping.model_id if skill_extractor_mapping else None
    })


@router.post("/")
async def create_skill(
    request: Request,
    candidate_id: int,
    skill_name: str = Form(...),
    category: str = Form("preferred"),  # Kept for backward compatibility
    years_experience: Optional[int] = Form(None),  # Kept for backward compatibility
    is_enabled: str = Form("true"),  # Changed to string for easier handling
    db: Session = Depends(get_db)
):
    """Create a new skill"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Check for duplicate
    existing = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.skill_name.ilike(skill_name.strip()),
        CandidateSkill.is_active == True
    ).first()

    if existing:
        return JSONResponse({
            "success": False,
            "message": f"Skill '{skill_name}' already exists"
        }, status_code=400)

    try:
        # Parse is_enabled from string
        is_enabled_bool = is_enabled.lower() == 'true'
        
        skill = CandidateSkill(
            candidate_id=candidate_id,
            skill_name=skill_name.strip(),
            category=category,
            years_experience=years_experience,
            is_enabled=is_enabled_bool
        )
        db.add(skill)
        db.commit()

        return JSONResponse({
            "success": True,
            "message": f"Skill '{skill_name}' added",
            "skill": {
                "id": skill.id,
                "skill_name": skill.skill_name,
                "is_enabled": skill.is_enabled
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/{skill_id}/toggle")
async def toggle_skill(
    request: Request,
    candidate_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """Toggle skill enable/disable"""
    skill = db.query(CandidateSkill).filter(
        CandidateSkill.id == skill_id,
        CandidateSkill.candidate_id == candidate_id
    ).first()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    skill.is_enabled = not skill.is_enabled
    db.commit()
    
    return JSONResponse({
        "success": True,
        "is_enabled": skill.is_enabled,
        "message": f"Skill '{skill.skill_name}' {'enabled' if skill.is_enabled else 'disabled'}"
    })


@router.post("/{skill_id}/update")
async def update_skill(
    request: Request,
    candidate_id: int,
    skill_id: int,
    skill_name: str = Form(...),
    category: str = Form("preferred"),  # Kept for compatibility but ignored
    years_experience: Optional[int] = Form(None),  # Kept for compatibility but ignored
    db: Session = Depends(get_db)
):
    """Update a skill (inline edit)"""
    skill = db.query(CandidateSkill).filter(
        CandidateSkill.id == skill_id,
        CandidateSkill.candidate_id == candidate_id
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    try:
        # Only update skill name (category and years_experience ignored in new UI)
        skill.skill_name = skill_name.strip()
        db.commit()

        return JSONResponse({
            "success": True,
            "message": f"Skill '{skill.skill_name}' updated",
            "skill": {
                "id": skill.id,
                "skill_name": skill.skill_name,
                "is_enabled": skill.is_enabled
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/{skill_id}/delete")
async def delete_skill(
    request: Request,
    candidate_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """Soft delete a skill"""
    skill = db.query(CandidateSkill).filter(
        CandidateSkill.id == skill_id,
        CandidateSkill.candidate_id == candidate_id
    ).first()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    try:
        skill.is_active = False
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"Skill '{skill.skill_name}' deleted"
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/bulk-delete")
async def bulk_delete_skills(
    request: Request,
    candidate_id: int,
    skill_ids: str = Form(...),  # Comma-separated list
    db: Session = Depends(get_db)
):
    """Bulk delete skills"""
    try:
        ids = [int(x.strip()) for x in skill_ids.split(",") if x.strip()]
        
        db.query(CandidateSkill).filter(
            CandidateSkill.id.in_(ids),
            CandidateSkill.candidate_id == candidate_id
        ).update({"is_active": False}, synchronize_session=False)
        
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"{len(ids)} skill(s) deleted"
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/bulk-toggle")
async def bulk_toggle_skills(
    request: Request,
    candidate_id: int,
    skill_ids: str = Form(...),  # Comma-separated list
    is_enabled: bool = Form(...),
    db: Session = Depends(get_db)
):
    """Bulk toggle skills enable/disable"""
    try:
        ids = [int(x.strip()) for x in skill_ids.split(",") if x.strip()]
        
        db.query(CandidateSkill).filter(
            CandidateSkill.id.in_(ids),
            CandidateSkill.candidate_id == candidate_id
        ).update({"is_enabled": is_enabled}, synchronize_session=False)
        
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"{len(ids)} skill(s) {'enabled' if is_enabled else 'disabled'}"
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/parse", response_class=HTMLResponse)
async def parse_skills_from_documents(
    request: Request,
    candidate_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Parse skills from candidate's uploaded documents using AI"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Get documents with parsed content
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.parse_status == "completed",
        CandidateDocument.is_active == True,
        CandidateDocument.document_type.in_(["profile", "resume", "job_titles"])
    ).all()

    if not documents:
        return templates.TemplateResponse("skills/parse_result.html", {
            "request": request,
            "candidate": candidate,
            "success": False,
            "message": "No parsed documents found. Upload and parse documents first.",
            "skills": [],
            "existing_skills": []
        })

    # Get existing skills
    existing_skills = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.is_active == True
    ).all()
    existing_names = {s.skill_name.lower().strip() for s in existing_skills}

    # Read document content from files
    all_content = []
    from pathlib import Path
    
    for doc in documents:
        try:
            file_path = Path("data") / doc.file_path
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                all_content.append(content)
        except Exception as e:
            print(f"Error reading {doc.filename}: {e}")
            continue

    if not all_content:
        return templates.TemplateResponse("skills/parse_result.html", {
            "request": request,
            "candidate": candidate,
            "success": False,
            "message": "No parseable content found in documents.",
            "skills": [],
            "existing_skills": []
        })

    combined_content = "\n\n".join(all_content)

    # Extract skills using AI
    try:
        # Pass db session for LLM model lookup
        extracted_skills = extract_skills_from_text(combined_content, db)

        # Filter out duplicates and prepare skills
        new_skills = []
        for skill_data in extracted_skills:
            skill_name = skill_data.get("skill", "").strip()
            if not skill_name:
                continue

            # Skip if already exists
            if skill_name.lower() in existing_names:
                continue

            new_skills.append({
                "skill_name": skill_name,
                "category": skill_data.get("category", "preferred"),
                "years_experience": skill_data.get("years_experience"),
                "source_document_id": documents[0].id if documents else None
            })

        return templates.TemplateResponse("skills/parse_result.html", {
            "request": request,
            "candidate": candidate,
            "success": True,
            "message": f"Found {len(new_skills)} new skills from AI parsing",
            "skills": new_skills,
            "existing_skills": [
                {"id": s.id, "skill_name": s.skill_name, "category": s.category, "is_enabled": s.is_enabled}
                for s in existing_skills
            ],
            "documents": [doc.filename for doc in documents]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("skills/parse_result.html", {
            "request": request,
            "candidate": candidate,
            "success": False,
            "message": f"AI parsing failed: {str(e)}",
            "skills": [],
            "existing_skills": []
        })


@router.post("/save-parsed")
async def save_parsed_skills(
    request: Request,
    candidate_id: int,
    skills_data: str = Form(...),  # JSON string
    db: Session = Depends(get_db)
):
    """Save AI-parsed skills to database"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    try:
        skills = json.loads(skills_data)
        saved_count = 0
        
        for skill_data in skills:
            # Check if already exists
            existing = db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.skill_name.ilike(skill_data["skill_name"].strip()),
                CandidateSkill.is_active == True
            ).first()
            
            if not existing:
                skill = CandidateSkill(
                    candidate_id=candidate_id,
                    skill_name=skill_data["skill_name"].strip(),
                    category=skill_data.get("category", "preferred"),
                    years_experience=skill_data.get("years_experience"),
                    is_enabled=skill_data.get("is_enabled", True),
                    source_document_id=skill_data.get("source_document_id")
                )
                db.add(skill)
                saved_count += 1
        
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"{saved_count} skill(s) saved",
            "saved_count": saved_count
        })
        
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)
