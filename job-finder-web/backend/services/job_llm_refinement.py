"""Bounded, optional LLM fit refinement for deterministic top job results."""
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from sqlalchemy.orm import Session

from backend.ai_capabilities import Purpose
from backend.config import JOB_LLM_REFINEMENT_PROMPT_VERSION, JOB_LLM_REFINEMENT_TOP_N
from backend.models.candidate import Candidate
from backend.models.job import Job
from backend.services.llm_service import send_message

logger = logging.getLogger(__name__)

LLM_REFINEMENT_PROMPT = """Assess this job's fit for the candidate profile. Return JSON only:
{{"llm_score": <integer 0-100>, "rationale": "<one concise sentence>"}}

Candidate profile:
{profile}

Job title: {title}
Company: {company}
Job description:
{description}
"""


@dataclass(frozen=True)
class LLMRefinement:
    llm_score: int
    rationale: str


def profile_fingerprint(candidate: Candidate) -> str:
    """Stable profile version for refinement idempotency, without PII such as email."""
    titles = sorted(
        title.title.strip() for title in candidate.job_titles
        if title.is_active and title.title and title.title.strip()
    )
    skills = sorted(
        skill.skill_name.strip() for skill in candidate.skills
        if skill.is_active and skill.is_enabled and skill.skill_name and skill.skill_name.strip()
    )
    payload = json.dumps({
        "candidate_id": candidate.id,
        "current_role": candidate.current_role or "",
        "experience_years": candidate.experience_years,
        "titles": titles,
        "skills": skills,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _profile_text(candidate: Candidate) -> str:
    titles = [title.title.strip() for title in candidate.job_titles if title.is_active and title.title]
    skills = [skill.skill_name.strip() for skill in candidate.skills if skill.is_active and skill.is_enabled and skill.skill_name]
    return "\n".join((
        f"Current role: {candidate.current_role or 'Not provided'}",
        f"Years of experience: {candidate.experience_years if candidate.experience_years is not None else 'Not provided'}",
        f"Preferred titles: {', '.join(titles) or 'Not provided'}",
        f"Skills: {', '.join(skills) or 'Not provided'}",
    ))


def _parse_refinement(response: str | None) -> LLMRefinement | None:
    if not response:
        return None
    match = re.search(r"\{.*\}", response, re.DOTALL)
    try:
        payload = json.loads(match.group(0) if match else response)
        score = int(payload["llm_score"])
        rationale = " ".join(str(payload["rationale"]).split())
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if not 0 <= score <= 100 or not rationale:
        return None
    # A short, single line remains usable in the row-expansion UI.
    return LLMRefinement(llm_score=score, rationale=rationale[:500])


class JobLLMRefinementService:
    """Refine only deterministic top-N jobs; never mutate their sort score."""

    def __init__(self, db: Session, *, prompt_version: str = JOB_LLM_REFINEMENT_PROMPT_VERSION):
        self.db = db
        self.prompt_version = prompt_version

    def top_deterministic_jobs(self, candidate_id: int, top_n: int = JOB_LLM_REFINEMENT_TOP_N) -> list[Job]:
        """The bounded candidate set, ordered solely by deterministic composite."""
        return (
            self.db.query(Job)
            .filter(Job.candidate_id == candidate_id)
            .order_by(Job.deterministic_score.desc(), Job.id.asc())
            .limit(max(0, top_n))
            .all()
        )

    async def refine_top_jobs(self, candidate: Candidate, top_n: int = JOB_LLM_REFINEMENT_TOP_N) -> int:
        fingerprint = profile_fingerprint(candidate)
        refined = 0
        for job in self.top_deterministic_jobs(candidate.id, top_n):
            if (job.llm_score is not None and job.llm_prompt_version == self.prompt_version
                    and job.llm_profile_fingerprint == fingerprint):
                continue
            result = await self._refine(job, candidate)
            if result is None:
                continue
            job.llm_score = result.llm_score
            job.llm_rationale = result.rationale
            job.llm_prompt_version = self.prompt_version
            job.llm_profile_fingerprint = fingerprint
            refined += 1
        if refined:
            self.db.commit()
        return refined

    async def _refine(self, job: Job, candidate: Candidate) -> LLMRefinement | None:
        description = job.description_snippet or "Not provided"
        prompt = LLM_REFINEMENT_PROMPT.format(
            profile=_profile_text(candidate), title=job.title, company=job.company,
            description=description[:8000],
        )
        try:
            response = await send_message(
                prompt, temperature=0.1, db=self.db,
                routing_purpose=Purpose.CANDIDATE_ANALYSIS,
            )
        except Exception:
            logger.exception("LLM refinement failed for job %s", job.id)
            return None
        return _parse_refinement(response)


def get_job_llm_refinement_service(db: Session) -> JobLLMRefinementService:
    return JobLLMRefinementService(db)
