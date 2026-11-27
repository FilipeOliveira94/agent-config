"""Tests for change_ledger.py. No network: `gh` is replaced by a fake.

Run from the repo root: python3 -m unittest discover -s tools/change-ledger -v
"""
import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest import mock

import change_ledger as cl

ROADMAP = """# Roadmap

| ID | Title | Depends on | Expected/Seen Risk | Expected/Seen Size | Status | Acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| P1-03 | Account signup | — | Med/Hi | Md/Md | Delivered | Users sign up |
| P1-04 | Password reset | P1-03 | Lo/- | Sm/- | Not started | Reset by email |
| ADR-001 | Not an issue | — | Lo/- | Sm/- | — | — |

## Phase 7

### 7.2 Dependency updates

| Issue 7.2 | Detail |
| --- | --- |
| Status | `verified` |
| Expected/Seen Risk | Med/Med |
| Expected/Seen Size | Sm/Lg |
"""

AGENTS = "## Agent workflow\n\n- **Profile:** reviewed\n- **Language:** English\n"


def ts(delta_hours: float) -> str:
    return cl.iso(cl.now_utc() + timedelta(hours=delta_hours))


def node(number, title, branch, state="OPEN", created=-3.0, merged=None, commits=(-3.1,), checks=(),
         mergeable="MERGEABLE", files=(("src/app.py", 120, 10), ("README.md", 30, 0)), bot=False,
         draft=False, first_event=None, last_ready=None, more_files=False, base="main", oid=None,
         head=None):
    """A pull request as the GraphQL query returns it. Times are hours from now. first_event is the
    first draft event on its timeline, e.g. ("ReadyForReviewEvent", -2); last_ready is when it was last
    marked ready; more_files says GitHub has a second page of files (FakeGh.more_files)."""
    events = [{"__typename": first_event[0], "createdAt": ts(first_event[1])}] if first_event else []
    ready = [{"__typename": "ReadyForReviewEvent", "createdAt": ts(last_ready)}] if last_ready is not None else []
    return {
        "number": number, "title": title, "url": f"https://github.com/acme/demo/pull/{number}",
        "state": state, "isDraft": draft, "createdAt": ts(created),
        "mergedAt": ts(merged) if merged is not None else None,
        "closedAt": ts(merged) if merged is not None else None,
        "headRefName": branch, "baseRefName": base, "mergeCommit": {"oid": oid} if oid else None,
        "headRefOid": head,
        "additions": sum(f[1] for f in files), "deletions": sum(f[2] for f in files),
        "changedFiles": len(files), "mergeable": mergeable,
        "author": {"__typename": "Bot" if bot else "User", "login": "dependabot" if bot else "acme"},
        "comments": {"totalCount": 1}, "reviews": {"totalCount": 0},
        "files": {"pageInfo": {"hasNextPage": more_files, "endCursor": "files-2" if more_files else None},
                  "nodes": [{"path": p, "additions": a, "deletions": d} for p, a, d in files]},
        "commits": {"totalCount": len(commits), "nodes": [{"commit": {"authoredDate": ts(c)}} for c in commits]},
        "draftEvents": {"nodes": events},
        "lastReady": {"nodes": ready},
        "last": {"nodes": [{"commit": {"statusCheckRollup": {"contexts": {"nodes": list(checks)}} if checks else None}}]},
    }


