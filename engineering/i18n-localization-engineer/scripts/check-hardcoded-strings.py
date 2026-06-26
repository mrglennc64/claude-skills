#!/usr/bin/env python3
"""
check-hardcoded-strings.py

Walks a source tree and reports user-visible string literals that appear to
bypass an i18n layer. Skips log statements, developer comments, URLs, internal
IDs, and strings under 3 characters.

Usage:
    python3 check-hardcoded-strings.py --src ./src --ext tsx,ts,jsx,js
    python3 check-hardcoded-strings.py --src ./src --json > audit.json
    python3 check-hardcoded-strings.py --help
"""

import argparse
import ast
import json
import os
import re
import sys

# Patterns that indicate a string is NOT user-visible
SKIP_PATTERNS = [
    re.compile(r"^https?://"),          # URLs
    re.compile(r"^[a-z0-9._-]+$"),      # IDs, keys, slugs
    re.compile(r"^\s*$"),               # whitespace-only
    re.compile(r"^[A-Z_]+$"),           # ALL_CAPS constants
    re.compile(r"^#[0-9a-fA-F]{3,8}$"), # CSS colours
    re.compile(r"^\d+(\.\d+)?$"),       # pure numbers
    re.compile(r"^\w+\.\w+"),           # dotted identifiers (module.method)
]

# Call-site patterns that look like i18n usage (skip these)
I18N_CALL_PATTERNS = [
    re.compile(r"\bt\s*\("),
    re.compile(r"\bi18n\s*\("),
    re.compile(r"formatMessage\s*\("),
    re.compile(r"intl\.formatMessage"),
    re.compile(r"gettext\s*\("),
    re.compile(r"_\s*\("),              # Python gettext shorthand
    re.compile(r"ngettext\s*\("),
    re.compile(r"FormattedMessage"),
    re.compile(r"useTranslation"),
    re.compile(r"useIntl"),
]

# Lines that contain these tokens are almost certainly non-user-visible
LOG_TOKENS = ("console.", "logger.", "logging.", "print(", "debug(", "warn(", "error(", "trace(")


def is_log_line(line: str) -> bool:
    stripped = line.strip()
    return any(tok in stripped for tok in LOG_TOKENS)


def is_i18n_line(line: str) -> bool:
    return any(pat.search(line) for pat in I18N_CALL_PATTERNS)


def should_skip_string(s: str) -> bool:
    if len(s) < 3:
        return True
    return any(pat.search(s) for pat in SKIP_PATTERNS)


def extract_js_strings(filepath: str) -> list[dict]:
    """Regex-based extraction for JS/TS/JSX/TSX files."""
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return findings

    # Match single/double/template literals (non-greedy, single line)
    string_re = re.compile(r"""(?P<q>["'`])(?P<text>(?:\\.|[^\\])*?)(?P=q)""")

    for lineno, line in enumerate(lines, 1):
        if line.strip().startswith("//") or line.strip().startswith("*"):
            continue
        if is_log_line(line) or is_i18n_line(line):
            continue
        for m in string_re.finditer(line):
            text = m.group("text")
            if should_skip_string(text):
                continue
            # Heuristic: must contain at least one space or mixed case to look like prose
            if " " not in text and text == text.lower():
                continue
            findings.append({"file": filepath, "line": lineno, "string": text})

    return findings


def extract_py_strings(filepath: str) -> list[dict]:
    """AST-based extraction for Python files."""
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=filepath)
    except (OSError, SyntaxError):
        return findings

    lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        if should_skip_string(text):
            continue
        lineno = node.lineno
        raw_line = lines[lineno - 1] if lineno <= len(lines) else ""
        if is_log_line(raw_line) or is_i18n_line(raw_line):
            continue
        if " " not in text and text == text.lower():
            continue
        findings.append({"file": filepath, "line": lineno, "string": text})

    return findings


def walk_tree(src: str, extensions: set[str]) -> list[str]:
    matched = []
    for dirpath, _dirnames, filenames in os.walk(src):
        for fname in filenames:
            ext = fname.rsplit(".", 1)[-1] if "." in fname else ""
            if ext in extensions:
                matched.append(os.path.join(dirpath, fname))
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect hardcoded user-visible strings that bypass an i18n layer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--src", default=".", help="Root directory to scan (default: .)")
    parser.add_argument(
        "--ext",
        default="tsx,ts,jsx,js,py",
        help="Comma-separated list of file extensions to scan (default: tsx,ts,jsx,js,py)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--verbose", action="store_true", help="Include per-file progress")
    args = parser.parse_args()

    extensions = {e.strip().lstrip(".") for e in args.ext.split(",")}
    files = walk_tree(args.src, extensions)

    if args.verbose and not args.json:
        print(f"Scanning {len(files)} file(s) in '{args.src}'…", file=sys.stderr)

    all_findings: list[dict] = []
    for filepath in files:
        if args.verbose and not args.json:
            print(f"  {filepath}", file=sys.stderr)
        ext = filepath.rsplit(".", 1)[-1]
        if ext == "py":
            all_findings.extend(extract_py_strings(filepath))
        else:
            all_findings.extend(extract_js_strings(filepath))

    if args.json:
        output = {
            "total": len(all_findings),
            "scanned_files": len(files),
            "findings": all_findings,
        }
        print(json.dumps(output, indent=2))
        return 0 if not all_findings else 1

    if not all_findings:
        print("No hardcoded user-visible strings detected.")
        return 0

    print(f"Found {len(all_findings)} potential hardcoded string(s):\n")
    for f in all_findings:
        print(f"  {f['file']}:{f['line']}  →  {f['string']!r}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
