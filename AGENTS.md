# agent-config

Filipe's agent setup: the dev workflow, reviewer subagents and skills that every project uses. `install.sh` links them from the live copy, `~/.agents`, into `~/.claude`. The README covers the layout and the install.

## Agent workflow

Language, size and risk, review gates and model policy: `~/.agents/claude/workflow.md` (repo `FilipeOliveira94/agent-config`).

- **Profile:** reviewed
- **Language:** English for everything
- **Hi risk here:** what agents are allowed to do (the "No agent merges…" rule, the review gates and the model policy in `claude/workflow.md`, and each reviewer's tools in `claude/agents/`); the default model and effort in `claude/settings.fragment.json`; `install.sh` steps that delete or overwrite files outside the repo (the link prune, the `settings.json` merge); anything that sends local files or data off the machine
- **Extra reviewers:** none
- **Skip review:** none. Changes under `skills/` and `claude/` change how agents work, so they get `code-reviewer` like code, not the docs-only skip. README.md, AGENTS.md and LICENSE are docs.
- **Model exceptions:** none
