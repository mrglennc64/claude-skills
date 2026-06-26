#!/usr/bin/env python3
"""
verify-claim.py

Scans source files for UNVERIFIED markers left by the zero-hallucination-coder
workflow and reports them. Exits non-zero when any unverified claims are found
so CI can block merges.

Usage:
    python3 verify-claim.py --src ./src --ext py,ts,tsx,js
    python3 verify-claim.py --src . --json > report.json
    python3 verify-claim.py --help
"""

import argparse
import json
import os
import re
import sys

# Marker patterns this tool searches for
UNVERIFIED_RE = re.compile(r"UNVERIFIED\b", re.IGNORECASE)
VERIFIED_RE = re.compile(r"#\s*verified\s*:", re.IGNORECASE)
TODO_VERIFY_RE = re.compile(r"TODO.*verif", re.IGNORECASE)

# Severity scoring
SEVERITY = {
    "UNVERIFIED": "error",     # blocks merge
    "TODO_VERIFY": "warning",  # should be resolved before release
}


def scan_file(filepath: str, verbose: bool) -> list[dict]:
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        if verbose:
            print(f"  [skip] {filepath}: {exc}", file=sys.stderr)
        return findings

    for lineno, line in enumerate(lines, 1):
        if UNVERIFIED_RE.search(line):
            findings.append({
                "file": filepath,
                "line": lineno,
                "severity": SEVERITY["UNVERIFIED"],
                "type": "UNVERIFIED",
                "text": line.strip(),
            })
        elif TODO_VERIFY_RE.search(line) and not VERIFIED_RE.search(line):
            findings.append({
                "file": filepath,
                "line": lineno,
                "severity": SEVERITY["TODO_VERIFY"],
                "type": "TODO_VERIFY",
                "text": line.strip(),
            })

    return findings


def count_verified(filepath: str) -> int:
    count = 0
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if VERIFIED_RE.search(line):
                    count += 1
    except OSError:
        pass
    return count


def walk_tree(src: str, extensions: set) -> list:
    matched = []
    for dirpath, _dirs, filenames in os.walk(src):
        # Skip hidden dirs and common noise
        _dirs[:] = [d for d in _dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "dist", "build")]
        for fname in filenames:
            ext = fname.rsplit(".", 1)[-1] if "." in fname else ""
            if ext in extensions:
                matched.append(os.path.join(dirpath, fname))
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find UNVERIFIED claim markers left by the zero-hallucination-coder workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--src", default=".", help="Root directory to scan (default: .)")
    parser.add_argument(
        "--ext",
        default="py,ts,tsx,js,jsx,go,rb,java",
        help="Comma-separated extensions to scan",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--verbose", action="store_true", help="Show per-file progress")
    args = parser.parse_args()

    extensions = {e.strip().lstrip(".") for e in args.ext.split(",")}
    files = walk_tree(args.src, extensions)

    if args.verbose and not args.json:
        print(f"Scanning {len(files)} file(s)…", file=sys.stderr)

    all_findings: list[dict] = []
    total_verified = 0
    for filepath in files:
        if args.verbose and not args.json:
            print(f"  {filepath}", file=sys.stderr)
        all_findings.extend(scan_file(filepath, args.verbose))
        total_verified += count_verified(filepath)

    errors = [f for f in all_findings if f["severity"] == "error"]
    warnings = [f for f in all_findings if f["severity"] == "warning"]

    if args.json:
        print(json.dumps({
            "scanned_files": len(files),
            "verified_annotations": total_verified,
            "errors": len(errors),
            "warnings": len(warnings),
            "findings": all_findings,
        }, indent=2))
        return 1 if errors else 0

    if not all_findings:
        print(f"All clear. {total_verified} verified annotation(s) found across {len(files)} file(s).")
        return 0

    if errors:
        print(f"\n{len(errors)} UNVERIFIED claim(s) — must be resolved before merging:\n")
        for f in errors:
            print(f"  ERROR  {f['file']}:{f['line']}")
            print(f"         {f['text']}\n")

    if warnings:
        print(f"\n{len(warnings)} TODO-verify warning(s):\n")
        for f in warnings:
            print(f"  WARN   {f['file']}:{f['line']}")
            print(f"         {f['text']}\n")

    print(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s), {total_verified} verified annotation(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
