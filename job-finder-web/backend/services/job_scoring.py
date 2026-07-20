"""Deterministic, explainable profile-to-job scoring primitives."""
import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

from fuzzywuzzy import fuzz

from backend.config import JOB_SCORING_WEIGHTS, SKILL_MATCH_ALIASES, TITLE_MATCH_ALIASES

SCORING_ALGORITHM_VERSION = "r5-composite-v1"


def _normalise_title(title: str | None) -> str:
    """Return a comparable title, expanding configured whole-title aliases."""
    normalised = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    if not normalised:
        return ""

    for canonical, aliases in TITLE_MATCH_ALIASES.items():
        canonical_normalised = re.sub(r"[^a-z0-9]+", " ", canonical.lower()).strip()
        for alias in (canonical, *aliases):
            alias_normalised = re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip()
            if alias_normalised:
                normalised = re.sub(
                    rf"(?<!\w){re.escape(alias_normalised)}(?!\w)",
                    canonical_normalised,
                    normalised,
                )
    return " ".join(normalised.split())


def title_match_score(job_title: str | None, preferred_titles: Iterable[str]) -> int:
    """Return the best normalized fuzzy title match on the 0--100 scale.

    ``token_set_ratio`` is the same fuzzy machinery used by deduplication, but
    this score intentionally has no deduplication threshold.  Empty titles on
    either side never produce a match.
    """
    normalised_job_title = _normalise_title(job_title)
    if not normalised_job_title:
        return 0

    scores = (
        fuzz.token_set_ratio(normalised_job_title, normalised_preferred)
        for preferred_title in preferred_titles
        if (normalised_preferred := _normalise_title(preferred_title))
    )
    return max(scores, default=0)


def _tokenise(value: str | None) -> tuple[str, ...]:
    """Lowercase and strip punctuation, preserving phrase token boundaries."""
    return tuple(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _contains_phrase(tokens: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    if not phrase or len(phrase) > len(tokens):
        return False
    return any(tokens[index:index + len(phrase)] == phrase for index in range(len(tokens) - len(phrase) + 1))


def _skill_variants(skill: str) -> tuple[tuple[str, ...], ...]:
    """Return a candidate skill and the configured canonical/alias phrases."""
    normalised_skill = " ".join(_tokenise(skill))
    variants = {normalised_skill} if normalised_skill else set()
    for canonical, aliases in SKILL_MATCH_ALIASES.items():
        vocabulary = {" ".join(_tokenise(canonical))}
        vocabulary.update(" ".join(_tokenise(alias)) for alias in aliases)
        if normalised_skill in vocabulary:
            variants.update(vocabulary)
    return tuple(_tokenise(variant) for variant in variants if variant)


def skills_overlap_score(description: str | None, candidate_skills: Iterable[str]) -> float | None:
    """Return the fraction of curated candidate skills present in a description.

    The profile, not the posting, defines the denominator.  A missing
    description is intentionally different from a present description that
    simply matches none of the skills.
    """
    description_tokens = _tokenise(description)
    if not description_tokens:
        return None

    skills = [skill for skill in candidate_skills if _tokenise(skill)]
    if not skills:
        return 0.0
    matches = sum(
        any(_contains_phrase(description_tokens, variant) for variant in _skill_variants(skill))
        for skill in skills
    )
    return matches / len(skills)


def scoring_version() -> str:
    """Return an immutable label for the current deterministic configuration."""
    scoring_config = {
        "algorithm": SCORING_ALGORITHM_VERSION,
        "aliases": SKILL_MATCH_ALIASES,
        "weights": JOB_SCORING_WEIGHTS,
    }
    encoded = json.dumps(scoring_config, sort_keys=True, separators=(",", ":")).encode()
    return f"{SCORING_ALGORITHM_VERSION}:{hashlib.sha256(encoded).hexdigest()[:12]}"


@dataclass(frozen=True)
class DeterministicScore:
    composite_score: int
    title_similarity: int
    skills_overlap: float | None
    skills_status: str
    scoring_version: str

    def as_dict(self) -> dict[str, int | float | str | None]:
        return {
            "title_similarity": self.title_similarity,
            "skills_overlap": self.skills_overlap,
            "skills_status": self.skills_status,
            "composite_score": self.composite_score,
        }


def score_job(
    job_title: str | None,
    description: str | None,
    preferred_titles: Iterable[str],
    candidate_skills: Iterable[str],
) -> DeterministicScore:
    """Score one job with the R5 weighted deterministic composite contract."""
    title_similarity = title_match_score(job_title, preferred_titles)
    skills_overlap = skills_overlap_score(description, candidate_skills)
    if skills_overlap is None:
        composite_score = title_similarity
        skills_status = "no_description"
    else:
        weighted_score = (
            title_similarity * JOB_SCORING_WEIGHTS["title_similarity"]
            + (skills_overlap * 100) * JOB_SCORING_WEIGHTS["skills_overlap"]
        )
        composite_score = math.floor(weighted_score + 0.5)
        skills_status = "matched"
    return DeterministicScore(
        composite_score=composite_score,
        title_similarity=title_similarity,
        skills_overlap=skills_overlap,
        skills_status=skills_status,
        scoring_version=scoring_version(),
    )
