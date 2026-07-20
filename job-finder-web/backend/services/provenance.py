"""Extraction provenance helpers shared by profile parsers and routes."""
from backend.models.supporting import CandidateJobTitle, CandidateSkill, ExtractionOccurrence


def record_title_extraction(db, candidate_id, document_id, title, *, priority=2, description=None, extractor_version=None):
    curated = db.query(CandidateJobTitle).filter(
        CandidateJobTitle.candidate_id == candidate_id,
        CandidateJobTitle.title == title,
    ).first()
    if not curated:
        curated = CandidateJobTitle(
            candidate_id=candidate_id, title=title, priority=priority,
            description=description, source="extracted", original_extracted_value=title,
        )
        db.add(curated)
        db.flush()
    _record_occurrence(db, document_id, "job_title_id", curated.id, title, extractor_version)
    return curated


def record_skill_extraction(db, candidate_id, document_id, skill_name, *, category="preferred", years_experience=None, is_enabled=True, extractor_version=None):
    curated = db.query(CandidateSkill).filter(
        CandidateSkill.candidate_id == candidate_id,
        CandidateSkill.skill_name.ilike(skill_name), CandidateSkill.is_active == True,
    ).first()
    if not curated:
        curated = CandidateSkill(
            candidate_id=candidate_id, skill_name=skill_name, category=category,
            years_experience=years_experience, is_enabled=is_enabled,
            source="extracted", original_extracted_value=skill_name,
        )
        db.add(curated)
        db.flush()
    _record_occurrence(db, document_id, "skill_id", curated.id, skill_name, extractor_version)
    return curated


def _record_occurrence(db, document_id, fk_column, curated_id, raw_value, extractor_version):
    if not document_id:
        return
    filters = {"document_id": document_id, fk_column: curated_id, "raw_extracted_value": raw_value}
    if not db.query(ExtractionOccurrence).filter_by(**filters).first():
        db.add(ExtractionOccurrence(**filters, extractor_version=extractor_version))
