"""
Document Routes - Upload, view, delete candidate documents
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path
import uuid
import hashlib
import shutil
from datetime import datetime

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.config import DATA_DIR

router = APIRouter()

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)

# Allowed document types
DOCUMENT_TYPES = {
    "job_titles": "Job Titles",
    "profile": "Profile / Resume",
    "resume": "Resume / CV",
    "cover_letter": "Cover Letter",
    "custom": "Custom"
}

# Allowed file extensions
ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def detect_document_type(filename: str) -> str:
    """Auto-detect document type from filename"""
    filename_lower = filename.lower()
    
    if any(x in filename_lower for x in ["job_title", "preferred_title", "target_title"]):
        return "job_titles"
    elif any(x in filename_lower for x in ["profile", "about", "bio"]):
        return "profile"
    elif any(x in filename_lower for x in ["resume", "cv", "curriculum"]):
        return "resume"
    elif any(x in filename_lower for x in ["cover_letter", "coverletter", "letter"]):
        return "cover_letter"
    else:
        return "custom"


@router.post("/{candidate_id}/documents/upload", response_class=JSONResponse)
async def upload_document(
    request: Request,
    candidate_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(""),
    load_strategy: str = Form("immediate"),
    db: Session = Depends(get_db)
):
    """Upload a document for a candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return JSONResponse({
            "success": False,
            "message": f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }, status_code=400)
    
    # Auto-detect document type if not provided
    if not document_type:
        document_type = detect_document_type(file.filename)
    
    # Create candidate document folder
    candidate_folder = Path(candidate.folder_path) / "documents"
    candidate_folder.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = candidate_folder / unique_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"Failed to save file: {str(e)}"
        }, status_code=500)
    
    # Calculate file hash and size
    file_hash = calculate_file_hash(file_path)
    file_size = file_path.stat().st_size
    
    # Check for duplicates
    existing = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.file_hash == file_hash,
        CandidateDocument.is_active == True
    ).first()
    
    if existing:
        # Delete the duplicate file
        file_path.unlink()
        return JSONResponse({
            "success": False,
            "message": "Duplicate file detected (same content already exists)"
        }, status_code=409)
    
    # Create database record
    try:
        document = CandidateDocument(
            candidate_id=candidate_id,
            filename=file.filename,
            file_path=str(file_path.relative_to(DATA_DIR)),
            file_hash=file_hash,
            file_size=file_size,
            mime_type="text/markdown" if file_ext == ".md" else "text/plain" if file_ext == ".txt" else "application/pdf",
            document_type=document_type,
            load_strategy=load_strategy,
            parse_status="pending" if load_strategy == "immediate" else "not_required"
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # TODO: If immediate parsing is requested, trigger AI parsing here
        # For now, we'll just mark it as completed for markdown files
        if load_strategy == "immediate" and file_ext in [".md", ".txt"]:
            # Read content for future parsing
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Mark as completed (actual parsing will be done by AI agent in Phase 3)
            document.parse_status = "completed"
            db.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Document uploaded successfully",
            "document_id": document.id
        })
        
    except Exception as e:
        db.rollback()
        # Clean up file
        if file_path.exists():
            file_path.unlink()
        return JSONResponse({
            "success": False,
            "message": f"Database error: {str(e)}"
        }, status_code=500)


@router.get("/{candidate_id}/documents/{doc_id}/view", response_class=JSONResponse)
async def view_document(
    candidate_id: int,
    doc_id: int,
    db: Session = Depends(get_db)
):
    """View document content"""
    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == doc_id,
        CandidateDocument.candidate_id == candidate_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Read file content
    file_path = Path(document.file_path)
    if not file_path.is_absolute():
        file_path = DATA_DIR / file_path
    
    if not file_path.exists():
        return JSONResponse({
            "success": False,
            "message": "File not found on disk"
        }, status_code=404)
    
    try:
        if file_path.suffix in [".md", ".txt"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        elif file_path.suffix == ".pdf":
            content = "[PDF files cannot be displayed as text. Download to view.]"
        else:
            content = "[Unsupported file type for preview]"
        
        return JSONResponse({
            "success": True,
            "filename": document.filename,
            "content": content,
            "parsed_data": document.get_parsed_data_json()
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"Failed to read file: {str(e)}"
        }, status_code=500)


@router.post("/{candidate_id}/documents/{doc_id}/delete", response_class=JSONResponse)
async def delete_document(
    candidate_id: int,
    doc_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document (soft delete)"""
    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == doc_id,
        CandidateDocument.candidate_id == candidate_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Soft delete
        document.is_active = False
        db.commit()
        
        # Note: We keep the file on disk for audit purposes
        # Could add hard delete option if needed
        
        return JSONResponse({
            "success": True,
            "message": "Document deleted successfully"
        })
        
    except Exception as e:
        db.rollback()
        return JSONResponse({
            "success": False,
            "message": f"Failed to delete: {str(e)}"
        }, status_code=500)


@router.post("/{candidate_id}/documents/{doc_id}/reparse", response_class=JSONResponse)
async def reparse_document(
    candidate_id: int,
    doc_id: int,
    db: Session = Depends(get_db)
):
    """Re-parse a document with AI"""
    document = db.query(CandidateDocument).filter(
        CandidateDocument.id == doc_id,
        CandidateDocument.candidate_id == candidate_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.document_type not in ["job_titles", "profile"]:
        return JSONResponse({
            "success": False,
            "message": "Only job titles and profile documents can be parsed"
        }, status_code=400)
    
    try:
        # Reset parse status
        document.parse_status = "pending"
        document.parse_error = None
        document.parsed_data = None
        db.commit()
        
        # TODO: Trigger AI parsing here (Phase 3)
        # For now, just mark as completed
        document.parse_status = "completed"
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Document re-parsed successfully"
        })
        
    except Exception as e:
        db.rollback()
        return JSONResponse({
            "success": False,
            "message": f"Re-parse failed: {str(e)}"
        }, status_code=500)
