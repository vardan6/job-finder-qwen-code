"""
Per-Job Tailored Document Generation (R11)

Generates a tailored resume or cover letter for a specific job from the
candidate's most recently uploaded resume/CV, using the configured
Document Analysis route (backend.services.ai_routing / llm_service).
"""
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import DATA_DIR
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument, GeneratedDocument
from backend.models.job import Job
from backend.security import safe_resolve_path
from backend.services import llm_service
from backend.services.ai_routing import resolve_chat_model_selection

logger = logging.getLogger(__name__)

RESUME = "resume"
COVER_LETTER = "cover_letter"

# Tailored generation reuses the Document Analysis routing purpose — the
# closest existing bucket to "produce a document from source text" and
# already configured in AI Settings, avoiding a new unconfigured purpose.
GENERATION_ROUTING_PURPOSE = "document_analysis"

# Source documents are truncated so prompts stay within typical provider
# context windows regardless of how large an uploaded resume or job posting is.
MAX_RESUME_CHARS = 12000
MAX_JOB_DESCRIPTION_CHARS = 6000


class DocumentGenerationError(Exception):
    """Raised when a tailored document cannot be generated for a job."""


def _read_document_text(document: CandidateDocument) -> Optional[str]:
    """Read a candidate document's text content, confined to DATA_DIR."""
    raw_path = Path(document.file_path)
    if not raw_path.is_absolute():
        raw_path = DATA_DIR / raw_path
    try:
        file_path = safe_resolve_path(str(raw_path), DATA_DIR)
    except ValueError:
        return None
    # Only plain-text/markdown sources can be fed into the prompt directly.
    if not file_path.exists() or file_path.suffix.lower() not in (".md", ".txt"):
        return None
    return file_path.read_text(encoding="utf-8")


def get_source_resume_text(db: Session, candidate: Candidate) -> Optional[str]:
    """Return the candidate's most recently uploaded resume/CV text, if any."""
    document = (
        db.query(CandidateDocument)
        .filter(
            CandidateDocument.candidate_id == candidate.id,
            CandidateDocument.document_type.in_([RESUME, "cv"]),
            CandidateDocument.is_active == True,
        )
        .order_by(CandidateDocument.created_at.desc())
        .first()
    )
    if not document:
        return None
    return _read_document_text(document)


def get_job_description_text(job: Job) -> str:
    """Return the job's full description if stored on disk, else its snippet."""
    if job.description_path:
        try:
            desc_path = safe_resolve_path(job.description_path, DATA_DIR)
            if desc_path.exists():
                return desc_path.read_text(encoding="utf-8")
        except ValueError:
            pass
    return job.description_snippet or ""


def _build_prompt(document_type: str, resume_text: str, job_description: str, job: Job) -> str:
    resume_excerpt = resume_text[:MAX_RESUME_CHARS]
    job_excerpt = job_description[:MAX_JOB_DESCRIPTION_CHARS]

    if document_type == RESUME:
        return f"""You are an expert resume writer. Tailor the candidate's resume below to \
best match the target job, while staying strictly truthful to the candidate's \
actual experience — do not invent employers, titles, dates, or skills.

Rewrite the resume so that relevant experience and skills for this job are \
emphasized and reordered where appropriate. Keep it in clean markdown, ready \
to save as a standalone resume file.

Target job: {job.title} at {job.company}
Job description:
---
{job_excerpt}
---

Candidate's existing resume:
---
{resume_excerpt}
---

Return only the tailored resume in markdown, with no extra commentary."""

    return f"""You are an expert cover letter writer. Write a concise, tailored cover \
letter for the candidate below applying to the target job. Base every claim \
strictly on the candidate's actual resume content — do not invent employers, \
titles, dates, or skills.

Target job: {job.title} at {job.company}
Job description:
---
{job_excerpt}
---

Candidate's resume:
---
{resume_excerpt}
---

Return only the cover letter text in markdown, with no extra commentary."""


async def generate_tailored_document(
    db: Session, candidate: Candidate, job: Job, document_type: str
) -> GeneratedDocument:
    """Generate (or regenerate) a tailored document for a job and persist it.

    Regeneration replaces the existing row for (job, document_type) rather
    than keeping version history.
    """
    if document_type not in (RESUME, COVER_LETTER):
        raise DocumentGenerationError(f"Unsupported document type '{document_type}'")

    resume_text = get_source_resume_text(db, candidate)
    if not resume_text:
        raise DocumentGenerationError(
            "Upload a resume or CV (markdown/text) before generating tailored documents."
        )

    try:
        selection = resolve_chat_model_selection(db, purpose=GENERATION_ROUTING_PURPOSE)
    except ValueError:
        raise DocumentGenerationError(
            "No LLM provider is configured for Document Analysis. Configure one in AI Settings."
        )

    job_description = get_job_description_text(job)
    prompt = _build_prompt(document_type, resume_text, job_description, job)

    content = await llm_service.send_message(
        prompt, db=db, routing_purpose=GENERATION_ROUTING_PURPOSE
    )
    if not content:
        raise DocumentGenerationError(
            "The configured LLM provider returned no content. Check AI Settings."
        )

    generated = (
        db.query(GeneratedDocument)
        .filter(
            GeneratedDocument.job_id == job.id,
            GeneratedDocument.document_type == document_type,
        )
        .first()
    )
    if generated is None:
        generated = GeneratedDocument(
            candidate_id=candidate.id,
            job_id=job.id,
            document_type=document_type,
        )
        db.add(generated)

    generated.content = content.strip()
    generated.llm_provider_name = selection.provider.name if selection.provider else None
    generated.llm_model_name = selection.model.model_name if selection.model else None
    db.commit()
    db.refresh(generated)
    return generated
