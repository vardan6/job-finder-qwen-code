"""
Document Routes - Handle document uploads and management
"""
import os
import hashlib
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument, DocumentParsePrompt
from backend.services.document_parser import (
    parse_document_content,
    get_candidate_prompt,
    reset_candidate_prompt_to_system,
)

router = APIRouter(prefix="/candidates", tags=["documents"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


def get_candidate_folder(candidate_id: int) -> Path:
    """Get the folder path for a candidate's documents"""
    base_path = Path("data/candidates") / str(candidate_id)
    base_path.mkdir(parents=True, exist_ok=True)
    
    docs_path = base_path / "documents"
    docs_path.mkdir(parents=True, exist_ok=True)
    
    return docs_path


def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA256 hash of file content"""
    return hashlib.sha256(content).hexdigest()


def detect_document_type(filename: str) -> str:
    """Detect document type from filename"""
    filename_lower = filename.lower()
    
    if "job" in filename_lower and "title" in filename_lower:
        return "job_titles"
    elif "profile" in filename_lower or "linkedin" in filename_lower:
        return "profile"
    elif "resume" in filename_lower or "cv" in filename_lower:
        return "resume"
    elif "cover" in filename_lower and "letter" in filename_lower:
        return "cover_letter"
    
    return "custom"


@router.get("/{candidate_id}/documents")
async def get_candidate_documents(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """Get all documents for a candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.is_active == True
    ).order_by(CandidateDocument.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "candidates/documents.html",
        {
            "request": request,
            "candidate": candidate,
            "documents": documents,
        }
    )


@router.post("/{candidate_id}/documents/upload")
async def upload_document(
    request: Request,
    candidate_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(default=None),
    load_strategy: str = Form(default="immediate"),
    db: Session = Depends(get_db)
):
    """Upload a document for a candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Read file content
    content = await file.read()
    file_hash = calculate_file_hash(content)
    
    # Check for duplicate
    existing = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.file_hash == file_hash,
        CandidateDocument.is_active == True
    ).first()
    
    if existing:
        # File already uploaded
        return {
            "success": False,
            "message": f"File '{existing.filename}' with same content already exists",
            "document_id": existing.id
        }
    
    # Detect document type if not specified
    if not document_type:
        document_type = detect_document_type(file.filename)
    
    # Save file to disk
    docs_folder = get_candidate_folder(candidate_id)
    file_path = docs_folder / file.filename
    
    # Handle duplicate filenames
    counter = 1
    original_name = file.filename
    while file_path.exists():
        name, ext = os.path.splitext(original_name)
        new_filename = f"{name}_{counter}{ext}"
        file_path = docs_folder / new_filename
        counter += 1
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create database record
    document = CandidateDocument(
        candidate_id=candidate_id,
        filename=file_path.name,
        file_path=str(file_path.relative_to(Path("data"))),
        file_hash=file_hash,
        file_size=len(content),
        mime_type=file.content_type or "text/markdown",
        document_type=document_type,
        load_strategy=load_strategy,
        parse_status="pending" if load_strategy == "immediate" else "not_started"
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Parse immediately if requested
    if load_strategy == "immediate":
        # Run parsing in background (for now, synchronous)
        parse_document_content(db, document)
    
    return {
        "success": True,
        "message": f"Document uploaded successfully",
        "document_id": document.id,
        "parse_status": document.parse_status,
        "job_titles_found": len(candidate.job_titles) if hasattr(candidate, 'job_titles') else 0
    }


@router.post("/{candidate_id}/documents/{document_id}/reparse")
async def reparse_document(
    request: Request,
    candidate_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Re-parse a document with the current prompt"""
    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.candidate_id == candidate_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Reset parse status
    document.parse_status = "pending"
    document.parse_error = None
    db.commit()

    # Parse
    success = parse_document_content(db, document)

    if success:
        return {"success": True, "message": "Document re-parsed successfully"}
    else:
        return {"success": False, "message": f"Re-parsing failed: {document.parse_error}"}


@router.post("/{candidate_id}/documents/{document_id}/delete")
async def delete_document(
    request: Request,
    candidate_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document (soft delete)"""
    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.candidate_id == candidate_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Soft delete
    document.is_active = False

    # Optionally delete the file
    file_path = Path("data") / document.file_path
    if file_path.exists():
        file_path.unlink()

    db.commit()

    return {"success": True, "message": "Document deleted successfully"}


@router.get("/{candidate_id}/documents/{document_id}/view")
async def view_document(
    request: Request,
    candidate_id: int,
    document_id: int,
    db: Session = Depends(get_db)
):
    """View document content"""
    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == document_id,
        CandidateDocument.candidate_id == candidate_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path("data") / document.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    content = file_path.read_text(encoding="utf-8")

    return {
            "success": True,
            "filename": document.filename,
            "content": content,
            "parsed_data": document.get_parsed_data_json()
        }


@router.get("/{candidate_id}/prompts/{document_type}")
async def get_prompt(
    request: Request,
    candidate_id: int,
    document_type: str,
    db: Session = Depends(get_db)
):
    """Get the parse prompt for a document type"""
    prompt = get_candidate_prompt(db, candidate_id, document_type)

    if not prompt:
        return {"success": False, "message": "No prompt found for this document type"}

    return {
        "success": True,
        "prompt": {
            "id": prompt.id,
            "name": prompt.name,
            "description": prompt.description,
            "prompt_template": prompt.prompt_template,
            "output_schema": prompt.output_schema,
            "is_system": prompt.is_system,
            "is_candidate_specific": prompt.candidate_id == candidate_id
        }
    }


@router.post("/{candidate_id}/prompts/{document_type}/save")
async def save_prompt(
    request: Request,
    candidate_id: int,
    document_type: str,
    prompt_template: str = Form(...),
    description: str = Form(default=None),
    db: Session = Depends(get_db)
):
    """Save a candidate-specific prompt"""
    # Get system prompt as base
    system_prompt = db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.document_type == document_type,
        DocumentParsePrompt.candidate_id.is_(None)
    ).first()

    if not system_prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")

    # Get or create candidate-specific prompt
    prompt = db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.document_type == document_type,
        DocumentParsePrompt.candidate_id == candidate_id
    ).first()

    if prompt:
        # Update existing
        prompt.prompt_template = prompt_template
        prompt.description = description or prompt.description
    else:
        # Create new
        prompt = DocumentParsePrompt(
            candidate_id=candidate_id,
            name=system_prompt.name,
            description=description or system_prompt.description,
            document_type=document_type,
            prompt_template=prompt_template,
            output_schema=system_prompt.output_schema,
            is_system=False
        )
        db.add(prompt)

    db.commit()

    return {"success": True, "message": "Prompt saved successfully"}


@router.post("/{candidate_id}/prompts/{document_type}/reset")
async def reset_prompt(
    request: Request,
    candidate_id: int,
    document_type: str,
    db: Session = Depends(get_db)
):
    """Reset to system prompt"""
    system_prompt = reset_candidate_prompt_to_system(db, candidate_id, document_type)

    if not system_prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")

    return {
        "success": True,
        "message": "Prompt reset to system default",
        "prompt": {
            "id": system_prompt.id,
            "name": system_prompt.name,
            "prompt_template": system_prompt.prompt_template,
            "description": system_prompt.description
        }
    }
