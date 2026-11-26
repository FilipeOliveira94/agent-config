"""Tests for change_ledger.py. No network: `gh` is replaced by a fake.

Run from the repo root: python3 -m unittest discover -s tools/change-ledger -v
"""
import csv
import io
import json
import os
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
         mergeable="MERGEABLE", files=(("src/app.py", 120, 10), ("README.md", 30, 0)), bot=False):
    """A pull request as the GraphQL query returns it."""
    return {
        "number": number, "title": title, "url": f"https://github.com/acme/demo/pull/{number}",
        "state": state, "isDraft": False, "createdAt": ts(created),
        "mergedAt": ts(merged) if merged is not None else None,
        "closedAt": ts(merged) if merged is not None else None,
        "headRefName": branch, "additions": sum(f[1] for f in files), "deletions": sum(f[2] for f in files),
        "changedFiles": len(files), "mergeable": mergeable,
        "author": {"__typename": "Bot" if bot else "User", "login": "dependabot" if bot else "acme"},
        "comments": {"totalCount": 1}, "reviews": {"totalCount": 0},
        "files": {"nodes": [{"path": p, "additions": a, "deletions": d} for p, a, d in files]},
        "commits": {"nodes": [{"commit": {"committedDate": ts(c)}} for c in commits]},
        "last": {"nodes": [{"commit": {"statusCheckRollup": {"contexts": {"nodes": list(checks)}} if checks else None}}]},
    }


def check(name, conclusion, status="COMPLETED"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


class FakeGh:
    def __init__(self):
        self.prs = []
        self.files = {"ROADMAP.md": ROADMAP, "AGENTS.md": AGENTS}
        self.calls = []

    def __call__(self, args, timeout=120, retries=1):
        self.calls.append(args)
        if args[:2] == ["api", "graphql"]:
            return json.dumps({"data": {"repository": {"pullRequests": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": self.prs}}}})
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

    def test_issue_cycle_from_plan_to_merge(self):
        out = self.run_cli("start", "--issue", "p1-03", "--title", "Account signup", "--kind", "feat",
                           "--risk", "med", "--size", "Md", "--model", "claude-opus-5-5")
        self.assertIn("#1 demo P1-03", out)
        self.assertIn("already open", self.run_cli("start", "--issue", "P1-03", "--title", "Account signup"))
        r = self.row()
        self.assertEqual((r["profile"], r["thread"], r["effort"], r["risk"], r["size"]),
                         ("reviewed", "thread-1", "medium", "Med/-", "Md/-"))

        self.run_cli("log", "plan", "email + password, no social login")
        self.assertEqual(self.row()["status"], "awaiting_approval")
        self.assertIn("1 open question", self.run_cli("log", "ask", "--reason", "context", "where do auth errors live?"))
        self.run_cli("log", "answer", "apps/api/errors.py; add it to AGENTS.md")
        self.run_cli("log", "approved", "drop the CSV export")
        self.assertEqual(self.row()["status"], "in_progress")

        self.git("checkout", "-q", "-b", "feat/p1-03-signup")  # found by thread, then the branch is recorded
        self.assertIn("round 1", self.run_cli("log", "review", "--actor", "code-reviewer", "--verdict", "block", "missing rate limit"))
        self.assertIn("round 2", self.run_cli("log", "review", "--actor", "code-reviewer", "--verdict", "PASS"))
        self.assertEqual(self.row()["branch"], "feat/p1-03-signup")
        self.run_cli("set", "--summary", "Email signup with verification.", "--seen-risk", "Hi", "--seen-size", "Md",
                     "--merge-after", "acme/other#2", "--owner-actions", "run make migrate")
        self.assertIn("L1 open · demo #1", self.run_cli("lesson", "auth error path belongs in AGENTS.md", "--target", "AGENTS.md"))

        self.fake.prs = [node(5, "feat(P1-03): account signup", "feat/p1-03-signup", created=-2,
                              commits=(-2.2,), checks=[check("tests", "FAILURE")], mergeable="CONFLICTING")]
        self.run_cli("sync")
        r = self.row()
        self.assertEqual((r["pr"], r["status"], r["ci"], r["conflicted"], r["code_lines"]), (5, "pr_open", "fail", 1, 120))
        self.assertEqual(r["issue_title"], "Account signup")
        brief = self.run_cli("brief", "--no-sync")
        for expected in ("profile reviewed", "PR #5 P1-03", "CI fail", "CONFLICTS", "merge after acme/other#2",
                         "at merge: run make migrate", "L1 [AGENTS.md]"):
            self.assertIn(expected, brief)

        self.fake.prs = [node(5, "feat(P1-03): account signup", "feat/p1-03-signup", state="MERGED", created=-2,
                              merged=-0.5, commits=(-2.2, -1.0, -0.8), checks=[check("tests", "SUCCESS")])]
        self.run_cli("sync")
        r = self.row()
        self.assertEqual((r["status"], r["outcome"], r["commits_after_open"]), ("merged", "rework", 2))
        self.assertEqual((r["asks"], r["asks_context"], r["plan_rounds"], r["review_rounds"], r["review_blocks"]),
                         (1, 1, 1, 2, 1))
        self.assertEqual((r["risk"], r["size"], r["rating_from"]), ("Med/Hi", "Md/Md", "ledger"))
        self.assertAlmostEqual(r["hours_to_merge"], 1.5, delta=0.05)
        self.assertEqual(self.kinds(), ["start", "plan", "ask", "answer", "approved", "review", "review", "rated",
                                        "pr_opened", "ci", "conflict", "merged", "ci"])

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
