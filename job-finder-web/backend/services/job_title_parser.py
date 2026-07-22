"""
Job Title Parsing Service - AI-powered extraction from candidate documents

Uses LiteLLM native async (acompletion) for true non-blocking operation.
"""
import json
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.document import CandidateDocument, DocumentParsePrompt
from backend.models.supporting import CandidateJobTitle, ExtractionOccurrence
from backend.services.provenance import record_title_extraction
from backend.services.llm_service import extract_json_from_response, send_message


def get_parse_prompt(db: Session, document_type: str) -> Optional[DocumentParsePrompt]:
    """Get system prompt for document type"""
    return db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.document_type == document_type,
        DocumentParsePrompt.candidate_id.is_(None),
        DocumentParsePrompt.is_system == True
    ).first()


def _build_experience_summary(parsed_data: Dict) -> str:
    """Render a profile's structured experience entries as compact text.

    Kept in the same shape a resume would present them so the shared
    target-role policy prompt (`_run_job_titles_prompt`) judges the fast
    path the same way it judges raw file text — this is the only place
    that decides "concise target role" vs. "full work history", so both
    paths must go through it rather than a second, divergent heuristic.
    """
    lines = []
    for exp in parsed_data.get("experience", []):
        if not isinstance(exp, dict):
            continue
        title = (exp.get("title") or "").strip()
        if not title:
            continue
        company = (exp.get("company") or "Unknown").strip()
        start = (exp.get("start") or "").strip()
        end = (exp.get("end") or "").strip()
        dates = f" ({start} - {end})" if (start or end) else ""
        lines.append(f"- {title} at {company}{dates}")
    return "\n".join(lines)


_BARE_GENERIC_TITLE_LABELS = {
    "analyst", "architect", "consultant", "designer", "developer",
    "director", "engineer", "intern", "lead", "manager", "principal",
    "senior", "specialist", "staff", "technician",
}


def _is_usable_preferred_job_title(value: object) -> bool:
    """Keep model output aligned with the concise target-role contract.

    The prompt is the primary quality control, but small or permissive models
    can still return a bare seniority word or generic occupation. Those are
    not actionable search titles and should never be presented for saving.
    Multi-word titles such as ``Principal Software Engineer`` remain valid.
    """
    if not isinstance(value, str):
        return False
    title = value.strip()
    return bool(title) and title.casefold() not in _BARE_GENERIC_TITLE_LABELS


async def _run_job_titles_prompt(
    db: Session,
    document: CandidateDocument,
    content: str,
) -> Tuple[bool, List[Dict], Optional[str]]:
    """Apply the canonical target-role policy prompt to arbitrary content."""
    prompt_template = get_parse_prompt(db, "job_titles")
    if not prompt_template:
        return False, [], "No job_titles parse prompt configured"

    full_prompt = prompt_template.prompt_template.replace("{{content}}", content)
    # ``response_format={"type": "json_object"}`` (used by OpenAI and other
    # compatible providers) requires an object at the top level.  Persisted
    # prompts created before JSON mode asked for an array, so add the runtime
    # contract here until those prompts are edited or recreated.
    full_prompt += (
        '\n\nReturn a JSON object with this exact top-level shape: '
        '{"job_titles": [{"title": "...", "priority": 1, "description": "..."}]}. '
        'Use {"job_titles": []} when no suitable title is supported.'
    )

    # Resolve the configured Document Analysis provider and model.  This is
    # the same routing configured in AI Settings; function mappings are no
    # longer consulted.
    result = await send_message(
        full_prompt,
        db=db,
        routing_purpose="document_analysis",
        json_mode=True,
    )

    if not result:
        return False, [], "No usable Document Analysis provider is configured"

    parsed_data = extract_json_from_response(result)

    if parsed_data is None:
        return False, [], f"Failed to extract JSON from response: {result[:200]}"

    # Accept legacy array replies from non-JSON-mode providers as well as the
    # object wrapper required by JSON-mode providers.
    if isinstance(parsed_data, dict):
        parsed_data = parsed_data.get("job_titles")

    if not isinstance(parsed_data, list):
        return False, [], f"Expected JSON array, got: {type(parsed_data)}"

    job_titles = []
    for item in parsed_data:
        if isinstance(item, dict) and _is_usable_preferred_job_title(item.get("title")):
            job_titles.append({
                "title": item.get("title", "").strip(),
                "original_extracted_title": item.get("title", "").strip(),
                "priority": item.get("priority", 2),
                "description": item.get("description", ""),
                "source_file": document.filename,
                "source_document_id": document.id
            })

    return True, job_titles, None


