## Agent workflow

Language, size and risk, review gates and model policy: `~/.agents/claude/workflow.md` (repo `FilipeOliveira94/agent-config`).

- **Profile:** reviewed | solo
- **Language:** English for everything (default); name any scope that uses another language, for example "site content: pt-BR"
- **High risk here:** what makes an issue High in this project, beyond the general list
- **Extra reviewers:** (reviewed only) `<agent>` from `.claude/agents/`, when `<paths or topics>`; or "none"
- **Skip review:** `<kinds of PR that skip the gates>`, or "none"
- **Model exceptions:** for example "Fable allowed for P3 parser plans", or "none"

<!-- Examples

aconta:
- Profile: reviewed
- Language: English for everything; the UI is bilingual (en + pt-BR) through i18n keys
- High risk here: any hard rule in §5
- Extra reviewers: `migration-reviewer` for migrations or any new table, column or index; `privacy-auditor` for imports, llm_gateway, logging, identity, audit or admin. `code-reviewer` is the project's own, in .claude/agents/.
- Skip review: none
- Model exceptions: none

pedsletter:
- Profile: reviewed
- Language: English for everything; site content (posts, pages, UI) in pt-BR
- High risk here: the §4 content rules, the auto-merge workflow and its token, calculator math
- Extra reviewers: none
- Skip review: content PRs in src/content/posts/ published by the auto-merge workflow (ADR-003)
- Model exceptions: none

dra-victoria-laufer:
- Profile: solo
- Language: English for everything; site content in pt-BR
- High risk here: any published word (CFM checklist), deploy, private assets
- Model exceptions: none
-->
