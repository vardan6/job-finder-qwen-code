# Project Context

This document is the stable, current-use context for the repository. It is intentionally shorter than the historical plans and summaries preserved under `history/`.

## Goal

Build and maintain a local-first job-search application that:

- manages multiple candidates
- stores data locally
- parses candidate documents
- manages platform accounts and preferences
- searches and analyzes jobs with AI assistance

The primary user context is remote work from Armenia targeting US, EU, and Canada opportunities.

## Repository Shape

```text
job-finder-qwen-code/
├── README.md
├── AGENTS.md
├── docs/
│   ├── README.md
│   ├── project-context.md
│   └── reference/
├── history/
└── job-finder-web/
```

## Code Layout

The application code lives in `job-finder-web/`.

- `backend/` - FastAPI app, routes, models, services, scrapers
- `frontend/` - Jinja templates and static assets
- `tests/` - automated tests
- `requirements.txt` - Python dependencies
- `run.py` - local entrypoint

## Documentation Policy

- `README.md` is the repository entrypoint.
- `docs/` contains active documentation only.
- `docs/reference/` contains user or domain reference inputs.
- `history/` contains historical plans, summaries, and superseded notes.
- `job-finder-web/README.md` contains app setup and runtime instructions.

## Source Of Truth

- Current implementation behavior: code under `job-finder-web/`
- Current setup instructions: `job-finder-web/README.md`
- Current repository and documentation structure: `README.md` and `docs/README.md`
- Historical rationale and snapshots: `history/`

## Reference Inputs

The repository includes user-specific reference material in `docs/reference/`, including:

- professional profile
- preferred job titles
- role-description source material
- platform research
- cover-letter material

These files support document parsing and candidate setup workflows. They are not implementation specs.

## Historical Material

Earlier documents in `history/` may still be useful for:

- feature traceability
- recovering discarded ideas
- comparing past and current workflows

They should not be assumed current without checking the code.
