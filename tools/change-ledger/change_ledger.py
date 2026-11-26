#!/usr/bin/env python3
"""change-ledger: a local database of changes per project, for Filipe's agent workflow.

One row per change (a PR, or work meant to become one): what it is, a short
summary, its Expected/Seen Risk and Size, and what it cost on the way to the
merge: questions to Filipe, plan and review rounds, rework after the PR opened,
CI failures and conflicts. Agents write twice per issue: `start` when the work
begins, and `finish` when the PR opens. `finish` reads the questions, plan
answers, review verdicts and feedback that the agent listed under "Questions and
decisions" in the PR text as they happened. `sync` reads what GitHub and each
roadmap already know, so nobody types PR numbers, line counts, CI states or
merge times.

The data is one SQLite file outside every repository:
~/.local/share/change-ledger/ledger.db, or $CHANGE_LEDGER_DB. Towards GitHub the
tool only reads (`gh pr list`, `gh api` GET); it never posts, comments or
uploads. Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# CREATE ... IF NOT EXISTS never changes a table that already exists: bumping SCHEMA_VERSION needs an
# entry in MIGRATIONS with the statements that take version N-1 to N.
SCHEMA_VERSION = 2
MIGRATIONS: dict[int, tuple[str, ...]] = {
    2: ("ALTER TABLE events ADD COLUMN source TEXT", "ALTER TABLE lessons ADD COLUMN source TEXT"),
}
VIEWS_VERSION = "1"

RISKS = ("Lo", "Med", "Hi")
SIZES = ("Sm", "Md", "Lg")
STATUSES = ("planning", "awaiting_approval", "in_progress", "pr_open", "merged", "closed", "abandoned")
FINISHED = ("merged", "closed", "abandoned")
DEFAULT_BRANCHES = {"main", "master", "HEAD"}
STALE_HOURS = 48
SM_MAX, MD_MAX = 400, 1000  # hand-written lines, from the size scale in workflow.md
HOTSPOT_FILES = {"roadmap.md", "project_status.md", "changelog.md", "decisions.md", "status-log.md"}

ASK_REASONS = {
    "decision": "a choice that is Filipe's (scope, product, trade-off) and the issue did not settle",
    "context": "information that should have been in the repo; the answer names the file that should hold it",
    "access": "a permission, credential, setting or tool the agent could not use",
    "correction": "Filipe corrected a result or a misunderstanding",
    "blocked": "an environment failure: usage limit, broken tool, CI infrastructure",
}
LOG_KINDS = {
    "plan": "the plan is presented and waits for Filipe's approval",
    "approved": "Filipe approved the plan; the note lists his adjustments, if any",
    "rejected": "Filipe rejected the plan on substance",
    "ask": "stopped for Filipe outside a planned gate (needs --reason)",
    "answer": "Filipe answered the open question; the note says where the answer belongs",
    "checks": "local checks or tests ran (needs --verdict pass or fail)",
    "review": "one reviewer round (needs --actor and --verdict)",
    "feedback": "Filipe asked for changes after the PR opened",
    "note": "anything else worth keeping",
}
STATUS_AFTER = {"plan": "awaiting_approval", "approved": "in_progress", "rejected": "planning"}
IDLE_HOURS = 72  # a change in progress with no PR and no update for this long is flagged in `brief`

# The PR text's "Questions and decisions" section: one bullet per event, written when it happens.
NOTES_HEADING = "Questions and decisions"
NOTE_ASK = re.compile(r"^(decision|context|access|correction|blocked)\s*:\s*(.+)$", re.I)
NOTE_PLAN = re.compile(r"^plan\s*:?\s*(approved|rejected)\b[\s:,.-]*(.*)$", re.I)
NOTE_FEEDBACK = re.compile(r"^feedback\s*:\s*(.+)$", re.I)
NOTE_LESSON = re.compile(r"^lesson(?:\s+for\s+([^:]+?))?\s*:\s*(.+)$", re.I)
# reviewers are subagents with hyphenated names (code-reviewer, privacy-auditor), so "checks: PASS" is not one
# The verdict words the reviewer agent files define. BLOCK and CHANGES NEEDED count as blocking (v_changes).
REVIEW_VERDICTS = ("PASS", "BLOCK", "APPROVED", "CHANGES NEEDED", "NEEDS FILIPE", "NEEDS INPUT")
# Words a reviewer has used instead (aconta #15: "ACCEPT WITH NOTES"), recorded as the defined word they mean.
REVIEW_DRIFT = {"APPROVED WITH NOTES": "APPROVED", "ACCEPT WITH NOTES": "APPROVED", "ACCEPT": "APPROVED",
                "REJECTED": "CHANGES NEEDED", "REJECT": "CHANGES NEEDED", "FAIL": "BLOCK"}
_VERDICT_WORDS = sorted((*REVIEW_VERDICTS, *REVIEW_DRIFT), key=len, reverse=True)  # longest first
NOTE_REVIEW = re.compile(r"^([a-z][a-z0-9]*(?:[-_.][a-z0-9]+)+)\s*:\s*"
                         r"(" + "|".join(w.replace(" ", r"\s+") for w in _VERDICT_WORDS) + r")\b[\s,.:;-]*(.*)$", re.I)
NOTE_REVIEWER = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)+\s*:", re.I)  # a reviewer line, any word
NOTE_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")  # a bullet or a numbered item


# ---------------------------------------------------------------- basics

def die(msg: str, code: int = 1):
    print(f"change-ledger: {msg}", file=sys.stderr)
    raise SystemExit(code)


def warn(msg: str) -> None:
    print(f"change-ledger: warning: {msg}", file=sys.stderr)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_ts(value: str | None) -> datetime | None:
    if not value or value.startswith("0001-"):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hours_since(value: str | None) -> float:
    dt = parse_ts(value)
    return (now_utc() - dt).total_seconds() / 3600 if dt else 0.0


def fmt_age(value: str | None) -> str:
    dt = parse_ts(value)
    if not dt:
        return "?"
    secs = max((now_utc() - dt).total_seconds(), 0)
    if secs < 3600:
        return f"{secs // 60:.0f}m"
    if secs < 48 * 3600:
        return f"{secs / 3600:.0f}h"
    return f"{secs / 86400:.0f}d"


def fmt_hours(hours: float | None) -> str:
    if hours is None:
        return "-"
    if hours < 1:
        return f"{hours * 60:.0f}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def fmt_local(value: str | None) -> str:
    dt = parse_ts(value)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "-"


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"


def ratio(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def short(text: str | None, width: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def parse_since(value: str | None) -> str | None:
    if not value:
        return None
    m = re.fullmatch(r"\s*(\d+)\s*([dh])\s*", value)
    if m:
        n = int(m.group(1))
        return iso(now_utc() - (timedelta(days=n) if m.group(2) == "d" else timedelta(hours=n)))
    dt = parse_ts(value if "T" in value else value + "T00:00:00")
    if not dt:
        die(f"--since takes 30d, 12h or a date like 2026-11-01, not {value!r}", 2)
    return iso(dt)


def md_table(headers: list[str], rows: list[list]) -> str:
    def cell(value) -> str:
        return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------- database

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS projects (
  name      TEXT PRIMARY KEY,   -- repository name, e.g. aconta
  repo      TEXT NOT NULL,      -- owner/name on GitHub
  path      TEXT,               -- main local clone
  profile   TEXT,               -- reviewed | solo, from the AGENTS.md "Agent workflow" block
  roadmap   TEXT,               -- roadmap path in the repo, when it has one
  synced_at TEXT
);

CREATE TABLE IF NOT EXISTS changes (
  id                 INTEGER PRIMARY KEY,
  project            TEXT NOT NULL REFERENCES projects(name),
  issue              TEXT,      -- roadmap issue ID (P1-03, I-01, 7.2); NULL for work outside the roadmap
  title              TEXT NOT NULL,
  kind               TEXT,      -- feat, fix, docs, chore, refactor, test, ci, build, perf, content, deps...
  summary            TEXT,      -- one or two sentences: what changed and why
  status             TEXT NOT NULL DEFAULT 'planning' CHECK (status IN
                       ('planning','awaiting_approval','in_progress','pr_open','merged','closed','abandoned')),
  exp_risk           TEXT CHECK (exp_risk IN ('Lo','Med','Hi')),
  seen_risk          TEXT CHECK (seen_risk IN ('Lo','Med','Hi')),
  exp_size           TEXT CHECK (exp_size IN ('Sm','Md','Lg')),
  seen_size          TEXT CHECK (seen_size IN ('Sm','Md','Lg')),
  rating_note        TEXT,      -- why a rating was set or changed
  profile            TEXT,      -- project profile when the change started
  model              TEXT,      -- dev model, e.g. claude-opus-5-5
  effort             TEXT,      -- dev effort, from CLAUDE_EFFORT when T3 sets it
  thread             TEXT,      -- T3 thread id, from T3CODE_THREAD_ID
  branch             TEXT,
  pr                 INTEGER,
  pr_url             TEXT,
  author             TEXT,
  additions          INTEGER,
  deletions          INTEGER,
  files              INTEGER,
  code_lines         INTEGER,   -- lines added outside docs, lockfiles, generated files and binaries
  doc_lines          INTEGER,   -- lines added in docs (.md, .rst, .txt, docs/)
  paths              TEXT,      -- JSON list of changed paths, most-changed first
  commits            INTEGER,
  commits_after_open INTEGER,   -- commits pushed after the PR opened: rework
  ci                 TEXT CHECK (ci IN ('pass','fail','pending','none')),
  mergeable          TEXT,      -- MERGEABLE | CONFLICTING | UNKNOWN at the last sync
  conflicted         INTEGER NOT NULL DEFAULT 0,  -- 1 once a sync saw a conflict
  gh_comments        INTEGER,   -- comments and reviews on the PR page
  merge_after        TEXT,      -- PRs that must merge first, e.g. agent-config#7
  owner_actions      TEXT,      -- what Filipe does before or after the merge
  source             TEXT NOT NULL DEFAULT 'agent' CHECK (source IN ('agent','github')),
  created_at         TEXT NOT NULL,
  opened_at          TEXT,
  merged_at          TEXT,
  closed_at          TEXT,
  updated_at         TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS changes_pr ON changes(project, pr) WHERE pr IS NOT NULL;
CREATE INDEX IF NOT EXISTS changes_status ON changes(project, status);

CREATE TABLE IF NOT EXISTS events (
  id        INTEGER PRIMARY KEY,
  change_id INTEGER NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
  ts        TEXT NOT NULL,
  kind      TEXT NOT NULL,   -- start, rated, plan, approved, rejected, ask, answer, checks, review,
                             -- feedback, note; from sync: pr_opened, ready, ci, conflict, merged, closed
  reason    TEXT,            -- ask: decision | context | access | correction | blocked
  actor     TEXT,            -- dev, filipe, a reviewer's name, github
  verdict   TEXT,            -- review or checks verdict, CI state
  round     INTEGER,         -- plan round, or round per reviewer
  note      TEXT,
  source    TEXT             -- 'pr_text' when finish read it from the PR text; finish rewrites only those
);
CREATE INDEX IF NOT EXISTS events_change ON events(change_id, id);

CREATE TABLE IF NOT EXISTS lessons (
  id         INTEGER PRIMARY KEY,
  project    TEXT NOT NULL REFERENCES projects(name),
  change_id  INTEGER REFERENCES changes(id) ON DELETE SET NULL,
  ts         TEXT NOT NULL,
  text       TEXT NOT NULL,   -- what would have prevented the question, the rework or the failure
  target     TEXT,            -- where the fix belongs: AGENTS.md, workflow.md, the issue text, a test, CI...
  state      TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open','applied','dropped')),
  applied_in TEXT,            -- the PR or commit that applied it
  updated_at TEXT,
  source     TEXT             -- 'pr_text' when finish read it from the PR text
);

CREATE TABLE IF NOT EXISTS issues (   -- mirror of the roadmap on the default branch, refreshed by sync
  project   TEXT NOT NULL,
  issue     TEXT NOT NULL,
  title     TEXT,
  exp_risk  TEXT,
  seen_risk TEXT,
  exp_size  TEXT,
  seen_size TEXT,
  status    TEXT,
  synced_at TEXT NOT NULL,
  PRIMARY KEY (project, issue)
);
"""

