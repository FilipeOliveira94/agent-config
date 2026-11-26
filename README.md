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

## Install (Linux or WSL)

```bash
git clone https://github.com/FilipeOliveira94/agent-config.git ~/.agents
~/.agents/install.sh
```

The script is safe to re-run; run it again after a pull that adds or removes a skill or an agent. It:

- links each skill into `~/.claude/skills/`, and removes links there that point at skills this repo no longer has;
- links each subagent into `~/.claude/agents/`;
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
| reviewed | open-data-platform, aconta, pedsletter | Opus 5.5 dev; `code-reviewer` before each code PR; `po-reviewer` on every issue rated above Sm + Lo |
| solo | dra-victoria-laufer, dra-victoria-laufer-assets, filipeoliveira-hub, filipeoliveira-hub-assets | Opus 5.5 for everything, no reviewers |

Extra reviewers are subagent files in the project's own `.claude/agents/`. A project file with the same name as a global subagent replaces it there; aconta does this for `code-reviewer`.

## Two homes on Windows

`~` is the home of the system that starts the agent. On a Windows PC with WSL that means two homes: the Linux home and `C:\Users\<user>`. A clone in one is invisible to an agent started in the other. Claude Code threads in T3 run these projects from WSL, so install there. `install.sh` does not set up a Windows-native home.

| Agent | Path it reads, under that same home |
| --- | --- |
| Claude Code, and Claude threads in T3 Code | `.claude/skills`, `.claude/agents`, `.claude/CLAUDE.md` |
| Codex | `.agents/skills` |
