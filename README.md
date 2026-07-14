# job-finder-qwen-code

Local-first job search application and working repository for the `job-finder-web` app.

## Read Order

1. `README.md` - repository entrypoint
2. `docs/README.md` - active documentation map
3. `docs/project-context.md` - current product and repo context
4. `job-finder-web/README.md` - app setup and runtime details
5. `history/` - historical plans and implementation summaries

## Repository Layout

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

## Documentation Rules

- Keep active, current-use documents under `docs/`.
- Keep historical plans, summaries, and superseded notes under `history/`.
- Keep personal source material under `docs/reference/`.
- Treat code as the source of truth for implementation details and current behavior.

## Application Code

The application lives in `job-finder-web/`:

- `backend/` - FastAPI app, models, routes, services, scrapers
- `frontend/` - Jinja templates and static assets
- `tests/` - Python test suite

## Notes

- This repo previously stored many markdown files at the root. Those have been moved into `docs/` and `history/` to keep the active surface small.
- Historical documents are preserved for traceability, not as the primary source of current system behavior.
