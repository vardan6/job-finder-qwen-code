"""
Job Title Parsing Service - AI-powered extraction from candidate documents
"""
import json
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.document import CandidateDocument, DocumentParsePrompt, LLMFunctionMapping
from backend.models.llm_provider import LLMProvider, LLMModel
from backend.models.supporting import CandidateJobTitle
from backend.services.llm_service import call_llm, extract_json_from_response, get_llm_for_function


def get_parse_prompt(db: Session, document_type: str) -> Optional[DocumentParsePrompt]:
    """Get system prompt for document type"""
    return db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.document_type == document_type,
        DocumentParsePrompt.candidate_id.is_(None),
        DocumentParsePrompt.is_system == True
    ).first()


def parse_document_for_job_titles(
    db: Session,
    document: CandidateDocument
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse a single document for job titles using AI.

    For profile/resume documents that have already been parsed, extracts job titles
    from the existing parsed data instead of making a new LLM call.

    Returns:
        (success, job_titles_list, error_message)
    """
    try:
        # For profile/resume documents, try to use already-parsed data first
        if document.document_type in ["profile", "resume"]:
            # Check if document has already been parsed
            if document.parse_status == "completed" and document.parsed_data:
                parsed_data = document.get_parsed_data_json()
                
                # Extract job titles from profile data (experience section)
                job_titles = []
                if isinstance(parsed_data, dict) and "experience" in parsed_data:
                    experience_list = parsed_data.get("experience", [])
                    for exp in experience_list:
                        if isinstance(exp, dict) and "title" in exp:
                            job_titles.append({
                                "title": exp.get("title", "").strip(),
                                "priority": 2,  # Medium priority for historical roles
                                "description": f"From experience at {exp.get('company', 'Unknown')}",
                                "source_file": document.filename,
                                "source_document_id": document.id
                            })
                    
                    if job_titles:
                        return True, job_titles, None
                
                # If no experience-based titles found, fall through to AI parsing below
                # But use job_titles-specific prompt, not profile prompt
                # This handles cases where profile was parsed but didn't extract titles
        
        # Read document content
        file_path = Path("data") / document.file_path
        if not file_path.exists():
            return False, [], f"File not found: {file_path}"

        content = file_path.read_text(encoding="utf-8")

        # Get appropriate prompt - ALWAYS use job_titles prompt for job title extraction
        prompt_template = get_parse_prompt(db, "job_titles")

        if not prompt_template:
            return False, [], "No job_titles parse prompt configured"

        # Build the prompt
        full_prompt = prompt_template.prompt_template.replace("{{content}}", content)

        # Get LLM model for job_title_parser function
        model = get_llm_for_function(db, "job_title_parser")

        # Fall back to default Ollama if not configured
        if not model:
            ollama = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
            if ollama:
                model = db.query(LLMModel).filter(
                    LLMModel.provider_id == ollama.id,
                    LLMModel.is_default_for_provider == True
                ).first()

        if not model:
            return False, [], "No LLM model configured for parsing"

        # Call LLM
        result = call_llm(db, model, full_prompt)

        # Fallback to direct Ollama call if configured model failed
        if not result:
            try:
                from litellm import completion
                response = completion(
                    model="ollama/llama3",
                    messages=[{"role": "user", "content": full_prompt}],
                    api_base="http://localhost:11434"
                )
                result = response.choices[0].message.content if response else None
            except Exception as ollama_error:
                print(f"Direct Ollama fallback failed: {ollama_error}")
                return False, [], f"LLM call failed: {str(ollama_error)}"

        if not result:
            return False, [], "LLM returned empty response"

        # Extract JSON from response
        parsed_data = extract_json_from_response(result)

        if not parsed_data:
            return False, [], f"Failed to extract JSON from response: {result[:200]}"

        # Validate it's a list
        if not isinstance(parsed_data, list):
            return False, [], f"Expected JSON array, got: {type(parsed_data)}"

        # Normalize the data
        job_titles = []
        for item in parsed_data:
            if isinstance(item, dict) and "title" in item:
                job_titles.append({
                    "title": item.get("title", "").strip(),
                    "priority": item.get("priority", 2),
                    "description": item.get("description", ""),
                    "source_file": document.filename,
                    "source_document_id": document.id
                })

        return True, job_titles, None

    except Exception as e:
        return False, [], str(e)


def parse_selected_documents(
    db: Session,
    candidate_id: int,
    document_ids: List[int]
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse only selected documents for job titles.
    
    Returns:
        (success, job_titles_list, error_message)
    """
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.id.in_(document_ids),
        CandidateDocument.is_active == True
    ).all()
    
    if not documents:
        return False, [], "No documents found"
    
    all_job_titles = []
    errors = []
    
    for doc in documents:
        success, titles, error = parse_document_for_job_titles(db, doc)
        if success:
            all_job_titles.extend(titles)
        else:
            errors.append(f"{doc.filename}: {error}")
    
    if not all_job_titles:
        return False, [], f"All documents failed: {'; '.join(errors)}"
    
    # Deduplicate by title
    deduplicated = {}
    for title_data in all_job_titles:
        title = title_data["title"]
        if title not in deduplicated or title_data["priority"] < deduplicated[title]["priority"]:
            deduplicated[title] = title_data
    
    result = sorted(deduplicated.values(), key=lambda x: x["priority"])
    
    warning = f"Warning: {'; '.join(errors)}" if errors else None
    return True, result, warning