def check(name, conclusion, status="COMPLETED"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


class FakeGh:
    """Answers the three GraphQL queries from `prs` (newest first) and file GETs from `files`."""

    def __init__(self):
        self.prs = []
        self.more_files = {}  # PR number -> the files on its second page
        self.bodies = {}  # PR number -> its description on GitHub
        self.files = {"ROADMAP.md": ROADMAP, "AGENTS.md": AGENTS}
        self.on_main = set()  # merge commits that are ancestors of main
        self.calls = []

    def __call__(self, args, timeout=120, retries=1):
        self.calls.append(args)
        if args[:2] == ["api", "graphql"]:
            fields = dict(a.split("=", 1) for a in args[3::2])  # -f/-F key=value pairs
            query = fields["query"]
            if "pullRequests(" in query:  # a page of the newest PRs
                start, size = int(fields.get("after", 0)), int(fields["first"])
                return json.dumps({"data": {"repository": {"pullRequests": {
                    "pageInfo": {"hasNextPage": start + size < len(self.prs), "endCursor": str(start + size)},
                    "nodes": self.prs[start:start + size]}}}})
            if "files(first: 100, after:" in query:  # the next page of one PR's files
                return json.dumps({"data": {"repository": {"pullRequest": {"files": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": self.more_files[int(fields["number"])]}}}}})
            by_number = {pr["number"]: pr for pr in self.prs}  # PRs asked for by number
            wanted = [int(n) for n in re.findall(r"p(\d+): pullRequest\(number: \d+\)", query)]
            body = {"data": {"repository": {f"p{n}": by_number.get(n) for n in wanted}}}
            unknown = [n for n in wanted if n not in by_number]
            if unknown:  # like GitHub: a NOT_FOUND error per unknown number, gh exits 1, the rest still printed
                body["errors"] = [{"type": "NOT_FOUND", "path": ["repository", f"p{n}"]} for n in unknown]
                raise cl.GhError(f"gh: Could not resolve to a PullRequest with the number of {unknown[-1]}.",
                                 json.dumps(body))
            return json.dumps(body)
        if args[:2] == ["api", "repos/acme/demo"]:
            return "main\n"
        if args[0] == "api" and "/compare/main..." in args[1]:
            return ("behind" if args[1].rsplit("...", 1)[1] in self.on_main else "diverged") + "\n"
        if args[0] == "api" and "/pulls/" in args[1]:
            return self.bodies.get(int(args[1].rsplit("/", 1)[1]), "") + "\n"
        if args[0] == "api" and "contents/" in args[-1]:
            path = args[-1].split("contents/", 1)[1]
            if path in self.files:
                return self.files[path]
            raise cl.GhError("gh: Not Found (HTTP 404)")
        raise AssertionError(f"unexpected gh call {args}")


class Parsing(unittest.TestCase):
    def test_issue_from_title_and_branch(self):
        cases = [
            ("feat(P0-04): Money type", None, "P0-04"),
            ("fix(p3-17): Gold metric grain", None, "P3-17"),
            ("feat(I-01): Astro structure", "feat/i-01-astro-deploy", "I-01"),
            ("fix(lakehouse): replace read tables (P3-11)", None, "P3-11"),
            ("docs: record home page", "docs/7.2-verified", "7.2"),
            ("feat(2.2): portrait", None, "2.2"),
            ("docs(ADR-003): approve", "docs/adr-003", None),
            ("chore(deps-dev): Bump typescript from 6.0.3 to 7.0.2", "dependabot/npm_and_yarn/typescript-7.0.2", None),
            ("docs: agent workflow", "chore/agent-workflow", None),
            ("refactor: runtime", "feat/p3-10-runtime-hardening", "P3-10"),
        ]
        for title, branch, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(cl.issue_of(title, branch), expected)

    def test_kind(self):
        self.assertEqual(cl.kind_of("feat(P1-01): x", None), "feat")
        self.assertEqual(cl.kind_of("ci(deps): Bump actions/checkout", None), "deps")
        self.assertEqual(cl.kind_of("Add logo", "brand/linkedin-v2-logo"), "content")
        self.assertEqual(cl.kind_of("Bump x", "dependabot/npm/x"), "deps")
        self.assertIsNone(cl.kind_of("Update things", "misc/things"))

    def test_classify_path(self):
        self.assertEqual(cl.classify_path("src/app.py"), "code")
        self.assertEqual(cl.classify_path("site/src/content/docs/index.mdx"), "code")
        self.assertEqual(cl.classify_path("README.md"), "doc")
        self.assertEqual(cl.classify_path("docs/architecture/overview.html"), "doc")
        self.assertEqual(cl.classify_path("requirements-dev.txt"), "code")
        for skipped in ("package-lock.json", "uv.lock", "dist/app.js", "web/node_modules/x/y.js",
                        "site/src/assets/fonts/urbanist.woff2", "brand/logo.svg", "app.min.js"):
            self.assertEqual(cl.classify_path(skipped), "skip", skipped)

    def test_ci_state(self):
        self.assertEqual(cl.ci_state([]), ("none", None))
        self.assertEqual(cl.ci_state([check("lint", "SUCCESS"), check("e2e", "SKIPPED")]), ("pass", None))
        self.assertEqual(cl.ci_state([check("lint", "SUCCESS"), check("tests", "", "IN_PROGRESS")]), ("pending", None))
        self.assertEqual(cl.ci_state([check("lint", "FAILURE"), {"context": "deploy", "state": "PENDING"}]), ("fail", "lint"))
        self.assertEqual(cl.ci_state([{"context": "deploy", "state": "ERROR"}]), ("fail", "deploy"))

    def test_parse_roadmap_both_layouts(self):
        issues = cl.parse_roadmap(ROADMAP)
        self.assertEqual(issues["P1-03"]["risk"], ("Med", "Hi"))
        self.assertEqual(issues["P1-03"]["size"], ("Md", "Md"))
        self.assertEqual(issues["P1-03"]["status"], "Delivered")
        self.assertEqual(issues["P1-04"]["risk"], ("Lo", None))
        self.assertEqual(issues["7.2"], {"title": "Dependency updates", "status": "verified",
                                         "risk": ("Med", "Med"), "size": ("Sm", "Lg")})
        self.assertNotIn("ADR-001", issues)

    def test_normalize_pr_marks_bots(self):
        pr = cl.normalize_pr(node(9, "chore(deps): Bump x", "dependabot/npm/x", bot=True))
        self.assertEqual(pr["author"]["login"], "app/dependabot")
        self.assertEqual(pr["statusCheckRollup"], [])
        fields = cl.pr_fields(pr)
        self.assertEqual((fields["code_lines"], fields["doc_lines"]), (120, 30))
        self.assertEqual(fields["commits_after_open"], 0)

    def test_parse_notes(self):
        events, lessons, unknown = cl.parse_notes([
            "", "Prose around the items is ignored.", "- None.",
            "- Decision: email or SMS? Answer: email", "- plan rejected: split it first", "- plan: approved",
            "- code-reviewer: changes needed, x", "1. po-reviewer: APPROVED", "* code-reviewer: pass",
            "- feedback: rename it", "- lesson for AGENTS.md: write it down", "- lesson: no target",
            "- checks: PASS, 21 tests", "context: no list marker", "- odd line"])
        self.assertEqual([(e["kind"], e.get("reason"), e.get("verdict"), e.get("round")) for e in events], [
            ("ask", "decision", None, None), ("plan", None, None, 1), ("rejected", None, None, None),
            ("plan", None, None, 2), ("approved", None, None, None), ("review", None, "CHANGES NEEDED", 1),
            ("review", None, "APPROVED", 1), ("review", None, "PASS", 2), ("feedback", None, None, None)])
        self.assertEqual(lessons, [("AGENTS.md", "write it down"), (None, "no target")])
        self.assertEqual(unknown, ["checks: PASS, 21 tests", "context: no list marker (not a list item)", "odd line"])

    def test_parse_notes_reads_drift_verdicts_as_the_defined_words(self):
        events, _, unknown = cl.parse_notes([
            "- po-reviewer: ACCEPT WITH NOTES, DP-02 wording fixed",  # aconta #15, as po-reviewer wrote it
            "- po-reviewer: approved with notes", "- po-reviewer: Accept, fine", "- po-reviewer: REJECTED, AC 2 not met",
            "- po-reviewer: REJECT", "- privacy-auditor: FAIL, payload logged", "- code-reviewer: CHANGES  NEEDED, x",
            "- po-reviewer: PASS (ACCEPT WITH NOTES), kept", "- po-reviewer: LGTM", "- po-reviewer: ACCEPTABLE",
            "- po-reviewer: accept with changes needed: fix X", "- code-reviewer: PASS with 2 warnings"])
        self.assertEqual([(e["verdict"], e["note"]) for e in events], [
            ("APPROVED", "ACCEPT WITH NOTES: DP-02 wording fixed"), ("APPROVED", "APPROVED WITH NOTES"),
            ("APPROVED", "ACCEPT: fine"), ("CHANGES NEEDED", "REJECTED: AC 2 not met"), ("CHANGES NEEDED", "REJECT"),
            ("BLOCK", "FAIL: payload logged"), ("CHANGES NEEDED", "x"), ("PASS", "(ACCEPT WITH NOTES), kept"),
            ("PASS", "with 2 warnings")])
        self.assertEqual(unknown, ["po-reviewer: LGTM", "po-reviewer: ACCEPTABLE",
                                   "po-reviewer: accept with changes needed: fix X"])

    def test_rework_counts_author_dates_from_the_start_of_review(self):
        def after_open(pr):
            return cl.pr_fields(cl.normalize_pr(pr))["commits_after_open"]

        rebased = node(1, "feat: x", "feat/x", created=-5, commits=(-6.0, -5.5))
        for item in rebased["commits"]["nodes"]:
            item["commit"]["committedDate"] = ts(-0.1)  # a rebase rewrites commit dates, not author dates
        self.assertEqual(after_open(rebased), 0)
        self.assertEqual(after_open(node(2, "feat: y", "feat/y", draft=True, created=-5, commits=(-4.0,))), 0)
        ready = node(3, "feat: z", "feat/z", created=-5, commits=(-4.0, -1.0), first_event=("ReadyForReviewEvent", -2))
        self.assertEqual(after_open(ready), 1)
        self.assertEqual(cl.pr_fields(cl.normalize_pr(ready))["opened_at"], ready["draftEvents"]["nodes"][0]["createdAt"])
        # opened for review, then turned into a draft: review began when the PR opened
        converted = node(4, "feat: w", "feat/w", draft=True, created=-5, commits=(-6.0, -4.0),
                         first_event=("ConvertToDraftEvent", -3))
        self.assertEqual(after_open(converted), 1)


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "demo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("remote", "add", "origin", "https://github.com/acme/demo.git")
        (self.repo / "AGENTS.md").write_text(AGENTS)
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "init")
        self.env = {k: os.environ.get(k) for k in ("CHANGE_LEDGER_DB", "CHANGE_LEDGER_ROOTS", "CHANGE_LEDGER_OWNERS",
                                                   "T3CODE_THREAD_ID", "CLAUDE_EFFORT")}
        os.environ.update({"CHANGE_LEDGER_DB": str(root / "ledger.db"), "CHANGE_LEDGER_ROOTS": str(root),
                           "CHANGE_LEDGER_OWNERS": "acme", "T3CODE_THREAD_ID": "thread-1", "CLAUDE_EFFORT": "medium"})
        self.cwd = os.getcwd()
        os.chdir(self.repo)
        self.fake = FakeGh()
        self.real_gh, cl.gh = cl.gh, self.fake

    def tearDown(self):
        cl.gh = self.real_gh
        os.chdir(self.cwd)
        for key, value in self.env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def run_cli(self, *argv) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            cl.main(list(argv))
        return out.getvalue()

    def query(self, sql, params=()):
        with closing(cl.connect()) as con:
            cl._CONNECTIONS.remove(con)
            return [dict(r) for r in con.execute(sql, params)]

    def row(self, cid=1):
        return self.query("SELECT * FROM v_changes WHERE id = ?", (cid,))[0]

    def kinds(self, cid=1):
        return [r["kind"] for r in self.query("SELECT kind FROM events WHERE change_id = ? ORDER BY id", (cid,))]

    def test_issue_cycle_from_start_to_merge(self):
        out = self.run_cli("start", "--issue", "p1-03", "--title", "Account signup", "--kind", "feat",
                           "--risk", "med", "--size", "Md", "--model", "claude-opus-5-5")
        self.assertIn("#1 demo P1-03", out)
        self.assertIn("Open PRs: none", out)  # the brief comes with it
        notes = Path(re.search(r"PR text: (\S+)", out).group(1))
        self.assertEqual(notes.read_text(encoding="utf-8"), "## Questions and decisions\n\n")
        self.assertIn("already open", self.run_cli("start", "--issue", "P1-03", "--title", "Account signup"))
        r = self.row()
        self.assertEqual((r["profile"], r["thread"], r["effort"], r["exp_risk"], r["exp_size"], r["seen_risk"]),
                         ("reviewed", "thread-1", "medium", "Med", "Md", None))
        self.assertEqual(r["issue_title"], "Account signup")  # start mirrors the roadmap

        # the lines the agent adds as things happen, then the PR text it writes above them at delivery
        self.git("checkout", "-q", "-b", "feat/p1-03-signup")  # found by thread, then the branch is recorded
        with notes.open("a", encoding="utf-8") as f:
            f.write("- plan approved: drop the CSV export\n"
                    "- context: where do auth errors live? Answer: apps/api/errors.py; it belongs in AGENTS.md\n"
                    "- code-reviewer: BLOCK, missing rate limit\n- code-reviewer: PASS\n"
                    "- lesson for AGENTS.md: the auth error path belongs in AGENTS.md\n- a line in no known form\n")
        notes.write_text("## Summary\n\nEmail signup with verification.\n\nMore detail.\n\n"
                         + notes.read_text(encoding="utf-8"), encoding="utf-8")
        self.fake.prs = [node(5, "feat(P1-03): account signup", "feat/p1-03-signup", created=-2,
                              commits=(-2.2,), checks=[check("tests", "FAILURE")], mergeable="CONFLICTING")]
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            out = self.run_cli("finish", "--seen-risk", "Hi", "--seen-size", "Md",
                               "--merge-after", "acme/other#2", "--owner-actions", "run make migrate")
        self.assertIn("a line in no known form", err.getvalue())
        self.assertNotIn("plan approved", err.getvalue())  # the plan gate has its line
        for expected in ("1 question (context 1), 1 plan round, 2 reviews (1 blocking), 0 feedback rounds",
                         "PR #5 P1-03", "CI fail", "CONFLICTS", "merge after acme/other#2", "at merge: run make migrate"):
            self.assertIn(expected, out)
        r = self.row()
        self.assertEqual((r["summary"], r["branch"], r["pr"], r["status"], r["ci"], r["conflicted"], r["code_lines"]),
                         ("Email signup with verification.", "feat/p1-03-signup", 5, "pr_open", "fail", 1, 120))
        self.assertEqual(r["issue_title"], "Account signup")
        self.assertIn("L1 [AGENTS.md]", self.run_cli("brief", "--no-sync"))

        # a feedback round: one more line, and a second finish replaces what the first recorded
        with notes.open("a", encoding="utf-8") as f:
            f.write("- feedback: rename the endpoint\n")
        with mock.patch("sys.stderr", io.StringIO()):
            self.run_cli("finish", "--no-sync")
        r = self.row()
        self.assertEqual((r["asks"], r["plan_rounds"], r["review_rounds"], r["feedback_rounds"]), (1, 1, 2, 1))
        self.assertEqual(len(self.query("SELECT id FROM lessons")), 1)

        self.fake.prs = [node(5, "feat(P1-03): account signup", "feat/p1-03-signup", state="MERGED", created=-2,
                              merged=-0.5, commits=(-2.2, -1.0, -0.8), checks=[check("tests", "SUCCESS")])]
        self.run_cli("sync")
        r = self.row()
        self.assertEqual((r["status"], r["outcome"], r["commits_after_open"]), ("merged", "rework", 2))
        self.assertEqual((r["asks"], r["asks_context"], r["plan_rounds"], r["plan_rejections"], r["review_rounds"],
                          r["review_blocks"]), (1, 1, 1, 0, 2, 1))
        self.assertEqual((r["risk"], r["size"], r["rating_from"]), ("Med/Hi", "Md/Md", "ledger"))
        self.assertAlmostEqual(r["hours_to_merge"], 1.5, delta=0.05)
        self.assertEqual(self.kinds(), ["start", "rated", "pr_opened", "ci", "conflict", "plan", "approved", "ask",
                                        "review", "review", "feedback", "merged", "ci"])

        stats = self.run_cli("stats")
        self.assertIn("| demo | reviewed | 1 | 1 | 100% | 0% |", stats)
        rows = list(csv.DictReader(io.StringIO(self.run_cli("export"))))
        self.assertEqual((rows[0]["risk"], rows[0]["outcome"], rows[0]["asks_context"]), ("Med/Hi", "rework", "1"))
        self.assertIn("auth error path", self.run_cli("lesson", "--list"))
        self.run_cli("lesson", "--applied", "1", "--in", "acme/demo#6")
        self.assertIn("no lessons open", self.run_cli("lesson", "--list"))

    def test_sync_discovers_prs_and_mirrors_the_roadmap(self):
        self.fake.prs = [
            node(3, "feat(P1-04): password reset", "feat/p1-04-reset", state="MERGED", created=-30, merged=-29,
                 commits=(-30.5,)),
            node(4, "chore(deps): Bump x from 1 to 2", "dependabot/npm/x", created=-80, bot=True),
            node(2, "docs: old idea", "docs/old-idea", state="CLOSED", created=-100, merged=-99),
        ]
        self.run_cli("sync")
        rows = {r["pr"]: r for r in self.query("SELECT * FROM v_changes")}
        self.assertEqual(rows[3]["issue"], "P1-04")
        self.assertEqual((rows[3]["risk"], rows[3]["size"], rows[3]["rating_from"]), ("Lo/-", "Sm/-", "roadmap"))
        self.assertEqual((rows[3]["source"], rows[3]["outcome"]), ("github", "clean"))
        self.assertEqual((rows[4]["kind"], rows[4]["bot"]), ("deps", 1))
        self.assertEqual(rows[2]["outcome"], "dropped")
        self.assertEqual(self.query("SELECT profile FROM projects WHERE name = 'demo'")[0]["profile"], "reviewed")
        self.assertEqual(len(self.query("SELECT * FROM issues WHERE project = 'demo'")), 3)
        s = cl.summarize(list(rows.values()), self.query("SELECT * FROM issues"))
        self.assertEqual((s["changes"], s["merged"], s["closed"], s["open_prs"], s["stale"]), (2, 1, 1, 1, 1))
        self.assertEqual(s["size_est"], {"total": 2, "right": 1, "under": 1, "over": 0})
        before = len(self.query("SELECT id FROM events"))
        self.run_cli("sync")  # nothing changed on GitHub: no new events
        self.assertEqual(len(self.query("SELECT id FROM events")), before)

    def test_sync_warns_about_a_merge_that_never_reached_main(self):
        self.fake.prs = [
            node(88, "feat(P1-05): stacked", "feat/p1-05", state="MERGED", created=-5, merged=-1,
                 base="feat/p1-04", oid="dead88"),
            node(87, "feat: stacked, then its base merged", "feat/b", state="MERGED", created=-6, merged=-2,
                 base="feat/a", oid="good87"),
            node(85, "feat(P1-04): base", "feat/p1-04", state="MERGED", created=-8, merged=-3, oid="good85"),
            node(86, "feat: stranded, then re-landed by another PR", "feat/c", state="MERGED", created=-7,
                 merged=-2.5, base="feat/gone", oid="dead86", head="head86"),
            node(60, "feat: stranded long ago", "feat/old", state="MERGED", created=-2000, merged=-1999,
                 base="feat/older", oid="dead60"),
        ]
        self.fake.on_main = {"good87", "good85", "head86"}
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.run_cli("sync", "--no-roadmaps")
        self.assertIn("PR #88 merged into feat/p1-04, not main: its changes are not on main unless", err.getvalue())
        self.assertNotIn("#87", err.getvalue())
        self.assertNotIn("#86", err.getvalue())  # its head commit reached main through a later PR
        self.assertNotIn("#60", err.getvalue())  # older than STRANDED_DAYS
        compared = [c[1] for c in self.fake.calls if "/compare/" in c[1]]
        self.assertEqual(compared, ["repos/acme/demo/compare/main...dead88", "repos/acme/demo/compare/main...good87",
                                    "repos/acme/demo/compare/main...dead86", "repos/acme/demo/compare/main...head86"])

    def test_sync_reads_open_prs_that_fell_out_of_the_window(self):
        self.fake.prs = [node(1, "feat: old work", "feat/old-work", created=-50)]
        self.run_cli("sync", "--no-roadmaps")
        self.assertEqual(self.row()["status"], "pr_open")
        self.fake.prs = [node(3, "docs: c", "docs/c", created=-1), node(2, "docs: b", "docs/b", created=-2),
                         node(1, "feat: old work", "feat/old-work", state="MERGED", created=-50, merged=-0.5)]
        self.run_cli("sync", "--no-roadmaps", "--limit", "2")  # the window holds #3 and #2 only
        self.assertEqual(self.row()["status"], "merged")
        self.assertTrue(any("p1: pullRequest(number: 1)" in " ".join(call) for call in self.fake.calls))

    def test_a_pr_number_github_does_not_have_only_warns(self):
        self.fake.prs = [node(1, "feat: old work", "feat/old-work", created=-50)]
        self.run_cli("sync", "--no-roadmaps")
        self.git("checkout", "-q", "-b", "feat/typo")
        self.run_cli("start", "--title", "Typo in the PR number")
        self.run_cli("set", "--pr", "77")  # GitHub has no PR 77
        self.fake.prs = [node(2, "docs: b", "docs/b", created=-1),
                         node(1, "feat: old work", "feat/old-work", state="MERGED", created=-50, merged=-0.5)]
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.run_cli("sync", "--no-roadmaps", "--limit", "1")  # #1 and #77 are read by number
        self.assertEqual(self.row(1)["status"], "merged")
        self.assertIn("change #2 names PR #77, which GitHub does not have", err.getvalue())

    def test_a_draft_is_in_progress_until_it_is_marked_ready(self):
        self.fake.prs = [node(6, "feat: draft", "feat/draft", draft=True, created=-5, commits=(-5.1, -3.0))]
        self.run_cli("sync", "--no-roadmaps")
        r = self.row()
        self.assertEqual((r["status"], r["opened_at"], r["commits_after_open"]), ("in_progress", None, 0))
        brief = self.run_cli("brief", "--no-sync")
        self.assertIn("Open PRs: none", brief)
        self.assertIn("#1 feat: draft · draft PR #6 · edits src/app.py, README.md", brief)
        ready = node(6, "feat: draft", "feat/draft", created=-5, commits=(-5.1, -3.0, -0.5),
                     first_event=("ReadyForReviewEvent", -2), last_ready=-2)
        self.fake.prs = [ready]
        self.run_cli("sync", "--no-roadmaps")
        r = self.row()
        self.assertEqual((r["status"], r["opened_at"], r["commits_after_open"]),
                         ("pr_open", ready["draftEvents"]["nodes"][0]["createdAt"], 1))
        self.assertEqual(self.kinds(), ["pr_opened", "ready"])
        # back to draft, then ready again: the second event has the second time
        self.fake.prs = [node(6, "feat: draft", "feat/draft", draft=True, created=-5,
                              first_event=("ReadyForReviewEvent", -2), last_ready=-2)]
        self.run_cli("sync", "--no-roadmaps")
        self.assertEqual(self.row()["status"], "in_progress")
        again = node(6, "feat: draft", "feat/draft", created=-5, first_event=("ReadyForReviewEvent", -2), last_ready=-0.2)
        self.fake.prs = [again]
        self.run_cli("sync", "--no-roadmaps")
        ready_times = [e["ts"] for e in self.query("SELECT ts FROM events WHERE change_id = 1 AND kind = 'ready' ORDER BY id")]
        self.assertEqual(ready_times, [ready["lastReady"]["nodes"][0]["createdAt"], again["lastReady"]["nodes"][0]["createdAt"]])

    def test_a_large_pr_counts_files_past_the_first_page(self):
        self.fake.prs = [node(4, "feat: big", "feat/big", more_files=True)]
        self.fake.more_files[4] = [{"path": "src/more.py", "additions": 900, "deletions": 0}]
        self.run_cli("sync", "--no-roadmaps")
        r = self.row()
        self.assertEqual((r["code_lines"], r["measured_size"]), (1020, "Lg"))

    def test_set_pr_takes_over_the_row_sync_recorded(self):
        self.git("checkout", "-q", "-b", "feat/p1-04-reset")
        self.run_cli("start", "--title", "Password reset", "--issue", "P1-04")
        self.run_cli("log", "ask", "--reason", "decision", "email or SMS?")
        self.fake.prs = [node(9, "fix: reset", "fix/reset-renamed")]  # opened from another branch name
        self.run_cli("sync", "--no-roadmaps")
        self.assertEqual(len(self.query("SELECT id FROM changes")), 2)
        self.assertIn("PR #9", self.run_cli("set", "--pr", "9"))
        rows = self.query("SELECT * FROM v_changes")
        self.assertEqual([(r["id"], r["pr"], r["status"], r["asks"]) for r in rows], [(1, 9, "pr_open", 1)])
        self.assertEqual(self.kinds(), ["start", "ask", "pr_opened", "note"])
        self.assertIn("#1 note logged", self.run_cli("log", "note", "found through the T3 thread"))
        second = re.match(r"#(\d+) ", self.run_cli("start", "--title", "Second try", "--new")).group(1)
        err = io.StringIO()
        with (self.assertRaises(SystemExit) as caught, redirect_stdout(io.StringIO()), mock.patch("sys.stderr", err)):
            cl.main(["set", "--id", second, "--pr", "9"])  # #1, an agent's change, holds PR 9 now
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("PR #9 already belongs to change #1", err.getvalue())

    def test_finish_warns_when_a_gated_plan_has_no_line(self):
        out = self.run_cli("start", "--title", "Big change", "--risk", "Med", "--size", "Md")
        notes = Path(re.search(r"PR text: (\S+)", out).group(1))
        with notes.open("a", encoding="utf-8") as f:
            f.write("- code-reviewer: PASS\n")
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            out = self.run_cli("finish", "--no-sync")
        self.assertIn("1 review (0 blocking)", out)
        self.assertIn("no PR on GitHub", out)
        self.assertIn("rated Med/Md, so the plan went to Filipe", err.getvalue())

    def finish_warning(self, risk, size, agents=None) -> str:
        if agents is not None:
            (self.repo / "AGENTS.md").write_text(agents)
        out = self.run_cli("start", "--title", f"{risk}/{size} change", "--risk", risk, "--size", size, "--new")
        notes = Path(re.search(r"PR text: (\S+)", out).group(1))
        with notes.open("a", encoding="utf-8") as f:
            f.write("- code-reviewer: PASS\n")
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.run_cli("finish", "--no-sync")
        return err.getvalue()

    def test_finish_follows_the_projects_plan_stops_line(self):
        aconta = AGENTS + ("- **Plan stops (exception, 2026-11-26):** only Hi risk or Lg size stops for Filipe's plan "
                           "approval; any other issue goes straight to the PR, above Sm + Lo or not.\n")
        self.assertNotIn("plan went to Filipe", self.finish_warning("Med", "Sm", aconta))
        self.assertNotIn("plan went to Filipe", self.finish_warning("Med", "Md", aconta))
        self.assertIn("rated Hi/Sm, so the plan went to Filipe under the project's \"Plan stops\" line",
                      self.finish_warning("Hi", "Sm", aconta))
        self.assertIn("rated Lo/Lg, so the plan went", self.finish_warning("Lo", "Lg", aconta))

    def test_plan_stops_ignores_ratings_after_a_negation(self):
        for line, expected in (("Hi risk, not Med risk", ({"Hi"}, set())),
                               ("`Lg` size or hi RISK except Md size", ({"Hi"}, {"Lg"})),
                               ("Hi risk but also Lg size, not Med risk", ({"Hi"}, {"Lg"})),
                               ("none, except Hi risk", None)):
            with self.subTest(line=line):
                (self.repo / "AGENTS.md").write_text(AGENTS + f"- **Plan stops:** {line}\n")
                self.assertEqual(cl.read_plan_stops(self.repo), expected)

    def test_finish_without_a_plan_stops_rule_uses_the_default(self):
        self.assertIn("rated Med/Sm, so the plan went to Filipe under workflow.md's default",
                      self.finish_warning("Med", "Sm"))
        self.assertNotIn("plan went to Filipe", self.finish_warning("Lo", "Sm"))
        default = AGENTS + "- **Plan stops:** above Sm + Lo (workflow.md default)\n"
        self.assertIn("rated Lo/Md, so the plan went to Filipe under workflow.md's default",
                      self.finish_warning("Lo", "Md", default))

    def test_drift_verdicts_count_as_blocking_and_unknown_words_get_the_list(self):
        out = self.run_cli("start", "--title", "Small fix")
        notes = Path(re.search(r"PR text: (\S+)", out).group(1))
        with notes.open("a", encoding="utf-8") as f:
            f.write("- po-reviewer: REJECT, AC 1 not met\n- po-reviewer: ACCEPT WITH NOTES, wording\n"
                    "- code-reviewer: LGTM\n")
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            out = self.run_cli("finish", "--no-sync")
        self.assertIn("2 reviews (1 blocking)", out)
        self.assertIn("a reviewer verdict is one of PASS, BLOCK, APPROVED, CHANGES NEEDED, NEEDS FILIPE, NEEDS INPUT",
                      err.getvalue())
        with mock.patch("sys.stderr", io.StringIO()) as err:
            self.run_cli("log", "review", "--actor", "privacy-auditor", "--verdict", "fail", "payload logged")
            self.run_cli("log", "review", "--actor", "migration-reviewer", "--verdict", "lgtm")
        self.assertEqual(err.getvalue().count("is not one of"), 1)
        self.assertEqual(self.row()["review_blocks"], 2)
        self.assertEqual(self.query("SELECT verdict, note FROM events WHERE actor = 'privacy-auditor'"),
                         [{"verdict": "BLOCK", "note": "FAIL: payload logged"}])

    def test_finish_rewrites_only_what_came_from_the_pr_text(self):
        out = self.run_cli("start", "--title", "Small fix", "--no-sync")
        notes = Path(re.search(r"PR text: (\S+)", out).group(1))
        self.run_cli("log", "ask", "--reason", "access", "need the deploy token")  # a correction, not from the file
        with notes.open("a", encoding="utf-8") as f:
            f.write("- context: where is the config? Answer: config/app.toml\n"
                    "- code-reviewer: PASS\n- lesson for AGENTS.md: name the config file\n")
        with mock.patch("sys.stderr", io.StringIO()):
            self.run_cli("finish", "--no-sync")
        self.assertEqual((self.row()["asks"], self.row()["asks_access"]), (2, 1))
        earlier = ts(-10)
        with closing(cl.connect()) as con:
            cl._CONNECTIONS.remove(con)
            con.execute("UPDATE events SET ts = ? WHERE source = 'pr_text'", (earlier,))
            con.commit()
        lesson_ids = [x["id"] for x in self.query("SELECT id FROM lessons")]

        notes.write_text("## Questions and decisions\n\n", encoding="utf-8")  # emptied by mistake
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.run_cli("finish", "--no-sync")
        self.assertIn("lists nothing now: kept the 2 events and 1 lesson", err.getvalue())
        self.assertEqual(self.row()["asks"], 2)

        with notes.open("a", encoding="utf-8") as f:  # the same lines again, one feedback round, a reworded lesson
            f.write("- context: where is the config? Answer: config/app.toml\n- code-reviewer: PASS\n"
                    "- feedback: shorter name\n- lesson for AGENTS.md: name the config file in AGENTS.md\n")
        with mock.patch("sys.stderr", io.StringIO()):
            self.run_cli("finish", "--no-sync")
        r = self.row()
        self.assertEqual((r["asks"], r["review_rounds"], r["feedback_rounds"]), (2, 1, 1))
        times = {e["kind"]: e["ts"] for e in self.query("SELECT kind, ts FROM events WHERE source = 'pr_text'")}
        self.assertEqual((times["ask"], times["review"]), (earlier, earlier))  # recorded lines keep their time
        lessons = self.query("SELECT id, text FROM lessons")
        self.assertEqual([x["text"] for x in lessons], ["name the config file in AGENTS.md"])
        self.assertNotIn(lessons[0]["id"], lesson_ids)

        notes.write_text(notes.read_text(encoding="utf-8").replace("lesson for AGENTS.md", "lesson for README.md"),
                         encoding="utf-8")  # same lesson, another file
        with mock.patch("sys.stderr", io.StringIO()):
            self.run_cli("finish", "--no-sync")
        self.assertEqual([(x["id"], x["target"]) for x in self.query("SELECT id, target FROM lessons")],
                         [(lessons[0]["id"], "README.md")])

    def test_finish_reads_the_pr_text_from_github_when_the_file_is_gone(self):
        out = self.run_cli("start", "--title", "Fix", "--no-sync")
        Path(re.search(r"PR text: (\S+)", out).group(1)).unlink()  # its worktree was removed
        self.run_cli("set", "--pr", "12")
        self.fake.bodies[12] = "## Summary\n\nFixes it.\n\n## Questions and decisions\n\n- decision: A or B? Answer: B\n"
        with mock.patch("sys.stderr", io.StringIO()):
            self.run_cli("finish", "--no-sync")
        r = self.row()
        self.assertEqual((r["asks_decision"], r["summary"]), (1, "Fixes it."))

    def test_a_version_1_ledger_gains_the_source_columns(self):
        path = Path(self.tmp.name) / "old.db"
        with closing(sqlite3.connect(path)) as con:
            con.executescript(cl.SCHEMA)
            con.executescript("ALTER TABLE events DROP COLUMN source; ALTER TABLE lessons DROP COLUMN source; "
                              "PRAGMA user_version = 1;")
        with closing(cl.connect(path)) as con:
            cl._CONNECTIONS.remove(con)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], cl.SCHEMA_VERSION)
            for table in ("events", "lessons"):
                self.assertIn("source", [c[1] for c in con.execute(f"PRAGMA table_info({table})")])

    def test_brief_flags_idle_work(self):
        self.run_cli("start", "--title", "Forgotten work")
        with closing(cl.connect()) as con:
            cl._CONNECTIONS.remove(con)
            con.execute("UPDATE changes SET updated_at = ?", (ts(-100),))
            con.commit()
        self.assertIn("#1 Forgotten work · idle 4d", self.run_cli("brief", "--no-sync"))

    def test_logging_needs_an_open_change(self):
        with (self.assertRaises(SystemExit) as caught, redirect_stdout(io.StringIO()),
              open(os.devnull, "w") as devnull, mock.patch("sys.stderr", devnull)):
            cl.main(["log", "note", "nothing started"])
        self.assertEqual(caught.exception.code, 2)

    def test_a_branch_switch_before_the_pr_keeps_the_link(self):
        self.git("checkout", "-q", "-b", "t3/scratch")
        self.run_cli("start", "--title", "Small fix", "--issue", "P1-04")
        self.git("checkout", "-q", "-b", "fix/p1-04-reset")
        self.run_cli("log", "checks", "--verdict", "pass", "make test: 12 passed")
        self.assertEqual(self.row()["branch"], "fix/p1-04-reset")
        self.fake.prs = [node(8, "fix(P1-04): reset link", "fix/p1-04-reset")]
        self.run_cli("sync", "--no-roadmaps")
        self.assertEqual(self.row()["pr"], 8)
        self.assertEqual(len(self.query("SELECT id FROM changes")), 1)

    def test_start_adopts_a_pr_that_sync_found_first(self):
        self.git("checkout", "-q", "-b", "feat/p1-04-reset")
        self.fake.prs = [node(7, "feat(P1-04): reset link", "feat/p1-04-reset")]
        self.run_cli("sync", "--no-roadmaps")
        self.assertEqual(self.row()["source"], "github")
        out = self.run_cli("start", "--title", "Password reset", "--risk", "Lo", "--size", "Sm", "--model", "m-1")
        self.assertIn("adopted: #1", out)
        r = self.row()
        self.assertEqual((r["source"], r["thread"], r["effort"], r["model"], r["exp_risk"], r["issue"]),
                         ("agent", "thread-1", "medium", "m-1", "Lo", "P1-04"))
        self.assertIn("already open", self.run_cli("start", "--title", "Password reset"))
        self.assertEqual(len(self.query("SELECT id FROM changes")), 1)

    def test_report_escapes_the_payload(self):
        self.run_cli("start", "--title", "</script><b>x</b> & more")
        out = Path(self.tmp.name) / "report.html"
        self.run_cli("report", "--out", str(out))
        html = out.read_text(encoding="utf-8")
        payload = html.split('<script id="ledger-data" type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("<", payload)
        self.assertEqual(json.loads(payload)["changes"][0]["title"], "</script><b>x</b> & more")


if __name__ == "__main__":
    unittest.main()
