"""Offline tests for ghsa_coverage_check. The Flowise fixtures are trimmed copies of
api.github.com/advisories responses as seen on 13 October 2026 (no network access needed)."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghsa_coverage_check as gcc  # noqa: E402

# CVE-2026-100607: imported from the CVE record, unreviewed, no package listed.
FLOWISE_NO_PACKAGE = {
    "ghsa_id": "GHSA-mjgh-prrr-9qw5",
    "cve_id": "CVE-2026-100607",
    "type": "unreviewed",
    "withdrawn_at": None,
    "vulnerabilities": [],
}

# A reviewed Flowise advisory with both npm packages mapped.
FLOWISE_REVIEWED = {
    "ghsa_id": "GHSA-9gvv-qjj3-2p6g",
    "type": "reviewed",
    "withdrawn_at": None,
    "vulnerabilities": [
        {"package": {"ecosystem": "npm", "name": "flowise"},
         "vulnerable_version_range": "<= 3.1.2", "first_patched_version": "3.1.3"},
        {"package": {"ecosystem": "npm", "name": "flowise-components"},
         "vulnerable_version_range": "<= 3.1.2", "first_patched_version": "3.1.3"},
    ],
}

# Synthetic: a reviewed advisory with no fix yet, in the older nested API shape.
NO_FIX_OLD_SHAPE = {
    "ghsa_id": "GHSA-aaaa-bbbb-cccc",
    "type": "reviewed",
    "vulnerabilities": [
        {"package": {"ecosystem": "pip", "name": "example"},
         "vulnerable_version_range": "<= 2.0.0", "first_patched_version": None},
        {"package": {"ecosystem": "pip", "name": "example-extra"},
         "vulnerable_version_range": "< 1.0.1", "first_patched_version": {"identifier": "1.0.1"}},
    ],
}

# Synthetic: withdrawn advisories never alert, and that is not a gap.
WITHDRAWN = {
    "ghsa_id": "GHSA-dddd-eeee-ffff",
    "type": "reviewed",
    "withdrawn_at": "2026-10-07T16:17:21Z",
    "vulnerabilities": [],
}

# Synthetic: a package without a version range.
NO_RANGE = {
    "ghsa_id": "GHSA-gggg-hhhh-jjjj",
    "type": "unreviewed",
    "vulnerabilities": [{"package": {"ecosystem": "npm", "name": "thing"},
                         "vulnerable_version_range": "", "first_patched_version": None}],
}


def fake_lookup(vuln_id):
    table = {
        "GHSA-mjgh-prrr-9qw5": ([FLOWISE_NO_PACKAGE], None),
        "CVE-2026-100607": ([FLOWISE_NO_PACKAGE], None),
        "GHSA-9gvv-qjj3-2p6g": ([FLOWISE_REVIEWED], None),
        # The upstream repository advisory: published, but not in the global database yet.
        "GHSA-cffm-583c-vffr": ([], None),
    }
    return table.get(vuln_id, (None, "HTTP 403"))


class ClassifyTests(unittest.TestCase):
    def test_unreviewed_without_package_is_a_gap(self):
        r = gcc.classify(FLOWISE_NO_PACKAGE)
        self.assertEqual(r["status"], "no_package")
        self.assertTrue(r["gap"])
        self.assertIn("https://github.com/advisories/GHSA-mjgh-prrr-9qw5/improve", r["message"])

    def test_reviewed_with_packages_is_ok(self):
        r = gcc.classify(FLOWISE_REVIEWED)
        self.assertEqual(r["status"], "ok")
        self.assertFalse(r["gap"])
        self.assertEqual(r["packages"][0], ["npm", "flowise", "<= 3.1.2", "3.1.3"])
        self.assertIn("npm flowise-components <= 3.1.2 (patched in 3.1.3)", r["message"])

    def test_no_fix_and_old_shape(self):
        r = gcc.classify(NO_FIX_OLD_SHAPE)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["packages"][0][3], None)
        self.assertEqual(r["packages"][1][3], "1.0.1")
        self.assertIn("pip example <= 2.0.0 (no patched version)", r["message"])

    def test_withdrawn_is_not_a_gap(self):
        r = gcc.classify(WITHDRAWN)
        self.assertEqual(r["status"], "withdrawn")
        self.assertFalse(r["gap"])
        self.assertIn("2026-10-07", r["message"])

    def test_package_without_range_is_a_gap(self):
        r = gcc.classify(NO_RANGE)
        self.assertEqual(r["status"], "no_range")
        self.assertTrue(r["gap"])

    def test_asked_id_is_kept_for_cve_lookups(self):
        r = gcc.classify(FLOWISE_NO_PACKAGE, "CVE-2026-100607")
        self.assertEqual(r["id"], "CVE-2026-100607")
        self.assertEqual(r["ghsa_id"], "GHSA-mjgh-prrr-9qw5")


class NormaliseTests(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(gcc.normalise(" ghsa-MJGH-prrr-9qw5 "), "GHSA-mjgh-prrr-9qw5")
        self.assertEqual(gcc.normalise("cve-2026-100607"), "CVE-2026-100607")
        self.assertEqual(gcc.normalise("PYSEC-2026-1"), "PYSEC-2026-1")


class CheckTests(unittest.TestCase):
    def test_not_in_database(self):
        results, failed = gcc.check(["GHSA-cffm-583c-vffr"], lookup_fn=fake_lookup)
        self.assertFalse(failed)
        self.assertEqual(results[0]["status"], "not_in_database")
        self.assertTrue(results[0]["gap"])

    def test_lookup_failure(self):
        results, failed = gcc.check(["GHSA-zzzz-zzzz-zzzz"], lookup_fn=fake_lookup)
        self.assertTrue(failed)
        self.assertEqual(results[0]["status"], "lookup_failed")
        self.assertFalse(results[0]["gap"])


class MainTests(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gcc.main(argv, lookup_fn=fake_lookup)
        return code, out.getvalue()

    def test_gap_exits_1_with_text(self):
        code, out = self._run(["cve-2026-100607", "GHSA-9gvv-qjj3-2p6g"])
        self.assertEqual(code, 1)
        self.assertIn("CVE-2026-100607 (GHSA-mjgh-prrr-9qw5): NO_PACKAGE:", out)
        self.assertIn("GHSA-9gvv-qjj3-2p6g: OK: reviewed:", out)

    def test_all_ok_exits_0(self):
        code, out = self._run(["GHSA-9gvv-qjj3-2p6g"])
        self.assertEqual(code, 0)

    def test_failure_only_exits_2(self):
        code, out = self._run(["GHSA-9gvv-qjj3-2p6g", "GHSA-zzzz-zzzz-zzzz"])
        self.assertEqual(code, 2)
        self.assertIn("LOOKUP_FAILED", out)

    def test_file_and_json(self):
        path = os.path.join(tempfile.mkdtemp(), "saved.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([FLOWISE_REVIEWED, WITHDRAWN], fh)
        code, out = self._run(["--file", path, "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual([r["status"] for r in data], ["ok", "withdrawn"])


if __name__ == "__main__":
    unittest.main()