VIEWS = f"""
CREATE VIEW v_changes AS
WITH ev AS (
  SELECT change_id,
         SUM(kind = 'ask') AS asks,
         SUM(kind = 'ask' AND reason = 'decision') AS asks_decision,
         SUM(kind = 'ask' AND reason = 'context') AS asks_context,
         SUM(kind = 'ask' AND reason = 'access') AS asks_access,
         SUM(kind = 'ask' AND reason = 'correction') AS asks_correction,
         SUM(kind = 'ask' AND reason = 'blocked') AS asks_blocked,
         SUM(kind = 'plan') AS plan_rounds,
         SUM(kind = 'rejected') AS plan_rejections,
         SUM(kind = 'review') AS review_rounds,
         SUM(kind = 'review' AND verdict IN ('BLOCK', 'CHANGES NEEDED')) AS review_blocks,
         SUM(kind = 'feedback') AS feedback_rounds,
         SUM(kind = 'ci' AND verdict = 'fail') AS ci_failures
  FROM events GROUP BY change_id
)
SELECT c.*,
       i.title AS issue_title,
       i.status AS issue_status,
       COALESCE(c.exp_risk, i.exp_risk) AS risk_expected,
       COALESCE(c.seen_risk, i.seen_risk) AS risk_seen,
       COALESCE(c.exp_size, i.exp_size) AS size_expected,
       COALESCE(c.seen_size, i.seen_size) AS size_seen,
       COALESCE(c.exp_risk, i.exp_risk, '-') || '/' || COALESCE(c.seen_risk, i.seen_risk, '-') AS risk,
       COALESCE(c.exp_size, i.exp_size, '-') || '/' || COALESCE(c.seen_size, i.seen_size, '-') AS size,
       CASE WHEN COALESCE(c.exp_risk, c.seen_risk, c.exp_size, c.seen_size) IS NOT NULL THEN 'ledger'
            WHEN COALESCE(i.exp_risk, i.seen_risk, i.exp_size, i.seen_size) IS NOT NULL THEN 'roadmap'
       END AS rating_from,
       CASE WHEN COALESCE(c.code_lines, 0) = 0 THEN NULL
            WHEN c.code_lines <= {SM_MAX} THEN 'Sm'
            WHEN c.code_lines <= {MD_MAX} THEN 'Md'
            ELSE 'Lg' END AS measured_size,
       COALESCE(ev.asks, 0) AS asks,
       COALESCE(ev.asks_decision, 0) AS asks_decision,
       COALESCE(ev.asks_context, 0) AS asks_context,
       COALESCE(ev.asks_access, 0) AS asks_access,
       COALESCE(ev.asks_correction, 0) AS asks_correction,
       COALESCE(ev.asks_blocked, 0) AS asks_blocked,
       COALESCE(ev.plan_rounds, 0) AS plan_rounds,
       COALESCE(ev.plan_rejections, 0) AS plan_rejections,
       COALESCE(ev.review_rounds, 0) AS review_rounds,
       COALESCE(ev.review_blocks, 0) AS review_blocks,
       COALESCE(ev.feedback_rounds, 0) AS feedback_rounds,
       COALESCE(ev.ci_failures, 0) AS ci_failures,
       CASE WHEN c.status = 'merged' AND COALESCE(c.commits_after_open, 0) = 0
                 AND COALESCE(ev.feedback_rounds, 0) = 0 THEN 'clean'
            WHEN c.status = 'merged' THEN 'rework'
            WHEN c.status IN ('closed', 'abandoned') THEN 'dropped'
            WHEN c.status = 'pr_open' THEN 'open'
            ELSE 'in_progress' END AS outcome,
       ROUND((julianday(c.merged_at) - julianday(c.opened_at)) * 24, 2) AS hours_to_merge,
       (COALESCE(c.author, '') LIKE 'app/%' OR COALESCE(c.author, '') LIKE '%[bot]') AS bot
FROM changes c
LEFT JOIN ev ON ev.change_id = c.id
LEFT JOIN issues i ON i.project = c.project AND i.issue = c.issue;
"""

CHANGE_COLUMNS = {
    "issue", "title", "kind", "summary", "status", "exp_risk", "seen_risk", "exp_size", "seen_size",
    "rating_note", "profile", "model", "effort", "thread", "branch", "pr", "pr_url", "author", "additions",
    "deletions", "files", "code_lines", "doc_lines", "paths", "commits", "commits_after_open", "ci",
    "mergeable", "conflicted", "gh_comments", "merge_after", "owner_actions", "source", "opened_at",
    "merged_at", "closed_at",
}


def db_path() -> Path:
    env = os.environ.get("CHANGE_LEDGER_DB")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "change-ledger" / "ledger.db"


_CONNECTIONS: list[sqlite3.Connection] = []  # closed by main() when the command ends


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=15)
    _CONNECTIONS.append(con)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 15000")
    con.execute("PRAGMA foreign_keys = ON")
    if con.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
        with contextlib.suppress(sqlite3.OperationalError):  # another process may hold the lock
            con.execute("PRAGMA journal_mode = WAL")
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        die(f"{path} uses schema {version}; this change-ledger knows {SCHEMA_VERSION}. Pull agent-config.")
    # Each upgrade runs under BEGIN IMMEDIATE: a second process starting at the same moment waits for
    # the first one instead of colliding with it.
    if version == 0:  # a new database; IF NOT EXISTS makes a second run harmless
        con.executescript(f"BEGIN IMMEDIATE;\n{SCHEMA}\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;")
    elif version < SCHEMA_VERSION:
        con.execute("BEGIN IMMEDIATE")
        version = con.execute("PRAGMA user_version").fetchone()[0]  # another process may have upgraded it
        for step in range(version + 1, SCHEMA_VERSION + 1):
            if step not in MIGRATIONS:
                con.rollback()
                die(f"{path}: no migration to schema {step}")
            for statement in MIGRATIONS[step]:
                con.execute(statement)
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        con.commit()
    views = con.execute("SELECT value FROM meta WHERE key = 'views'").fetchone()
    if not views or views[0] != VIEWS_VERSION:
        con.executescript(f"BEGIN IMMEDIATE;\nDROP VIEW IF EXISTS v_changes;\n{VIEWS}\n"
                          f"INSERT INTO meta(key, value) VALUES ('views', '{VIEWS_VERSION}') "
                          "ON CONFLICT(key) DO UPDATE SET value = excluded.value;\nCOMMIT;")
    return con


def meta_get(con, key: str) -> str | None:
    row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def meta_set(con, key: str, value: str) -> None:
    con.execute("INSERT INTO meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def get_change(con, cid: int):
    return con.execute("SELECT * FROM changes WHERE id = ?", (cid,)).fetchone()


def update_change(con, cid: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in CHANGE_COLUMNS}
    if not fields:
        return
    fields["updated_at"] = iso(now_utc())
    assignments = ", ".join(f"{k} = ?" for k in fields)
    con.execute(f"UPDATE changes SET {assignments} WHERE id = ?", (*fields.values(), cid))


def add_event(con, cid: int, kind: str, ts: str | None = None, reason: str | None = None,
              actor: str | None = None, verdict: str | None = None, round: int | None = None,
              note: str | None = None, source: str | None = None) -> None:
    con.execute("INSERT INTO events(change_id, ts, kind, reason, actor, verdict, round, note, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, ts or iso(now_utc()), kind, reason, actor, verdict, round, note, source))


# ---------------------------------------------------------------- git and projects

GITHUB_REMOTE = re.compile(r"github\.com[:/]+([\w.-]+)/([\w.-]+?)(?:\.git)?/*$", re.I)
PROFILE_RE = re.compile(r"\*\*Profile:\*\*\s*`?(reviewed|solo)\b", re.I)


def git(cwd, *args) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def checkout_info(cwd) -> tuple[str, str, str, str] | None:
    """(name, owner/name, checkout top, main clone) for a GitHub checkout, or None."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return None
    m = GITHUB_REMOTE.search(git(top, "remote", "get-url", "origin") or "")
    if not m:
        return None
    common = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")
    main = str(Path(common).parent) if common else top
    return m.group(2), f"{m.group(1)}/{m.group(2)}", top, main


def current_branch(cwd) -> str | None:
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    return None if not branch or branch in DEFAULT_BRANCHES else branch


def read_profile(top) -> str | None:
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = Path(top) / name
        if path.is_file():
            m = PROFILE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
            if m:
                return m.group(1).lower()
    return None


def ensure_project(con, name: str, repo: str, path: str | None = None, profile: str | None = None) -> None:
    con.execute("INSERT INTO projects(name, repo, path, profile) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET repo = excluded.repo, "
                "path = COALESCE(excluded.path, projects.path), "
                "profile = COALESCE(projects.profile, excluded.profile)",  # sync sets it from the default branch
                (name, repo, path, profile))


def here(con, project: str | None = None):
    """The project row for --project or for the checkout in the working directory."""
    info = checkout_info(Path.cwd())
    if project:
        row = con.execute("SELECT * FROM projects WHERE name = ?", (project,)).fetchone()
        if row:
            return row, (info if info and info[0] == project else None)
        if not (info and info[0] == project):
            die(f"unknown project {project!r}: run inside its checkout once, or run `change-ledger sync`", 2)
    if not info:
        die("not inside a GitHub checkout: cd into the repo or pass --project (or --id for a known change)", 2)
    name, repo, top, main = info
    ensure_project(con, name, repo, main, read_profile(top))
    con.commit()
    return con.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone(), info


def scan_roots() -> list[Path]:
    env = os.environ.get("CHANGE_LEDGER_ROOTS")
    if env:
        return [Path(p).expanduser() for p in env.split(os.pathsep) if p]
    return [Path.home()]


def allowed_owners(con) -> set[str]:
    env = os.environ.get("CHANGE_LEDGER_OWNERS")
    if env:
        return {o.strip().lower() for o in env.split(",") if o.strip()}
    user = meta_get(con, "gh_user")
    if not user:
        try:
            user = gh(["api", "user", "--jq", ".login"]).strip()
        except GhError:
            user = ""
        if user:
            meta_set(con, "gh_user", user)
    return {user.lower()} if user else set()


def discover(con) -> list[sqlite3.Row]:
    """Register every clone owned by the allowed owners under the scan roots (one level deep)."""
    owners = allowed_owners(con)
    if not owners:
        warn("cannot tell whose repos to scan (gh not logged in?); set CHANGE_LEDGER_OWNERS")
    else:
        for root in scan_roots():
            try:
                dirs = sorted(d for d in root.iterdir() if d.is_dir())
            except OSError:
                continue
            for d in dirs:
                if not (d / ".git").exists():
                    continue
                info = checkout_info(d)
                if not info or info[1].split("/")[0].lower() not in owners:
                    continue
                name, repo, top, main = info
                if Path(main).resolve() != d.resolve():
                    continue  # a worktree: its main clone stands for the project
                ensure_project(con, name, repo, main, read_profile(d))
        con.commit()
    return con.execute("SELECT * FROM projects ORDER BY name").fetchall()


# ---------------------------------------------------------------- titles, issues, paths, CI

CONVENTIONAL = re.compile(r"^\s*(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?!?:\s*\S")
KINDS = {"feat", "fix", "docs", "chore", "refactor", "test", "ci", "build", "perf", "style", "revert",
         "content", "deps"}
BRANCH_KINDS = {"brand": "content", "dependabot": "deps"}
ISSUE_RE = r"(?:[A-Za-z]{1,3}\d{0,2}-\d{1,3}|\d{1,2}\.\d{1,2})"
NOT_ISSUES = {"ADR", "DP", "D", "RFC", "CVE", "GH", "PR"}


def norm_issue(token: str | None) -> str | None:
    token = (token or "").strip().strip("()[]`*").upper()
    if not re.fullmatch(ISSUE_RE, token):
        return None
    if "-" in token and token.split("-")[0].rstrip("0123456789") in NOT_ISSUES:
        return None
    return token


def kind_of(title: str | None, branch: str | None) -> str | None:
    m = CONVENTIONAL.match(title or "")
    if m:
        kind, scope = m.group("type").lower(), (m.group("scope") or "").lower()
        if scope.startswith("deps"):
            return "deps"
        if kind in KINDS:
            return kind
    prefix = (branch or "").split("/", 1)[0].lower()
    return BRANCH_KINDS.get(prefix) or (prefix if prefix in KINDS else None)


def issue_of(title: str | None, branch: str | None) -> str | None:
    m = CONVENTIONAL.match(title or "")
    if m and m.group("scope"):
        for token in re.split(r"[,\s/]+", m.group("scope")):
            found = norm_issue(token)
            if found:
                return found
    for token in re.findall(r"\(([^()]{1,12})\)", title or ""):
        found = norm_issue(token)
        if found and "-" in found:
            return found
    if branch and "/" in branch:
        m = re.match(rf"({ISSUE_RE})(?=-|$)", branch.split("/", 1)[1], re.I)
        if m:
            return norm_issue(m.group(1))
    return None


LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock",
             "poetry.lock", "pipfile.lock", "cargo.lock", "composer.lock", "gemfile.lock", "go.sum"}
SKIP_SUFFIXES = (".min.js", ".min.css", ".map", ".snap", ".lock", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                 ".avif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".zip", ".gz",
                 ".mp4", ".webm", ".mp3", ".wav")
SKIP_DIRS = ("dist/", "build/", "node_modules/", "vendor/", ".astro/", "coverage/", "__snapshots__/")
DOC_SUFFIXES = (".md", ".markdown", ".rst", ".txt", ".adoc")


def classify_path(path: str) -> str:
    """'code', 'doc' or 'skip' (lockfiles, generated files, binaries), for the measured size."""
    p = path.lower()
    name = p.rsplit("/", 1)[-1]
    if name in LOCKFILES or p.endswith(SKIP_SUFFIXES) or any(p.startswith(d) or f"/{d}" in p for d in SKIP_DIRS):
        return "skip"
    if name.startswith("requirements") and name.endswith(".txt"):
        return "code"
    if p.endswith(DOC_SUFFIXES) or p.startswith("docs/") or name.startswith(("license", "copying", "notice")):
        return "doc"
    return "code"


CI_FAIL = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}
CI_PENDING = {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED", "EXPECTED"}


def ci_state(rollup) -> tuple[str, str | None]:
    """('pass' | 'fail' | 'pending' | 'none', names of failing checks)."""
    if not rollup:
        return "none", None
    failing, pending = [], False
    for check in rollup:
        name = check.get("name") or check.get("context") or "check"
        state = (check.get("conclusion") or check.get("state") or check.get("status") or "").upper()
        if state in CI_FAIL:
            failing.append(name)
        elif state in CI_PENDING or not state:
            pending = True
    if failing:
        return "fail", ", ".join(failing[:5])
    return ("pending", None) if pending else ("pass", None)


def hot_paths(paths_json: str | None, limit: int = 3) -> list[str]:
    try:
        paths = json.loads(paths_json or "[]")
    except ValueError:
        return []
    if not isinstance(paths, list):
        return []
    hot = [p for p in paths if p.rsplit("/", 1)[-1].lower() in HOTSPOT_FILES]
    rest = [p for p in paths if p not in hot]
    picked = (hot + rest)[:limit]
    extra = len(paths) - len(picked)
    return picked + ([f"+{extra} more"] if extra > 0 else [])


# ---------------------------------------------------------------- GitHub (read-only)

class GhError(Exception):
    def __init__(self, message: str, stdout: str = ""):
        super().__init__(message)
        self.stdout = stdout  # what gh printed anyway: GraphQL sends partial data along with some errors


TRANSIENT = re.compile(r"internet connection|timed out|timeout|connection reset|HTTP 50[234]|EOF", re.I)


def gh(args: list[str], timeout: int = 120, retries: int = 1) -> str:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise GhError("gh (GitHub CLI) is not on PATH") from None
    except subprocess.TimeoutExpired:
        if retries:
            return gh(args, timeout, retries - 1)
        raise GhError(f"gh {' '.join(args[:2])} timed out") from None
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        message = lines[-1] if lines else f"gh exited with {proc.returncode}"
        if retries and TRANSIENT.search(message):
            time.sleep(2)
            return gh(args, timeout, retries - 1)
        raise GhError(message, proc.stdout or "")
    return proc.stdout


# Only the fields the ledger uses, so a page of 50 PRs stays far below GraphQL's node limit
# (`gh pr list --json commits` also pulls every commit's authors and hits it at 100 PRs).
# commits(last: 100): rework commits are the newest ones. draftEvents: the first of these events tells
# whether the PR opened as a draft (ReadyForReviewEvent first) or was converted later. lastReady: when
# it was last marked ready, for the `ready` event.
PR_FIELDS = """
fragment pr on PullRequest {
  number title url state isDraft createdAt mergedAt closedAt headRefName
  additions deletions changedFiles mergeable
  author { __typename login }
  comments { totalCount }
  reviews { totalCount }
  files(first: 100) { pageInfo { hasNextPage endCursor } nodes { path additions deletions } }
  commits(last: 100) { totalCount nodes { commit { authoredDate } } }
  draftEvents: timelineItems(itemTypes: [READY_FOR_REVIEW_EVENT, CONVERT_TO_DRAFT_EVENT], first: 1) {
    nodes { __typename ... on ReadyForReviewEvent { createdAt } ... on ConvertToDraftEvent { createdAt } }
  }
  lastReady: timelineItems(itemTypes: [READY_FOR_REVIEW_EVENT], last: 1) {
    nodes { ... on ReadyForReviewEvent { createdAt } }
  }
  last: commits(last: 1) { nodes { commit { statusCheckRollup { contexts(first: 50) { nodes {
    __typename
    ... on CheckRun { name status conclusion }
    ... on StatusContext { context state }
  } } } } } }
}
"""

PR_QUERY = """
query($owner: String!, $name: String!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { ...pr }
    }
  }
}
""" + PR_FIELDS

FILES_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      files(first: 100, after: $after) { pageInfo { hasNextPage endCursor } nodes { path additions deletions } }
    }
  }
}
"""


