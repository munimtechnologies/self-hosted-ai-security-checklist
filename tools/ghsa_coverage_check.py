#!/usr/bin/env python3
"""ghsa_coverage_check: show whether an advisory can reach Dependabot through the GitHub Advisory Database.

Dependabot (and other tools that read the GitHub Advisory Database) only alert on an
advisory that is in the global database and names a package in a supported ecosystem
with a version range. Two common gaps:
  - a published repository advisory (github.com/<owner>/<repo>/security/advisories/GHSA-...)
    that GitHub's curators haven't imported yet: the global API returns 404;
  - an unreviewed advisory made from a CVE record with no package listed.
Anyone can fix the second kind by suggesting a package at
https://github.com/advisories/<GHSA-ID>/improve, which opens a pull request to
github/advisory-database.

Usage:
    python ghsa_coverage_check.py GHSA-mjgh-prrr-9qw5 GHSA-cffm-583c-vffr
    python ghsa_coverage_check.py CVE-2026-100607
    python ghsa_coverage_check.py --json GHSA-9gvv-qjj3-2p6g
    python ghsa_coverage_check.py --file advisory.json   # check a saved API response, offline

Read-only: it only GETs https://api.github.com/advisories, without a token (GitHub allows
60 unauthenticated requests an hour). Standard library only.
Exit code 0 = every advisory can reach Dependabot (or is withdrawn), 1 = at least one gap,
2 = a lookup failed.

Written by MV2 of Munim, Inc., an AI. MIT licence.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com/advisories"
GHSA_RE = re.compile(r"^GHSA(-[0-9a-z]{4}){3}$", re.IGNORECASE)
CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)


def normalise(vuln_id):
    """GHSA IDs as GHSA-xxxx-xxxx-xxxx, CVE IDs upper case; anything else unchanged."""
    vuln_id = vuln_id.strip()
    if GHSA_RE.match(vuln_id):
        return "GHSA-" + vuln_id[5:].lower()
    if CVE_RE.match(vuln_id):
        return vuln_id.upper()
    return vuln_id


def _packages(advisory):
    """Return [ecosystem, name, vulnerable range, first patched or None] for each listed package."""
    out = []
    for vuln in advisory.get("vulnerabilities") or []:
        pkg = vuln.get("package") or {}
        if not pkg.get("name"):
            continue
        patched = vuln.get("first_patched_version")
        if isinstance(patched, dict):  # older API responses nest it
            patched = patched.get("identifier")
        out.append([pkg.get("ecosystem") or "?", pkg["name"],
                    vuln.get("vulnerable_version_range") or "", patched or None])
    return out


def _describe(pkg):
    ecosystem, name, rng, patched = pkg
    return "%s %s %s (%s)" % (ecosystem, name, rng or "with no range",
                              "patched in %s" % patched if patched else "no patched version")


def classify(advisory, asked=None):
    """Return one result dict for an advisory from the global API. Pure; no network."""
    ghsa = advisory.get("ghsa_id") or asked or "?"
    kind = advisory.get("type") or "?"
    packages = _packages(advisory)
    result = {"id": asked or ghsa, "ghsa_id": ghsa, "type": kind, "packages": packages}
    if advisory.get("withdrawn_at"):
        result.update(status="withdrawn", gap=False,
                      message="withdrawn on %s" % str(advisory["withdrawn_at"])[:10])
    elif not packages:
        result.update(status="no_package", gap=True,
                      message="%s advisory with no package, so Dependabot can't alert on it; "
                              "suggest one at https://github.com/advisories/%s/improve" % (kind, ghsa))
    elif any(not p[2] for p in packages):
        result.update(status="no_range", gap=True,
                      message="%s advisory with a package but no version range: %s"
                              % (kind, "; ".join(_describe(p) for p in packages)))
    else:
        result.update(status="ok", gap=False,
                      message="%s: %s" % (kind, "; ".join(_describe(p) for p in packages)))
    return result


def not_found(vuln_id):
    return {"id": vuln_id, "ghsa_id": vuln_id if vuln_id.startswith("GHSA-") else None,
            "type": None, "packages": [], "status": "not_in_database", "gap": True,
            "message": "not in the global GitHub Advisory Database, so Dependabot can't alert on it "
                       "(a published repository advisory may still be waiting for GitHub's curators)"}


def _get(url, timeout):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ghsa-coverage-check (MV2 of Munim, Inc.)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def lookup(vuln_id, timeout=20):
    """Return (advisories, None); ([], None) if the database has none; (None, reason) on failure."""
    try:
        if vuln_id.startswith("CVE-"):
            data = _get(API + "?cve_id=" + urllib.parse.quote(vuln_id), timeout)
            return list(data or []), None
        return [_get(API + "/" + urllib.parse.quote(vuln_id), timeout)], None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return [], None
        return None, "HTTP %d" % exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, str(exc)


def check(ids=(), files=(), lookup_fn=lookup):
    """Return (results, failed) for IDs looked up online and saved API responses."""
    results, failed = [], False
    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for advisory in data if isinstance(data, list) else [data]:
            results.append(classify(advisory))
    for raw in ids:
        vuln_id = normalise(raw)
        found, err = lookup_fn(vuln_id)
        if found is None:
            failed = True
            results.append({"id": vuln_id, "ghsa_id": None, "type": None, "packages": [],
                            "status": "lookup_failed", "gap": False, "message": "lookup failed (%s)" % err})
        elif not found:
            results.append(not_found(vuln_id))
        else:
            results.extend(classify(advisory, vuln_id) for advisory in found)
    return results, failed


def main(argv=None, lookup_fn=lookup):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ids", nargs="*", help="GHSA or CVE IDs")
    parser.add_argument("--file", action="append", default=[], help="check a saved api.github.com/advisories response")
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(argv)
    if not args.ids and not args.file:
        parser.error("give at least one ID or --file")

    results, failed = check(args.ids, args.file, lookup_fn)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            label = r["id"]
            if r["ghsa_id"] and r["ghsa_id"] != r["id"]:
                label += " (%s)" % r["ghsa_id"]
            print("%s: %s: %s" % (label, r["status"].upper(), r["message"]))

    if any(r["gap"] for r in results):
        return 1
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
