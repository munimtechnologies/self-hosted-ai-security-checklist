"""Offline tests for advisory_gap_finder. The fixtures are shaped like github/advisory-database
files. The Flowise IDs and references are trimmed from records seen on 13 October 2026; the
duplicate links and the example/tool record are synthetic (no network access needed)."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advisory_gap_finder as agf  # noqa: E402

NPM_FLOWISE = {"package": {"ecosystem": "npm", "name": "flowise"},
               "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "3.1.3"}]}]}

# Reviewed, with no github_reviewed flag: recognised by its github-reviewed folder.
REVIEWED = {"id": "GHSA-9gvv-qjj3-2p6g", "published": "2026-10-07T16:17:21Z",
            "aliases": ["CVE-2026-73487"], "summary": "Flowise Python validator bypass",
            "affected": [NPM_FLOWISE], "references": [],
            "database_specific": {"severity": "CRITICAL"}}

# Cites the Flowise repository advisory, which isn't in the database; no summary.
NOT_IMPORTED = {"id": "GHSA-mjgh-prrr-9qw5", "published": "2026-09-26T15:31:21Z",
                "aliases": ["CVE-2026-100607"], "details": "Flowise through 3.1.4 resolves SSO ...",
                "affected": [],
                "references": [
                    {"type": "WEB", "url": "https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-cffm-583c-vffr"},
                    {"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-100607"},
                    {"type": "ADVISORY", "url": "https://github.com/advisories/GHSA-mjgh-prrr-9qw5"}],
                "database_specific": {"github_reviewed": False, "severity": "CRITICAL"}}

# Same CVE as the reviewed advisory.
DUP_BY_CVE = {"id": "GHSA-x3jw-7gj7-qv6m", "published": "2026-08-13T10:00:00Z",
              "aliases": ["cve-2026-73487"], "summary": "Flowise CSV and Airtable Agent validator bypass",
              "affected": [],
              "references": [{"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-73487"}],
              "database_specific": {"github_reviewed": False, "severity": "CRITICAL"}}

# Cites a repository advisory that is reviewed in the database (upper-case ID in the URL).
DUP_BY_UPSTREAM = {"id": "GHSA-aaaa-bbbb-cccc", "published": "2026-09-15T10:00:00Z",
                   "aliases": ["CVE-2026-90001"], "summary": "Flowise issue",
                   "affected": [],
                   "references": [{"type": "WEB",
                                   "url": "https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-9GVV-QJJ3-2P6G"}],
                   "database_specific": {"github_reviewed": False, "severity": "HIGH"}}

# Cites only the repo and source files.
NO_UPSTREAM = {"id": "GHSA-qj5g-x3q9-pvxj", "published": "2026-09-10T10:00:00Z",
               "aliases": ["CVE-2026-52098"], "summary": "",
               "affected": [],
               "references": [
                   {"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-52098"},
                   {"type": "PACKAGE", "url": "https://github.com/FlowiseAI/Flowise"},
                   {"type": "WEB", "url": "https://github.com/FlowiseAI/Flowise/blob/main/packages/server/src/utils/validateKey.ts"},
                   {"type": "ADVISORY", "url": "https://github.com/advisories/GHSA-qj5g-x3q9-pvxj"}],
               "database_specific": {"github_reviewed": False, "severity": "CRITICAL"}}

# Not gaps: a package is listed, or the record is withdrawn.
HAS_PACKAGE = {"id": "GHSA-dddd-eeee-ffff", "published": "2026-09-01T00:00:00Z", "aliases": [],
               "affected": [NPM_FLOWISE], "references": [],
               "database_specific": {"github_reviewed": False, "severity": "HIGH"}}
WITHDRAWN = {"id": "GHSA-gggg-hhhh-jjjj", "published": "2026-09-01T00:00:00Z", "aliases": [],
             "withdrawn": "2026-10-01T00:00:00Z", "affected": [], "references": [],
             "database_specific": {"github_reviewed": False, "severity": "HIGH"}}

# An older record from another project.
OLD_OTHER = {"id": "GHSA-kkkk-mmmm-nnnn", "published": "2024-05-01T00:00:00Z", "aliases": ["CVE-2024-11111"],
             "summary": "example tool flaw", "affected": [],
             "references": [{"type": "WEB", "url": "https://github.com/example/tool/security/advisories/GHSA-pppp-qqqq-rrrr"}],
             "database_specific": {"github_reviewed": False, "severity": "MODERATE"}}


def write(root, folder, record):
    path = os.path.join(root, *folder.split("/"), record["id"], record["id"] + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh)


def make_clone():
    root = tempfile.mkdtemp()
    write(root, "advisories/github-reviewed/2026/10", REVIEWED)
    write(root, "advisories/unreviewed/2026/09", NOT_IMPORTED)
    write(root, "advisories/unreviewed/2026/08", DUP_BY_CVE)
    write(root, "advisories/unreviewed/2026/09", DUP_BY_UPSTREAM)
    write(root, "advisories/unreviewed/2026/09", NO_UPSTREAM)
    write(root, "advisories/unreviewed/2026/09", HAS_PACKAGE)
    write(root, "advisories/unreviewed/2026/09", WITHDRAWN)
    write(root, "advisories/unreviewed/2024/05", OLD_OTHER)
    with open(os.path.join(root, "advisories", "unreviewed", "2026", "09", "broken.json"), "w") as fh:
        fh.write("{not json")
    with open(os.path.join(root, "package.json"), "w") as fh:
        json.dump({"name": "not-an-advisory"}, fh)
    return root


class ScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = make_clone()
        cls.index, cls.candidates, cls.skipped = agf.scan(cls.root)

    def test_index_and_candidates(self):
        self.assertEqual(self.index["reviewed"], {"GHSA-9gvv-qjj3-2p6g"})
        self.assertEqual(self.index["cve"], {"CVE-2026-73487": ["GHSA-9gvv-qjj3-2p6g"]})
        self.assertEqual({c["ghsa_id"] for c in self.candidates},
                         {"GHSA-mjgh-prrr-9qw5", "GHSA-x3jw-7gj7-qv6m", "GHSA-aaaa-bbbb-cccc",
                          "GHSA-qj5g-x3q9-pvxj", "GHSA-kkkk-mmmm-nnnn"})
        self.assertEqual(self.skipped, 1)

    def test_since_skips_older_year_folders(self):
        _index, candidates, _skipped = agf.scan(self.root, since="2026-01-01")
        self.assertNotIn("GHSA-kkkk-mmmm-nnnn", {c["ghsa_id"] for c in candidates})
        self.assertEqual(len(candidates), 4)

    def test_statuses(self):
        rows = {r["ghsa_id"]: r for r in agf.find_gaps(self.index, self.candidates)}
        self.assertEqual(rows["GHSA-mjgh-prrr-9qw5"]["status"], "upstream_not_imported")
        self.assertEqual(rows["GHSA-x3jw-7gj7-qv6m"]["status"], "duplicate")
        self.assertEqual(rows["GHSA-aaaa-bbbb-cccc"]["status"], "duplicate")
        self.assertEqual(rows["GHSA-qj5g-x3q9-pvxj"]["status"], "no_upstream")
        self.assertEqual(rows["GHSA-kkkk-mmmm-nnnn"]["status"], "upstream_not_imported")

    def test_upstream_row(self):
        row = {r["ghsa_id"]: r for r in agf.find_gaps(self.index, self.candidates)}["GHSA-mjgh-prrr-9qw5"]
        self.assertEqual(row["repo"], "FlowiseAI/Flowise")
        self.assertEqual(row["upstream"], [["FlowiseAI/Flowise", "GHSA-cffm-583c-vffr"]])
        self.assertTrue(row["needs_title"])
        self.assertIn("https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-cffm-583c-vffr", row["message"])
        self.assertIn("https://github.com/advisories/GHSA-mjgh-prrr-9qw5/improve", row["message"])
        self.assertIn("Title", row["message"])

    def test_duplicates_name_the_reviewed_advisory(self):
        rows = {r["ghsa_id"]: r for r in agf.find_gaps(self.index, self.candidates)}
        self.assertEqual(rows["GHSA-x3jw-7gj7-qv6m"]["duplicate_of"], ["GHSA-9gvv-qjj3-2p6g"])
        self.assertEqual(rows["GHSA-aaaa-bbbb-cccc"]["duplicate_of"], ["GHSA-9gvv-qjj3-2p6g"])
        self.assertIsNone(rows["GHSA-x3jw-7gj7-qv6m"]["repo"])

    def test_no_upstream_row(self):
        row = {r["ghsa_id"]: r for r in agf.find_gaps(self.index, self.candidates)}["GHSA-qj5g-x3q9-pvxj"]
        self.assertEqual(row["repo"], "FlowiseAI/Flowise")
        self.assertEqual(row["upstream"], [])
        self.assertTrue(row["needs_title"])

    def test_order_is_severity_then_newest(self):
        ids = [r["ghsa_id"] for r in agf.find_gaps(self.index, self.candidates)]
        self.assertEqual(ids, ["GHSA-mjgh-prrr-9qw5", "GHSA-qj5g-x3q9-pvxj", "GHSA-x3jw-7gj7-qv6m",
                               "GHSA-aaaa-bbbb-cccc", "GHSA-kkkk-mmmm-nnnn"])

    def test_filters(self):
        def ids(**kw):
            return {r["ghsa_id"] for r in agf.find_gaps(self.index, self.candidates, **kw)}
        self.assertEqual(ids(repos=["flowiseai/flowise"]),
                         {"GHSA-mjgh-prrr-9qw5", "GHSA-aaaa-bbbb-cccc", "GHSA-qj5g-x3q9-pvxj"})
        self.assertEqual(ids(since="2026-09-01"),
                         {"GHSA-mjgh-prrr-9qw5", "GHSA-aaaa-bbbb-cccc", "GHSA-qj5g-x3q9-pvxj"})
        self.assertEqual(ids(severities={"MODERATE"}), {"GHSA-kkkk-mmmm-nnnn"})
        self.assertEqual(ids(statuses={"upstream_not_imported"}), {"GHSA-mjgh-prrr-9qw5", "GHSA-kkkk-mmmm-nnnn"})

    def test_summarise(self):
        table = agf.summarise(agf.find_gaps(self.index, self.candidates))
        self.assertEqual(table[0], ("FlowiseAI/Flowise", 3,
                                    {"upstream_not_imported": 1, "duplicate": 1, "no_upstream": 1}))
        self.assertEqual(sum(t[1] for t in table), 5)


class MainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = make_clone()

    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = agf.main([self.root] + argv)
        return code, out.getvalue()

    def test_text(self):
        code, out = self._run([])
        self.assertEqual(code, 1)
        self.assertIn("CRITICAL 2026-09-26 GHSA-mjgh-prrr-9qw5 (CVE-2026-100607) FlowiseAI/Flowise: "
                      "UPSTREAM_NOT_IMPORTED:", out)
        self.assertIn("GHSA-x3jw-7gj7-qv6m (CVE-2026-73487) -: DUPLICATE:", out)

    def test_json(self):
        code, out = self._run(["--json", "--status", "no_upstream"])
        self.assertEqual(code, 1)
        self.assertEqual([r["ghsa_id"] for r in json.loads(out)], ["GHSA-qj5g-x3q9-pvxj"])

    def test_summary(self):
        code, out = self._run(["--summary", "--since", "2026-01-01"])
        self.assertEqual(code, 1)
        self.assertIn("FlowiseAI/Flowise: 3 (duplicate 1, no_upstream 1, upstream_not_imported 1)", out)
        self.assertNotIn("example/tool", out)

    def test_nothing_found_exits_0(self):
        code, out = self._run(["--repo", "nobody/nothing"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