def normalize_pr(node: dict) -> dict:
    author = node.get("author") or {}
    login = author.get("login")
    if login and author.get("__typename") == "Bot":
        login = f"app/{login}"  # the form `gh pr list` prints, e.g. app/dependabot
    last = (node.get("last") or {}).get("nodes") or [{}]
    rollup = (last[0].get("commit") or {}).get("statusCheckRollup") or {}
    files = node.get("files") or {}
    more_files = files.get("pageInfo") or {}
    commits = node.get("commits") or {}
    first_event = ((node.get("draftEvents") or {}).get("nodes") or [None])[0] or {}
    last_ready = ((node.get("lastReady") or {}).get("nodes") or [None])[0] or {}
    if first_event.get("__typename") == "ReadyForReviewEvent":
        review_since = first_event.get("createdAt")  # opened as a draft: review starts when it was marked ready
    elif node.get("isDraft") and not first_event:
        review_since = None  # a draft that was never ready for review
    else:
        review_since = node.get("createdAt")
    return {
        "number": node["number"], "title": node.get("title"), "url": node.get("url"),
        "state": node.get("state"), "isDraft": node.get("isDraft"), "createdAt": node.get("createdAt"),
        "reviewSince": review_since, "lastReadyAt": last_ready.get("createdAt"),
        "mergedAt": node.get("mergedAt"), "closedAt": node.get("closedAt"),
        "headRefName": node.get("headRefName"), "additions": node.get("additions"),
        "deletions": node.get("deletions"), "changedFiles": node.get("changedFiles"),
        "mergeable": node.get("mergeable"), "author": {"login": login},
        "comments_count": (node.get("comments") or {}).get("totalCount", 0),
        "reviews_count": (node.get("reviews") or {}).get("totalCount", 0),
        "files": files.get("nodes") or [],
        "files_after": more_files.get("endCursor") if more_files.get("hasNextPage") else None,
        "commits": [n.get("commit") or {} for n in commits.get("nodes") or []],
        "commit_count": commits.get("totalCount"),
        "statusCheckRollup": (rollup.get("contexts") or {}).get("nodes") or [],
    }


def graphql(query: str, **variables) -> dict:
    """The `data` of a read-only GraphQL query; ints go as typed fields (-F), the rest as strings (-f)."""
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is not None:
            args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    return json.loads(gh(args) or "{}").get("data") or {}


def fetch_prs(repo: str, limit: int) -> list[dict]:
    """The most recent `limit` PRs of owner/name, newest first."""
    owner, name = repo.split("/", 1)
    prs: list[dict] = []
    after = None
    while len(prs) < limit:
        repository = graphql(PR_QUERY, owner=owner, name=name, first=min(50, limit - len(prs)),
                             after=after).get("repository")
        if repository is None:
            raise GhError(f"{repo}: repository not found or not visible to gh")
        page = repository["pullRequests"]
        prs += [normalize_pr(n) for n in page["nodes"]]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return complete_files(repo, prs)


def fetch_prs_by_number(repo: str, numbers: list[int]) -> tuple[list[dict], list[int]]:
    """Given PRs of owner/name, 25 per query, and the numbers GitHub does not have."""
    owner, name = repo.split("/", 1)
    prs: list[dict] = []
    missing: list[int] = []
    for i in range(0, len(numbers), 25):
        fields = " ".join(f"p{int(n)}: pullRequest(number: {int(n)}) {{ ...pr }}" for n in numbers[i:i + 25])
        query = ("query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { "
                 + fields + " } }" + PR_FIELDS)
        try:
            data = graphql(query, owner=owner, name=name)
        except GhError as err:
            # An unknown number gets a NOT_FOUND error and a null alias; gh exits 1 but still prints
            # the other PRs. Any other error stops the sync of this project.
            try:
                body = json.loads(err.stdout or "{}")
            except ValueError:
                raise err from None
            if (not isinstance(body, dict) or not body.get("errors")
                    or any(e.get("type") != "NOT_FOUND" for e in body["errors"])):
                raise err from None
            data = body.get("data") or {}
        repository = data.get("repository") or {}
        prs += [normalize_pr(n) for n in repository.values() if n]
        missing += [int(alias[1:]) for alias, n in repository.items() if n is None]
    return complete_files(repo, prs), missing


def complete_files(repo: str, prs: list[dict]) -> list[dict]:
    """Read the files past the first 100 of a large PR, so its line counts cover every file."""
    owner, name = repo.split("/", 1)
    for pr in prs:
        after = pr.pop("files_after", None)
        while after:
            data = graphql(FILES_QUERY, owner=owner, name=name, number=pr["number"], after=after)
            files = ((data.get("repository") or {}).get("pullRequest") or {}).get("files") or {}
            pr["files"] = pr["files"] + (files.get("nodes") or [])
            page = files.get("pageInfo") or {}
            after = page.get("endCursor") if page.get("hasNextPage") else None
    return prs


ROADMAP_PATHS = ("ROADMAP.md", "docs/ROADMAP.md")


def fetch_file(repo: str, path: str) -> str | None:
    """A file from the default branch (GET), or None when it does not exist."""
    try:
        return gh(["api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/{path}"])
    except GhError as err:
        if "404" in str(err) or "Not Found" in str(err):
            return None
        raise


def fetch_roadmap(repo: str) -> tuple[str, str] | None:
    for path in ROADMAP_PATHS:
        text = fetch_file(repo, path)
        if text is not None:
            return path, text
    return None


# ---------------------------------------------------------------- roadmap mirror

RISK_CELL = re.compile(r"^(Lo|Med|Hi|-)\s*/\s*(Lo|Med|Hi|-)$")
SIZE_CELL = re.compile(r"^(Sm|Md|Lg|-)\s*/\s*(Sm|Md|Lg|-)$")
HEADING = re.compile(r"^#{2,6}\s+(.+)$")


def strip_md(text: str) -> str:
    return (text or "").replace("`", "").replace("**", "").strip()


def split_rating(cell: str | None, pattern) -> tuple[str | None, str | None]:
    m = pattern.match(strip_md(cell or ""))
    if not m:
        return None, None
    return tuple(None if part == "-" else part for part in m.groups())


def table_cells(line: str) -> list[str] | None:
    text = line.strip()
    if not text.startswith("|"):
        return None
    text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", text)]


