# Software factory

`/factory <feature>` runs a feature through: spec-writer -> builder -> 4 parallel reviewers
(security, ux, ui, code) -> approver -> local merge to main (or needs-human).

- Loop and rules: `.claude/skills/factory/SKILL.md` (edit the loop there)
- Agents: `.claude/agents/*.md` (one file per role, each writes one file)
- State: `factory/board.json` (orchestrator-only, gitignored); artifacts in `factory/jobs/<id>/` (gitignored)
- Backlog: `factory/backlog.md` -> `/factory next`
- Human gate: `/factory approve <id>`, `/factory rework <id> <note>`
- Check command (no test suite in this repo): `node factory/check.mjs`
- Dashboard: `python3 -m http.server 8077 -d factory` -> http://localhost:8077/dashboard.html

Approved jobs are merged into local `main` and never pushed: pushing main deploys to all nodes.
