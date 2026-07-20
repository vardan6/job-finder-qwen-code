from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.supporting import CandidateJobTitle, CandidateSkill, ExtractionOccurrence
from backend.services.provenance import record_skill_extraction, record_title_extraction


def _document(db, candidate, name):
    document = CandidateDocument(candidate_id=candidate.id, filename=name, file_path=name, document_type="profile")
    db.add(document)
    db.flush()
    return document


def test_same_extracted_title_retains_an_occurrence_per_file(db):
    candidate = Candidate(name="Provenance", folder_path="/tmp/provenance", uuid="provenance")
    db.add(candidate)
    db.flush()
    first, second = _document(db, candidate, "resume.md"), _document(db, candidate, "preferences.md")

    first_title = record_title_extraction(db, candidate.id, first.id, "Platform Engineer", extractor_version="v1")
    second_title = record_title_extraction(db, candidate.id, second.id, "Platform Engineer", extractor_version="v1")
    db.commit()

    assert first_title.id == second_title.id
    assert first_title.source == "extracted"
    assert first_title.original_extracted_value == "Platform Engineer"
    assert db.query(ExtractionOccurrence).filter_by(job_title_id=first_title.id).count() == 2


def test_reset_value_keeps_occurrences_after_curated_edit(db):
    candidate = Candidate(name="Provenance", folder_path="/tmp/provenance-2", uuid="provenance-2")
    db.add(candidate)
    db.flush()
    document = _document(db, candidate, "resume.md")
    skill = record_skill_extraction(db, candidate.id, document.id, "PostgreSQL")
    skill.skill_name = "Postgres"
    skill.source = "edited"
    db.commit()

    skill.skill_name = skill.original_extracted_value
    skill.source = "extracted"
    db.commit()

    assert skill.skill_name == "PostgreSQL"
    assert db.query(ExtractionOccurrence).filter_by(skill_id=skill.id).count() == 1
