"""
Regression tests for consistent target-role policy application across both
job-title extraction paths (Phase 9.5 — preferred-title extraction quality).

The profile/resume "fast path" used to raw-dump every experience.title as a
curated job title, bypassing the concise target-role policy the LLM prompt
enforces on the raw-file path. Both paths must now route through the same
policy prompt (`_run_job_titles_prompt`) instead of one path re-implementing
its own divergent heuristic.
"""
import json

import pytest

from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument, DocumentParsePrompt
from backend.services.job_title_parser import (
    parse_document_for_job_titles,
    parse_selected_documents,
)

JOB_TITLES_PROMPT = 'Curate concise target titles.\n{{content}}'


def _seed_job_titles_prompt(db):
    db.add(DocumentParsePrompt(
        name="job_titles_parser",
        document_type="job_titles",
        prompt_template=JOB_TITLES_PROMPT,
        is_system=True,
    ))
    db.commit()


def _profile_document(db, candidate, experience):
    document = CandidateDocument(
        candidate_id=candidate.id,
        filename="profile.md",
        file_path="profile.md",
        document_type="profile",
        parse_status="completed",
    )
    document.set_parsed_data_json({"experience": experience})
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@pytest.fixture
def candidate(db):
    c = Candidate(name="Policy", folder_path="/tmp/policy", uuid="policy")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.mark.asyncio
async def test_profile_fast_path_routes_experience_through_the_policy_prompt(db, candidate, monkeypatch):
    """The fast path must not raw-dump every historical title; it must ask
    the same policy prompt to judge the experience data, same as the raw-file
    path does."""
    _seed_job_titles_prompt(db)
    experience = [
        {"title": "Software Engineer", "company": "Acme", "start": "2018", "end": "2020"},
        {"title": "Senior Software Engineer", "company": "Acme", "start": "2020", "end": "2022"},
        {"title": "Staff Software Engineer", "company": "Beta Corp", "start": "2022", "end": "2024"},
    ]
    document = _profile_document(db, candidate, experience)

    captured_prompts = []

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        captured_prompts.append(prompt)
        return json.dumps([{"title": "Staff Software Engineer", "priority": 1, "description": "Most recent target"}])

    monkeypatch.setattr("backend.services.job_title_parser.send_message", fake_send_message)

    success, job_titles, error = await parse_document_for_job_titles(db, document)

    assert success, error
    # The policy prompt decided the output, not a raw dump of all 3 roles.
    assert [jt["title"] for jt in job_titles] == ["Staff Software Engineer"]
    assert len(captured_prompts) == 1
    # The experience data (not raw resume text) was fed to the policy prompt.
    assert "Software Engineer at Acme" in captured_prompts[0]
    assert "Staff Software Engineer at Beta Corp" in captured_prompts[0]


@pytest.mark.asyncio
async def test_title_parser_rejects_bare_generic_labels_from_model_output(db, candidate, monkeypatch):
    _seed_job_titles_prompt(db)
    document = _profile_document(db, candidate, [{"title": "Staff Software Engineer"}])

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        return json.dumps([
            {"title": "Principal", "priority": 1},
            {"title": "Engineer", "priority": 2},
            {"title": "Staff Software Engineer", "priority": 1},
        ])

    monkeypatch.setattr("backend.services.job_title_parser.send_message", fake_send_message)

    success, job_titles, error = await parse_document_for_job_titles(db, document)

    assert success, error
    assert [job_title["title"] for job_title in job_titles] == ["Staff Software Engineer"]


@pytest.mark.asyncio
async def test_title_parser_accepts_the_json_mode_object_wrapper(db, candidate, monkeypatch):
    _seed_job_titles_prompt(db)
    document = _profile_document(db, candidate, [{"title": "Staff Software Engineer"}])

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        assert kwargs.get("json_mode") is True
        assert '"job_titles"' in prompt
        return json.dumps({
            "job_titles": [{"title": "AI Engineer", "priority": 1}],
        })

    monkeypatch.setattr("backend.services.job_title_parser.send_message", fake_send_message)

    success, job_titles, error = await parse_document_for_job_titles(db, document)

    assert success, error
    assert [job_title["title"] for job_title in job_titles] == ["AI Engineer"]


@pytest.mark.asyncio
async def test_generic_only_model_output_is_a_successful_empty_review(db, candidate, monkeypatch):
    """A successful LLM call with no usable target title is not a server error."""
    _seed_job_titles_prompt(db)
    document = _profile_document(db, candidate, [{"title": "Staff Software Engineer"}])

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        return json.dumps([
            {"title": "Principal", "priority": 1},
            {"title": "Engineer", "priority": 2},
        ])

    monkeypatch.setattr("backend.services.job_title_parser.send_message", fake_send_message)

    success, job_titles, warning = await parse_selected_documents(
        db, candidate.id, [document.id],
    )

    assert success
    assert job_titles == []
    assert warning == (
        "No suitable preferred job titles found. The model response did "
        "not contain a specific target role."
    )


@pytest.mark.asyncio
async def test_explicit_empty_json_mode_result_is_a_successful_empty_review(db, candidate, monkeypatch):
    _seed_job_titles_prompt(db)
    document = _profile_document(db, candidate, [{"title": "Staff Software Engineer"}])

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        return json.dumps({"job_titles": []})

    monkeypatch.setattr("backend.services.job_title_parser.send_message", fake_send_message)

    success, job_titles, warning = await parse_selected_documents(
        db, candidate.id, [document.id],
    )

    assert success
    assert job_titles == []
    assert warning == (
        "No suitable preferred job titles found. The model response did "
        "not contain a specific target role."
    )


@pytest.mark.asyncio
async def test_profile_fast_path_falls_back_to_raw_file_when_no_experience_titles(db, candidate, monkeypatch, tmp_path):
    _seed_job_titles_prompt(db)
    document = CandidateDocument(
        candidate_id=candidate.id,
        filename="profile.md",
        file_path="profile.md",
        document_type="profile",
        parse_status="completed",
    )
    document.set_parsed_data_json({"experience": []})
    db.add(document)
    db.commit()
    db.refresh(document)

    resume_file = tmp_path / "profile.md"
    resume_file.write_text("# Raw resume text", encoding="utf-8")
    monkeypatch.setattr("backend.config.DATA_DIR", tmp_path)

    captured_prompts = []

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        captured_prompts.append(prompt)
        return json.dumps([{"title": "Staff SDET", "priority": 1, "description": "Explicit target"}])

    monkeypatch.setattr("backend.services.job_title_parser.send_message", fake_send_message)

    success, job_titles, error = await parse_document_for_job_titles(db, document)

    assert success, error
    assert [jt["title"] for jt in job_titles] == ["Staff SDET"]
    assert "Raw resume text" in captured_prompts[0]