def parse_all_candidate_documents(
    db: Session, 
    candidate_id: int
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse all relevant documents for a candidate and extract job titles.
    
    Returns:
        (success, combined_job_titles_list, error_message)
    """
    # Get all active documents for this candidate
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.is_active == True,
        CandidateDocument.document_type.in_(["job_titles", "profile", "resume"])
    ).all()
    
    if not documents:
        return False, [], "No documents found to parse"
    
    all_job_titles = []
    errors = []
    
    for doc in documents:
        success, titles, error = parse_document_for_job_titles(db, doc)
        
        if success:
            all_job_titles.extend(titles)
        else:
            errors.append(f"{doc.filename}: {error}")
    
    if not all_job_titles:
        return False, [], f"All documents failed to parse: {'; '.join(errors)}"
    
    # Deduplicate by title (keep highest priority)
    deduplicated = {}
    for title_data in all_job_titles:
        title = title_data["title"]
        if title not in deduplicated or title_data["priority"] < deduplicated[title]["priority"]:
            deduplicated[title] = title_data
    
    # Convert to list and sort by priority
    result = sorted(deduplicated.values(), key=lambda x: x["priority"])
    
    # Add warnings if some documents failed
    warning = None
    if errors:
        warning = f"Warning: Some documents failed to parse: {'; '.join(errors)}"
    
    return True, result, warning


def save_job_titles_to_candidate(
    db: Session,
    candidate_id: int,
    job_titles_data: List[Dict],
    clear_existing: bool = False
) -> Tuple[bool, int, Optional[str]]:
    """
    Save parsed job titles to candidate's profile.
    
    Args:
        db: Database session
        candidate_id: Candidate ID
        job_titles_data: List of job title dicts with title, priority, description
        clear_existing: If True, remove existing job titles first
    
    Returns:
        (success, count_saved, error_message)
    """
    try:
        if clear_existing:
            # Soft delete existing job titles
            existing = db.query(CandidateJobTitle).filter(
                CandidateJobTitle.candidate_id == candidate_id
            ).all()
            for jt in existing:
                db.delete(jt)
            db.commit()
        
        # Add new job titles
        count = 0
        for title_data in job_titles_data:
            # Skip empty titles
            if not title_data.get("title"):
                continue
            
            # Check for duplicates
            existing = db.query(CandidateJobTitle).filter(
                CandidateJobTitle.candidate_id == candidate_id,
                CandidateJobTitle.title == title_data["title"]
            ).first()
            
            if existing:
                continue
            
            job_title = CandidateJobTitle(
                candidate_id=candidate_id,
                title=title_data["title"],
                priority=title_data.get("priority", 2),
                description=title_data.get("description", ""),
                source_document_id=title_data.get("source_document_id")
            )
            db.add(job_title)
            count += 1
        
        db.commit()
        return True, count, None
        
    except Exception as e:
        db.rollback()
        return False, 0, str(e)


def get_candidate_job_titles_with_sources(
    db: Session,
    candidate_id: int
) -> List[Dict]:
    """Get candidate's job titles with source document info"""
    job_titles = db.query(CandidateJobTitle).filter(
        CandidateJobTitle.candidate_id == candidate_id
    ).order_by(CandidateJobTitle.priority).all()
    
    result = []
    for jt in job_titles:
        result.append({
            "id": jt.id,
            "title": jt.title,
            "priority": jt.priority,
            "description": jt.description or "",
            "source_document_id": jt.source_document_id,
            "source_file": jt.source_document.filename if jt.source_document else "Manual"
        })
    
    return result
