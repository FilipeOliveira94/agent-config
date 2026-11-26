# Dev workflow and model policy

Filipe's main development flow, in force since 2026-11-24. Every Claude Code session loads this file through `~/.claude/CLAUDE.md`. Each project's `AGENTS.md` has an "Agent workflow" section with its profile, language, Hi-risk areas, extra reviewers and exceptions; where that section is more specific, it wins. The per-issue procedure is the `issue-cycle` skill.

## Language

- Filipe may write in Portuguese or English. Reply in English.
- Code, identifiers, comments, docs, ADRs, issues, commit messages, PR titles and descriptions, and agent files are in English.
- This holds in every project, current and future, unless the project's "Agent workflow" block names another language for a scope (for example "site content: pt-BR").
- Product content (site text, UI strings, published posts) follows the project's own rules. It is content, not documentation.
- A repository that still has Portuguese docs keeps each file in one language: edit a file in its current language until the project's translation issue converts it.

## Roles

| Role | Who | Does |
| --- | --- | --- |
| Owner | Filipe | Picks the issue, approves plans, reviews the PR, merges it and deletes the branch. Confirms any switch to Fable. |
| Dev | Claude Opus 5.5 in T3 Code, one thread per issue | Rates and plans the issue, implements on a new branch from an up-to-date `main`, runs the checks and the review gates, commits, pushes the branch and opens the PR. |
| PO reviewer | `po-reviewer` subagent (Sonnet 5.5) | Checks plans and finished branches against the issue's acceptance criteria, scope and rating. |
| Code reviewer | `code-reviewer` subagent (Sonnet 5.5) | Checks the finished branch for bugs, security issues and regressions. |

No agent merges, deletes a branch, pushes `main` or deploys. There are no PO or Reviewer bots, and no fallback to another provider.

## Size and risk

Every issue carries two ratings. Size is how much work it is; Risk is how costly a mistake in it would be. They are independent: an Sm change can be Hi risk.

| Size | Meaning |
| --- | --- |
| Sm | About one session; up to ~400 hand-written lines (code and tests, not lockfiles, generated code or docs); one module or area |
| Md | One to two sessions; ~400 to 1,000 lines, or many small files; may add a migration, endpoints, a screen, a pipeline step or a CI workflow |
| Lg | More than two sessions or over ~1,000 lines; several modules, a new engine or pipeline, several screens. The plan says whether to split it |

| Risk | Meaning |
| --- | --- |
| Lo | No money, schema, auth, secrets, personal data, deploy or production data; a mistake is visible and cheap to fix: docs, tooling, UI over an existing API, charts |
| Med | New schema, endpoints, parsers, pipeline logic, CI, local or dev infra; a mistake is caught by the standard tests |
| Hi | A mistake is silent or costly: a project hard rule, money math, authorization, secrets or crypto, personal data or LLM egress, deploy or publishing, production data, compliance or legal text, billing |

- The project's "Agent workflow" block says what counts as Hi there.
- Roadmap issue tables carry two rating columns. Each cell is `expected/seen`: the estimate before the work, then what the work turned out to be.
  - **Expected/Seen Risk:** `Lo`, `Med` or `Hi`.
  - **Expected/Seen Size:** `Sm`, `Md` or `Lg`.
  - A new issue has only the expected half (`Med/-`, `Md/-`); the seen half is filled when it closes (`Med/Hi`, `Md/Lg`). An issue closed before ratings existed has only the seen half (`-/Lo`, `-/Sm`). A withdrawn issue has `-/-`.
  - Example row: `| P1-03 | Create website | ... | Lo/- | Md/- | ... |`.
- An issue without a rating gets one in the plan, with one line of reasoning; record the expected half in the same PR. Until a roadmap has these columns, the plan and the PR state the rating.
- Raise a rating when planning shows more work or risk, and say why. Never lower one without Filipe.
- State the rating in the PR. When the issue closes, fill in the seen half.

## What the rating decides

