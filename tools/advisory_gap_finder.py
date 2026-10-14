#!/usr/bin/env python3
"""advisory_gap_finder: list GitHub Advisory Database records that Dependabot can't alert on, and how to fix each.

Many CVE records reach the GitHub Advisory Database as unreviewed advisories with no package
listed, so Dependabot, `npm audit` and other tools that read the database never alert on them.
Often the project has published its own repository advisory for the same bug
(github.com/<owner>/<repo>/security/advisories/GHSA-...) naming the package and versions, but
GitHub's curators haven't imported it yet. This script reads a local clone of
github/advisory-database and sorts every unreviewed record with no package into:
  upstream_not_imported  it cites a repository advisory that isn't a reviewed advisory in the
                         database: copy that advisory's packages and versions into the record
  duplicate              its CVE, or the repository advisory it cites, is already in a reviewed
                         advisory, so Dependabot covers it under that ID
  no_upstream            it cites no repository advisory: the package has to be found by hand
Fixes go through https://github.com/advisories/<GHSA-ID>/improve, which opens a pull request.
Records with no summary are flagged, because that form also requires a Title.

Usage:
    git clone --depth 1 https://github.com/github/advisory-database
    python advisory_gap_finder.py advisory-database --since 2026-08-01 --severity critical,high
    python advisory_gap_finder.py advisory-database --repo FlowiseAI/Flowise --json
    python advisory_gap_finder.py advisory-database --summary

Offline and read-only: it only reads the JSON files. Standard library only.
Exit code 0 = nothing listed, 1 = at least one record listed.

Written by MV2 of Munim, Inc., with AI agents. Apache-2.0 licence.
"""

import argparse
import json
import os
import re
import sys

UPSTREAM_RE = re.compile(
    r"^https?://github\.com/([^/\s]+)/([^/\s]+)/security/advisories/(GHSA(?:-[0-9a-z]{4}){3})(?![0-9a-z])",
    re.IGNORECASE)
REPO_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)", re.IGNORECASE)
NOT_REPOS = {"advisories", "orgs", "users", "search", "sponsors", "settings", "topics", "marketplace"}
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
IMPROVE = "https://github.com/advisories/%s/improve"


def normalise_ghsa(ghsa):
    """GHSA IDs as GHSA-xxxx-xxxx-xxxx."""
    return "GHSA-" + ghsa.strip()[5:].lower()


def is_reviewed(record, path=""):
    flag = (record.get("database_specific") or {}).get("github_reviewed")
    if flag is not None:
        return bool(flag)
    return "github-reviewed" in path.replace("\\", "/").split("/")


def has_package(record):
    return any(isinstance(a, dict) and (a.get("package") or {}).get("name")
               for a in record.get("affected") or [])


def _slim(record):
    """Keep only what classify() needs, so a full clone fits in memory."""
    own = normalise_ghsa(record["id"])
    upstream, repos = [], []
    for ref in record.get("references") or []:
        url = str(ref.get("url") or "") if isinstance(ref, dict) else ""
        m = UPSTREAM_RE.match(url)
        if m:
            ghsa = normalise_ghsa(m.group(3))
            if ghsa != own and ghsa not in [u[1] for u in upstream]:
                upstream.append(["%s/%s" % (m.group(1), m.group(2)), ghsa])
            continue
        m = REPO_RE.match(url)
        if m and m.group(1).lower() not in NOT_REPOS:
            repos.append("%s/%s" % (m.group(1), re.sub(r"\.git$", "", m.group(2))))
    return {"ghsa_id": own,
            "aliases": [a.strip().upper() for a in record.get("aliases") or [] if isinstance(a, str)],
            "published": str(record.get("published") or "")[:10],
            "severity": str((record.get("database_specific") or {}).get("severity") or "").upper(),
            "summary": str(record.get("summary") or "").strip(),
            "repo": upstream[0][0] if upstream else (repos[0] if repos else None),
            "upstream": upstream}


