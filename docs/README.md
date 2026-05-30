# Documentation

Active documentation for this repository lives here. The goal is a small current-use surface, with historical material separated for traceability.

## Read Order

1. `docs/README.md` - this map
2. `docs/project-context.md` - current repo and product context
3. `job-finder-web/README.md` - environment setup and app runtime
4. `history/README.md` - archive index when you need past decisions or summaries

## Structure

```text
docs/
├── README.md
├── adr/
│   ├── 0001-ai-foundation-source-of-truth.md
│   └── README.md
├── design/
│   └── ai-foundation-migration.md
├── project-context.md
└── reference/
    ├── linkedin-profile.md
    ├── prefered-job-titles.md
    ├── my-role-claude-gold.md
    ├── job-search-platforms.md
    └── cover-letter.md
```

## What Belongs Here

- Current documentation a maintainer should read first
- Stable project context
- User or domain reference material that still matters to the product

## What Does Not Belong Here

- Superseded plans
- Implementation diaries
- one-off fix notes
- status snapshots that are likely to drift

Those belong in `history/`.

## Current Sources Of Truth

- Product and repo context: `docs/project-context.md`
- Settled architecture decision: `docs/adr/0001-ai-foundation-source-of-truth.md`
- AI migration architecture: `docs/design/ai-foundation-migration.md`
- Runtime and local setup: `job-finder-web/README.md`
- Implementation behavior: the code in `job-finder-web/`

## Reference Material

`docs/reference/` contains the user-specific source material the app works from, such as profile, target-role, and cover-letter inputs. It is reference input, not architecture documentation.
