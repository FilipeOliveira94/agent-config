# agent-config

Filipe's agent setup: shared skills, Claude Code subagents, and the dev workflow with its model policy. This repo holds the canonical copies; `install.sh` links them into each tool's home. Do not commit secrets.

## Layout

| Path | Content | Where it lands |
| --- | --- | --- |
| `skills/<name>/` | Skills shared by Claude Code and Codex | Linked into `~/.claude/skills/`. Codex reads `~/.agents/skills/` directly |
| `claude/workflow.md` | Dev workflow: language, roles, Size and Risk rating, review gates, model policy and escalation | Imported by `~/.claude/CLAUDE.md`, so every Claude Code session loads it |
| `claude/agents/` | Subagents `po-reviewer` and `code-reviewer` (Sonnet 5.5) | Linked into `~/.claude/agents/` |
| `claude/templates/agent-workflow.md` | The "Agent workflow" block each project keeps in its `AGENTS.md` | Copied by hand into a new project |
| `claude/settings.fragment.json` | Default model and effort (Opus 5.5 at medium), Opus as the fallback model, Fable at high effort when chosen | Merged into `~/.claude/settings.json` |
| `tools/change-ledger/` | `change-ledger`, the local database of changes per project: command, HTML report template, tests | Linked as `~/.local/bin/change-ledger` |

## Install (Linux or WSL)

```bash
git clone https://github.com/FilipeOliveira94/agent-config.git ~/.agents
~/.agents/install.sh
```

The script is safe to re-run; run it again after a pull that adds or removes a skill or an agent. It:

- links each skill into `~/.claude/skills/`, and removes links there that point at skills this repo no longer has;
- links each subagent into `~/.claude/agents/`;
- links `change-ledger` into `~/.local/bin/`;
- adds `@~/.agents/claude/workflow.md` to `~/.claude/CLAUDE.md`;
- adds the keys of `claude/settings.fragment.json` that `~/.claude/settings.json` does not have yet, after a timestamped backup. It never overwrites a value, so a model or effort set with `/model` or `/effort` stays. The file is merged, not linked, because Claude Code rewrites it.

Keep the clone at `~/.agents`, on `main` or on a branch that has these files; the links point into the working tree.

## Skills

| Skill | Use |
| --- | --- |
| `issue-cycle` | Takes an issue from plan to an open PR |
| `module-boundaries` | Where shared logic lives when extracting repeated code or choosing a boundary |
| `browser-proof` | Proof that a browser-visible change works: statements, screenshots, passed / failed / untested |
| `plain-voice` | Second pass over prose a person reads: posts (spoken) and PR text (engineering). Adapted from unslop, MIT. Its `voice/` files hold Filipe's samples and corrections |
| `linkedin-platform-post` | Portuguese-first LinkedIn posts about data work, with an optional SVG poster |

## Change ledger

`change-ledger` keeps one row per change, per project, in a local SQLite database. It shows which PRs merge without rework, and why work stops for Filipe. Agents write the judgment fields while `issue-cycle` runs. `change-ledger sync` reads everything else from GitHub and from each project's roadmap and `AGENTS.md` on the default branch. The rules for agents are the "Change ledger" section of `claude/workflow.md`.

| Command | What it does |
| --- | --- |
| `brief` | Start-of-work view for the repo in the working directory: what waits on Filipe (open PRs with CI, conflicts, merge order and edited files; plans; unanswered questions), open lessons, last 30 days. Syncs that project first |
| `start`, `set`, `log`, `lesson` | Agent writes: a new change, its fields, an event (`plan`, `approved`, `rejected`, `ask`, `answer`, `checks`, `review`, `feedback`, `note`), a lesson |
| `sync` | Reads PRs (state, lines, CI, conflicts, commits after opening, merge time) and roadmap ratings. Finds every clone under `~` owned by the `gh` user, PRs nobody logged included |
| `list`, `show <id>` | Recent changes as a table; one change with its event history |
| `stats` | Merge rate, clean merges, time to merge, rework, questions by reason, estimate accuracy, data gaps |
| `report` | Writes `~/.local/share/change-ledger/report.html`, a self-contained dashboard with filters by project and period |
| `export` | Changes as CSV, or changes, events, lessons and roadmap issues as JSON |

What a change records:

| Field | Filled by | Why |
| --- | --- | --- |
| Project, issue, title, kind | `start`; sync for PRs it finds | Group by project and by roadmap issue; compare kinds (feat, fix, docs…) |
| Summary | Agent, after opening the PR | What changed and why, in one or two sentences |
| Expected/Seen Risk, Expected/Seen Size | Agent; otherwise the issue's rating from the roadmap | Same tags and `expected/seen` cells as the roadmaps |
| Rating note | Agent | Why a rating was set or raised |
| Status and outcome | `log` and sync | planning → awaiting_approval → in_progress → pr_open → merged or closed. Outcome: clean merge, merged after rework, open, dropped |
| Code lines, doc lines, measured size | Sync | Lines added outside docs, lockfiles, generated files and binaries, on the Sm/Md/Lg scale, to check the seen size |
| Commits after opening, feedback rounds | Sync; agent `log feedback` | Rework once the PR was up |
| CI, mergeable, conflicted | Sync | Red checks and conflicts on open PRs. Conflicted stays set once a sync saw a conflict |
| Edited paths | Sync | `brief` shows them, so overlap with an open PR shows before planning |
| Questions by reason | Agent `log ask` | Why work stopped for Filipe: decision, context, access, correction, blocked |
| Plan rounds and rejections, review rounds and blocks | Agent `log` | Where rework came from before the PR |
| Merge after, owner actions | Agent | Merge order and the step Filipe takes at merge, shown in `brief` and the report |
| Model, effort, T3 thread, profile | `start`, from the session | The model policy in practice (Fable on at most 10% of issues), effort against outcome, the thread to reopen |
| Opened, merged, time to merge | Sync | How long PRs wait |
| Lessons | Agent `lesson` | What would have prevented a question or a rework round, where the fix belongs, and the PR that applied it |

