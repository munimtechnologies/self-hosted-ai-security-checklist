"""Offline tests for osv_record_check. Fixtures are trimmed copies of real OSV.dev
records as published on 13 October 2026 (no network access needed)."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osv_record_check as orc  # noqa: E402

# CVE-2026-100607: VulnCheck says "through 3.1.4", no patch; OSV's range has a "fixed" commit.
FLOWISE = {
    "id": "CVE-2026-100607",
    "summary": "Flowise through 3.1.4 Authentication Bypass via Email-Only SSO",
    "details": "Flowise through 3.1.4 identifies SSO and local-password users by email alone.",
    "affected": [{
        "ranges": [{
            "type": "GIT",
            "repo": "https://github.com/flowiseai/flowise",
            "events": [{"introduced": "0"}, {"fixed": "a65f81bb43ef66d3ce734bf0dff4223ae8041c95"}],
            "database_specific": {
                "source": ["AFFECTED_FIELD", "DESCRIPTION"],
                "extracted_events": [{"introduced": "0"}, {"last_affected": "3.1.4"}, {"fixed": "3.1.4"}],
            },
        }],
        "versions": ["flowise@3.1.3", "flowise@3.1.2", "flowise-ui@3.1.3"],
    }],
}

# CVE-2026-96560: same pattern, tags with a leading v.
LIGHTLLM = {
    "id": "CVE-2026-96560",
    "summary": "LightLLM through 1.2.0 Unauthenticated Remote Code Execution via NCCL PD RPyC Control Channel",
    "affected": [{
        "ranges": [{
            "type": "GIT",
            "repo": "https://github.com/modeltc/lightllm",
            "events": [{"introduced": "0"}, {"fixed": "65c174ee95ac6a6fd36b18b63d0b33d97e76b770"}],
            "database_specific": {
                "source": ["AFFECTED_FIELD", "DESCRIPTION"],
                "extracted_events": [{"introduced": "0"}, {"last_affected": "1.2.0"}, {"fixed": "1.2.0"}],
            },
        }],
        "versions": ["v1.1.0", "v1.0.1", "v1.0.0"],
    }],
}

# CVE-2026-96673: "through 2.4.0" extracted as fixed 2.4.0, but real fix commits came
# from the references and v2.4.0 is still in the versions list, so it's only informational.
PHOTOVIEW = {
    "id": "CVE-2026-96673",
    "summary": "Photoview through 2.4.0 SQL Injection via album download route",
    "affected": [{
        "ranges": [{
            "type": "GIT",
            "repo": "https://github.com/photoview/photoview",
            "events": [{"introduced": "0"}, {"fixed": "f79d379e38241c687c55e9f899e30661fd9f115a"}],
            "database_specific": {
                "source": ["DESCRIPTION", "REFERENCES"],
                "extracted_events": [{"introduced": "0"}, {"fixed": "2.4.0"}],
            },
        }],
        "versions": ["v2.4.0", "v2.3.13", "v2.3.12"],
    }],
}

# CVE-2026-45312: a correct record (last_affected only).
RAGFLOW_OK = {
    "id": "CVE-2026-45312",
    "summary": "RAGFlow Server-Side Template Injection in Prompt Generator",
    "affected": [{
        "ranges": [{
            "type": "GIT",
            "repo": "https://github.com/infiniflow/ragflow",
            "events": [{"introduced": "0"}, {"last_affected": "392ec99651da78f6a8e1a2f60fe4818a95a8651d"}],
            "database_specific": {
                "source": "AFFECTED_FIELD",
                "extracted_events": [{"introduced": "0"}, {"last_affected": "0.24.0"}],
            },
        }],
        "versions": ["v0.24.0", "nightly", "v0.23.1"],
    }],
}

# A correct ECOSYSTEM record where "before" is used and the fixed version is real.
ECOSYSTEM_OK = {
    "id": "GHSA-xxxx-yyyy-zzzz",
    "summary": "Example before 1.4.7",
    "affected": [{
        "package": {"name": "example", "ecosystem": "PyPI"},
        "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "1.4.7"}]}],
        "versions": ["1.4.5", "1.4.6"],
    }],
}


class CheckRecordTests(unittest.TestCase):
    def test_flowise_is_suspect_once(self):
        findings = orc.check_record(FLOWISE)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["kind"], "fixed_equals_last_affected")
        self.assertEqual(f["version"], "3.1.4")
        self.assertEqual(f["severity"], "suspect")
        self.assertEqual(f["where"], "https://github.com/flowiseai/flowise")

    def test_lightllm_is_suspect(self):
        findings = orc.check_record(LIGHTLLM)
        self.assertEqual([(f["version"], f["severity"]) for f in findings], [("1.2.0", "suspect")])

    def test_photoview_is_info_only(self):
        findings = orc.check_record(PHOTOVIEW)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "through_read_as_fixed")
        self.assertEqual(findings[0]["version"], "2.4.0")
        self.assertEqual(findings[0]["severity"], "info")

    def test_correct_records_have_no_findings(self):
        self.assertEqual(orc.check_record(RAGFLOW_OK), [])
        self.assertEqual(orc.check_record(ECOSYSTEM_OK), [])

    def test_unresolved_ranges_are_checked(self):
        record = {
            "id": "CVE-0000-0001",
            "summary": "Thing through 2.0",
            "affected": [],
            "database_specific": {"unresolved_ranges": [
                {"extracted_events": [{"introduced": "0"}, {"fixed": "2.0"}]},
            ]},
        }
        findings = orc.check_record(record)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "through_read_as_fixed")
        self.assertEqual(findings[0]["severity"], "suspect")

    def test_trailing_period_and_v_prefix(self):
        record = {
            "id": "CVE-0000-0002",
            "details": "Affects Thing through v3.0.",
            "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "v3.0"}]}]}],
        }
        findings = orc.check_record(record)
        self.assertEqual([f["version"] for f in findings], ["3.0"])

    def test_listed_handles_package_prefixes(self):
        self.assertTrue(orc._listed("3.1.3", ["flowise@3.1.3"]))
        self.assertTrue(orc._listed("1.1.0", ["v1.1.0"]))
        self.assertFalse(orc._listed("3.1.4", ["flowise@3.1.3", "3.1.40"]))


class MainTests(unittest.TestCase):
    def _run(self, records, extra=()):
        paths = []
        tmp = tempfile.mkdtemp()
        for i, rec in enumerate(records):
            path = os.path.join(tmp, "r%d.json" % i)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh)
            paths += ["--file", path]
        out = io.StringIO()
        with redirect_stdout(out):
            code = orc.main(paths + list(extra))
        return code, out.getvalue()

    def test_exit_1_and_text_for_suspect(self):
        code, out = self._run([FLOWISE, RAGFLOW_OK])
        self.assertEqual(code, 1)
        self.assertIn("CVE-2026-100607: SUSPECT:", out)
        self.assertIn("CVE-2026-45312: ok", out)

    def test_info_only_exits_0(self):
        code, out = self._run([PHOTOVIEW])
        self.assertEqual(code, 0)
        self.assertIn("INFO", out)

    def test_json_output(self):
        code, out = self._run([LIGHTLLM], extra=["--json"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data[0]["id"], "CVE-2026-96560")
        self.assertEqual(data[0]["findings"][0]["version"], "1.2.0")


if __name__ == "__main__":
    unittest.main()
