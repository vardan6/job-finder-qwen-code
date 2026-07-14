"""
Skills Manager Routes - AI-powered skill extraction from documents
Matches Job Titles Parser pattern

Features:
- Parse selected files or all documents
- Merge or overwrite existing skills
- Real-time parsing status
- Bulk save skills
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Dict, Optional
import logging

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.supporting import CandidateSkill
from backend.services.llm_service import extract_skills_from_text
from backend.config import DATA_DIR

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Skills Manager"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


@router.get("/{candidate_id}/documents")
async def get_candidate_documents(candidate_id: int, db: Session = Depends(get_db)):
    """Get list of parseable documents with metadata (reuse for skills)"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.is_active == True
    ).order_by(CandidateDocument.created_at.desc()).all()

    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
                "parse_status": doc.parse_status
            }
            for doc in documents
        ]
    }


@router.post("/{candidate_id}/skills/parse")
async def parse_skills(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Parse selected documents for skills extraction.
    Supports sequential parsing with status updates.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Parse request body
    try:
        body = await request.json()
        document_ids = body.get("document_ids", [])
        parse_mode = body.get("parse_mode", "merge")  # "merge" or "overwrite"
        protected_skill_ids = body.get("protected_skill_ids", [])
    except (ValueError, KeyError):
        document_ids = []
        parse_mode = "merge"
        protected_skill_ids = []

    # Get documents
    if document_ids:
        documents = db.query(CandidateDocument).filter(
            CandidateDocument.id.in_(document_ids),
            CandidateDocument.candidate_id == candidate_id,
            CandidateDocument.is_active == True
        ).all()
    else:
        documents = db.query(CandidateDocument).filter(
            CandidateDocument.candidate_id == candidate_id,
            CandidateDocument.is_active == True,
            CandidateDocument.document_type.in_(["profile", "resume", "job_titles"])
        ).all()

    if not documents:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No documents found to parse", "skills": []}
        )

    logger.info(f"Parsing skills from {len(documents)} documents for candidate {candidate_id}")

    # Read and combine document content
    all_content = []
    file_messages = []
    
    for i, doc in enumerate(documents, 1):
        try:
            file_path = DATA_DIR / doc.file_path
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                all_content.append(f"=== {doc.filename} ===\n{content}")
                file_messages.append(f"Parsing file: {doc.filename} ({i}/{len(documents)})...")
                logger.info(f"Read document {i}/{len(documents)}: {doc.filename}")
        except Exception as e:
            logger.warning(f"Error reading {doc.filename}: {e}")
            continue

    if not all_content:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Could not read document content", "skills": []}
        )

    combined_content = "\n\n".join(all_content)
    logger.info(f"Combined content: {len(combined_content)} chars from {len(documents)} files")

    # Extract skills using AI
    try:
        logger.info("Calling AI skill extraction...")
        extracted_skills = await extract_skills_from_text(combined_content, db)
        logger.info(f"AI extracted {len(extracted_skills)} skills")

        # Get existing skills for merge mode
        existing_skills = []
        if parse_mode == "merge":
            existing_skills = db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.is_active == True
            ).all()
            existing_names = {s.skill_name.lower().strip() for s in existing_skills}

            # Filter out duplicates
            new_skills = []
            for skill_data in extracted_skills:
                skill_name = skill_data.get("skill", "").strip().lower()
                if skill_name and skill_name not in existing_names:
                    new_skills.append(skill_data)

            message = f"Found {len(new_skills)} new skills ({len(extracted_skills) - len(new_skills)} duplicates skipped)"
            logger.info(message)
        else:
            new_skills = extracted_skills
            message = f"Found {len(new_skills)} skills (overwrite mode)"
            logger.info(message)

        return {
            "success": True,
            "message": message,
            "skills": new_skills,
            "file_messages": file_messages,
            "parse_mode": parse_mode,
            "documents_parsed": len(documents)
        }

    except Exception as e:
        logger.error(f"Skill extraction failed: {e}", exc_info=True)
        # Return JSON error response (not HTML)
        error_message = str(e)
        # Provide more helpful error message for common issues
        if "timeout" in error_message.lower():
            error_message = "AI request timed out. Your LLM provider may be slow or unavailable. Try again or check your LLM configuration."
        elif "connection" in error_message.lower() or "refused" in error_message.lower():
            error_message = "Could not connect to LLM provider. Please ensure your LLM service (Ollama/NVIDIA/etc.) is running."
        
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"AI parsing failed: {error_message}", "skills": []}
        )


