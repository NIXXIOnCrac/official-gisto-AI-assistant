#!/usr/bin/env python3
"""
Local CI runner for the Gisto repo.

Replicates what `.github/workflows/chat-command.yml` does:
  1. Install dependencies from requirements.txt
  2. Run smoke_test.py
  3. Run verify_keys.py
  4. Run verify_exe.py (only if dist/Gisto.exe exists — i.e. a build has happened)

Usage:
    python ci_local.py              # run all steps
    python ci_local.py --quick     # skip pip install (assume deps present)
    python ci_local.py --no-exe    # skip EXE verification (no build yet)

Exit code 0 = all passed. Non-zero = something failed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
REQUIREMENTS = REPO_ROOT / "requirements.txt"
SMOKE_TEST = REPO_ROOT / "scripts" / "smoke_test.py"
VERIFY_KEYS = REPO_ROOT / "scripts" / "verify_keys.py"
VERIFY_EXE = REPO_ROOT / "scripts" / "verify_exe.py"
EXE_PATH = REPO_ROOT / "dist" / "Gisto.exe"


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 300) -> tuple[bool, str]:
    """Run a command, return (success, combined_output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = proc.stdout + proc.stderr
        ok = proc.returncode == 0
        return ok, out
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return False, f"Command not found: {cmd[0]} ({e})"


def step(title: str, fn) -> bool:
    """Run a step, print header + result."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    ok, out = fn()
    print(out)
    if ok:
        print("[PASS]")
    else:
        print("[FAIL]")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Local CI runner for Gisto")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip pip install step (assume dependencies already present)",
    )
    parser.add_argument(
        "--no-exe",
        action="store_true",
        help="Skip EXE verification (no dist/Gisto.exe yet)",
    )
    args = parser.parse_args()

    results: list[tuple[str, bool]] = []

    # ------------------------------------------------------------------
    # Step 0: environment check
    # ------------------------------------------------------------------
    python = sys.executable
    print(f"Python: {python}")
    print(f"Repo root: {REPO_ROOT}")
    print(f"requirements.txt exists: {REQUIREMENTS.exists()}")
    print(f"dist/Gisto.exe exists: {EXE_PATH.exists()}")
    print()

    # ------------------------------------------------------------------
    # Step 1: install dependencies
    # ------------------------------------------------------------------
    if args.quick:
        results.append(("pip install (skipped --quick)", True))
    else:
        results.append(
            (
                "pip install -r requirements.txt",
                step(
                    "Step 1: Install dependencies",
                    lambda: run(
                        [python, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
                        cwd=REPO_ROOT,
                        timeout=300,
                    ),
                ),
            )
        )

    # ------------------------------------------------------------------
    # Step 2: smoke test
    # ------------------------------------------------------------------
    results.append(
        (
            "smoke_test.py",
            step(
                "Step 2: Smoke test (construct app, no mainloop)",
                lambda: run([python, str(SMOKE_TEST)], cwd=REPO_ROOT, timeout=30),
            ),
        )
    )

    # ------------------------------------------------------------------
    # Step 3: verify on-disk keys
    # ------------------------------------------------------------------
    results.append(
        (
            "verify_keys.py",
            step(
                "Step 3: Verify on-disk _built_keys.py decodes correctly",
                lambda: run([python, str(VERIFY_KEYS)], cwd=REPO_ROOT, timeout=30),
            ),
        )
    )

    # ------------------------------------------------------------------
    # Step 4: verify EXE (only if built)
    # ------------------------------------------------------------------
    if args.no_exe or not EXE_PATH.exists():
        results.append(("verify_exe.py (skipped — no EXE)", True))
    else:
        results.append(
            (
                "verify_exe.py",
                step(
                    "Step 4: Verify EXE bundles correct _built_keys.py",
                    lambda: run([python, str(VERIFY_EXE)], cwd=REPO_ROOT, timeout=60),
                ),
            )
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    all_ok = True
    for name, ok in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("All checks passed.")
        return 0
    else:
        print("One or more checks failed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