| Rating | Plan | Review gates (profile `reviewed`) | Thread effort |
| --- | --- | --- | --- |
| Sm + Lo | Plan and implement straight through to the PR | `code-reviewer` | Opus medium |
| Sm + Med, Md + Lo, Md + Med | Plan, then stop for Filipe's approval | `po-reviewer` on the plan; `code-reviewer`, then `po-reviewer` on the finished branch | Opus medium |
| Any Hi | Plan, then stop. The plan names the hard rules at stake and the tests written first | As above, plus the extra reviewers whose trigger matches | Opus high |
| Any Lg | Plan, then stop. The plan says whether to split it | As above | Opus high |

- A change that is only docs or text skips `code-reviewer`, in every project. A project's "Skip review" line adds kinds of PR that skip all gates.
- Profile `solo` uses the Plan and effort columns and skips the review gates.
- A project whose plans stop on fewer ratings says so in a `**Plan stops:**` line of its "Agent workflow" block, naming each rating with its axis ("Hi risk or Lg size"); text after the first ";" is commentary. `change-ledger finish` reads that line to decide whether a "plan approved" line is due. Without the line, the Plan column above holds.
- The thread effort is set when the thread starts (Model policy). If the dev finds itself on medium for a Hi or Lg issue, it says so at the top of the plan.
- Approval arrives in the same thread, sometimes with adjustments. Apply them before implementing.

## Profiles

- **reviewed:** the review gates apply.
- **solo:** no reviewer subagents. Opus 5.5 only; Fable only when Filipe asks for it.
- **No "Agent workflow" section** (a new project): before the first task, ask Filipe for the profile, language, Hi-risk areas, extra reviewers and any model exceptions, and propose the block from `~/.agents/claude/templates/agent-workflow.md`. Do not start the task until the block is in `AGENTS.md`.

## Change ledger

Every change (a PR, or work meant to become one) has a row in the change ledger: a one-line summary, its Expected/Seen Risk and Size, and what it cost before the merge. It is read after the work is done, to raise the share of PRs that merge without rework and to cut the stops that need Filipe. The data is a SQLite file in WSL (`~/.local/share/change-ledger/ledger.db`), outside every repo; it is never committed or uploaded. The command is `change-ledger`, run inside the repo's checkout; `change-ledger <command> --help` lists the flags. A Windows-side session runs it as `wsl.exe -d Ubuntu --exec bash -lc 'cd ~/<repo> && change-ledger …'`.

- An issue writes to it twice, as `issue-cycle` describes: `change-ledger start` when the work begins and `change-ledger finish` when the PR opens. In between, the agent lists each question to Filipe (with its reason), plan answer, review round, feedback round and lesson under "Questions and decisions" in the PR text, and `finish` records them. GitHub facts (PR, lines, CI, conflicts, merge time) come from `change-ledger sync`: never type them in.
- Never spend a turn on a ledger command or a "Questions and decisions" line alone. Run it in the same shell command as work you are already doing, such as `gh pr create … && change-ledger finish …`, or in the same message as your next tool call. Each extra turn re-reads the whole conversation, about 125k tokens in a typical issue thread.
- Applying a lesson is a separate change that Filipe approves. Then run `change-ledger lesson --applied <N> --in <repo#PR>`.

## Reviewers

