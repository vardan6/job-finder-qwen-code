from backend.routes.documents import detect_document_type
from backend.services.document_classification import classify_document_content


def test_classifies_misnamed_resume_from_its_content():
    content = b"""
    Jane Doe | jane@example.com | linkedin.com/in/janedoe
    Experience
    Software Engineer, Example Co.
    Skills
    Python, FastAPI, SQL
    Education
    BSc Computer Science
    """

    assert detect_document_type(content, "notes-for-monday.txt") == "resume"


def test_filename_does_not_turn_non_resume_content_into_a_resume():
    cover_letter = b"Dear hiring manager, I am excited to apply for this role."

    assert detect_document_type(cover_letter, "my_resume_final.txt") == "custom"


def test_classifies_curriculum_vitae_content_as_resume():
    content = b"Curriculum Vitae\nPublications\nResearch Interests\nAcademic Appointments"

    assert classify_document_content(content, "untitled.md") == "resume"


def test_unstructured_content_stays_other():
    assert classify_document_content(b"Shopping list: tea, bread, and fruit.", "anything.txt") == "custom"
