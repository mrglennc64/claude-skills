#!/usr/bin/env python3
"""
verify-cross-tool.py

Verifies that a skill directory is correctly installed and loadable across
the formats supported by the claude-skills repository:
  - Claude Code (.claude-plugin/plugin.json)
  - Codex (.codex/<skill-name>.md)
  - Gemini CLI (.gemini/<skill-name>.md)
  - Cursor (.cursorrules fragment)
  - Hermes/Vibe (raw SKILL.md)

Run this before opening a PR or after running a sync script to confirm that
all target formats are present and structurally valid.

Usage:
    python3 verify-cross-tool.py --skill engineering/docker-development
    python3 verify-cross-tool.py --skill engineering/docker-development --json
    python3 verify-cross-tool.py --all-skills --root .
    python3 verify-cross-tool.py --help
"""

import argparse
import json
import os
import re
import sys

# ------------------------------------------------------------------
# Required SKILL.md frontmatter fields (only these two are allowed)
# ------------------------------------------------------------------
REQUIRED_FRONTMATTER = {"name", "description"}
FORBIDDEN_FRONTMATTER = {"license", "metadata", "triggers", "version", "author", "category", "updated"}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
YAML_KEY_RE = re.compile(r"^(\w+)\s*:", re.MULTILINE)


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    keys = YAML_KEY_RE.findall(m.group(1))
    return {k: True for k in keys}


def check_skill_md(skill_dir: str) -> list[dict]:
    """Validate the canonical SKILL.md."""
    issues = []
    skill_md = os.path.join(skill_dir, "SKILL.md")

    if not os.path.isfile(skill_md):
        issues.append({"tool": "SKILL.md", "severity": "error", "message": "SKILL.md not found"})
        return issues

    with open(skill_md, encoding="utf-8", errors="replace") as fh:
        content = fh.read()
        lines = content.splitlines()

    # Frontmatter
    fm = parse_frontmatter(content)
    missing = REQUIRED_FRONTMATTER - set(fm)
    extra = set(fm) & FORBIDDEN_FRONTMATTER
    if missing:
        issues.append({"tool": "SKILL.md", "severity": "error", "message": f"Missing frontmatter fields: {sorted(missing)}"})
    if extra:
        issues.append({"tool": "SKILL.md", "severity": "error", "message": f"Forbidden frontmatter fields: {sorted(extra)}"})

    # Line count
    if len(lines) > 500:
        issues.append({
            "tool": "SKILL.md",
            "severity": "warning",
            "message": f"File is {len(lines)} lines; limit is 500. Move verbose content to references/",
        })

    # Required sections
    headings = {line.strip("# ").lower() for line in lines if line.startswith("#")}
    for required in ("anti-patterns", "cross-references", "overview"):
        if not any(required in h for h in headings):
            issues.append({
                "tool": "SKILL.md",
                "severity": "warning",
                "message": f"Missing required section: '{required}'",
            })

    return issues


