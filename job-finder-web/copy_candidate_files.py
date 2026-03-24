#!/usr/bin/env python3
"""
Copy candidate documents from project root to candidate folder
"""
import shutil
from pathlib import Path
from backend.database import SessionLocal
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.config import DATA_DIR
import hashlib
import uuid

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Files to copy
FILES_TO_COPY = {
    "linkedin-profile.md": "profile",
    "prefered-job-titles.md": "job_titles",
    "cover-letter.md": "cover_letter",
}

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def copy_files_to_candidate(candidate_id: int = 1):
    """Copy files to candidate's document folder"""
    db = SessionLocal()
    
    try:
        # Get candidate
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            print(f"Candidate {candidate_id} not found!")
            return
        
        print(f"Copying files to: {candidate.name} (ID: {candidate_id})")
        print(f"Folder: {candidate.folder_path}")
        print("-" * 60)
        
        # Create documents folder
        candidate_folder = Path(candidate.folder_path) / "documents"
        candidate_folder.mkdir(parents=True, exist_ok=True)
        
        for filename, doc_type in FILES_TO_COPY.items():
            source = PROJECT_ROOT / filename
            if not source.exists():
                print(f"⚠️  File not found: {source}")
                continue
            
            # Generate unique filename
            file_ext = source.suffix
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            dest = candidate_folder / unique_filename
            
            # Copy file
            shutil.copy2(source, dest)
            
            # Calculate hash and size
            file_hash = calculate_file_hash(dest)
            file_size = dest.stat().st_size
            
            # Check for duplicates
            existing = db.query(CandidateDocument).filter(
                CandidateDocument.candidate_id == candidate_id,
                CandidateDocument.file_hash == file_hash,
                CandidateDocument.is_active == True
            ).first()
            
            if existing:
                print(f"⚠️  Skipping {filename} - duplicate already exists")
                dest.unlink()  # Remove the duplicate
                continue
            
            # Create database record
            document = CandidateDocument(
                candidate_id=candidate_id,
                filename=filename,
                file_path=str(dest.relative_to(DATA_DIR)),
                file_hash=file_hash,
                file_size=file_size,
                mime_type="text/markdown",
                document_type=doc_type,
                load_strategy="immediate",
                parse_status="completed"  # Will be parsed by AI in Phase 3
            )
            
            db.add(document)
            print(f"✅ Copied: {filename} → {doc_type}")
        
        db.commit()
        print("-" * 60)
        print(f"✅ Done! Files copied to {candidate.name}'s folder")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    candidate_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    copy_files_to_candidate(candidate_id)
