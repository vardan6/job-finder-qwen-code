from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.ai_config_store import load_ai_config
from backend.ai_session_store import get_ai_session_store
from backend.config import BASE_DIR
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.job import Job, JobApplication
from backend.models.supporting import CandidatePreferences


TOOL_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "name": "candidate_profile_lookup",
        "description": "Read candidate profile fields by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int"},
    },
    {
        "name": "candidate_titles_lookup",
        "description": "Read active candidate job titles by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int"},
    },
    {
        "name": "candidate_skills_lookup",
        "description": "Read active candidate skills by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int"},
    },
    {
        "name": "candidate_documents_lookup",
        "description": "Read active candidate documents by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int"},
    },
    {
        "name": "candidate_preferences_lookup",
        "description": "Read candidate preferences by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int"},
    },
    {
        "name": "candidate_jobs_lookup",
        "description": "Read candidate jobs/search results by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int", "status": "str?", "limit": "int?"},
    },
    {
        "name": "candidate_employers_lookup",
        "description": "Read employer summary from candidate jobs by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int", "limit": "int?"},
    },
    {
        "name": "candidate_applications_lookup",
        "description": "Read application tracker rows joined to candidate jobs by candidate_id.",
        "mode": "read",
        "params": {"candidate_id": "int", "status": "str?", "limit": "int?"},
    },
    {
        "name": "chat_history_lookup",
        "description": "Read AI chat messages by session_id.",
        "mode": "read",
        "params": {"session_id": "str", "limit": "int?"},
    },
    {
        "name": "settings_lookup",
        "description": "Read current AI settings, provider settings, and routing.",
        "mode": "read",
        "params": {},
    },
    {
        "name": "workspace_files_read",
        "description": "Read a workspace file path.",
        "mode": "read",
        "params": {"path": "str"},
    },
    {
        "name": "workspace_files_write",
        "description": "Write a workspace file path (policy-gated).",
        "mode": "write",
        "params": {"path": "str", "content": "str", "create_dirs": "bool?"},
    },
)


def get_tool_definition(name: str) -> dict[str, Any] | None:
    return next((tool for tool in TOOL_REGISTRY if tool.get("name") == name), None)


