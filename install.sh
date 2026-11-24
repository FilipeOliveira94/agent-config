#!/usr/bin/env bash
# Link this repo into the agent homes. Safe to re-run.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CURSOR_SKILLS="$HOME/.cursor/skills"

if [ "$REPO" != "$HOME/.agents" ]; then
  echo "warning: the repo is at $REPO, not ~/.agents. The projects' AGENTS.md files and Codex refer to ~/.agents; clone it there." >&2
fi

link() {  # link <target> <link path>
  local target="$1" dest="$2"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "skip $dest: a real file or directory is already there" >&2
    return
  fi
  if [ "$(readlink "$dest" 2>/dev/null)" != "$target" ]; then
    ln -sfn "$target" "$dest"
    echo "linked $dest"
  fi
}

prune() {  # remove links in <dir> that point into this repo and no longer resolve
  local dir="$1" l
  for l in "$dir"/*; do
    [ -L "$l" ] || continue
    case "$(readlink "$l")" in
      "$REPO"/*) [ -e "$l" ] || { rm "$l"; echo "removed stale $l"; } ;;
    esac
  done
}

# Skills
mkdir -p "$CLAUDE_HOME/skills" "$CURSOR_SKILLS"
for s in "$REPO"/skills/*/; do
  s="${s%/}"
  link "$s" "$CLAUDE_HOME/skills/$(basename "$s")"
  link "$s" "$CURSOR_SKILLS/$(basename "$s")"
done
prune "$CLAUDE_HOME/skills"
prune "$CURSOR_SKILLS"

# Subagents
mkdir -p "$CLAUDE_HOME/agents"
for a in "$REPO"/claude/agents/*.md; do
  link "$a" "$CLAUDE_HOME/agents/$(basename "$a")"
done
prune "$CLAUDE_HOME/agents"

# Workflow import in the user CLAUDE.md
case "$REPO" in
  "$HOME"/*) REL="~${REPO#"$HOME"}" ;;
  *) REL="$REPO" ;;
esac
IMPORT="@$REL/claude/workflow.md"
touch "$CLAUDE_HOME/CLAUDE.md"
if ! grep -qxF "$IMPORT" "$CLAUDE_HOME/CLAUDE.md"; then
  printf '\n# Dev workflow\n%s\n' "$IMPORT" >> "$CLAUDE_HOME/CLAUDE.md"
  echo "added $IMPORT to $CLAUDE_HOME/CLAUDE.md"
fi

# Default model and effort, added to settings.json only where a key is missing, so a value set with
# /model or /effort is never overwritten. Not linked: Claude Code rewrites this file.
SETTINGS="$CLAUDE_HOME/settings.json"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
python3 - "$SETTINGS" "$REPO/claude/settings.fragment.json" <<'PY'
import copy, json, shutil, sys, time

path, frag_path = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        current = json.load(f)
except ValueError as err:
    print(f"warning: {path} is not valid JSON ({err}); settings left unchanged", file=sys.stderr)
    sys.exit(0)
with open(frag_path) as f:
    fragment = json.load(f)

def add_missing(base, extra):
    for key, value in extra.items():
        if key not in base:
            base[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(base[key], dict):
            add_missing(base[key], value)
    return base

merged = add_missing(copy.deepcopy(current), fragment)
if merged == current:
    print(f"{path} already has every key of the settings fragment")
else:
    shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    with open(path, "w") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"added the missing settings fragment keys to {path} (backup next to it)")
PY
