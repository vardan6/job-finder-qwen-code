from __future__ import annotations

from backend.ai_session_store import AISessionStore, default_source_controls


def test_create_session_defaults_source_controls(tmp_path) -> None:
    store = AISessionStore(tmp_path / "ai-sessions.sqlite3")

    session = store.create_session()

    assert session["source_controls"] == default_source_controls()
    assert session["meta"]["source_controls"] == default_source_controls()


def test_update_session_persists_provider_and_source_controls(tmp_path) -> None:
    store = AISessionStore(tmp_path / "ai-sessions.sqlite3")
    session = store.create_session()

    updated = store.update_session(
        session["id"],
        provider_id="provider-a",
        source_controls={
            "candidate_profile": True,
            "candidate_job_titles": False,
            "candidate_skills": True,
            "candidate_documents": True,
            "job_preferences": True,
            "ai_chat_history": True,
            "settings_config": True,
            "workspace_files": False,
        },
    )

    assert updated is not None
    assert updated["provider_id"] == "provider-a"
    assert updated["source_controls"]["candidate_job_titles"] is False
    assert updated["source_controls"]["job_preferences"] is True
    assert updated["meta"]["source_controls"] == updated["source_controls"]


def test_message_search_excludes_archived_sessions_by_default(tmp_path) -> None:
    store = AISessionStore(tmp_path / "ai-sessions.sqlite3")
    active = store.create_session(title="Active")
    archived = store.create_session(title="Archived")
    store.add_message(active["id"], role="user", content="resume summary")
    store.add_message(archived["id"], role="user", content="resume summary archived")
    store.archive_session(archived["id"])

    matches = store.search_messages("resume", limit=10)

    assert len(matches) == 1
    assert matches[0]["session_id"] == active["id"]


def test_maybe_auto_title_uses_first_prompt(tmp_path) -> None:
    store = AISessionStore(tmp_path / "ai-sessions.sqlite3")
    session = store.create_session()

    renamed = store.maybe_auto_title(session["id"], "Help me tailor my resume for staff backend roles")

    assert renamed is not None
    assert renamed["title"].startswith("Help me tailor my resume")
