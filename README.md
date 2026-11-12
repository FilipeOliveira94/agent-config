# Personal agent skills

Canonical copies live in `skills/`. This directory is the git repo. Links stay on each machine. Do not commit secrets.

`~` means the home of the system that starts the agent. On one Windows PC that is often two homes: the Linux home inside WSL, and `C:\Users\<user>` for a Windows app. A clone in one is invisible to an agent started in the other. Clone into the home of the system you will start the agent from.

Linux or WSL:

```bash
git clone <repo-url> ~/.agents
mkdir -p ~/.cursor/skills ~/.claude/skills
ln -sfn ~/.agents/skills/issue-cycle ~/.cursor/skills/issue-cycle
ln -sfn ~/.agents/skills/issue-cycle ~/.claude/skills/issue-cycle
ln -sfn ~/.agents/skills/linkedin-platform-post ~/.cursor/skills/linkedin-platform-post
ln -sfn ~/.agents/skills/linkedin-platform-post ~/.claude/skills/linkedin-platform-post
```

Windows PowerShell, for a Windows-native agent:

```powershell
git clone <repo-url> "$env:USERPROFILE\.agents"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.cursor\skills", "$env:USERPROFILE\.claude\skills"
New-Item -ItemType SymbolicLink -Force -Path "$env:USERPROFILE\.cursor\skills\issue-cycle" -Target "$env:USERPROFILE\.agents\skills\issue-cycle"
New-Item -ItemType SymbolicLink -Force -Path "$env:USERPROFILE\.claude\skills\issue-cycle" -Target "$env:USERPROFILE\.agents\skills\issue-cycle"
New-Item -ItemType SymbolicLink -Force -Path "$env:USERPROFILE\.cursor\skills\linkedin-platform-post" -Target "$env:USERPROFILE\.agents\skills\linkedin-platform-post"
New-Item -ItemType SymbolicLink -Force -Path "$env:USERPROFILE\.claude\skills\linkedin-platform-post" -Target "$env:USERPROFILE\.agents\skills\linkedin-platform-post"
```

| Agent | Path it reads, under that same home |
| --- | --- |
| Cursor, including Grok in Cursor | `.cursor/skills` |
| Claude Code, and Claude threads in T3 Code | `.claude/skills` |
| Codex, and the Grok CLI | `.agents/skills` |
