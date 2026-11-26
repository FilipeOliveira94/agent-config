## Agent workflow

Language, size and risk, review gates and model policy: `~/.agents/claude/workflow.md` (repo `FilipeOliveira94/agent-config`).

- **Profile:** reviewed | solo
- **Language:** English for everything (default); name any scope that uses another language, for example "site content: pt-BR"
- **Hi risk here:** what makes an issue Hi in this project, beyond the general list
- **Extra reviewers:** (reviewed only) `<agent>` from `.claude/agents/`, when `<paths or topics>`; or "none"
- **Skip review:** `<kinds of PR that skip all gates>`, or "none" (docs-only changes always skip `code-reviewer`)
- **Plan stops:** above Sm + Lo (the default), or the ratings whose plan stops for approval, each named with its axis, for example "Hi risk or Lg size"; keep it on one line
- **Model exceptions:** for example "Fable allowed for P3 parser plans", or "none"

<!-- Examples

aconta:
- Profile: reviewed
- Language: English for everything; the UI is bilingual (en + pt-BR) through i18n keys
- Hi risk here: any hard rule in §5
- Extra reviewers: `migration-reviewer` for migrations or any new table, column or index; `privacy-auditor` for imports, llm_gateway, logging, identity, audit or admin. The global `code-reviewer` also reports on the hard-rule checklist in .claude/review-checklist.md.
- Skip review: none
- Model exceptions: none

pedsletter:
- Profile: reviewed
- Language: English for everything; site content (posts, pages, UI) in pt-BR
- Hi risk here: the §4 content rules, the auto-merge workflow and its token, calculator math
- Extra reviewers: none
- Skip review: content PRs in src/content/posts/ published by the auto-merge workflow (ADR-003)
- Model exceptions: none

dra-victoria-laufer:
- Profile: solo
- Language: English for everything; site content in pt-BR
- Hi risk here: any published word (CFM checklist), deploy, private assets
- Model exceptions: none
-->