def scan(root, since=None):
    """Read every advisory JSON file under root.

    Returns (index, candidates, skipped): index holds the reviewed GHSA IDs and a CVE -> reviewed
    GHSA map, candidates are the unreviewed records with no package, skipped counts unreadable files."""
    index = {"reviewed": set(), "cve": {}}
    candidates, skipped = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        if since and os.path.basename(dirpath) == "unreviewed":
            # Unreviewed records sit under <year>/<month>/ by publish date: skip years before --since.
            dirnames[:] = [d for d in dirnames if not (len(d) == 4 and d.isdigit() and d < since[:4])]
        for name in sorted(filenames):
            if not name.endswith(".json"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                skipped += 1
                continue
            if not isinstance(data, dict) or not str(data.get("id") or "").upper().startswith("GHSA-"):
                continue
            if data.get("withdrawn"):
                continue
            ghsa = normalise_ghsa(data["id"])
            if is_reviewed(data, path):
                index["reviewed"].add(ghsa)
                for alias in data.get("aliases") or []:
                    if isinstance(alias, str) and alias.strip().upper().startswith("CVE-"):
                        index["cve"].setdefault(alias.strip().upper(), []).append(ghsa)
            elif not has_package(data):
                candidates.append(_slim(data))
    return index, candidates, skipped


def classify(cand, index):
    """Return the candidate with status, duplicate_of, needs_title, improve_url and message added. Pure."""
    dup = []
    for alias in cand["aliases"]:
        dup.extend(g for g in index["cve"].get(alias, []) if g not in dup)
    for _repo, ghsa in cand["upstream"]:
        if ghsa in index["reviewed"] and ghsa not in dup:
            dup.append(ghsa)
    missing = [u for u in cand["upstream"] if u[1] not in index["reviewed"]]
    row = dict(cand, duplicate_of=dup, needs_title=not cand["summary"], improve_url=IMPROVE % cand["ghsa_id"])
    if dup:
        row.update(status="duplicate",
                   message="already in reviewed advisory %s, which Dependabot uses; nothing to add here"
                           % ", ".join(dup))
    elif missing:
        row.update(status="upstream_not_imported",
                   message="repository advisory %s isn't in the database; copy its packages and versions into %s"
                           % (", ".join("https://github.com/%s/security/advisories/%s" % (r, g) for r, g in missing),
                              row["improve_url"]))
    else:
        row.update(status="no_upstream",
                   message="no repository advisory cited; find the package and versions, then suggest them at %s"
                           % row["improve_url"])
    if row["needs_title"] and row["status"] != "duplicate":
        row["message"] += " (the record has no summary, so the form also needs a Title)"
    return row


def find_gaps(index, candidates, repos=(), since=None, severities=(), statuses=()):
    """Classify and filter candidates; most severe first, then newest first."""
    wanted = {r.strip().lower() for r in repos if r.strip()}
    rows = []
    for cand in candidates:
        if since and cand["published"] < since:
            continue
        if severities and cand["severity"] not in severities:
            continue
        if wanted and not wanted & {r.lower() for r in [cand["repo"] or ""] + [u[0] for u in cand["upstream"]]}:
            continue
        row = classify(cand, index)
        if statuses and row["status"] not in statuses:
            continue
        rows.append(row)
    rows.sort(key=lambda r: r["ghsa_id"])
    rows.sort(key=lambda r: r["published"], reverse=True)
    rows.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
    return rows


def summarise(rows):
    """Return [(repo, total, {status: count})], biggest first."""
    by_repo = {}
    for r in rows:
        counts = by_repo.setdefault(r["repo"] or "(no GitHub repo cited)", {})
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out = [(repo, sum(c.values()), c) for repo, c in by_repo.items()]
    out.sort(key=lambda t: (-t[1], t[0].lower()))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", help="a local clone of github/advisory-database (or any folder of its JSON files)")
    parser.add_argument("--repo", action="append", default=[], help="only records citing this GitHub repo (owner/name)")
    parser.add_argument("--since", help="only records published on or after this date (YYYY-MM-DD)")
    parser.add_argument("--severity", default="", help="comma-separated: critical,high,moderate,low")
    parser.add_argument("--status", default="", help="comma-separated: upstream_not_imported,duplicate,no_upstream")
    parser.add_argument("--summary", action="store_true", help="print counts per repository instead of each record")
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.root):
        parser.error("not a folder: %s" % args.root)
    if args.since and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.since):
        parser.error("--since needs YYYY-MM-DD")

    severities = {s.strip().upper() for s in args.severity.split(",") if s.strip()}
    statuses = {s.strip().lower() for s in args.status.split(",") if s.strip()}
    index, candidates, skipped = scan(args.root, args.since)
    rows = find_gaps(index, candidates, args.repo, args.since, severities, statuses)

    if args.summary:
        table = summarise(rows)
        if args.json:
            print(json.dumps([{"repo": r, "total": t, "by_status": c} for r, t, c in table], indent=2))
        else:
            for repo, total, counts in table:
                print("%s: %d (%s)" % (repo, total, ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    elif args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            cves = ", ".join(a for a in r["aliases"] if a.startswith("CVE-"))
            print("%s %s %s%s %s: %s: %s" % (r["severity"] or "?", r["published"] or "?", r["ghsa_id"],
                                             " (%s)" % cves if cves else "", r["repo"] or "-",
                                             r["status"].upper(), r["message"]))
    if skipped:
        print("skipped %d unreadable file(s)" % skipped, file=sys.stderr)
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
