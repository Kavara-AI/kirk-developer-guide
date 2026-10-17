# Issue tracker: Jira (project EN)

Issues and specs for this repo live in Jira project **EN** on <https://kavara.atlassian.net>. This is not GitHub Issues. Do not call `gh issue`. The GitHub remote is only the code host.

## Identity

- **Site**: <https://kavara.atlassian.net>
- **Project key**: `EN`
- **Issue key**: `EN-<number>` (for example `EN-1148`)
- **Browse URL**: `https://kavara.atlassian.net/browse/EN-<number>`

Resolve the Atlassian cloud id from the site at runtime. Do not store cloud ids, tokens, emails, account ids, or API keys in this repo or in issue bodies.

## Conventions

Use the Jira connection already available to the agent. Never invent credentials.

- **Create an issue**: project `EN`, type **Task**, with a summary and a markdown description. Add a label from `docs/agents/triage-labels.md` when a skill names a triage role.
- **Read an issue**: fetch `EN-<number>` including summary, description, status, labels, comments, parent, and issue links. A bare `#42`, or a GitHub `Closes #45`, is not an EN issue. Commit and PR references use `EN-<number>` or the browse URL.
- **List issues**: JQL scoped to this project. Example: `project = EN AND labels = "needs-triage" AND statusCategory != Done ORDER BY created ASC`.
- **Make an issue a child of a parent**: Jira's parent field, matching the EN hierarchy. A Task, Story, Feature, or Bug can parent to an Epic. A Subtask can parent to a Task, Story, Feature, or Bug. If the parent is an Epic, create a Task. If the parent is a Task, Story, Feature, or Bug, create a Subtask. If the hierarchy rejects the parent, put `Part of EN-<number>` at the top of the child description.
- **Comment on an issue**: add a Jira comment. Do not include tokens, emails, or secrets.
- **Apply / remove labels**: add or remove that label string on the issue. Jira creates the label on first use. Do not invent a second vocabulary.
- **Close**: comment, then transition the issue to **Done**. Open means the status category is not Done. The EN workflow statuses are To Do, In Progress, In Review, and Done.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub pull requests are the code-review surface. They are not issues on this tracker and they do not take these labels.

## When a skill says "publish to the issue tracker"

Create a Jira issue in project EN, as in **Create an issue** above.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single EN issue. Its tickets are child issues of the map.

- **Map**: one issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. Create it as a Task unless the effort already has an Epic to hang it on.
- **Child ticket**: a child of the map (see **Make an issue a child of a parent**). Labels: `wayfinder:<type>` (`research`, `prototype`, `grilling`, or `task`). No triage label. Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: Jira's native **Blocks** link. The blocker is the inward issue (`is blocked by`); the blocked ticket is the outward issue (`blocks`). A ticket is unblocked when every issue it `is blocked by` is Done. If the link cannot be created, fall back to a `Blocked by: EN-<n>, EN-<n>` line at the top of the child description.
- **Frontier query**: open children of the map (`parent = EN-<map>` and status category is not Done), dropping any that `is blocked by` an open issue or that has an assignee. First in map order wins.
- **Claim**: assign the issue to the authenticated user. That assignment is the session's first write. Resolve the account at runtime. Do not write an email or account id into the repo.
- **Resolve**: comment with the answer, transition the issue to **Done**, then append a context pointer (gist + link) to the map's Decisions-so-far.
