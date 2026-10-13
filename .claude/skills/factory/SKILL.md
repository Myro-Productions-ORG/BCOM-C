---
name: factory
description: Run a feature through the BCOM-C software factory (spec -> build -> 4 parallel reviews -> approve). Use for /factory <feature>, /factory next, /factory approve <job-id>, /factory rework <job-id> <note>.
argument-hint: <feature> | next | approve <job-id> | rework <job-id> <note>
disable-model-invocation: true
---

# /factory — orchestrator

You (this session) are the orchestrator. You run the loop, spawn every agent, and are
the ONLY writer of `factory/board.json`. You never write code or specs yourself.

Arguments: `$ARGUMENTS`

## The loop (edit this to change the factory)

```
feature -> spec-writer (opus) -> builder (opus) -+-> review-security (opus)  -+
              ^                                  +-> review-ux (sonnet)       |  WAIT FOR ALL 4
              |                                  +-> review-ui (sonnet)       |
              |                                  +-> review-code (sonnet)    -+
              |                                                               |
              +----- any CHANGES: resume same builder (max 2 rounds) ---------+
                                                                              | all PASS
                                     approver (opus) -> APPROVE  -> merge to main (local)
                                                     -> ESCALATE -> needs-human  <- /factory approve
```

## Paths and names

- `REPO` = `git rev-parse --show-toplevel` (always pass absolute paths to agents).
- Job id: next 3-digit number after the highest in `factory/jobs/` + kebab slug of the feature (max 5 words), e.g. `004-terminal-rate-limit`.
- Job folder: `$REPO/factory/jobs/<id>/` — `spec.md`, `build.md`, `round-N/review-{security,ux,ui,code}.md`, `decision.md`, `rework-N.md`.
- Branch `factory/<id>`, worktree `$REPO/.worktrees/<id>` (gitignored). The builder works ONLY there, so this
  session's checkout, `board.json`, and `jobs/` are never disturbed.
- Builder agent name: `builder-<id>`.

## board.json

Create from `factory/board.example.json` shape if missing (`{"jobs": []}`). Rewrite the whole file on every
change (valid JSON). One object per job:

```json
{ "id": "004-x", "title": "<feature text>", "branch": "factory/004-x",
  "stage": "spec|build|review|approve|needs-human|done", "round": 1, "maxRound": 2,
  "reviews": { "security": "pending", "ux": "pending", "ui": "pending", "code": "pending" },
  "rounds": [ { "round": 1, "reviews": { "...": "same shape" } } ],
  "decision": null, "note": "", "builder": "builder-004-x",
  "files": ["spec.md", "build.md", "round-1/review-security.md"], "updated": "<ISO time>" }
```

Update it at every transition below, and update each review chip (in `reviews` AND the current `rounds` entry)
as each reviewer finishes. Append every file to `files` as it lands. Set `note` to one short human line.

Dashboard: if nothing listens on 8077 (`lsof -i :8077`), start `python3 -m http.server 8077 -d "$REPO/factory"` in
the background and tell the user `http://localhost:8077/dashboard.html`.

## /factory <feature>

1. Create the job folder and board entry, stage `spec`.
2. Spawn `spec-writer`: feature text, job folder path. Wait. Check `spec.md` exists. Stage `build`.
3. `git -C $REPO worktree add .worktrees/<id> -b factory/<id> main`.
4. Spawn `builder` with `name: builder-<id>` (record the returned agent id in `builder` if naming isn't
   available): job folder, worktree path, branch. Wait. Check `build.md` exists and the branch has commits
   ahead of main (`git -C $REPO log main..factory/<id> --oneline`). If not, stage `needs-human` with a note; stop.
5. Review round N (start N=1): create `round-N/`, stage `review`, all four chips `pending`.
   Spawn `review-security`, `review-ux`, `review-ui`, `review-code` IN ONE MESSAGE (parallel). Give each:
   job folder, worktree path, branch, N, its output file path, and the previous round folder if N>1.
6. **WAIT FOR ALL.** The round is done only when all four `round-N/review-*.md` exist and each first line is
   exactly `VERDICT: PASS` or `VERDICT: CHANGES`. A missing or malformed file: re-run that one reviewer.
   Never message the builder mid-round.
7. Any CHANGES:
   - N < maxRound: SendMessage `builder-<id>`: "Round N review is in `<job>/round-N/`. Address every CHANGES
     finding, commit, re-run checks, append a `## Round N response` section to build.md." Wait, then go to 5 with N+1.
   - N == maxRound: stage `needs-human`, note `round cap hit — CHANGES in round N`. Stop.
8. All PASS: stage `approve`. Spawn `approver` (job folder, worktree, branch). First line of `decision.md`:
   - `APPROVE` -> **Merge** (below), stage `done`, decision `APPROVE`.
   - `ESCALATE` -> stage `needs-human`, decision `ESCALATE`, note = its one-line reason.
9. Report one line: job id, final stage, branch, dashboard URL.

## Merge (local only — NEVER push)

Pushing `main` triggers `.github/workflows/deploy.yml`, which deploys to all three nodes including the live
site. Merging is local; pushing is the human's call.

- If this checkout is on `main`: `git merge --no-ff factory/<id> -m "merge: factory/<id> — <title>"`.
- Otherwise: `git worktree add .worktrees/_merge main`, merge there, `git worktree remove .worktrees/_merge`.
  (If main is checked out in another worktree, merge in that worktree instead.)
- Conflict: `git merge --abort`, stage `needs-human`, note `merge conflict`. Stop.
- Success: `git worktree remove .worktrees/<id>`. Keep the branch. Tell the user "merged locally, not pushed".

## /factory next

Take the first `- [ ]` line in `factory/backlog.md`, change it to `- [x]` (append ` -> <id>`), run it as
`/factory <that text>`. If none unchecked, say so.

## /factory approve <job-id>

Only for stage `needs-human`. Run **Merge**, stage `done`, decision `APPROVE (human)`. If the worktree is
gone, merge the branch directly.

## /factory rework <job-id> <note>

1. Write the note verbatim to `<job>/rework-K.md` (next K), add to `files`.
2. Recreate the worktree if missing (`git worktree add .worktrees/<id> factory/<id>`).
3. SendMessage `builder-<id>` pointing at the rework file. If that builder isn't reachable (new session),
   spawn a fresh `builder` named `builder-<id>` told to read spec.md, build.md, every round folder, and the
   rework file before changing anything.
4. Set `maxRound = round + 2`, then run step 5 onward with N = round + 1.

## Rules

- Agents get context from files, never from this conversation. Prompts contain only paths, ids, and N.
- Each agent writes only its own file; the builder additionally commits on its branch in its worktree.
- Never edit spec/build/review/decision files yourself. Never resume the builder mid-round.
- Stop-the-line: an agent errors or writes nothing twice -> stage `needs-human` with the reason.