@router.post("/{candidate_id}/skills/bulk-save")
async def bulk_save_skills(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Bulk save skills for a candidate.
    Supports merge (default) or overwrite mode.
    Protected skills are never deleted.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        body = await request.json()
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    skills_data = body.get("skills", [])
    clear_existing = body.get("clear_existing", False)
    protected_skill_ids = body.get("protected_skill_ids", [])

    if not skills_data:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No skills provided"}
        )

    # Overwrite mode: delete all existing skills EXCEPT protected ones
    if clear_existing:
        logger.info(f"Overwrite mode: Deleting non-protected skills for candidate {candidate_id}")
        logger.info(f"Protected skill IDs: {protected_skill_ids}")
        
        # Delete all skills that are NOT protected
        if protected_skill_ids:
            db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.is_active == True,
                CandidateSkill.id.notin_(protected_skill_ids)
            ).update({"is_active": False})
        else:
            # No protected skills, delete all
            db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.is_active == True
            ).update({"is_active": False})
        
        db.commit()

    # Add new skills
    count = 0
    for skill_data in skills_data:
        skill_name = skill_data.get("skill_name", "").strip()
        if not skill_name:
            continue

        # Check for duplicates (skip if exists in merge mode)
        if not clear_existing:
            existing = db.query(CandidateSkill).filter(
                CandidateSkill.candidate_id == candidate_id,
                CandidateSkill.skill_name.ilike(skill_name),
                CandidateSkill.is_active == True
            ).first()
            if existing:
                continue

        # Create skill
        skill = CandidateSkill(
            candidate_id=candidate_id,
            skill_name=skill_name,
            category=skill_data.get("category", "preferred"),
            years_experience=skill_data.get("years_experience"),
            is_enabled=skill_data.get("is_enabled", True),
            is_active=True
        )
        db.add(skill)
        count += 1

    db.commit()

    return {
        "success": True,
        "message": f"Saved {count} skills to candidate profile",
        "count": count
    }


@router.get("/{candidate_id}/skills")
async def get_candidate_skills(candidate_id: int, db: Session = Depends(get_db)):
    """Get candidate's current skills with source information"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    skills = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.is_active == True
    ).order_by(CandidateSkill.category, CandidateSkill.skill_name).all()

    return {
        "success": True,
        "skills": [
            {
                "id": s.id,
                "skill_name": s.skill_name,
                "category": s.category,
                "years_experience": s.years_experience,
                "is_enabled": s.is_enabled,
                "source_document_id": s.source_document_id
            }
            for s in skills
        ]
    }


@router.post("/{candidate_id}/skills")
async def add_skill(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add a single skill manually"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        body = await request.json()
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    skill_name = body.get("skill_name", "").strip()
    category = body.get("category", "preferred")
    years_experience = body.get("years_experience")
    is_enabled = body.get("is_enabled", True)

    if not skill_name:
        raise HTTPException(status_code=400, detail="Skill name is required")

    # Check for duplicates
    existing = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.skill_name.ilike(skill_name),
        CandidateSkill.is_active == True
    ).first()

    if existing:
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": "Skill already exists"}
        )

    # Add new skill
    skill = CandidateSkill(
        candidate_id=candidate_id,
        skill_name=skill_name,
        category=category,
        years_experience=years_experience,
        is_enabled=is_enabled
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)

    return {
        "success": True,
        "message": "Skill added",
        "id": skill.id
    }


@router.put("/{candidate_id}/skills/{skill_id}")
async def update_skill(
    candidate_id: int,
    skill_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a single skill"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    skill = db.query(CandidateSkill).filter(
        CandidateSkill.id == skill_id,
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.is_active == True
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    try:
        body = await request.json()
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Update fields
    if "skill_name" in body:
        skill.skill_name = body["skill_name"].strip()
    if "category" in body:
        skill.category = body["category"]
    if "years_experience" in body:
        skill.years_experience = body["years_experience"]
    if "is_enabled" in body:
        skill.is_enabled = body["is_enabled"]

    db.commit()

    return {
        "success": True,
        "message": "Skill updated"
    }


@router.delete("/{candidate_id}/skills/{skill_id}")
async def delete_skill(
    candidate_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """Delete a single skill (soft delete)"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    skill = db.query(CandidateSkill).filter(
        CandidateSkill.id == skill_id,
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.is_active == True
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill.is_active = False
    db.commit()

    return {"success": True, "message": "Skill deleted"}


@router.post("/{candidate_id}/skills/{skill_id}/toggle")
async def toggle_skill(
    candidate_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """Toggle skill enabled/disabled"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    skill = db.query(CandidateSkill).filter(
        CandidateSkill.id == skill_id,
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.is_active == True
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill.is_enabled = not skill.is_enabled
    db.commit()

    return {
        "success": True,
        "is_enabled": skill.is_enabled,
        "message": f"Skill '{skill.skill_name}' {'enabled' if skill.is_enabled else 'disabled'}"
    }