def check_plugin_json(skill_dir: str) -> list[dict]:
    """Validate Claude Code plugin manifest."""
    issues = []
    plugin_json = os.path.join(skill_dir, ".claude-plugin", "plugin.json")

    if not os.path.isfile(plugin_json):
        issues.append({"tool": "claude-code", "severity": "warning", "message": ".claude-plugin/plugin.json not found (optional but recommended)"})
        return issues

    try:
        with open(plugin_json, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        issues.append({"tool": "claude-code", "severity": "error", "message": f"plugin.json is invalid JSON: {exc}"})
        return issues

    for field in ("name", "description", "skill"):
        if field not in data:
            issues.append({"tool": "claude-code", "severity": "error", "message": f"plugin.json missing required field: '{field}'"})

    skill_ref = data.get("skill", "")
    if skill_ref and not os.path.isfile(os.path.join(skill_dir, skill_ref)):
        issues.append({"tool": "claude-code", "severity": "error", "message": f"plugin.json 'skill' path not found: {skill_ref}"})

    return issues


def check_converted_format(root: str, skill_dir: str, tool_name: str, subdir: str) -> list[dict]:
    """Check that a sync-generated format file exists under <root>/<subdir>/."""
    issues = []
    skill_name = os.path.basename(skill_dir)
    target = os.path.join(root, subdir, f"{skill_name}.md")

    if not os.path.isfile(target):
        issues.append({
            "tool": tool_name,
            "severity": "info",
            "message": f"Converted file not found: {os.path.relpath(target, root)} — run the appropriate sync script",
        })
        return issues

    with open(target, encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    if len(content.strip()) < 50:
        issues.append({"tool": tool_name, "severity": "warning", "message": f"Converted file looks empty: {target}"})

    return issues


def check_python_scripts(skill_dir: str) -> list[dict]:
    """Validate Python scripts under <skill>/scripts/."""
    issues = []
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return issues

    for fname in os.listdir(scripts_dir):
        if not fname.endswith(".py"):
            continue
        script_path = os.path.join(scripts_dir, fname)
        with open(script_path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()

        # Check for pip imports
        pip_re = re.compile(r"^\s*import\s+(requests|numpy|pandas|scipy|sklearn|torch|tensorflow|flask|django|fastapi)\b", re.MULTILINE)
        bad_imports = pip_re.findall(source)
        if bad_imports:
            issues.append({
                "tool": "scripts",
                "severity": "error",
                "message": f"{fname}: non-stdlib imports detected: {bad_imports}. Scripts must use stdlib only.",
            })

        # Check for --help support
        if "argparse" not in source and "sys.argv" not in source:
            issues.append({
                "tool": "scripts",
                "severity": "warning",
                "message": f"{fname}: no argparse or sys.argv found — scripts must support --help",
            })

        # Check for --json flag
        if '"--json"' not in source and "'--json'" not in source:
            issues.append({
                "tool": "scripts",
                "severity": "warning",
                "message": f"{fname}: --json flag not found — scripts must support JSON output",
            })

    return issues


def verify_skill(skill_dir: str, root: str) -> dict:
    """Run all checks for a single skill directory."""
    all_issues: list[dict] = []
    all_issues.extend(check_skill_md(skill_dir))
    all_issues.extend(check_plugin_json(skill_dir))
    all_issues.extend(check_python_scripts(skill_dir))

    # Sync-generated formats (info-only when missing — run sync scripts first)
    all_issues.extend(check_converted_format(root, skill_dir, "codex", ".codex"))
    all_issues.extend(check_converted_format(root, skill_dir, "gemini", ".gemini"))

    errors = sum(1 for i in all_issues if i["severity"] == "error")
    warnings = sum(1 for i in all_issues if i["severity"] == "warning")

    return {
        "skill": os.path.relpath(skill_dir, root),
        "errors": errors,
        "warnings": warnings,
        "issues": all_issues,
        "pass": errors == 0,
    }


def find_all_skills(root: str) -> list[str]:
    """Walk the repo and find all directories containing a SKILL.md."""
    skills = []
    for dirpath, _dirs, filenames in os.walk(root):
        _dirs[:] = [d for d in _dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "scripts", "templates", "docs")]
        if "SKILL.md" in filenames:
            skills.append(dirpath)
    return skills


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify skill installation and format compliance across all supported tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--skill", help="Path to a single skill directory to verify")
    parser.add_argument("--all-skills", action="store_true", help="Verify every skill found under --root")
    parser.add_argument("--root", default=".", help="Repository root (default: .)")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--verbose", action="store_true", help="Show all checks including passing ones")
    args = parser.parse_args()

    if not args.skill and not args.all_skills:
        parser.error("Provide --skill <path> or --all-skills")

    root = os.path.abspath(args.root)

    if args.all_skills:
        skill_dirs = find_all_skills(root)
    else:
        skill_dirs = [os.path.abspath(args.skill)]

    if not skill_dirs:
        print("No skills found.", file=sys.stderr)
        return 1

    results = [verify_skill(sd, root) for sd in skill_dirs]

    if args.json:
        total_errors = sum(r["errors"] for r in results)
        total_warnings = sum(r["warnings"] for r in results)
        print(json.dumps({
            "skills_checked": len(results),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "all_pass": all(r["pass"] for r in results),
            "results": results,
        }, indent=2))
        return 0 if total_errors == 0 else 1

    # Human-readable output
    total_errors = 0
    for r in results:
        total_errors += r["errors"]
        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"] or args.verbose:
            print(f"\n[{status}] {r['skill']}  ({r['errors']} error(s), {r['warnings']} warning(s))")
            for issue in r["issues"]:
                sev = issue["severity"].upper()
                if sev == "INFO" and not args.verbose:
                    continue
                print(f"  {sev:8s} [{issue['tool']}] {issue['message']}")

    passing = sum(1 for r in results if r["pass"])
    print(f"\n{passing}/{len(results)} skill(s) passed. {total_errors} total error(s).")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
