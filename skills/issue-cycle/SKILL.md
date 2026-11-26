---
name: issue-cycle
description: "Takes an issue (or phase) from plan to an open PR for Filipe to review and merge. Use when someone cites an issue, an acceptance criterion or a feature to build, or asks to plan, implement, verify or open the PR for an issue."
---

# Issue cycle

One issue or phase at a time. The acceptance text is the definition of done: do not pull in future issues and do not change the acceptance while building. The general rules (language, roles, size and risk, review gates and model policy) are in `~/.agents/claude/workflow.md`; the repository's `AGENTS.md` prevails on anything project-specific, including its "Agent workflow" section.

Cycle: brief → rate size and risk → plan → (above Sm + Lo: `po-reviewer` on the plan in a `reviewed` project, and Filipe's approval) → implementation on a new branch from an up-to-date `main` → checks and tests → review gates → commit, push of the branch and PR with a summary → CI and conflict check. The merge is always Filipe's: the agent never merges and never deletes a branch.

Each step writes to the change ledger (`change-ledger`, "Change ledger" in `workflow.md`), from inside the repo's checkout. The commands find the current change from the git branch or the T3 thread. When they cannot (on `main` outside T3), pass `--id <change id>` from `start`. Every stop for Filipe outside the plan-approval gate is logged with `change-ledger log ask --reason …`, and his answer with `change-ledger log answer`.

## Size and risk

Every issue carries a Size (Sm, Md, Lg) and a Risk (Lo, Med, Hi) on the scale in `workflow.md`. Use the expected half of the roadmap's "Expected/Seen Risk" and "Expected/Seen Size" columns; if there is none, estimate it in the plan with one line of reasoning and record the expected half in the same PR (format in `workflow.md`). The rating decides:

- **Sm + Lo:** plan and implement straight through to the PR.
- **Anything else:** plan and **stop**. Present the plan in the thread and wait for Filipe's approval before touching code. Apply the adjustments that come with the approval.
- **Hi risk or Lg size:** the thread runs at Opus high, set when it starts. If you find yourself on medium, say so at the top of the plan. Never switch your model or effort by yourself; a switch happens only when Filipe decides it ("Model policy" in `workflow.md`). For Hi, the plan names the hard rules at stake and the tests written first; for Lg, the plan says whether to split it.
- If planning shows the issue is bigger or riskier, raise the rating, say why and follow the new mode. Never lower a rating without Filipe.

## 0. Brief

Run `change-ledger brief`. It refreshes this project's PRs and prints what waits on Filipe (open PRs with their CI, conflicts, merge order and the files they edit; plans waiting for approval; unanswered questions), this project's open lessons and its recent rates. Use it in the plan:
- An open PR that edits the same files (often `ROADMAP.md` or `PROJECT_STATUS.md`) will conflict with this branch: name it in the plan and keep your edits to those files small.
- Check the plan against each open lesson.

## 1. Plan

Read the issue, the acceptance, the rating, the project status (`PROJECT_STATUS.md`/`ROADMAP.md`) and the "Agent workflow" section of `AGENTS.md`, without changing files. If the project has no such section, stop and ask Filipe to define it ("Profiles" in `workflow.md`). Define scope, out of scope, approach, risks and what a person can do once it is done.

Once the rating is set, record the change: `change-ledger start --issue <ID> --title "<issue title>" --kind <feat|fix|docs|chore|…> --risk <Lo|Med|Hi> --size <Sm|Md|Lg> --model <your model id>`. It prints the change id and records the T3 thread and effort itself. When the rating changes later, run `change-ledger set --risk … --size … --rating-note "<why>"`.

Above Sm + Lo in a `reviewed` project, run `po-reviewer` (mode `plan`) with the issue ID, the rating and the plan, fix what it points out and show its verdict with the plan. Above Sm + Lo, this plan is what goes for approval: run `change-ledger log plan "<approach in one line>"` and end the turn here. When Filipe replies, log `change-ledger log approved "<his adjustments, if any>"` or `change-ledger log rejected "<why>"`. On a thread running Fable, ask with the plan whether to implement on Fable or switch to Opus 5.5 ("Model policy" in `workflow.md`).

## 2. Implement

Update `main` (`git pull`) and create a new branch from it.

Make the smallest change that makes the accepted behavior true. Do not add confirmations, restrictions or steps the issue did not ask for. When extracting repeated logic or choosing module boundaries, consult the `module-boundaries` skill; the project's existing architecture prevails.

## 3. Verify

- Run the project's checks and tests. A check that was not run is not a pass; record the command and the output.
- Exercise each behavior of the issue the way the user would. A behavior that was not exercised is not done; say which one was left out and why.
- A green internal check is not enough if the user sees another surface. Look at that surface.
- When the issue changes something a person sees or does in a browser, follow the `browser-proof` skill and put its statement table in the PR.
- Record the result: `change-ledger log checks --verdict <pass|fail> "<command: result>"`.

## 4. Review (profile `reviewed`)

With the branch ready and the checks run:

- `code-reviewer` on every code or config change, with the base branch and the goal of the change. A docs-only or text-only change skips this gate.
- The extra reviewers that the "Agent workflow" section lists, when their trigger matches. They live in the project's `.claude/agents/`.
- Above Sm + Lo, after `code-reviewer`, `po-reviewer` (mode `acceptance`) with the issue ID, the rating, the base branch and the checks run with their output.

After each reviewer round, run `change-ledger log review --actor <reviewer> --verdict <its verdict> "<the findings that held, or none>"`.

Check each finding against the code before acting on it: reproduce it, or trace the path it describes. Fix the ones that hold. Do not change code to satisfy a finding that does not hold; give the reviewer the evidence in the next round and note it in the PR.

Fix the critical findings and the NOT MET criteria and run the reviewer again. If the same finding is still open after 2 rounds, stop and report to Filipe; he decides whether to raise the effort, switch to Fable or change the plan ("Model policy" in `workflow.md`). Profile `solo`: skip this step.

## 5. Deliver

Conventional commits, push of the branch and a PR with a summary:
- what was done and how it meets the acceptance;
- the rating (Size and Risk) and whether it changed along the way; when the PR closes the issue, fill the seen half of both columns in the roadmap;
- checks and tests run, with the relevant output;
- each reviewer's final verdict, or which gates were skipped and why;
- what stays open or was left out.

Once the title and body are written, run the `plain-voice` skill (engineering register) over them.

Open the PR and update the ledger in one command: `gh pr create … && change-ledger set --summary "<one or two sentences: what changed and why>" --seen-risk <Lo|Med|Hi> --seen-size <Sm|Md|Lg> && change-ledger brief`.
- Add `--merge-after <repo#N>` to `set` when another PR must merge first, and `--owner-actions "<what Filipe does at merge>"` when the merge needs a step from him (run `install.sh`, a migration, a setting).
- Read the line `brief` prints for this PR. Fix a failing check or a conflict with `main` before handing back, and name a check that is still pending in the handoff.

Stop there. Do not merge, do not delete the branch, do not run CD. Fixes requested in review go in as new commits on the same branch: first log the request with `change-ledger log feedback "<what Filipe asked>"`, and when the round could have been avoided, add a lesson ("Change ledger" in `workflow.md`).
