# Active Context

- Mode: implementation (Phase 9 product completion)
- Phase: 9 — three parallel threads, branch `stabilize/cleanup-foundation`
- State: T1 fully done. T3 R3 HITL (LinkedIn CAPTCHA verification, WWR live authorization) still needs maintainer manual validation. T2 R7 search/list work, Phase-10 R9 profile UX, and T2 P1 (application pipeline UI) are complete and merged; WWR is selectable but policy-gated.
- Next atomic step: reconcile and merge T2 P2 (tailored resume/cover letter) from worktree `worktree-agent-ad360b5d67189f2aa` — its baseline diverged from main's uncommitted ownership groundwork, needs selective file-by-file merge, not a plain apply. Full instructions in `handoff-2026-07-19-0444.md`.
- Next after that: T2 P3 scheduled re-search with "N new since last run" diff, building on saved lists (unblocked now that P1 is merged) — do this as its own slice, not parallelized. T3 R3 HITL (LinkedIn CAPTCHA trial, WWR authorization) also remains open whenever maintainer is available.
- Blockers/env: Do not tick T3 R3 until the maintainer manually validates LinkedIn and authorizes/validates WWR live access; its current WWR path fails closed without provider access. Use `./job-finder-web/venv/bin/python -m pytest -s ...`; local `python3` lacks `pytest`. P2 worktree at `.claude/worktrees/agent-ad360b5d67189f2aa` must stay until reconciled; P1 worktree at `.claude/worktrees/agent-a459fce5da360d96d` is merged and safe to remove.
- Open questions: none — all resolved 2026-07-19 (`docs/open-questions.md`).
- Discarded as noise: Full rewrite (rejected); doing provenance before card unification (rework); scheduling new tables before Q8 groundwork (double migration); parallelizing P1+P3 together (both touch models/job.py + routes/jobs.py, would collide).
