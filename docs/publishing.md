# What this repository publishes

The developer guide is this public Git repository. GitHub Pages is not enabled.
There is no documentation site build and no workflow that copies or filters files.

A file is published when it is on the default branch. The reader guide is the
Markdown under `docs/` (indexed by [docs/README.md](README.md)), plus the root
`README.md`, `START_HERE.md`, `benchmarks/`, `examples/`, `decisions/`,
`catalogues/`, and `roadmap/`.

`AGENTS.md`, `CLAUDE.md`, and `.agents/` are agent instructions. No site build
selects them, so there is no site config to exclude. They are public because
the repository is public.

Agent issue-tracking notes live in `.agents/issue-tracker.md` and
`.agents/triage-labels.md`. They are not part of the reader guide under `docs/`.
