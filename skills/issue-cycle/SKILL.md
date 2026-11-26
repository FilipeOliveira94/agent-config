---
name: issue-cycle
description: "Takes an issue (or phase) from plan to an open PR for Filipe to review and merge. Use when someone cites an issue, an acceptance criterion or a feature to build, or asks to plan, implement, verify or open the PR for an issue."
---

# Issue cycle

One issue or phase at a time. The acceptance text is the definition of done: do not pull in future issues and do not change the acceptance while building. The general rules (language, roles, size and risk, review gates and model policy) are in `~/.agents/claude/workflow.md`; the repository's `AGENTS.md` prevails on anything project-specific, including its "Agent workflow" section.

Cycle: start → rate size and risk → plan → (above Sm + Lo: `po-reviewer` on the plan in a `reviewed` project, and Filipe's approval) → implementation on a new branch from an up-to-date `main` → checks and tests → review gates → commit, push of the branch, PR with a summary and `finish` → CI and conflict check. The merge is always Filipe's: the agent never merges and never deletes a branch.

The change ledger ("Change ledger" in `workflow.md`) is written twice, each time inside a command you are running anyway: `change-ledger start` when the work begins and `change-ledger finish` when the PR opens. Run both from the repo's checkout. They find the change from the git branch or the T3 thread; on `main` outside T3, pass `--id <change id>` from `start`.

Between the two, keep the PR text in the file `start` printed. Under its "Questions and decisions" heading, add one line when one of these happens, inside a tool call you are making anyway (usually the first one after Filipe answers):
- Every stop for Filipe outside the plan-approval gate: `- <reason>: <question> Answer: <his answer, and the file that should have held it>`. The reasons:
  - `decision`: a choice that is Filipe's (scope, product, trade-off) and the issue did not settle;
  - `context`: information that should have been in the repo or the issue;
  - `access`: a permission, credential, setting or tool the agent could not use;
  - `correction`: Filipe corrected a result or a misunderstanding;
  - `blocked`: an environment failure, such as a usage limit, a broken tool or CI infrastructure.
- His answer to a plan: `- plan approved: <his adjustments, or "as proposed">` or `- plan rejected: <why>`.
- Each reviewer round: `- <reviewer>: <verdict>, <the findings that held>`, for example `- code-reviewer: BLOCK, no rate limit on /signup`.
  - Copy the reviewer's verdict word; `change-ledger` reads only these. `code-reviewer`: PASS, BLOCK or NEEDS INPUT. `po-reviewer`: APPROVED, CHANGES NEEDED, NEEDS FILIPE or NEEDS INPUT. A project reviewer with no verdict list: BLOCK when it reports a critical or high-severity finding or a failed must-check item (the rule `code-reviewer` uses), PASS otherwise.
  - BLOCK and CHANGES NEEDED count as blocking rounds. A reviewer that answers in other words, such as ACCEPT WITH NOTES or REJECT, is still read (as APPROVED or CHANGES NEEDED), but write the defined word.
- Each change he asks for after the PR opened: `- feedback: <what he asked>`.
- When a question, a feedback round or a second review round could have been avoided: `- lesson for <AGENTS.md, workflow.md, the issue, a test, CI>: <what would have prevented it>`.

The section is published with the PR, so Filipe sees it in review. Never put secrets or personal data in it.

## Size and risk

Every issue carries a Size (Sm, Md, Lg) and a Risk (Lo, Med, Hi) on the scale in `workflow.md`. Use the expected half of the roadmap's "Expected/Seen Risk" and "Expected/Seen Size" columns; if there is none, estimate it in the plan with one line of reasoning and record the expected half in the same PR (format in `workflow.md`). The rating decides:

- **Sm + Lo:** plan and implement straight through to the PR.
- **Anything else:** plan and **stop**. Present the plan in the thread and wait for Filipe's approval before touching code. Apply the adjustments that come with the approval.
- **Hi risk or Lg size:** the thread runs at Opus high, set when it starts. If you find yourself on medium, say so at the top of the plan. Never switch your model or effort by yourself; a switch happens only when Filipe decides it ("Model policy" in `workflow.md`). For Hi, the plan names the hard rules at stake and the tests written first; for Lg, the plan says whether to split it.
- If planning shows the issue is bigger or riskier, raise the rating, say why and follow the new mode. Never lower a rating without Filipe.

## 0. Start

With your first reads of the issue, run `change-ledger start --issue <ID> --title "<issue title>" --kind <feat|fix|docs|chore|…> --model <your model id>`. Add `--risk <Lo|Med|Hi> --size <Sm|Md|Lg>` when the roadmap has no rating and you already have one. It records the change with the T3 thread and effort, creates the PR text file, and prints the brief: open PRs with their CI, conflicts, merge order and the files they edit, work in progress, and the project's open lessons. Use the brief in the plan:
- An open PR that edits the same files (often `ROADMAP.md` or `PROJECT_STATUS.md`) will conflict with this branch: name it in the plan and keep your edits to those files small.
- Check the plan against each open lesson.

## 1. Plan

Read the issue, the acceptance, the rating, the project status (`PROJECT_STATUS.md`/`ROADMAP.md`) and the "Agent workflow" section of `AGENTS.md`, without changing files. If the project has no such section, stop and ask Filipe to define it ("Profiles" in `workflow.md`). Define scope, out of scope, approach, risks and what a person can do once it is done.

When the roadmap has no rating, the plan gives one, and `finish` records it with `--risk` and `--size`. A rating raised along the way also gets `--rating-note "<why>"`.

Above Sm + Lo in a `reviewed` project, run `po-reviewer` (mode `plan`) with the issue ID, the rating and the plan, fix what it points out and show its verdict with the plan. Above Sm + Lo, this plan is what goes for approval: end the turn here. When Filipe replies, add `- plan approved: …` or `- plan rejected: …` to the PR text. On a thread running Fable, ask with the plan whether to implement on Fable or switch to Opus 5.5 ("Model policy" in `workflow.md`).

## 2. Implement

Update `main` (`git pull`) and create a new branch from it.

Make the smallest change that makes the accepted behavior true. Do not add confirmations, restrictions or steps the issue did not ask for. When extracting repeated logic or choosing module boundaries, consult the `module-boundaries` skill; the project's existing architecture prevails.

## 3. Verify

- Run the project's checks and tests. A check that was not run is not a pass; record the command and the output.
- Exercise each behavior of the issue the way the user would. A behavior that was not exercised is not done; say which one was left out and why.
- A green internal check is not enough if the user sees another surface. Look at that surface.
- When the issue changes something a person sees or does in a browser, follow the `browser-proof` skill and put its statement table in the PR.

## 4. Review (profile `reviewed`)

With the branch ready and the checks run:

- `code-reviewer` on every code or config change, with the base branch and the goal of the change. A docs-only or text-only change skips this gate.
- The extra reviewers that the "Agent workflow" section lists, when their trigger matches. They live in the project's `.claude/agents/`.
- Above Sm + Lo, after `code-reviewer`, `po-reviewer` (mode `acceptance`) with the issue ID, the rating, the base branch and the checks run with their output.

After each reviewer round, add its line to the PR text: `- <reviewer>: <verdict>, <the findings that held, or none>`.

Check each finding against the code before acting on it: reproduce it, or trace the path it describes. Fix the ones that hold. Do not change code to satisfy a finding that does not hold; give the reviewer the evidence in the next round and note it in the PR.

Fix the critical findings and the NOT MET criteria and run the reviewer again. If the same finding is still open after 2 rounds, stop and report to Filipe; he decides whether to raise the effort, switch to Fable or change the plan ("Model policy" in `workflow.md`). Profile `solo`: skip this step.

## 5. Deliver

Conventional commits, push of the branch and a PR. Write the PR text in the file `start` created, above its "Questions and decisions" section:
- `## Summary`: what was done and how it meets the acceptance. Its first paragraph becomes the ledger's summary, so make it one or two sentences on what changed and why;
- the rating (Size and Risk) and whether it changed along the way; when the PR closes the issue, fill the seen half of both columns in the roadmap;
- checks and tests run, with the relevant output;
- each reviewer's final verdict, or which gates were skipped and why;
- what stays open or was left out.

Once the title and body are written, run the `plain-voice` skill (engineering register) over them.

Open the PR and finish the ledger in one command: `gh pr create --title "<title>" --body-file <PR text file> && change-ledger finish --seen-risk <Lo|Med|Hi> --seen-size <Sm|Md|Lg>`.
- Add `--risk` and `--size` when the roadmap has no rating or the plan changed it (with `--rating-note`). Add `--merge-after <repo#N>` when another PR must merge first, and `--owner-actions "<what Filipe does at merge>"` when the merge needs a step from him (run `install.sh`, a migration, a setting).
- Read the PR line `finish` prints. Fix a failing check or a conflict with `main` before handing back, and name a check that is still pending in the handoff.
- When `finish` warns about a line it cannot read, or a missing plan line, fix the PR text. Then run `gh pr edit --body-file <PR text file> && change-ledger finish` in one command.

Stop there. Do not merge, do not delete the branch, do not run CD. Fixes requested in review go in as new commits on the same branch. Add `- feedback: <what Filipe asked>` to the PR text, plus a lesson line when the round could have been avoided. Then push, update the PR and finish in one command: `git push && gh pr edit --body-file <PR text file> && change-ledger finish`.