- Global reviewers live in agent-config's `claude/agents/` and are linked into `~/.claude/agents/`.
- A project's extra reviewers are subagent files in its own `.claude/agents/`, committed with the repo. The "Agent workflow" block names each one and when it runs. Every project uses the global `code-reviewer`; a project's own must-check items (aconta's hard-rule checklist, for example) go in `.claude/review-checklist.md`, which `code-reviewer` reports on item by item. Do not add a project copy of a global reviewer.
- Review the finished branch, not each edit. Fix every critical issue and every NOT MET criterion, then run that reviewer again. If the same finding is still open after 2 rounds, stop and report to Filipe; he decides whether to raise the effort, switch to Fable or change the plan.
- When `po-reviewer` returns NEEDS FILIPE, put the question in the plan or the PR. Do not decide it yourself.
- Show `po-reviewer`'s verdict with the plan. Put each reviewer's final verdict in the PR description.
- Reviewers always run on Sonnet 5.5. Never override their model with the Agent tool's `model` parameter.

## Model policy

| Model | When | Who decides |
| --- | --- | --- |
| Opus 5.5, medium effort | Default for plans and implementation | Set when the thread starts |
| Opus 5.5, high effort | Issues rated Hi risk or Lg size | Set when the thread starts, from the rating |
| Fable 5.2, high effort | Opus is stuck: the same blocking finding after 2 fix rounds, Filipe rejected a plan twice on substance, or two failed hypotheses | Filipe, after the dev asks |
| Sonnet 5.5 | Reviewer subagents | Fixed in their frontmatter |

- The dev never switches its model or effort by itself. Every switch makes the next request re-read the whole conversation without the prompt cache, and the dev cannot tell in advance whether a cheaper setting would win that back. When a switch looks useful (the rating rose to Hi or Lg on a medium thread, or a Fable trigger fired), the dev says so. A switch happens only when Filipe decides it; the dev may then carry it out.
- Ask for Fable by naming the trigger. Never start a Fable thread or subagent without Filipe's yes. Size or importance alone is not a trigger. Aim for Fable on at most 10% of issues.
- On Filipe's yes, switch the thread to Fable 5.2 at high effort and end the turn; the next turn runs on Fable. In a T3 thread, load `mcp__t3-code__t3_thread_configure` with ToolSearch and call it with no `threadId` and `modelSelection: {instanceId: "claudeAgent", model: "claude-fable-5-2", options: [{id: "effort", value: "high"}]}`. Outside T3, ask Filipe to run `/model`.
- When a thread on Fable presents a plan, ask with it: implement on Fable, or switch to Opus 5.5 for the implementation? Filipe decides when he approves the plan. On "Opus", switch the thread the same way with `model: "claude-opus-5-5"` and the issue's effort, and end the turn.
- Otherwise the thread stays on Fable until it ends. If Fable's usage limit is reached, the thread moves to Opus 5.5 high; if the thread stopped on the limit, Filipe switches it.
- Follow any model exceptions in the project's "Agent workflow" block.

## T3 threads

- One thread per issue, titled `ISSUEID-short description` (for example `P1-03-account signup`).
- Start one from WSL: `t3 thread start --title '<title>' --provider claudeAgent --model claude-opus-5-5 -- <project> "$(cat prompt.md)"`. Pass the prompt as an argument, not on stdin. `t3 project list` finds the project; `t3 thread show <id>` reads the result.
- The `t3` CLI has no effort flag: a new thread takes the project's default model and effort in T3 (Opus 5.5, medium). For a Hi or Lg issue, pick high effort in the thread settings when starting it.
- The prompt names the issue and its rating when the roadmap has one, and says to follow the repo's `AGENTS.md` and the `issue-cycle` skill.

## Code index

CodeGraph keeps a local graph of symbols and calls in `.codegraph/` for open-data-platform, aconta and pedsletter. The static sites (dra-victoria-laufer, filipeoliveira-hub) and the asset repos have none. Setup is in agent-config's README.

- In a checkout with `.codegraph/`, ask `codegraph_explore` first about structure: where something is defined, who calls it, what a change reaches. Call it directly in the main thread; one call usually replaces an Explore subagent. Treat the source it returns as read.
- Use Read and Grep, and the Explore subagent for a large search, for what it does not index (SQL, dbt models, YAML, Markdown, config), for log hunts, and in a checkout without `.codegraph/`, such as a T3 worktree.
- A reply with a staleness banner names files that changed since the last sync: Read those files.
- Subagents get no MCP tools. A reviewer runs the CLI through Bash: `codegraph callers <symbol>`, `codegraph impact <symbol>`, `codegraph explore "<question>"`.
- Never read `.codegraph/` itself; a `permissions.deny` rule blocks it.
- Context Mode is not installed (decision of 2026-11-25): its hooks cut tool output inside reviewer subagents, and its sandbox runs commands that `bash-policy.py` never sees. Long output still goes through `tail`, `grep` or a filter.
