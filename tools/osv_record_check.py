#!/usr/bin/env python3
"""osv_record_check: flag OSV.dev records that may call the last vulnerable version "fixed".

OSV.dev converts CVE records into OSV records. When a CVE says "Product through X"
(X is the last affected version) and no patch exists, the converted record can end up
with X as both last_affected and fixed, so scanners that read OSV treat X as clean.
See google/osv.dev issue #6149.

Usage:
    python osv_record_check.py CVE-2026-100607 CVE-2026-100606
    python osv_record_check.py --json CVE-2026-100607
    python osv_record_check.py --file record.json      # check a saved record, offline

Read-only: it only GETs https://api.osv.dev/v1/vulns/<id>. Standard library only.
Exit code 0 = nothing suspicious, 1 = at least one SUSPECT finding (INFO findings
don't count), 2 = a lookup failed.

Written by MV2 of Munim, Inc., with AI agents. Apache-2.0 licence.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

OSV_URL = "https://api.osv.dev/v1/vulns/"
THROUGH_RE = re.compile(r"\bthrough\s+(?:version\s+)?v?([0-9][\w.+\-]*)", re.IGNORECASE)


def _clean(version):
    """Normalise a version for comparison: strip a leading v and trailing periods."""
    version = str(version).strip().rstrip(".")
    if version[:1] in ("v", "V") and version[1:2].isdigit():
        version = version[1:]
    return version


def _event_versions(events, kind):
    return {_clean(e[kind]) for e in events or [] if isinstance(e, dict) and e.get(kind)}


def _ranges(record):
    """Yield (label, range dict, affected versions or None) for every range,
    plus top-level unresolved ranges (which have no versions list)."""
    for i, affected in enumerate(record.get("affected") or []):
        pkg = (affected.get("package") or {}).get("name") or ""
        versions = affected.get("versions")
        for j, rng in enumerate(affected.get("ranges") or []):
            label = pkg or rng.get("repo") or "affected[%d].ranges[%d]" % (i, j)
            yield label, rng, versions
    top = record.get("database_specific") or {}
    for j, rng in enumerate(top.get("unresolved_ranges") or []):
        if isinstance(rng, dict):
            yield "unresolved_ranges[%d]" % j, rng, None


def _listed(version, versions):
    """True if the record's versions list names this version (tags like v1.2.0 or pkg@1.2.0 count)."""
    for v in versions or []:
        v = str(v)
        if _clean(v) == version or _clean(v.rsplit("@", 1)[-1]) == version:
            return True
    return False


def check_record(record):
    """Return a list of findings (dicts) for one OSV record. Pure; no network."""
    findings = []
    vid = record.get("id", "?")
    text = " ".join(str(record.get(k) or "") for k in ("summary", "details"))
    through = {_clean(v) for v in THROUGH_RE.findall(text)}

    def add(label, versions, kind, version, message):
        # If the versions list still names the version, scanners that match on
        # versions see it as affected; only the range data is off.
        if versions is not None and _listed(version, versions):
            severity = "info"
            message += " (the versions list still includes it, so version matching is unaffected)"
        else:
            severity = "suspect"
        findings.append({"id": vid, "where": label, "kind": kind, "version": version,
                         "severity": severity, "message": message})

    for label, rng, versions in _ranges(record):
        events = rng.get("events") or []
        meta = rng.get("database_specific") or {}
        extracted = meta.get("extracted_events") or []

        for source_name, evs in (("events", events), ("extracted_events", extracted)):
            both = _event_versions(evs, "fixed") & _event_versions(evs, "last_affected")
            for version in sorted(both):
                add(label, versions, "fixed_equals_last_affected", version,
                    "%s lists %s as both last_affected and fixed in %s; "
                    "treat %s as still affected" % (vid, version, source_name, version))

        fixed_any = _event_versions(extracted, "fixed") | _event_versions(events, "fixed")
        for version in sorted(through & fixed_any):
            if any(f["version"] == version and f["where"] == label for f in findings):
                continue
            add(label, versions, "through_read_as_fixed", version,
                "%s text says 'through %s' (so %s is affected) but the record "
                "has fixed %s" % (vid, version, version, version))
    return findings


def fetch(vuln_id, timeout=20):
    """Return (record, None) on success, or (None, reason); a 404 gives (None, 'not in OSV')."""
    req = urllib.request.Request(OSV_URL + vuln_id, headers={"User-Agent": "osv-record-check (MV2 of Munim, Inc.)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp), None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, "not in OSV"
        return None, "HTTP %d" % exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ids", nargs="*", help="OSV, CVE or GHSA IDs")
    parser.add_argument("--file", action="append", default=[], help="check a saved OSV JSON record")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args(argv)
    if not args.ids and not args.file:
        parser.error("give at least one ID or --file")

    results = []
    failed = False
    for path in args.file:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        results.append({"id": record.get("id", path), "status": "checked", "findings": check_record(record)})
    for vuln_id in args.ids:
        record, err = fetch(vuln_id)
        if record is None:
            failed = failed or err != "not in OSV"
            results.append({"id": vuln_id, "status": err, "findings": []})
        else:
            results.append({"id": vuln_id, "status": "checked", "findings": check_record(record)})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            if r["status"] != "checked":
                print("%s: %s" % (r["id"], r["status"]))
            elif not r["findings"]:
                print("%s: ok" % r["id"])
            for f in r["findings"]:
                print("%s: %s: %s" % (r["id"], f["severity"].upper(), f["message"]))

    if any(f["severity"] == "suspect" for r in results for f in r["findings"]):
        return 1
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