def parse_roadmap(text: str) -> dict[str, dict]:
    """Issue ID -> {title, risk: (exp, seen), size: (exp, seen), status}.

    Reads both layouts in use: issue tables with "Expected/Seen Risk" and "Expected/Seen Size"
    columns, and one key/value table per issue under a heading that starts with the ID.
    """
    issues: dict[str, dict] = {}
    lines = text.splitlines()
    heading: tuple[str, str] | None = None
    i = 0
    while i < len(lines):
        h = HEADING.match(lines[i].strip())
        if h:
            first, _, rest = h.group(1).strip().partition(" ")
            iid = norm_issue(first.rstrip(":.—-"))
            heading = (iid, rest.strip(" —-:")) if iid else None
            i += 1
            continue
        cells = table_cells(lines[i])
        if cells and "Expected/Seen Risk" in cells and "Expected/Seen Size" in cells:
            col = {strip_md(c): n for n, c in enumerate(cells)}
            id_col = col.get("ID", col.get("Issue", 0))
            title_col, status_col = col.get("Title"), col.get("Status")
            risk_col, size_col = col["Expected/Seen Risk"], col["Expected/Seen Size"]
            i += 1
            while i < len(lines):
                row = table_cells(lines[i])
                if row is None:
                    break
                i += 1
                if all(re.fullmatch(r":?-{3,}:?", c) for c in row if c):
                    continue
                iid = norm_issue(strip_md(row[id_col])) if id_col < len(row) else None
                if not iid or len(row) <= max(risk_col, size_col):
                    continue
                rec = issues.setdefault(iid, {})
                if title_col is not None and title_col < len(row):
                    rec["title"] = strip_md(row[title_col])
                if status_col is not None and status_col < len(row):
                    rec["status"] = strip_md(row[status_col])
                rec["risk"] = split_rating(row[risk_col], RISK_CELL)
                rec["size"] = split_rating(row[size_col], SIZE_CELL)
            continue
        if cells and heading and len(cells) >= 2:
            key = strip_md(cells[0])
            if key in ("Expected/Seen Risk", "Expected/Seen Size", "Status"):
                rec = issues.setdefault(heading[0], {"title": heading[1]})
                if key == "Status":
                    rec["status"] = strip_md(cells[1])
                elif key == "Expected/Seen Risk":
                    rec["risk"] = split_rating(cells[1], RISK_CELL)
                else:
                    rec["size"] = split_rating(cells[1], SIZE_CELL)
        i += 1
    return issues


def import_roadmap(con, project: str, path: str, text: str) -> int:
    issues = parse_roadmap(text)
    ts = iso(now_utc())
    con.execute("UPDATE projects SET roadmap = ? WHERE name = ?", (path, project))
    for iid, rec in issues.items():
        exp_risk, seen_risk = rec.get("risk") or (None, None)
        exp_size, seen_size = rec.get("size") or (None, None)
        con.execute(
            "INSERT INTO issues(project, issue, title, exp_risk, seen_risk, exp_size, seen_size, status, synced_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(project, issue) DO UPDATE SET "
            "title = excluded.title, exp_risk = excluded.exp_risk, seen_risk = excluded.seen_risk, "
            "exp_size = excluded.exp_size, seen_size = excluded.seen_size, status = excluded.status, "
            "synced_at = excluded.synced_at",
            (project, iid, rec.get("title"), exp_risk, seen_risk, exp_size, seen_size, rec.get("status"), ts))
    con.execute("DELETE FROM issues WHERE project = ? AND synced_at <> ?", (project, ts))
    return len(issues)


# ---------------------------------------------------------------- sync

STATE_TO_STATUS = {"OPEN": "pr_open", "MERGED": "merged", "CLOSED": "closed"}


