"""Content-based classification for candidate uploads.

The stored document vocabulary deliberately keeps resumes and CVs together as
``resume``: the parsing and selection flows already treat them identically.
Classification is conservative; files without strong resume/CV structure stay
``custom`` rather than being inferred from their filename.
"""
from __future__ import annotations

from io import BytesIO
import re
from pathlib import Path


RESUME_SECTION_PATTERNS = (
    r"\b(?:professional |work )?experience\b",
    r"\bemployment history\b",
    r"\b(?:technical |core )?skills\b",
    r"\beducation\b",
    r"\b(?:selected )?projects\b",
    r"\bcertifications?\b",
)
CV_SIGNALS = (
    r"\bcurriculum vitae\b",
    r"\bacademic appointments?\b",
    r"\bresearch interests?\b",
    r"\bpublications?\b",
)
CONTACT_SIGNALS = (
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    r"\b(?:linkedin\.com|github\.com)\b",
    r"\b(?:phone|mobile|email|contact)\s*[:|]",
)


def classify_document_content(content: bytes, filename: str = "") -> str:
    """Return ``resume`` for resume/CV content and ``custom`` otherwise.

    ``filename`` is accepted for the upload boundary's convenience but is not
    used to classify the document.  PDF text is extracted when the optional
    parser is available; an unreadable or image-only PDF safely remains other.
    """
    text = _extract_text(content, Path(filename).suffix.lower())
    if not text:
        return "custom"

    normalized = " ".join(text.lower().split())
    section_count = sum(bool(re.search(pattern, normalized)) for pattern in RESUME_SECTION_PATTERNS)
    has_contact = any(re.search(pattern, normalized) for pattern in CONTACT_SIGNALS)
    has_cv_signal = any(re.search(pattern, normalized) for pattern in CV_SIGNALS)

    # A CV's distinctive academic sections are sufficient.  For a conventional
    # resume require multiple sections, or one section plus a contact signal,
    # so a job advert or a generic note does not become a resume by accident.
    if has_cv_signal or section_count >= 2 or (section_count >= 1 and has_contact):
        return "resume"
    return "custom"


def _extract_text(content: bytes, suffix: str) -> str:
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
        except Exception:
            return ""
    return content.decode("utf-8", errors="replace")
