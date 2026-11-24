# Dev workflow and model policy

Filipe's main development flow, in force since 2026-11-23. Every Claude Code session loads this file through `~/.claude/CLAUDE.md`. Each project's `AGENTS.md` has an "Agent workflow" section with its profile, extra reviewers and exceptions; where that section is more specific, it wins. The per-issue procedure is the `issue-cycle` skill.

## Roles

| Role | Who | Does |
| --- | --- | --- |
| Owner | Filipe | Picks the issue, approves the plan of a large task, reviews the PR, merges it and deletes the branch. |
| Dev | Claude Opus 5.5 in T3 Code, one thread per issue | Plans, implements on a new branch from an up-to-date `main`, runs the checks and the review gates, commits, pushes the branch and opens the PR. |
| PO reviewer | `po-reviewer` subagent (Sonnet 5.5) | Checks a large task's plan, and the finished branch, against the issue's acceptance criteria and scope. |
| Code reviewer | `code-reviewer` subagent (Sonnet 5.5) | Checks the finished branch for bugs, security issues and regressions. |

No agent merges, deletes a branch, pushes `main` or deploys. There are no PO or Reviewer bots.

Fallback when the Claude limit runs out: Grok 4.7 through the Cursor provider in T3. Subagents don't run there, so the PR lists the gates that were skipped.

## Task size

- **Small:** docs, text, a config tweak, a patch dependency bump, or a contained bugfix of up to ~50 lines in up to 3 files that touches none of: architecture, data model or schema, auth or security, infra or deploy, public API, pipeline logic. Plan and implement straight through to the PR.
- **Large:** everything else, or when in doubt. Plan and stop: present the plan in the thread and wait for Filipe's approval before touching code. Apply the adjustments he sends with the approval.
- Filipe's prompt says which mode applies. If planning shows a small task is bigger, reclassify it as large, say why and stop. Never reclassify large as small.
- State the classification again in the PR.
- A project's `AGENTS.md` may refine these criteria; its version wins.

## Profiles

- **reviewed:** the review gates below apply.
- **solo:** no reviewer subagents. Opus 5.5 plans and implements.
- **No "Agent workflow" section** (a new project): before the first task, ask Filipe for the profile, the extra reviewers and any model exceptions, and propose the block from `~/.agents/claude/templates/agent-workflow.md`. Do not start the task until the block is in `AGENTS.md`.

## Review gates (profile `reviewed`)

| Task | Before Filipe sees the plan | Before opening the PR |
| --- | --- | --- |
| Small, docs or text only | none | none |
| Small, code or config | none | `code-reviewer` |
| Large | `po-reviewer`, mode `plan` | `code-reviewer`, then `po-reviewer`, mode `acceptance` |

- Also run the extra reviewers the project's "Agent workflow" section lists, when their trigger matches.
- Review the finished branch, not each edit.
- Fix every critical issue and every NOT MET criterion, then run that reviewer again. If the same finding is still open after 2 rounds, stop and report to Filipe instead of looping.
- When `po-reviewer` returns NEEDS FILIPE, put the question in the plan or the PR. Do not decide it yourself.
- Show `po-reviewer`'s verdict with the plan. Put each reviewer's final verdict in the PR description.
- Never override a reviewer's model with the Agent tool's `model` parameter.

## Model policy

| Work | Model | Effort |
| --- | --- | --- |
| Plans | Opus 5.5 | medium |
| Implementation | Opus 5.5 | medium |
| Reviewer subagents | Sonnet 5.5, set in each agent's frontmatter | set per agent |
| Solo projects | Opus 5.5 for everything | medium |

The dev does not change its own model or effort. It recommends an escalation and Filipe decides: Opus medium, then Opus high (raise the thread's effort), then Fable 5.2.

Fable 5.2 is the exception, never the default. Aim for at most 10% of plans and almost no implementation.
- Only with Filipe's explicit OK. Never start a Fable thread or subagent yourself. When a trigger fires, stop, name the trigger and recommend the next step.
- Triggers: Filipe rejected an Opus plan twice on substance (not scope tweaks); the same blocking finding survived 2 fix rounds at high effort; a bug hunt tested two hypotheses and found no new evidence.
- Not triggers: issue size (split the issue instead), importance, a first failed attempt.
- Preferred shape: a Fable thread writes or fixes the plan, and an Opus thread implements it. Fable implements only when Filipe asks for that by name.
- Follow any model exceptions in the project's "Agent workflow" section.

## T3 threads

- One thread per issue, titled `ISSUEID-short description` (for example `P1-03-account signup`).
- Start one from WSL: `t3 thread start --title '<title>' --provider claudeAgent --model claude-opus-5-5 -- <project> "$(cat prompt.md)"`. Pass the prompt as an argument, not on stdin. `t3 project list` finds the project; `t3 thread show <id>` reads the result.
- A Fable thread, after Filipe's OK: the same command with `--model claude-fable-5-2` and the title `ISSUEID-fable plan`.
- The prompt names the issue and the mode (small or large), and says to follow the repo's `AGENTS.md` and the `issue-cycle` skill.
