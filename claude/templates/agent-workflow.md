## Agent workflow

Gates and model policy: `~/.agents/claude/workflow.md` (repo `FilipeOliveira94/agent-config`).

- **Profile:** reviewed | solo
- **Extra reviewers:** (reviewed only) `<agent>`, when `<paths or topics>`; or "none"
- **Skip review:** `<kinds of PR that skip the gates>`, or "none"
- **Model exceptions:** for example "Fable allowed for P3 parser plans", or "none"

<!-- Examples

aconta:
- Profile: reviewed
- Extra reviewers: `migration-reviewer` for migrations or any new table, column or index; `privacy-auditor` for imports, llm_gateway, logging, identity, audit or admin. `code-reviewer` is the project's own, in .claude/agents/.
- Skip review: none. An issue with Risk High in ROADMAP.md gets the large-task gates even when it is small.
- Model exceptions: none

pedsletter:
- Profile: reviewed
- Extra reviewers: none
- Skip review: content PRs in src/content/posts/ published by the auto-merge workflow (ADR-003)
- Model exceptions: none

dra-victoria-laufer:
- Profile: solo
- Model exceptions: none
-->