def pr_fields(pr: dict) -> dict:
    code = doc = 0
    weighted = []
    for item in pr.get("files") or []:
        path = item.get("path") or ""
        added = item.get("additions") or 0
        kind = classify_path(path)
        if kind == "code":
            code += added
        elif kind == "doc":
            doc += added
        weighted.append((added + (item.get("deletions") or 0), path))
    weighted.sort(key=lambda w: (-w[0], w[1]))
    created = parse_ts(pr.get("createdAt"))
    # Rework is counted from the moment the PR is up for review (a draft: when it was marked ready).
    # Author dates survive a rebase, commit dates do not, so a rebase alone does not count as rework.
    opened = parse_ts(pr["reviewSince"]) if "reviewSince" in pr else created
    commits = pr.get("commits") or []
    after = 0
    if opened:
        for commit in commits:
            when = parse_ts(commit.get("authoredDate"))
            if when and when > opened + timedelta(seconds=90):
                after += 1
    ci, failing = ci_state(pr.get("statusCheckRollup"))
    return {
        "pr": pr["number"],
        "pr_url": pr.get("url"),
        "branch": pr.get("headRefName") or None,
        "author": (pr.get("author") or {}).get("login"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "files": pr.get("changedFiles"),
        "code_lines": code,
        "doc_lines": doc,
        "paths": json.dumps([p for _, p in weighted[:40]]),
        "commits": pr["commit_count"] if pr.get("commit_count") is not None else len(commits),
        "commits_after_open": after,
        "ci": ci,
        "failing": failing,
        "mergeable": pr.get("mergeable") or None,
        "gh_comments": (pr.get("comments_count") or 0) + (pr.get("reviews_count") or 0),
        "opened_at": iso(opened),  # up for review; None while the PR is a draft that was never ready
        "merged_at": iso(parse_ts(pr.get("mergedAt"))),
        "closed_at": iso(parse_ts(pr.get("closedAt"))),
        "created": iso(created),  # not stored: the time of the pr_opened event and of a new row
        "draft": bool(pr.get("isDraft")),
    }


SYNCED_FIELDS = ("pr", "pr_url", "branch", "author", "additions", "deletions", "files", "code_lines",
                 "doc_lines", "paths", "commits", "commits_after_open", "ci", "mergeable", "gh_comments",
                 "opened_at", "merged_at", "closed_at")


def upsert_pr(con, project, pr: dict) -> tuple[int, int]:
    """Create or refresh the change for one PR. Returns (created, updated) as 0/1."""
    name = project["name"]
    f = pr_fields(pr)
    row = con.execute("SELECT * FROM changes WHERE project = ? AND pr = ?", (name, f["pr"])).fetchone()
    if row is None and f["branch"]:
        row = con.execute("SELECT * FROM changes WHERE project = ? AND pr IS NULL AND branch = ? "
                          "ORDER BY id DESC LIMIT 1", (name, f["branch"])).fetchone()
    title = pr.get("title") or f"PR #{f['pr']}"
    created = row is None
    if created:
        ts = f["created"] or iso(now_utc())
        cur = con.execute(
            "INSERT INTO changes(project, issue, title, kind, status, profile, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'pr_open', ?, 'github', ?, ?)",
            (name, issue_of(title, f["branch"]), title, kind_of(title, f["branch"]), project["profile"], ts, ts))
        row = get_change(con, cur.lastrowid)
    status = STATE_TO_STATUS.get(pr.get("state"), row["status"])
    if status == "pr_open" and f["draft"]:  # a draft is still being worked on, not waiting on Filipe
        status = row["status"] if row["status"] in ("planning", "awaiting_approval", "in_progress") else "in_progress"
    if row["status"] == "abandoned" and status == "closed":
        status = "abandoned"
    events = []
    if row["pr"] is None:
        events.append({"kind": "pr_opened", "ts": f["created"], "actor": "github",
                       "note": f"PR #{f['pr']}" + (" as a draft" if f["draft"] else "")})
    elif status == "pr_open" and row["status"] == "in_progress" and pr.get("lastReadyAt"):
        events.append({"kind": "ready", "ts": pr["lastReadyAt"], "actor": "github", "note": "marked ready for review"})
    if status == "merged" and row["status"] != "merged":
        events.append({"kind": "merged", "ts": f["merged_at"], "actor": "github"})
    if status == "closed" and row["status"] not in ("closed", "abandoned"):
        events.append({"kind": "closed", "ts": f["closed_at"], "actor": "github", "note": "closed without merging"})
    if f["ci"] == "fail" and row["ci"] != "fail":
        events.append({"kind": "ci", "actor": "github", "verdict": "fail", "note": f["failing"]})
    elif f["ci"] == "pass" and row["ci"] == "fail":
        events.append({"kind": "ci", "actor": "github", "verdict": "pass", "note": "checks green again"})
    if f["mergeable"] == "CONFLICTING" and row["mergeable"] != "CONFLICTING":
        events.append({"kind": "conflict", "actor": "github", "note": "conflicts with the base branch"})
    updates = {k: f[k] for k in SYNCED_FIELDS}
    updates["status"] = status
    updates["conflicted"] = 1 if row["conflicted"] or f["mergeable"] == "CONFLICTING" else 0
    if not row["kind"]:
        updates["kind"] = kind_of(title, f["branch"])
    if not row["issue"]:
        updates["issue"] = issue_of(title, f["branch"])
    if row["source"] == "github":
        updates["title"] = title
    changed = any(row[k] != v for k, v in updates.items())
    if changed:
        update_change(con, row["id"], **updates)
    for event in events:
        add_event(con, row["id"], **event)
    return int(created), int(changed and not created)


def sync(con, names: list[str] | None = None, limit: int = 100, roadmaps: bool = True,
         report=print) -> bool:
    projects = discover(con)
    if names:
        known = {p["name"] for p in projects}
        for missing in sorted(set(names) - known):
            warn(f"{missing}: not a known project")
        projects = [p for p in projects if p["name"] in names]
    ok = True
    for project in projects:
        # Every read from GitHub happens before the first write, so no write transaction stays open
        # while gh runs; another agent's `log` would otherwise wait on it and fail with "locked".
        try:
            prs = fetch_prs(project["repo"], limit)
        except GhError as err:
            warn(f"{project['name']}: {err}")
            ok = False
            continue
        seen = {pr["number"] for pr in prs}
        # A PR still open in the ledger but older than the window (many newer PRs since) is read by
        # number; otherwise it would stay open here after GitHub merged or closed it.
        behind = {r["pr"]: r["id"] for r in con.execute(
            "SELECT id, pr FROM changes WHERE project = ? AND pr IS NOT NULL "
            "AND status NOT IN ('merged', 'closed', 'abandoned')", (project["name"],)) if r["pr"] not in seen}
        if behind:
            try:
                older, missing = fetch_prs_by_number(project["repo"], sorted(behind))
                prs += older
            except GhError as err:
                warn(f"{project['name']}: PRs {', '.join(f'#{n}' for n in sorted(behind))}: {err}")
                ok, missing = False, []
            for n in missing:
                warn(f"{project['name']}: change #{behind[n]} names PR #{n}, which GitHub does not have; "
                     f"correct it with `change-ledger set --id {behind[n]} --pr <number>`")
        found = agents = None
        if roadmaps:  # the default branch is the truth: local checkouts often sit on old branches
            try:
                found = fetch_roadmap(project["repo"])
                agents = fetch_file(project["repo"], "AGENTS.md")
            except GhError as err:
                warn(f"{project['name']} roadmap: {err}")
                found = agents = None
        created = updated = 0
        for pr in prs:
            c, u = upsert_pr(con, project, pr)
            created, updated = created + c, updated + u
        note = ""
        if found:
            note = f", {import_roadmap(con, project['name'], *found)} roadmap issues"
        if agents is not None:
            m = PROFILE_RE.search(agents)
            con.execute("UPDATE projects SET profile = ? WHERE name = ?",
                        (m.group(1).lower() if m else None, project["name"]))
        con.execute("UPDATE projects SET synced_at = ? WHERE name = ?", (iso(now_utc()), project["name"]))
        con.commit()
        report(f"{project['name']}: {len(prs)} PRs read, {created} new, {updated} updated{note}")
    return ok


# ---------------------------------------------------------------- queries and metrics

def load_rows(con, project: str | None = None, since: str | None = None) -> list[dict]:
    query, params = "SELECT * FROM v_changes WHERE 1 = 1", []
    if project:
        query += " AND project = ?"
        params.append(project)
    if since:
        query += " AND COALESCE(opened_at, created_at) >= ?"
        params.append(since)
    query += " ORDER BY COALESCE(opened_at, created_at) DESC, id DESC"
    return [dict(r) for r in con.execute(query, params)]


def load_issues(con, project: str | None = None) -> list[dict]:
    if project:
        return [dict(r) for r in con.execute("SELECT * FROM issues WHERE project = ?", (project,))]
    return [dict(r) for r in con.execute("SELECT * FROM issues")]


def open_asks(con, project: str | None = None) -> list[dict]:
    query = ("SELECT e.*, c.project, c.issue, c.title FROM events e JOIN changes c ON c.id = e.change_id "
             "WHERE e.kind = 'ask' AND c.status NOT IN ('merged', 'closed', 'abandoned') "
             "AND NOT EXISTS (SELECT 1 FROM events a WHERE a.change_id = e.change_id "
             "AND a.kind = 'answer' AND a.id > e.id)")
    params = []
    if project:
        query += " AND c.project = ?"
        params.append(project)
    return [dict(r) for r in con.execute(query + " ORDER BY e.id", params)]


def estimate_hits(issues: list[dict], field: str, order: tuple) -> dict:
    pairs = [(r[f"exp_{field}"], r[f"seen_{field}"]) for r in issues if r[f"exp_{field}"] and r[f"seen_{field}"]]
    right = sum(1 for e, s in pairs if e == s)
    under = sum(1 for e, s in pairs if order.index(s) > order.index(e))
    return {"total": len(pairs), "right": right, "under": under, "over": len(pairs) - right - under}


def summarize(rows: list[dict], issues: list[dict]) -> dict:
    """Metrics over changes. Bot PRs (Dependabot) are left out of the rates."""
    human = [r for r in rows if not r["bot"]]
    merged = [r for r in human if r["status"] == "merged"]
    closed_prs = [r for r in human if r["status"] in ("closed", "abandoned") and r["pr"]]
    clean = [r for r in merged if r["outcome"] == "clean"]
    hours = [r["hours_to_merge"] for r in merged if r["hours_to_merge"] is not None]
    agent = [r for r in human if r["source"] == "agent"]
    asks = sum(r["asks"] for r in agent)
    open_prs = [r for r in rows if r["status"] == "pr_open"]
    by_size = {}
    for size in SIZES:
        group = [r for r in merged if r["measured_size"] == size]
        by_size[size] = (len(group), sum(1 for r in group if r["outcome"] == "clean"))
    return {
        "changes": len(human),
        "merged": len(merged),
        "closed": len(closed_prs),
        "clean": len(clean),
        "merge_rate": ratio(len(merged), len(merged) + len(closed_prs)),
        "clean_rate": ratio(len(clean), len(merged)),
        "median_hours": statistics.median(hours) if hours else None,
        "rework_commits": ratio(sum(r["commits_after_open"] or 0 for r in merged), len(merged)),
        "agent_changes": len(agent),
        "asks": asks,
        "asks_per_change": ratio(asks, len(agent)),
        "asks_by_reason": {k: sum(r[f"asks_{k}"] for r in agent) for k in ASK_REASONS},
        "review_blocks": sum(r["review_blocks"] for r in agent),
        "feedback_rounds": sum(r["feedback_rounds"] for r in agent),
        "open_prs": len(open_prs),
        "stale": sum(1 for r in open_prs if hours_since(r["opened_at"]) > STALE_HOURS),
        "ci_red": sum(1 for r in open_prs if r["ci"] == "fail"),
        "conflicting": sum(1 for r in open_prs if r["mergeable"] == "CONFLICTING"),
        "ever_conflicted": sum(1 for r in human if r["conflicted"]),
        "size_est": estimate_hits(issues, "size", SIZES),
        "risk_est": estimate_hits(issues, "risk", RISKS),
        "clean_by_size": by_size,
        "no_summary": sum(1 for r in agent if r["status"] in ("pr_open", "merged") and not r["summary"]),
        "no_seen": sum(1 for r in agent if r["status"] == "merged" and not (r["risk_seen"] and r["size_seen"])),
    }


def fmt_rate(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.0f}%"


def fmt_num(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


# ---------------------------------------------------------------- the PR text

def notes_file(cwd, cid: int) -> Path | None:
    """A change's PR text file, in the checkout's git folder: never committed, kept when a conversation is compacted."""
    gitdir = git(cwd, "rev-parse", "--absolute-git-dir")
    return Path(gitdir) / f"change-ledger-{cid}.md" if gitdir else None


def md_section(text: str, heading: str) -> list[str] | None:
    """The lines under a Markdown heading, up to the next heading of the same or a higher level."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not (m and m.group(2).strip().lower() == heading.lower()):
            continue
        body = []
        for nxt in lines[i + 1:]:
            h = re.match(r"^(#{1,6})\s", nxt)
            if h and len(h.group(1)) <= len(m.group(1)):
                break
            body.append(nxt)
        return body
    return None


def first_paragraph(lines: list[str], limit: int = 300) -> str | None:
    """The first paragraph of a section, as one line: the ledger's summary when finish gets none."""
    para = []
    for line in lines:
        if line.strip():
            para.append(re.sub(r"^\s*[-*+]\s+", "", line).strip())
        elif para:
            break
    text = " ".join(para)
    return short(text, limit) if text else None


def review_verdict(word: str, note: str | None = None) -> tuple[str, str | None]:
    """A reviewer's verdict word as the defined word, and the note; a drift word is kept at the front of the note."""
    word = " ".join(word.upper().split())
    if word not in REVIEW_DRIFT:
        return word, note
    return REVIEW_DRIFT[word], f"{word}: {note}" if note else word


def parse_notes(lines: list[str]) -> tuple[list[dict], list[tuple[str | None, str]], list[str]]:
    """Events and lessons from the list items under "Questions and decisions", and the lines not understood.

    - decision|context|access|correction|blocked: <question> Answer: <answer>
    - plan approved|rejected: <adjustments or why>
    - <reviewer>: PASS|BLOCK|APPROVED|CHANGES NEEDED|NEEDS FILIPE|NEEDS INPUT, <findings that held>
      (ACCEPT, ACCEPT WITH NOTES, APPROVED WITH NOTES, REJECT, REJECTED and FAIL are read too, see REVIEW_DRIFT)
    - feedback: <what Filipe asked for after the PR opened>
    - lesson for <target>: <what would have prevented it>
    """
    events: list[dict] = []
    lessons: list[tuple[str | None, str]] = []
    unknown: list[str] = []
    rounds: dict[str, int] = {}
    plans = 0
    for raw in lines:
        m = NOTE_ITEM.match(raw)
        if not m:  # prose is fine; an entry written without "- " in front would be lost, so say so
            text = raw.strip()
            if text and any(p.match(text) for p in (NOTE_ASK, NOTE_PLAN, NOTE_FEEDBACK, NOTE_LESSON, NOTE_REVIEW)):
                unknown.append(f"{text} (not a list item)")
            continue
        if re.fullmatch(r"(none|nothing|n/a)\.?", m.group(1), re.I):
            continue
        item = m.group(1)
        if a := NOTE_ASK.match(item):
            events.append({"kind": "ask", "reason": a.group(1).lower(), "actor": "dev", "note": a.group(2).strip()})
        elif p := NOTE_PLAN.match(item):
            plans += 1
            events.append({"kind": "plan", "actor": "dev", "round": plans})
            events.append({"kind": p.group(1).lower(), "actor": "filipe", "note": p.group(2).strip() or None})
        elif f := NOTE_FEEDBACK.match(item):
            events.append({"kind": "feedback", "actor": "filipe", "note": f.group(1).strip()})
        elif lesson := NOTE_LESSON.match(item):
            lessons.append(((lesson.group(1) or "").strip() or None, lesson.group(2).strip()))
        elif r := NOTE_REVIEW.match(item):
            actor = r.group(1).lower()
            rounds[actor] = rounds.get(actor, 0) + 1
            verdict, note = review_verdict(r.group(2), r.group(3).strip() or None)
            events.append({"kind": "review", "actor": actor, "verdict": verdict, "round": rounds[actor], "note": note})
        else:
            unknown.append(item)
    return events, lessons, unknown


# ---------------------------------------------------------------- resolving the current change

def find_current(con, project, info):
    """(open change on this branch, else open change of this T3 thread, or None; current branch)."""
    branch = current_branch(info[2]) if info else None
    thread = os.environ.get("T3CODE_THREAD_ID")
    base = "SELECT * FROM changes WHERE project = ? AND status NOT IN ('merged', 'closed', 'abandoned')"
    row = None
    if branch:
        row = con.execute(base + " AND branch = ? ORDER BY id DESC LIMIT 1", (project["name"], branch)).fetchone()
    if row is None and thread:
        row = con.execute(base + " AND thread = ? ORDER BY id DESC LIMIT 1", (project["name"], thread)).fetchone()
    if row is not None and branch and row["branch"] != branch and row["pr"] is None:
        update_change(con, row["id"], branch=branch)  # the work moved to a new branch before its PR opened
        row = get_change(con, row["id"])
    return row, branch


def resolve_change(con, args):
    """--id, else the open change on this branch, else the open change of this T3 thread."""
    if getattr(args, "id", None):
        row = get_change(con, args.id)
        if not row:
            die(f"no change #{args.id}", 2)
        return row
    project, info = here(con, getattr(args, "project", None))
    row, branch = find_current(con, project, info)
    if row is None:
        die(f"no open change for this checkout of {project['name']}"
            f"{' on ' + branch if branch else ''}: pass --id, or run `change-ledger start` first", 2)
    return row


def change_line(row) -> str:
    parts = [f"#{row['id']}", row["project"]]
    if row["issue"]:
        parts.append(row["issue"])
    text = " ".join(parts) + f' "{short(row["title"], 60)}" · {row["status"]}'
    text += f" · risk {row['exp_risk'] or '-'}/{row['seen_risk'] or '-'} · size {row['exp_size'] or '-'}/{row['seen_size'] or '-'}"
    if row["pr"]:
        text += f" · PR #{row['pr']}"
    return text


# ---------------------------------------------------------------- commands

def validated(value: str | None, allowed: tuple, flag: str) -> str | None:
    if value is None:
        return None
    for option in allowed:
        if value.lower() == option.lower():
            return option
    die(f"{flag} takes {', '.join(allowed)}, not {value!r}", 2)


def cmd_start(args) -> None:
    con = connect()
    project, info = here(con, args.project)
    if not args.no_sync:  # fresh PRs for the brief (one already open for this work is taken over), and the
        sync(con, [project["name"]], limit=30, report=lambda s: None)  # roadmap's rating for the issue
    issue = (norm_issue(args.issue) or args.issue.strip()) if args.issue else None
    branch = current_branch(info[2]) if info else None
    thread = args.thread or os.environ.get("T3CODE_THREAD_ID")
    model = args.model or os.environ.get("ANTHROPIC_MODEL")
    effort = args.effort or os.environ.get("CLAUDE_EFFORT")
    risk, size = validated(args.risk, RISKS, "--risk"), validated(args.size, SIZES, "--size")
    cid = headline = None
    if not args.new:
        rows = con.execute("SELECT * FROM changes WHERE project = ? AND status NOT IN "
                           "('merged', 'closed', 'abandoned') ORDER BY id DESC", (project["name"],)).fetchall()
        for row in rows:
            same_work = (issue and row["issue"] == issue) or (not issue and branch and row["branch"] == branch)
            same_place = ((thread and row["thread"] == thread) or (branch and row["branch"] == branch)
                          or (issue and row["issue"] == issue and not row["thread"]))
            if not (same_work and same_place):
                continue
            if row["source"] != "github":
                cid, headline = row["id"], f"already open (pass --new for a second change): {change_line(row)}"
                break
            # sync found this PR before anyone started it: the agent takes it over
            adopt = {"source": "agent", "thread": thread or row["thread"], "model": model or row["model"],
                     "effort": effort or row["effort"], "exp_risk": row["exp_risk"] or risk,
                     "exp_size": row["exp_size"] or size, "rating_note": args.rating_note or row["rating_note"],
                     "issue": row["issue"] or issue, "kind": row["kind"] or (args.kind.lower() if args.kind else None)}
            update_change(con, row["id"], **adopt)
            add_event(con, row["id"], "start", actor="dev", note="took over a change that sync found first")
            con.commit()
            cid, headline = row["id"], f"adopted: {change_line(get_change(con, row['id']))}"
            break
    if cid is None:
        ts = iso(now_utc())
        cur = con.execute(
            "INSERT INTO changes(project, issue, title, kind, status, exp_risk, exp_size, rating_note, profile, "
            "model, effort, thread, branch, source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'planning', ?, ?, ?, ?, ?, ?, ?, ?, 'agent', ?, ?)",
            (project["name"], issue, args.title, args.kind.lower() if args.kind else None, risk, size,
             args.rating_note, project["profile"], model, effort, thread, branch, ts, ts))
        add_event(con, cur.lastrowid, "start", ts, actor="dev",
                  note=f"expected risk {risk or '-'}, size {size or '-'}" + (f"; {args.rating_note}" if args.rating_note else ""))
        con.commit()
        cid, headline = cur.lastrowid, change_line(get_change(con, cur.lastrowid))
    print(headline)
    notes = notes_file(info[2], cid) if info else None
    if notes:
        if not notes.exists():
            notes.write_text(f"## {NOTES_HEADING}\n\n", encoding="utf-8")
        print(f"PR text: {notes} (one line under \"{NOTES_HEADING}\" for each question, plan answer, "
              "review verdict and feedback round, written when it happens)")
    print(brief_text(con, project["name"]))


def field_updates(con, row, args) -> tuple[dict, list[str], str | None]:
    """The column updates the field flags of `set` and `finish` ask for, the rating changes, and a takeover note."""
    updates = {}
    for flag in ("issue", "title", "summary", "rating_note", "merge_after", "owner_actions", "branch", "model", "effort"):
        value = getattr(args, flag, None)
        if value is not None:
            updates[flag] = value.strip() or None
    if getattr(args, "issue", None):
        updates["issue"] = norm_issue(args.issue) or args.issue.strip()
    if getattr(args, "kind", None):
        updates["kind"] = args.kind.lower()
    took_over = None
    if getattr(args, "pr", None) is not None:
        other = con.execute("SELECT * FROM changes WHERE project = ? AND pr = ? AND id <> ?",
                            (row["project"], args.pr, row["id"])).fetchone()
        if other is not None and other["source"] != "github":
            die(f"PR #{args.pr} already belongs to change #{other['id']}; pass --id {other['id']} to work on it", 2)
        if other is not None:  # sync recorded the PR before this change claimed it: fold that row into this one
            con.execute("UPDATE events SET change_id = ? WHERE change_id = ?", (row["id"], other["id"]))
            con.execute("UPDATE lessons SET change_id = ? WHERE change_id = ?", (row["id"], other["id"]))
            con.execute("DELETE FROM changes WHERE id = ?", (other["id"],))
            for key in (*SYNCED_FIELDS, "status", "conflicted"):
                updates.setdefault(key, other[key])  # a field given in this same call wins
            took_over = f"took over PR #{args.pr} from change #{other['id']}, which sync had recorded"
        updates["pr"] = args.pr
    if getattr(args, "status", None):
        updates["status"] = validated(args.status, STATUSES, "--status")
    rating_changes = []
    for flag, column, allowed in (("risk", "exp_risk", RISKS), ("size", "exp_size", SIZES),
                                  ("seen_risk", "seen_risk", RISKS), ("seen_size", "seen_size", SIZES)):
        value = getattr(args, flag, None)
        if value is None:
            continue
        value = validated(value, allowed, "--" + flag.replace("_", "-"))
        if row[column] != value:
            rating_changes.append(f"{column.replace('_', ' ')} {row[column] or '-'}→{value}")
        updates[column] = value
    return updates, rating_changes, took_over


def apply_updates(con, row, updates: dict, rating_changes: list[str], took_over: str | None, rating_note) -> None:
    if updates:
        update_change(con, row["id"], **updates)
    if took_over:
        add_event(con, row["id"], "note", actor="dev", note=took_over)
    if rating_changes:
        add_event(con, row["id"], "rated", actor="dev",
                  note="; ".join(rating_changes) + (f" ({rating_note})" if rating_note else ""))
    if updates.get("status") == "abandoned":
        add_event(con, row["id"], "note", actor="dev", note="abandoned")


def cmd_set(args) -> None:
    con = connect()
    row = resolve_change(con, args)
    updates, rating_changes, took_over = field_updates(con, row, args)
    if not updates:
        die("nothing to set: pass at least one field (see `change-ledger set --help`)", 2)
    apply_updates(con, row, updates, rating_changes, took_over, args.rating_note)
    con.commit()
    print(change_line(get_change(con, row["id"])))


def event_key(e) -> tuple:
    """What makes two events the same line of the PR text."""
    get = e.__getitem__ if isinstance(e, sqlite3.Row) else e.get
    return tuple(get(k) for k in ("kind", "reason", "actor", "verdict", "round", "note"))


def record_notes(con, row, notes: list[str]) -> None:
    """Bring the events and lessons that came from the PR text in line with its section.

    Only rows marked source = 'pr_text' change: what `log`, `start` and sync wrote stays. A line that was
    already recorded keeps its time and a lesson keeps its number; an emptied section changes nothing.
    """
    events, lessons, unknown = parse_notes(notes)
    for item in unknown:
        hint = f"; a reviewer verdict is one of {', '.join(REVIEW_VERDICTS)}" if NOTE_REVIEWER.match(item) else ""
        warn(f"not a known line under \"{NOTES_HEADING}\" (formats in issue-cycle{hint}): {short(item, 90)}")
    old = con.execute("SELECT * FROM events WHERE change_id = ? AND source = 'pr_text'", (row["id"],)).fetchall()
    if not events and not lessons:
        kept_lessons = con.execute("SELECT COUNT(*) FROM lessons WHERE change_id = ? AND source = 'pr_text'",
                                   (row["id"],)).fetchone()[0]
        if old or kept_lessons:
            warn(f"\"{NOTES_HEADING}\" lists nothing now: kept the {plural(len(old), 'event')} and "
                 f"{plural(kept_lessons, 'lesson')} recorded before")
        return
    stamps: dict[tuple, list[str]] = {}
    for e in old:
        stamps.setdefault(event_key(e), []).append(e["ts"])
    now = iso(now_utc())
    con.execute("DELETE FROM events WHERE change_id = ? AND source = 'pr_text'", (row["id"],))
    for event in events:
        kept = stamps.get(event_key(event))
        ts = kept.pop(0) if kept else now
        kind = event.pop("kind")
        add_event(con, row["id"], kind, ts=ts, source="pr_text", **event)
    listed = set()
    for target, text in lessons:
        listed.add(text)
        if not con.execute("SELECT 1 FROM lessons WHERE change_id = ? AND text = ?", (row["id"], text)).fetchone():
            con.execute("INSERT INTO lessons(project, change_id, ts, text, target, updated_at, source) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'pr_text')", (row["project"], row["id"], now, text, target, now))
        else:  # the same lesson, maybe pointed at another file
            con.execute("UPDATE lessons SET target = ?, updated_at = ? WHERE change_id = ? AND text = ? "
                        "AND source = 'pr_text' AND COALESCE(target, '') <> COALESCE(?, '')",
                        (target, now, row["id"], text, target))
    for lesson in con.execute("SELECT id, text FROM lessons WHERE change_id = ? AND source = 'pr_text' "
                              "AND state = 'open'", (row["id"],)).fetchall():
        if lesson["text"] not in listed:  # its line was removed or reworded
            con.execute("DELETE FROM lessons WHERE id = ?", (lesson["id"],))


def cmd_finish(args) -> None:
    """Record what the work went through, from the PR text, then show the PR's CI and conflicts."""
    con = connect()
    row = resolve_change(con, args)
    path = Path(args.body).expanduser() if args.body else notes_file(Path.cwd(), row["id"])
    if args.body and not path.is_file():
        die(f"{path}: no such file", 2)
    text = origin = None
    if path and path.is_file():
        text, origin = path.read_text(encoding="utf-8", errors="replace"), str(path)
    elif row["pr"]:  # the file went with its worktree, or finish runs in another checkout: read the PR itself
        repo = con.execute("SELECT repo FROM projects WHERE name = ?", (row["project"],)).fetchone()["repo"]
        try:
            text, origin = gh(["api", f"repos/{repo}/pulls/{row['pr']}", "--jq", ".body"]), f"PR #{row['pr']} on GitHub"
        except GhError as err:
            warn(f"PR #{row['pr']}: {err}")
    notes = md_section(text, NOTES_HEADING) if text else None
    updates, rating_changes, took_over = field_updates(con, row, args)
    if "summary" not in updates and not row["summary"] and text:
        summary = first_paragraph(md_section(text, "Summary") or [])
        if summary:
            updates["summary"] = summary
    apply_updates(con, row, updates, rating_changes, took_over, args.rating_note)
    if notes is not None:
        record_notes(con, row, notes)
    elif text:
        warn(f"{origin} has no \"{NOTES_HEADING}\" section: no questions, plan rounds or reviews recorded")
    elif not row["pr"]:  # with a PR, the failed read of its description was reported above
        warn(f"no PR text: no file at {path or '(not a git checkout)'} and no PR on record yet; pass --body <file>")
    con.commit()
    if not args.no_sync:
        sync(con, [row["project"]], limit=30, roadmaps=False, report=lambda s: None)
    r = dict(con.execute("SELECT * FROM v_changes WHERE id = ?", (row["id"],)).fetchone())
    if notes is not None and not r["plan_rounds"] and r["risk_expected"] and r["size_expected"] \
            and (r["risk_expected"], r["size_expected"]) != ("Lo", "Sm"):
        warn(f"rated {r['risk_expected']}/{r['size_expected']}, so the plan went to Filipe: add its "
             f"\"- plan approved: …\" line under \"{NOTES_HEADING}\" and run finish again")
    reasons = ", ".join(f"{k} {r['asks_' + k]}" for k in ASK_REASONS if r["asks_" + k])
    print(change_line(get_change(con, row["id"])))
    print(f"recorded: {plural(r['asks'], 'question')}" + (f" ({reasons})" if reasons else "")
          + f", {plural(r['plan_rounds'], 'plan round')}, {plural(r['review_rounds'], 'review')}"
          f" ({r['review_blocks']} blocking), {plural(r['feedback_rounds'], 'feedback round')}")
    if r["pr"]:
        print("  " + pr_line(r))
    else:
        print(f"  no PR on GitHub for branch {r['branch'] or '(none)'} yet: open it, then run finish again")


def cmd_log(args) -> None:
    kind = args.kind
    if kind == "ask" and args.reason not in ASK_REASONS:
        die("ask needs --reason " + "|".join(ASK_REASONS), 2)
    if kind == "review" and not (args.actor and args.verdict):
        die("review needs --actor <reviewer> and --verdict <verdict>", 2)
    if kind == "checks" and (args.verdict or "").lower() not in ("pass", "fail"):
        die("checks needs --verdict pass or fail", 2)
    if kind in ("ask", "feedback", "rejected") and not args.note:
        die(f"{kind} needs a note: what was asked or requested", 2)
    con = connect()
    row = resolve_change(con, args)
    verdict = args.verdict.upper() if args.verdict else None
    note = args.note
    if kind == "checks":
        verdict = verdict.lower()
    elif kind == "review":
        verdict, note = review_verdict(verdict, note)
    round_no = None
    if kind == "plan":
        round_no = con.execute("SELECT COUNT(*) FROM events WHERE change_id = ? AND kind = 'plan'",
                               (row["id"],)).fetchone()[0] + 1
    elif kind == "review":
        round_no = con.execute("SELECT COUNT(*) FROM events WHERE change_id = ? AND kind = 'review' AND actor = ?",
                               (row["id"], args.actor)).fetchone()[0] + 1
    actor = args.actor or ("filipe" if kind in ("approved", "rejected", "answer", "feedback") else "dev")
    add_event(con, row["id"], kind, reason=args.reason if kind == "ask" else None, actor=actor,
              verdict=verdict, round=round_no, note=note)
    if kind in STATUS_AFTER and row["status"] in ("planning", "awaiting_approval", "in_progress"):
        update_change(con, row["id"], status=STATUS_AFTER[kind])
    con.commit()
    row = get_change(con, row["id"])
    extra = f" ({args.reason})" if kind == "ask" else f" round {round_no}" if round_no else ""
    waiting = len([a for a in open_asks(con, row["project"]) if a["change_id"] == row["id"]])
    print(f"#{row['id']} {kind}{extra} logged · status {row['status']}"
          + (f" · {waiting} open question{'s' if waiting != 1 else ''}" if waiting else ""))


def cmd_lesson(args) -> None:
    con = connect()
    ts = iso(now_utc())
    if args.applied or args.drop:
        lid = args.applied or args.drop
        if not con.execute("SELECT 1 FROM lessons WHERE id = ?", (lid,)).fetchone():
            die(f"no lesson L{lid}", 2)
        state = "applied" if args.applied else "dropped"
        con.execute("UPDATE lessons SET state = ?, applied_in = COALESCE(?, applied_in), updated_at = ? WHERE id = ?",
                    (state, args.where, ts, lid))
        con.commit()
        print(f"L{lid} {state}" + (f" in {args.where}" if args.where else ""))
        return
    if args.list or not args.text:
        query, params = "SELECT * FROM lessons WHERE 1 = 1", []
        if args.project:
            query += " AND project = ?"
            params.append(args.project)
        if not args.all:
            query += " AND state = 'open'"
        rows = con.execute(query + " ORDER BY id DESC", params).fetchall()
        if not rows:
            print("no lessons" + ("" if args.all else " open"))
            return
        print(md_table(["Lesson", "Project", "Change", "Target", "State", "Text"],
                       [[f"L{r['id']}", r["project"], f"#{r['change_id']}" if r["change_id"] else "-",
                         r["target"] or "-", r["state"] + (f" ({r['applied_in']})" if r["applied_in"] else ""),
                         r["text"]] for r in rows]))
        return
    if args.id:
        change = get_change(con, args.id) or die(f"no change #{args.id}", 2)
        project = change["project"]
    else:
        proj, info = here(con, args.project)
        project = proj["name"]
        change, _ = find_current(con, proj, info)  # None: the lesson belongs to the project alone
    cur = con.execute("INSERT INTO lessons(project, change_id, ts, text, target, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (project, change["id"] if change else None, ts, args.text.strip(), args.target, ts))
    con.commit()
    print(f"L{cur.lastrowid} open · {project}" + (f" #{change['id']}" if change else "")
          + (f" · target {args.target}" if args.target else ""))


def cmd_sync(args) -> None:
    con = connect()
    names = [args.project] if args.project else None
    if not sync(con, names, limit=args.limit, roadmaps=not args.no_roadmaps,
                report=(lambda s: None) if args.quiet else print):
        raise SystemExit(1)


def pr_line(row: dict) -> str:
    bits = [f"PR #{row['pr']}" + (f" {row['issue']}" if row["issue"] else ""), short(row["title"], 60),
            f"open {fmt_age(row['opened_at'])}"]
    if row["ci"] and row["ci"] != "none":
        bits.append(f"CI {row['ci']}")
    if row["mergeable"] == "CONFLICTING":
        bits.append("CONFLICTS with base")
    if hours_since(row["opened_at"]) > STALE_HOURS:
        bits.append("stale")
    if row["merge_after"]:
        bits.append(f"merge after {row['merge_after']}")
    if row["owner_actions"]:
        bits.append(f"at merge: {' '.join(row['owner_actions'].split())}")  # in full: it is Filipe's to-do
    paths = hot_paths(row["paths"])
    if paths:
        bits.append("edits " + ", ".join(paths))
    return " · ".join(bits)


def brief_text(con, name: str) -> str:
    """Start-of-work context: open PRs and the files they edit, work in progress, open lessons, recent rates."""
    project = con.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    rows = load_rows(con, project=name)
    out = [f"{name} · profile {project['profile'] or 'unset (AGENTS.md has no Agent workflow block)'}"
           f" · synced {fmt_age(project['synced_at']) + ' ago' if project['synced_at'] else 'never'}"]
    open_prs = [r for r in rows if r["status"] == "pr_open"]
    if open_prs:
        out.append("Open PRs:")
        out += ["  " + pr_line(r) for r in open_prs]
    else:
        out.append("Open PRs: none")
    active = [r for r in rows if r["status"] in ("planning", "awaiting_approval", "in_progress")]
    if active:
        out.append("In progress:")
        for r in active[:6]:
            line = f"  #{r['id']}{' ' + r['issue'] if r['issue'] else ''} {short(r['title'], 50)}"
            if r["pr"]:  # a synced PR in progress is a draft; its files can conflict like an open PR's
                line += f" · draft PR #{r['pr']}" if r["pr_url"] else f" · PR #{r['pr']}, not synced yet"
                paths = hot_paths(r["paths"])
                line += f" · edits {', '.join(paths)}" if paths else ""
            else:
                line += f" ({r['branch']})" if r["branch"] else ""
                if hours_since(r["updated_at"]) > IDLE_HOURS:  # a thread that stopped before its PR
                    line += f" · idle {fmt_age(r['updated_at'])}"
            out.append(line)
    lessons = con.execute("SELECT * FROM lessons WHERE project = ? AND state = 'open' ORDER BY id DESC",
                          (name,)).fetchall()
    if lessons:
        out.append("Open lessons (check the plan against them):")
        out += [f"  L{lesson['id']} [{lesson['target'] or 'no target'}] {short(lesson['text'], 120)}"
                for lesson in lessons[:4]]
        if len(lessons) > 4:
            out.append(f"  … {len(lessons) - 4} more: change-ledger lesson --list --project {name}")
    recent = summarize(load_rows(con, project=name, since=iso(now_utc() - timedelta(days=30))), [])
    out.append(f"Last 30 days: {recent['merged']} merged, {recent['clean']} clean"
               f" · {fmt_num(recent['asks_per_change'])} questions per change")
    return "\n".join(out)


def cmd_brief(args) -> None:
    con = connect()
    project, _ = here(con, args.project)
    if not args.no_sync:
        sync(con, [project["name"]], limit=30, roadmaps=False, report=lambda s: None)
    print(brief_text(con, project["name"]))


LIST_HEADERS = ["Change", "Project", "Issue", "Title", "Outcome", "Expected/Seen Risk", "Expected/Seen Size",
                "Code lines", "PR", "CI", "Questions", "Rework commits", "Opened", "To merge"]


def list_row(r: dict) -> list:
    return [f"#{r['id']}", r["project"], r["issue"] or "-", short(r["title"], 50), r["outcome"],
            r["risk"], r["size"], r["code_lines"] if r["code_lines"] is not None else "-",
            f"#{r['pr']}" if r["pr"] else "-", r["ci"] or "-", r["asks"],
            r["commits_after_open"] if r["commits_after_open"] is not None else "-",
            fmt_local(r["opened_at"] or r["created_at"])[:10], fmt_hours(r["hours_to_merge"])]


def cmd_list(args) -> None:
    con = connect()
    if args.sync:
        sync(con, [args.project] if args.project else None, report=lambda s: None)
    rows = load_rows(con, args.project, parse_since(args.since))
    if args.status:
        rows = [r for r in rows if r["status"] == args.status or r["outcome"] == args.status]
    if not args.bots:
        rows = [r for r in rows if not r["bot"]]
    rows = rows[: args.limit]
    if not rows:
        print("no changes match")
        return
    print(md_table(LIST_HEADERS, [list_row(r) for r in rows]))


def cmd_show(args) -> None:
    con = connect()
    row = con.execute("SELECT * FROM v_changes WHERE id = ?", (args.change,)).fetchone()
    if not row:
        die(f"no change #{args.change}", 2)
    r = dict(row)
    fields = [
        ("Project", r["project"]), ("Issue", r["issue"] + (f" ({r['issue_title']})" if r["issue_title"] else "") if r["issue"] else "-"),
        ("Title", r["title"]), ("Kind", r["kind"]), ("Summary", r["summary"]),
        ("Status", f"{r['status']} ({r['outcome']})"),
        ("Expected/Seen Risk", r["risk"] + (f" (from {r['rating_from']})" if r["rating_from"] else "")),
        ("Expected/Seen Size", r["size"] + (f", measured {r['measured_size']}" if r["measured_size"] else "")),
        ("Rating note", r["rating_note"]),
        ("Lines added", f"code {r['code_lines']}, docs {r['doc_lines']} (+{r['additions']}/-{r['deletions']} in {r['files']} files)"
         if r["additions"] is not None else None),
        ("PR", f"#{r['pr']} {r['pr_url']}" if r["pr"] else None), ("Branch", r["branch"]),
        ("CI", r["ci"]),
        ("Mergeable", (r["mergeable"] or "?") + (" (conflicted before)" if r["conflicted"] else "")
         if r["status"] == "pr_open" else "had conflicts" if r["conflicted"] else None),
        ("Rework", f"{plural(r['commits_after_open'], 'commit')} after the PR opened, "
                   f"{plural(r['feedback_rounds'], 'feedback round')}" if r["commits_after_open"] is not None else None),
        ("Questions", f"{r['asks']} (decision {r['asks_decision']}, context {r['asks_context']}, access {r['asks_access']}, "
                      f"correction {r['asks_correction']}, blocked {r['asks_blocked']})"),
        ("Plan", f"{plural(r['plan_rounds'], 'round')}, {r['plan_rejections']} rejected"),
        ("Reviews", f"{plural(r['review_rounds'], 'round')}, {r['review_blocks']} blocking"),
        ("Merge after", r["merge_after"]), ("At merge", r["owner_actions"]),
        ("Dev", " · ".join(x for x in (r["model"], r["effort"] and f"effort {r['effort']}", r["thread"] and f"thread {r['thread']}") if x) or None),
        ("Opened", fmt_local(r["opened_at"])), ("Merged", fmt_local(r["merged_at"])),
        ("Time to merge", fmt_hours(r["hours_to_merge"])),
    ]
    print(md_table([f"Change #{r['id']}", "Detail"], [[k, v] for k, v in fields if v not in (None, "", "-") or k in ("Summary",)]))
    events = con.execute("SELECT * FROM events WHERE change_id = ? ORDER BY ts, id", (r["id"],)).fetchall()
    if events:
        print()
        print(md_table(["When", "Event", "Who", "Detail"],
                       [[fmt_local(e["ts"]), e["kind"] + (f" ({e['reason']})" if e["reason"] else "")
                         + (f" r{e['round']}" if e["round"] else ""), e["actor"] or "-",
                         " ".join(x for x in (e["verdict"], e["note"]) if x)] for e in events]))
    lessons = con.execute("SELECT * FROM lessons WHERE change_id = ?", (r["id"],)).fetchall()
    if lessons:
        print()
        print(md_table(["Lesson", "Target", "State", "Text"],
                       [[f"L{x['id']}", x["target"] or "-", x["state"], x["text"]] for x in lessons]))


def cmd_stats(args) -> None:
    con = connect()
    if args.sync:
        sync(con, [args.project] if args.project else None, report=lambda s: None)
    since = parse_since(args.since)
    projects = [args.project] if args.project else [p["name"] for p in con.execute(
        "SELECT DISTINCT project AS name FROM changes ORDER BY project")]
    table = []
    for name in projects + ([None] if len(projects) > 1 else []):
        s = summarize(load_rows(con, name, since), load_issues(con, name))
        if name and not s["changes"] and not s["open_prs"]:
            continue
        profile = con.execute("SELECT profile FROM projects WHERE name = ?", (name,)).fetchone() if name else None
        table.append([name or "**All**", (profile[0] if profile else None) or "-", s["changes"], s["merged"],
                      fmt_rate(s["merge_rate"]), fmt_rate(s["clean_rate"]), fmt_hours(s["median_hours"]),
                      fmt_num(s["rework_commits"]), s["asks"], fmt_num(s["asks_per_change"]),
                      s["open_prs"], s["stale"], s["ci_red"], s["ever_conflicted"]])
    scope = f"since {fmt_local(since)[:10]}" if since else "all time"
    print(f"## Change ledger · {args.project or 'all projects'} · {scope}\n")
    print(md_table(["Project", "Profile", "Changes", "Merged", "Merge rate", "Clean merges", "Median to merge",
                    "Rework commits per PR", "Questions", "Questions per change", "Open PRs", "Stale",
                    "CI red", "Ever conflicted"], table))
    total = summarize(load_rows(con, args.project, since), load_issues(con, args.project))
    print("\n### Questions to Filipe, by reason\n")
    reasons = sorted(total["asks_by_reason"].items(), key=lambda kv: -kv[1])
    print(md_table(["Reason", "Questions", "Share", "Meaning"],
                   [[k, v, pct(v, total["asks"]), ASK_REASONS[k]] for k, v in reasons]))
    print("\n### Estimates against the roadmaps (issues with both halves)\n")
    est = [["Size", total["size_est"]], ["Risk", total["risk_est"]]]
    print(md_table(["Rating", "Issues", "Right", "Under-estimated", "Over-estimated"],
                   [[k, e["total"], f"{e['right']} ({pct(e['right'], e['total'])})", e["under"], e["over"]]
                    for k, e in est]))
    print("\n### Clean merges by measured size (code lines)\n")
    print(md_table(["Measured size", "Merged", "Clean", "Clean rate"],
                   [[k, n, c, pct(c, n)] for k, (n, c) in total["clean_by_size"].items()]))
    gaps = []
    if total["no_summary"]:
        gaps.append(f"{total['no_summary']} agent changes with a PR but no summary (`change-ledger finish` was not run)")
    if total["no_seen"]:
        gaps.append(f"{total['no_seen']} merged agent changes without the seen half of both ratings")
    if gaps:
        print("\n### Data gaps\n")
        print("\n".join(f"- {g}" for g in gaps))
    print("\nClean merge: merged with no commit after the PR opened and no feedback round. "
          "Dependabot PRs are left out of the rates. Questions are counted on changes agents started.")


EXPORT_COLUMNS = ["id", "project", "issue", "issue_title", "title", "kind", "summary", "status", "outcome",
                  "risk", "size", "risk_expected", "risk_seen", "size_expected", "size_seen", "rating_from",
                  "rating_note", "measured_size", "code_lines", "doc_lines", "additions", "deletions", "files",
                  "pr", "pr_url", "branch", "author", "ci", "ci_failures", "mergeable", "conflicted",
                  "commits", "commits_after_open", "asks", "asks_decision", "asks_context", "asks_access",
                  "asks_correction", "asks_blocked", "plan_rounds", "plan_rejections", "review_rounds",
                  "review_blocks", "feedback_rounds", "merge_after", "owner_actions", "profile", "model",
                  "effort", "thread", "source", "bot", "created_at", "opened_at", "merged_at", "closed_at",
                  "hours_to_merge"]


def write_export(con, rows: list[dict], args, out) -> None:
    if args.format == "csv":
        writer = csv.writer(out)
        writer.writerow(EXPORT_COLUMNS)
        for r in rows:
            writer.writerow([r[c] for c in EXPORT_COLUMNS])
        return
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids)) or "NULL"
    data = {
        "changes": [{c: r[c] for c in EXPORT_COLUMNS} for r in rows],
        "events": [dict(e) for e in con.execute(f"SELECT * FROM events WHERE change_id IN ({marks}) ORDER BY id", ids)],
        "lessons": [dict(x) for x in con.execute("SELECT * FROM lessons ORDER BY id")],
        "issues": load_issues(con, args.project),
    }
    json.dump(data, out, indent=2, ensure_ascii=False)
    out.write("\n")


def cmd_export(args) -> None:
    con = connect()
    rows = load_rows(con, args.project, parse_since(args.since))
    if not args.out:
        write_export(con, rows, args, sys.stdout)
        return
    with open(args.out, "w", encoding="utf-8", newline="") as out:
        write_export(con, rows, args, out)
    print(f"wrote {len(rows)} changes to {args.out}")


REPORT_COLUMNS = ["id", "project", "issue", "issue_title", "title", "kind", "summary", "status", "outcome",
                  "risk", "size", "risk_expected", "risk_seen", "size_expected", "size_seen", "rating_from",
                  "measured_size", "code_lines", "doc_lines", "pr", "pr_url", "ci", "mergeable", "conflicted",
                  "commits_after_open", "asks", "asks_decision", "asks_context", "asks_access", "asks_correction",
                  "asks_blocked", "plan_rounds", "plan_rejections", "review_rounds", "review_blocks",
                  "feedback_rounds", "merge_after", "owner_actions", "branch", "bot", "source", "model", "effort",
                  "created_at", "opened_at", "merged_at", "hours_to_merge"]


def report_data(con) -> dict:
    asks = [{"change_id": e["change_id"], "project": e["project"], "issue": e["issue"], "title": e["title"],
             "ts": e["ts"], "reason": e["reason"], "note": e["note"]}
            for e in con.execute("SELECT e.*, c.project, c.issue, c.title FROM events e "
                                 "JOIN changes c ON c.id = e.change_id WHERE e.kind = 'ask' ORDER BY e.ts DESC, e.id")]
    return {
        "generated": iso(now_utc()),
        "db": str(db_path()),
        "stale_hours": STALE_HOURS,
        "reasons": ASK_REASONS,
        "projects": [dict(p) for p in con.execute("SELECT name, repo, profile, roadmap, synced_at FROM projects ORDER BY name")],
        "changes": [{c: r[c] for c in REPORT_COLUMNS} for r in load_rows(con)],
        "asks": asks,
        "lessons": [dict(x) for x in con.execute("SELECT * FROM lessons ORDER BY id DESC")],
        "issues": load_issues(con),
    }


def cmd_report(args) -> None:
    con = connect()
    if args.sync:
        sync(con, report=lambda s: None)
    template = Path(__file__).resolve().with_name("report.html").read_text(encoding="utf-8")
    payload = json.dumps(report_data(con), ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    if "/*__LEDGER_DATA__*/" not in template:
        die("report.html has no /*__LEDGER_DATA__*/ placeholder", 1)
    out = Path(args.out).expanduser() if args.out else db_path().with_name("report.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.replace("/*__LEDGER_DATA__*/", payload), encoding="utf-8")
    print(f"wrote {out}")
    distro = os.environ.get("WSL_DISTRO_NAME")
    full = str(out.resolve())
    drive = re.match(r"^/mnt/([a-z])(/.*)?$", full)
    if drive:
        print(f"open from Windows: {drive.group(1).upper()}:" + (drive.group(2) or "/").replace("/", "\\"))
    elif distro and full.startswith("/"):
        print("open from Windows: \\\\wsl.localhost\\" + distro + full.replace("/", "\\"))


# ---------------------------------------------------------------- argument parsing

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="change-ledger",
        description="Local database of changes per project: summaries, Expected/Seen Risk and Size, "
                    "and what each change cost (questions, plan and review rounds, rework, CI, conflicts).",
        epilog="The current change is found from --id, else the open change on this git branch, "
               "else the open change of this T3 thread (T3CODE_THREAD_ID). Data: " + str(db_path()))
    parser.add_argument("--db", help="database file (default: $CHANGE_LEDGER_DB or ~/.local/share/change-ledger/ledger.db)")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name: str, func, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

    p = add("start", cmd_start, "record a new change in the current repo; prints its PR text file and the brief")
    p.add_argument("--title", required=True, help="what the change does, or the issue title")
    p.add_argument("--issue", help="roadmap issue ID, e.g. P1-03")
    p.add_argument("--kind", help="feat, fix, docs, chore, refactor, test, ci, content...")
    p.add_argument("--risk", help="expected risk: Lo, Med or Hi")
    p.add_argument("--size", help="expected size: Sm, Md or Lg")
    p.add_argument("--rating-note", help="one line of reasoning for the rating")
    p.add_argument("--model", help="the dev's model id, e.g. claude-opus-5-5")
    p.add_argument("--effort", help="the dev's effort (default: $CLAUDE_EFFORT)")
    p.add_argument("--thread", help="T3 thread id (default: $T3CODE_THREAD_ID)")
    p.add_argument("--project", help="project name, when not running inside its checkout")
    p.add_argument("--new", action="store_true", help="start a second change even if one is open for this work")
    p.add_argument("--no-sync", action="store_true", help="do not refresh this project's PRs first")

    p = add("finish", cmd_finish, "when the PR opens (and after each feedback round): record the PR text's "
            "questions, plan answers, reviews and feedback, the summary and the seen rating; show CI and conflicts")
    p.add_argument("--body", help="the PR text file (default: the one `start` created for this change)")
    p.add_argument("--summary", help="one or two sentences (default: the first paragraph of the PR text's Summary)")
    p.add_argument("--risk", help="expected risk, when the roadmap has none or the plan raised it")
    p.add_argument("--size", help="expected size, when the roadmap has none or the plan raised it")
    p.add_argument("--seen-risk", help="seen risk")
    p.add_argument("--seen-size", help="seen size")
    p.add_argument("--rating-note", help="why a rating was set or changed")
    p.add_argument("--merge-after", help="PRs that must merge first, e.g. agent-config#7")
    p.add_argument("--owner-actions", help="what Filipe does at merge: run install.sh, a migration, a setting")
    p.add_argument("--id", type=int, help="change id (default: the current change)")
    p.add_argument("--project")
    p.add_argument("--no-sync", action="store_true", help="do not read the PR from GitHub")

    p = add("set", cmd_set, "correct fields of the current change")
    p.add_argument("--id", type=int, help="change id (default: the current change)")
    p.add_argument("--project")
    p.add_argument("--summary", help="one or two sentences: what changed and why")
    p.add_argument("--risk", help="expected risk")
    p.add_argument("--size", help="expected size")
    p.add_argument("--seen-risk", help="seen risk, when the work is done")
    p.add_argument("--seen-size", help="seen size, when the work is done")
    p.add_argument("--rating-note", help="why a rating was set or changed")
    p.add_argument("--merge-after", help="PRs that must merge first, e.g. agent-config#7")
    p.add_argument("--owner-actions", help="what Filipe does before or after the merge")
    p.add_argument("--issue")
    p.add_argument("--title")
    p.add_argument("--kind")
    p.add_argument("--status", help="usually set for you; 'abandoned' drops a change")
    p.add_argument("--branch")
    p.add_argument("--pr", type=int)
    p.add_argument("--model")
    p.add_argument("--effort")

    p = add("log", cmd_log, "append one event to the current change, for corrections (finish records the usual ones)")
    p.add_argument("kind", choices=list(LOG_KINDS), help="; ".join(f"{k}: {v}" for k, v in LOG_KINDS.items()))
    p.add_argument("note", nargs="?", help="what happened, in one line")
    p.add_argument("--reason", choices=list(ASK_REASONS), help="for ask: " + "; ".join(f"{k}: {v}" for k, v in ASK_REASONS.items()))
    p.add_argument("--actor", help="for review: the reviewer (code-reviewer, po-reviewer...)")
    p.add_argument("--verdict", help="for review: PASS, BLOCK, APPROVED, CHANGES NEEDED, NEEDS FILIPE or NEEDS INPUT; for checks: pass or fail")
    p.add_argument("--id", type=int)
    p.add_argument("--project")

    p = add("lesson", cmd_lesson, "record what would have prevented a question or rework; list or close lessons")
    p.add_argument("text", nargs="?", help="the lesson, in one line")
    p.add_argument("--target", help="where the fix belongs: AGENTS.md, workflow.md, the issue text, a test, CI...")
    p.add_argument("--id", type=int, help="attach to this change (default: the current change, if any)")
    p.add_argument("--project")
    p.add_argument("--list", action="store_true", help="list open lessons")
    p.add_argument("--all", action="store_true", help="with --list: include applied and dropped ones")
    p.add_argument("--applied", type=int, metavar="N", help="mark lesson N applied")
    p.add_argument("--drop", type=int, metavar="N", help="mark lesson N dropped")
    p.add_argument("--in", dest="where", help="with --applied: the PR or commit that applied it")

    p = add("sync", cmd_sync, "read PRs (state, size, CI, conflicts, merge) and roadmap ratings from GitHub")
    p.add_argument("--project", help="one project (default: every known clone)")
    p.add_argument("--limit", type=int, default=100, help="most recent PRs per repo (default 100)")
    p.add_argument("--no-roadmaps", action="store_true", help="skip the roadmap mirror")
    p.add_argument("--quiet", action="store_true")

    p = add("brief", cmd_brief, "what `start` prints: open PRs with CI, conflicts and edited files, work in progress, open lessons")
    p.add_argument("--project")
    p.add_argument("--no-sync", action="store_true", help="do not refresh this project's PRs first")

    p = add("list", cmd_list, "table of recent changes")
    p.add_argument("--project")
    p.add_argument("--status", help="a status or an outcome: open, clean, rework, dropped, in_progress...")
    p.add_argument("--since", help="30d, 12h or a date")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--bots", action="store_true", help="include Dependabot PRs")
    p.add_argument("--sync", action="store_true", help="sync first")

    p = add("show", cmd_show, "one change with its events and lessons")
    p.add_argument("change", type=int, help="change id")

    p = add("stats", cmd_stats, "merge rates, rework, questions by reason, estimate accuracy")
    p.add_argument("--project")
    p.add_argument("--since", help="30d, 12h or a date")
    p.add_argument("--sync", action="store_true", help="sync first")

    p = add("report", cmd_report, "write a self-contained HTML dashboard (no network)")
    p.add_argument("--out", help="output file (default: report.html next to the database)")
    p.add_argument("--sync", action="store_true", help="sync every project first")

    p = add("export", cmd_export, "changes as CSV, or everything as JSON")
    p.add_argument("--format", choices=("csv", "json"), default="csv")
    p.add_argument("--project")
    p.add_argument("--since")
    p.add_argument("--out", help="file to write (default: stdout)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    # Python 3.10 and 3.11 leave the text of `log ask --reason context "text"` unparsed when it follows
    # an option (3.12 and later fill it in): take one leftover word as that text.
    text_arg = {cmd_log: "note", cmd_lesson: "text"}.get(getattr(args, "func", None))
    if text_arg and len(extra) == 1 and not extra[0].startswith("-") and getattr(args, text_arg) is None:
        setattr(args, text_arg, extra.pop())
    if extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    if args.db:
        os.environ["CHANGE_LEDGER_DB"] = args.db
    try:
        args.func(args)
    except GhError as err:
        die(str(err))
    except sqlite3.DatabaseError as err:  # locked, constraint, corrupt file: a message, not a traceback
        die(f"database error: {err}")
    finally:
        while _CONNECTIONS:
            _CONNECTIONS.pop().close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
