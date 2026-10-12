#!/usr/bin/env python
"""Sync the self-contained Upwork Copilot *skill* bundle from the canonical source.

The skill (`skill/`) ships a standalone, LLM-free copy of just the data layer so
it can be installed and published without the full CrewAI project. To avoid
hand-maintaining two copies, the Python files live canonically in
`src/upwork_agent/` and are *generated* into the skill bundle by this script.

Run it after fixing anything in the shared data layer:

    python build_skill.py            # copy the canonical files into skill/
    python build_skill.py --check    # fail (non-zero) if the bundle is stale

Only the no-LLM closure is copied (see SKILL_MODULES). The script also verifies
that none of those files import a module outside that closure, so the bundle can
never silently start depending on the CrewAI stack.
"""
from __future__ import annotations

import argparse
import ast
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "upwork_agent"
DEST = ROOT / "upwork-copilot" / "skills" / "upwork-copilot" / "scripts" / "upwork_agent"

# The exact closure the skill CLI needs — nothing from the LLM/agent side.
SKILL_MODULES = [
    "__init__.py",
    "config.py",
    "scoring.py",
    "auth.py",
    "upwork_client.py",
    "queries.py",
    "skill_cli.py",
]
_ALLOWED = {m[:-3] for m in SKILL_MODULES if m.endswith(".py")}


def _internal_imports(path: Path) -> set[str]:
    """Relative (intra-package) module names imported by a file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            # e.g. `from .auth import x` -> "auth"; `from . import queries` is handled below
            found.add(node.module.split(".")[0])
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            for alias in node.names:  # `from . import queries`
                found.add(alias.name.split(".")[0])
    return found


def _verify_closure() -> list[str]:
    problems: list[str] = []
    for name in SKILL_MODULES:
        if not name.endswith(".py"):
            continue
        path = SRC / name
        if not path.exists():
            problems.append(f"missing source file: {path}")
            continue
        stray = _internal_imports(path) - _ALLOWED
        if stray:
            problems.append(
                f"{name} imports {sorted(stray)} which are not in the skill closure "
                f"(SKILL_MODULES). Either add them to the bundle or decouple."
            )
    return problems


def _is_stale() -> bool:
    for name in SKILL_MODULES:
        src, dest = SRC / name, DEST / name
        if not dest.exists() or not filecmp.cmp(src, dest, shallow=False):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit non-zero if the bundle is out of date")
    args = ap.parse_args(argv)

    problems = _verify_closure()
    if problems:
        print("✗ skill closure check failed:")
        for p in problems:
            print(f"  - {p}")
        return 2

    if args.check:
        stale = _is_stale()
        print("✗ skill bundle is STALE — run `python build_skill.py`" if stale else "✓ skill bundle is up to date")
        return 1 if stale else 0

    DEST.mkdir(parents=True, exist_ok=True)
    for name in SKILL_MODULES:
        shutil.copy2(SRC / name, DEST / name)
    print(f"✓ synced {len(SKILL_MODULES)} files -> {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