Definitions:
- **Clean merge:** merged with no commit after the PR opened and no feedback round.
- **Merge rate:** merged PRs out of merged plus closed-without-merging PRs.
- **Questions per change:** counted only on changes agents started with `start`, because PRs found by sync carry no events.
- **Dependabot:** its PRs show in "waiting on Filipe" but stay out of the rates.
- **Conflicts:** GitHub reports a conflict only while the PR is open, so conflicts from before the ledger existed are not in it.

The data lives in `~/.local/share/change-ledger/ledger.db` (set `CHANGE_LEDGER_DB` to move it), outside every repo, and stays on this machine.
- **GitHub:** read only. The tool runs GraphQL queries for PRs and `gh api` GETs for `ROADMAP.md` and `AGENTS.md`. It never posts, comments or uploads.
- **Report:** makes no network requests. From Windows, open `\\wsl.localhost\Ubuntu\home\<user>\.local\share\change-ledger\report.html`.
- **Repos:** set `CHANGE_LEDGER_ROOTS` and `CHANGE_LEDGER_OWNERS` to change which clones it scans.
- **Tests:** `python3 -m unittest discover -s tools/change-ledger`.
- **Remove:** delete `~/.local/bin/change-ledger` and the `change-ledger` data folder.

## CodeGraph (code index)

A local symbol and call graph for the repos with real code: open-data-platform, aconta, pedsletter. The routing rules are the "Code index" section of `claude/workflow.md`. Setup in WSL, done once:

```bash
npm i -g @colbymchenry/codegraph            # Node 20 to 24
ln -sfn "$(npm prefix -g)/bin/codegraph" ~/.local/bin/codegraph
codegraph telemetry off
claude mcp add-json -s user codegraph \
  '{"type":"stdio","command":"/home/filipe/.local/bin/codegraph","args":["serve","--mcp","--no-telemetry"],"alwaysLoad":true}'
cd ~/<repo> && codegraph init --local-only --yes   # per repo; nothing shows in git status
```

`~/.claude/settings.json` allows `mcp__codegraph__*` and the read-only CLI commands (`explore`, `callers`, `callees`, `impact`, `status`, `query`, `affected`), and denies `Read(**/.codegraph/**)`. The installer's own `codegraph install` is not used, so it never edits `CLAUDE.md` or the permissions. A T3 worktree is a separate folder with no index; run `codegraph init --local-only` there only when that thread needs the graph. Remove with `codegraph uninit` per repo, `claude mcp remove -s user codegraph` and `npm rm -g @colbymchenry/codegraph`.

Context Mode (mksglu/context-mode) was evaluated and not installed on 2026-11-25: it needs Node 24.15, its hooks shorten output inside reviewer subagents with no setting to turn that off, and its sandbox runs commands outside `bash-policy.py`.

## Projects

Each project declares its workflow in the "Agent workflow" section of its `AGENTS.md`: profile, language, Hi-risk areas, extra reviewers, review exceptions and model exceptions. A project without that section makes Claude ask for one before its first task. Every issue is rated Size (Sm, Md, Lg) and Risk (Lo, Med, Hi); the rating decides whether Claude stops for plan approval, which reviewers run and the starting effort.

| Profile | Projects | What runs |
| --- | --- | --- |
| reviewed | open-data-platform, aconta, pedsletter, plantao | Opus 5.5 dev; `code-reviewer` before each code PR; `po-reviewer` on every issue rated above Sm + Lo |
| solo | dra-victoria-laufer, dra-victoria-laufer-assets, filipeoliveira-hub, filipeoliveira-hub-assets | Opus 5.5 for everything, no reviewers |

Extra reviewers are subagent files in the project's own `.claude/agents/`. Every project uses the global `code-reviewer`; a project's own must-check items go in `.claude/review-checklist.md`, which `code-reviewer` reports on item by item (aconta keeps its hard-rule checklist there).

## Two homes on Windows

`~` is the home of the system that starts the agent. On a Windows PC with WSL that means two homes: the Linux home and `C:\Users\<user>`. A clone in one is invisible to an agent started in the other. Claude Code threads in T3 run these projects from WSL, so install there. `install.sh` does not set up a Windows-native home.

| Agent | Path it reads, under that same home |
| --- | --- |
| Claude Code, and Claude threads in T3 Code | `.claude/skills`, `.claude/agents`, `.claude/CLAUDE.md` |
| Codex | `.agents/skills` |