def _require_int(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{name} must be an integer") from exc


def _require_bounded_int(value: Any, name: str, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        parsed = default
    else:
        parsed = _require_int(value, name)
    if parsed < minimum or parsed > maximum:
        raise HTTPException(status_code=400, detail=f"{name} must be between {minimum} and {maximum}")
    return parsed


def _workspace_root() -> Path:
    configured = os.getenv("AI_WORKSPACE_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    return BASE_DIR.parent.parent.resolve()


def _safe_workspace_path(raw_path: Any) -> Path:
    path_str = str(raw_path or "").strip()
    if not path_str:
        raise HTTPException(status_code=400, detail="path is required")

    root = _workspace_root()
    target = (root / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path must stay inside AI_WORKSPACE_ROOT") from exc
    return target


def _candidate_or_404(db: Session, candidate_id: int) -> Candidate:
    candidate = db.query(Candidate).options(
        joinedload(Candidate.job_titles),
        joinedload(Candidate.skills),
        joinedload(Candidate.documents),
        joinedload(Candidate.preferences),
    ).filter(Candidate.id == candidate_id, Candidate.is_active == True).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


def execute_tool(name: str, args: dict[str, Any], db: Session) -> dict[str, Any]:
    if name == "candidate_profile_lookup":
        candidate = _candidate_or_404(db, _require_int(args.get("candidate_id"), "candidate_id"))
        return {
            "candidate": {
                "id": candidate.id,
                "name": candidate.name,
                "email": candidate.email,
                "location": candidate.location,
                "timezone": candidate.timezone,
                "experience_years": candidate.experience_years,
                "current_role": candidate.current_role,
            }
        }

    if name == "candidate_titles_lookup":
        candidate = _candidate_or_404(db, _require_int(args.get("candidate_id"), "candidate_id"))
        titles = [
            {
                "id": title.id,
                "title": title.title,
                "priority": title.priority,
                "description": title.description,
            }
            for title in sorted(candidate.job_titles, key=lambda item: (item.priority or 999, item.id or 0))
            if title.is_active and title.title
        ]
        return {"candidate_id": candidate.id, "titles": titles}

    if name == "candidate_skills_lookup":
        candidate = _candidate_or_404(db, _require_int(args.get("candidate_id"), "candidate_id"))
        skills = [
            {
                "id": skill.id,
                "skill_name": skill.skill_name,
                "category": skill.category,
                "years_experience": skill.years_experience,
                "is_enabled": skill.is_enabled,
            }
            for skill in candidate.skills
            if skill.is_active and skill.skill_name
        ]
        return {"candidate_id": candidate.id, "skills": skills}

    if name == "candidate_documents_lookup":
        candidate = _candidate_or_404(db, _require_int(args.get("candidate_id"), "candidate_id"))
        documents: list[CandidateDocument] = [doc for doc in candidate.documents if doc.is_active and doc.filename]
        return {
            "candidate_id": candidate.id,
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc.document_type,
                    "parse_status": doc.parse_status,
                    "load_strategy": doc.load_strategy,
                }
                for doc in documents
            ],
        }

    if name == "candidate_preferences_lookup":
        candidate = _candidate_or_404(db, _require_int(args.get("candidate_id"), "candidate_id"))
        prefs: CandidatePreferences | None = candidate.preferences
        if not prefs:
            return {
                "candidate_id": candidate.id,
                "preferences": {
                    "min_score": 60,
                    "min_ai_remote_score": 70,
                    "remote_only": False,
                    "experience_levels": ["Senior", "Staff", "Principal", "Lead"],
                },
            }

        try:
            experience_levels = json.loads(prefs.experience_levels or "[]")
        except (TypeError, json.JSONDecodeError):
            experience_levels = []
        return {
            "candidate_id": candidate.id,
            "preferences": {
                "min_score": prefs.min_score,
                "min_ai_remote_score": prefs.min_ai_remote_score,
                "remote_only": prefs.remote_only,
                "experience_levels": experience_levels,
            },
        }

    if name == "candidate_jobs_lookup":
        candidate_id = _require_int(args.get("candidate_id"), "candidate_id")
        _candidate_or_404(db, candidate_id)
        status = str(args.get("status", "")).strip()
        limit = _require_bounded_int(args.get("limit"), "limit", default=25, minimum=1, maximum=200)

        query = db.query(Job).filter(Job.candidate_id == candidate_id)
        if status:
            query = query.filter(Job.status == status)
        jobs = query.order_by(Job.found_at.desc(), Job.id.desc()).limit(limit).all()

        return {
            "candidate_id": candidate_id,
            "count": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "platform": job.platform,
                    "status": job.status,
                    "ai_remote_score": job.ai_remote_score,
                    "custom_fit_score": job.custom_fit_score,
                    "original_url": job.original_url,
                    "found_at": job.found_at.isoformat() if job.found_at else None,
                }
                for job in jobs
            ],
        }

    if name == "candidate_employers_lookup":
        candidate_id = _require_int(args.get("candidate_id"), "candidate_id")
        _candidate_or_404(db, candidate_id)
        limit = _require_bounded_int(args.get("limit"), "limit", default=20, minimum=1, maximum=200)
        jobs = (
            db.query(Job)
            .filter(Job.candidate_id == candidate_id)
            .order_by(Job.found_at.desc(), Job.id.desc())
            .all()
        )

        by_company: dict[str, dict[str, Any]] = defaultdict(dict)
        for job in jobs:
            company = (job.company or "").strip()
            if not company:
                continue
            entry = by_company.get(company)
            if not entry:
                by_company[company] = {
                    "company": company,
                    "job_count": 1,
                    "latest_job_title": job.title,
                    "latest_status": job.status,
                    "latest_found_at": job.found_at,
                    "platforms": {job.platform} if job.platform else set(),
                }
                continue
            entry["job_count"] += 1
            if job.found_at and (entry["latest_found_at"] is None or job.found_at > entry["latest_found_at"]):
                entry["latest_found_at"] = job.found_at
                entry["latest_job_title"] = job.title
                entry["latest_status"] = job.status
            if job.platform:
                entry["platforms"].add(job.platform)

        employers = sorted(
            by_company.values(),
            key=lambda item: (-int(item["job_count"]), item["company"].lower()),
        )[:limit]
        return {
            "candidate_id": candidate_id,
            "count": len(employers),
            "employers": [
                {
                    "company": item["company"],
                    "job_count": item["job_count"],
                    "latest_job_title": item["latest_job_title"],
                    "latest_status": item["latest_status"],
                    "latest_found_at": item["latest_found_at"].isoformat() if item["latest_found_at"] else None,
                    "platforms": sorted(item["platforms"]),
                }
                for item in employers
            ],
        }

    if name == "candidate_applications_lookup":
        candidate_id = _require_int(args.get("candidate_id"), "candidate_id")
        _candidate_or_404(db, candidate_id)
        status = str(args.get("status", "")).strip()
        limit = _require_bounded_int(args.get("limit"), "limit", default=25, minimum=1, maximum=200)

        query = (
            db.query(JobApplication, Job)
            .join(Job, Job.id == JobApplication.job_id)
            .filter(Job.candidate_id == candidate_id)
        )
        if status:
            query = query.filter(JobApplication.status == status)
        rows = query.order_by(JobApplication.id.desc()).limit(limit).all()

        return {
            "candidate_id": candidate_id,
            "count": len(rows),
            "applications": [
                {
                    "application_id": application.id,
                    "status": application.status,
                    "applied_date": application.applied_date.isoformat() if application.applied_date else None,
                    "follow_up_date": application.follow_up_date.isoformat() if application.follow_up_date else None,
                    "notes": application.notes,
                    "job": {
                        "id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "platform": job.platform,
                        "job_status": job.status,
                        "original_url": job.original_url,
                    },
                }
                for application, job in rows
            ],
        }

    if name == "chat_history_lookup":
        session_id = str(args.get("session_id", "")).strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        limit = _require_bounded_int(args.get("limit"), "limit", default=20, minimum=1, maximum=200)
        store = get_ai_session_store()
        session = store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="AI session not found")
        messages = store.list_session_messages(session_id, limit=limit)
        return {"session": session, "messages": messages}

    if name == "settings_lookup":
        config = load_ai_config()
        return {
            "ai_settings": config.ai_settings,
            "llm_providers": config.llm_providers,
            "model_routing": config.model_routing,
        }

    if name == "workspace_files_read":
        target = _safe_workspace_path(args.get("path"))
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if not target.is_file():
            raise HTTPException(status_code=400, detail="path must point to a file")
        return {
            "path": str(target),
            "content": target.read_text(encoding="utf-8"),
        }

    if name == "workspace_files_write":
        config = load_ai_config()
        mutation_policy = str(config.ai_settings.get("mutation_policy", "approve_writes")).strip().lower()
        if mutation_policy != "allow_writes":
            raise HTTPException(
                status_code=403,
                detail="workspace file writes are blocked by mutation_policy",
            )
        target = _safe_workspace_path(args.get("path"))
        create_dirs = bool(args.get("create_dirs", False))
        if create_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            raise HTTPException(status_code=400, detail="parent directory does not exist")
        target.write_text(str(args.get("content", "")), encoding="utf-8")
        return {"path": str(target), "written": True, "bytes": target.stat().st_size}

    raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