async def parse_document_for_job_titles(
    db: Session,
    document: CandidateDocument
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse a single document for job titles using AI (native async).

    For profile/resume documents that have already been parsed, reuses the
    already-extracted experience section as input instead of re-reading the
    raw file — but the target-role policy is still applied by the same LLM
    prompt used for raw parsing, so this fast path never returns a raw
    transcription of every historical role (see `_run_job_titles_prompt`).

    Returns:
        (success, job_titles_list, error_message)
    """
    try:
        # For profile/resume documents, try to use already-parsed data first
        if document.document_type in ["profile", "resume"]:
            if document.parse_status == "completed" and document.parsed_data:
                parsed_data = document.get_parsed_data_json()
                if isinstance(parsed_data, dict) and "experience" in parsed_data:
                    experience_summary = _build_experience_summary(parsed_data)
                    if experience_summary:
                        return await _run_job_titles_prompt(db, document, experience_summary)
                # No usable experience entries — fall through to raw file parsing.

        # Read document content
        from backend.config import DATA_DIR
        file_path = DATA_DIR / document.file_path
        if not file_path.exists():
            return False, [], f"File not found: {file_path}"

        content = file_path.read_text(encoding="utf-8")

        return await _run_job_titles_prompt(db, document, content)

    except Exception as e:
        return False, [], str(e)


async def parse_selected_documents(
    db: Session,
    candidate_id: int,
    document_ids: List[int]
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse only selected documents for job titles (native async).

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
        success, titles, error = await parse_document_for_job_titles(db, doc)
        if success:
            all_job_titles.extend(titles)
        else:
            errors.append(f"{doc.filename}: {error}")

    if not all_job_titles:
        if len(errors) == len(documents):
            return False, [], f"All documents failed: {'; '.join(errors)}"
        return True, [], (
            "No suitable preferred job titles found. The model response did "
            "not contain a specific target role."
        )

    # Deduplicate by title
    deduplicated = {}
    for title_data in all_job_titles:
        title = title_data["title"]
        if title not in deduplicated or title_data["priority"] < deduplicated[title]["priority"]:
            deduplicated[title] = title_data

    result = sorted(deduplicated.values(), key=lambda x: x["priority"])

    warning = f"Warning: {'; '.join(errors)}" if errors else None
    return True, result, warning


async def parse_all_candidate_documents(
    db: Session,
    candidate_id: int
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse all relevant documents for a candidate and extract job titles (native async).

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
        success, titles, error = await parse_document_for_job_titles(db, doc)

        if success:
            all_job_titles.extend(titles)
        else:
            errors.append(f"{doc.filename}: {error}")

    if not all_job_titles:
        if len(errors) == len(documents):
            return False, [], f"All documents failed to parse: {'; '.join(errors)}"
        return True, [], (
            "No suitable preferred job titles found. The model response did "
            "not contain a specific target role."
        )

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

            document_id = title_data.get("source_document_id")
            if document_id:
                # Curated deduplication never discards the fact that another
                # uploaded file produced this value.
                record_title_extraction(
                    db, candidate_id, document_id, title_data["title"],
                    priority=title_data.get("priority", 2), description=title_data.get("description", ""),
                    extractor_version="job_titles_parser",
                )
            elif not existing:
                db.add(CandidateJobTitle(
                    candidate_id=candidate_id, title=title_data["title"],
                    priority=title_data.get("priority", 2), description=title_data.get("description", ""), source="edited",
                ))
            if not existing:
                count += 1

        db.commit()
        return True, count, None

    except Exception as e:
        db.rollback()
        return False, 0, str(e)


def sync_reviewed_job_titles(db: Session, candidate_id: int, job_titles_data: List[Dict], source_document_ids: Optional[List[int]] = None) -> Tuple[bool, Dict, Optional[str]]:
    """Apply a parse-review table as curation, including removals and edits.

    The review rows retain their source-document and original extracted title.
    That lets an omission remove only that document's occurrence, rather than
    deleting an unrelated title contributed by another document.
    """
    try:
        sourced_rows = [row for row in job_titles_data if row.get("source_document_id")]
        selected_documents = set(source_document_ids or []) | {row["source_document_id"] for row in sourced_rows}
        desired_keys = {
            (row["source_document_id"], row.get("original_extracted_title", row.get("title", "")).strip())
            for row in sourced_rows
        }
        affected_titles = set()
        created = updated = removed = unchanged = 0

        existing_occurrences = db.query(ExtractionOccurrence).join(CandidateJobTitle).filter(
            CandidateJobTitle.candidate_id == candidate_id,
            ExtractionOccurrence.document_id.in_(selected_documents) if selected_documents else False,
        ).all()
        occurrences_by_key = {
            (occurrence.document_id, occurrence.raw_extracted_value): occurrence
            for occurrence in existing_occurrences
        }

        for row in job_titles_data:
            title = row.get("title", "").strip()
            if not title:
                continue
            document_id = row.get("source_document_id")
            raw_title = row.get("original_extracted_title", title).strip()
            if not document_id:
                if not db.query(CandidateJobTitle).filter_by(candidate_id=candidate_id, title=title).first():
                    db.add(CandidateJobTitle(candidate_id=candidate_id, title=title,
                                              priority=row.get("priority", 2),
                                              description=row.get("description", ""), source="edited"))
                    created += 1
                else:
                    unchanged += 1
                continue

            occurrence = occurrences_by_key.get((document_id, raw_title))
            if occurrence:
                curated = occurrence.job_title
                changed = False
                if curated.title != title:
                    curated.title = title
                    curated.source = "edited"
                    changed = True
                if curated.priority != row.get("priority", 2):
                    curated.priority = row.get("priority", 2)
                    changed = True
                if (curated.description or "") != row.get("description", ""):
                    curated.description = row.get("description", "")
                    changed = True
                affected_titles.add(curated)
                updated += int(changed)
                unchanged += int(not changed)
            else:
                curated = record_title_extraction(
                    db, candidate_id, document_id, raw_title,
                    priority=row.get("priority", 2), description=row.get("description", ""),
                    extractor_version="job_titles_parser",
                )
                if curated.title != title:
                    curated.title = title
                    curated.source = "edited"
                affected_titles.add(curated)
                created += 1

        for occurrence in existing_occurrences:
            if (occurrence.document_id, occurrence.raw_extracted_value) not in desired_keys:
                affected_titles.add(occurrence.job_title)
                db.delete(occurrence)
                removed += 1

        db.flush()
        for curated in affected_titles:
            if not db.query(ExtractionOccurrence).filter_by(job_title_id=curated.id).first():
                db.delete(curated)
        db.commit()
        return True, {"created": created, "updated": updated, "removed": removed, "unchanged": unchanged}, None
    except Exception as exc:
        db.rollback()
        return False, {}, str(exc)


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
            "source": jt.source,
            "original_extracted_value": jt.original_extracted_value,
            "source_file": jt.extraction_occurrences[0].document.filename if jt.extraction_occurrences else "Manual"
        })

    return result
