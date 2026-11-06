#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone E2E Test Suite Runner
Imjinrok 2+ Dawn Modding Toolkit

Executes the complete automated test suite across Tiers 1-5:
- Archive subsystem: Data.hq and Data codecs, unpacker, repacker, 100% bit-exact roundtrip
- Modding subsystem: Unit catalog (111 units), stat patcher, PE header preservation, command card code cave
- Map subsystem: 1.13MB .map binary parser, 180 pitch layout, 2D minimap PNG renderer, roundtrip modder
- Asset subsystem: .pal 6-bit to 8-bit RGBA, .YAV to RIFF WAV, Version 9 .spr/.ytl/.ypr decoders
- Acceptance criteria: Full E2E verification of all ORIGINAL_REQUEST.md requirements
- Safety & Integrity audit: Read-only protection of YM source assets and clean rea repository

Usage:
    python run_all_tests.py
    python run_all_tests.py --suite archive
    python run_all_tests.py --suite map --verbose
"""

import argparse
import io
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

# Force UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure reverse-imzinrok root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tests.conftest import (
    YM_DIR,
    DAWN_EXE,
    DATA_FILE,
    DATA_HQ_FILE,
    ORIGINAL_DATA_SIZE,
    ORIGINAL_DATA_HQ_SIZE,
    ORIGINAL_MAP_SIZE,
    ORIGINAL_DAWN_EXE_SIZE,
    verify_ym_integrity,
)

# Test Module Definitions
TEST_SUITES = [
    {
        "id": "archive",
        "name": "Archive Subsystem (R2)",
        "module": "tests.test_archive",
        "description": "Data.hq/Data XOR 0x10 codec, unpacker, repacker, 109-file bit-exact match",
    },
    {
        "id": "modding",
        "name": "Modding & PE Patcher (R1)",
        "module": "tests.test_modding",
        "description": "Unit catalog (111 units), stat patcher, PE header preservation, command card cave",
    },
    {
        "id": "map",
        "name": "Map Infrastructure (R3)",
        "module": "tests.test_map",
        "description": "1.13MB .map parser, 180 pitch validation, 2D minimap PNG renderer, roundtrip modder",
    },
    {
        "id": "assets",
        "name": "Proprietary Assets (R4)",
        "module": "tests.test_assets",
        "description": "6-bit .pal, .YAV to RIFF WAV, Version 9 .spr/.ytl/.ypr RLE decoders",
    },
    {
        "id": "e2e",
        "name": "E2E Acceptance Criteria",
        "module": "tests.test_e2e_runner",
        "description": "Comprehensive acceptance criteria AC1-AC5 verification from ORIGINAL_REQUEST.md",
    },
]


def run_safety_audit() -> bool:
    """Execute workspace safety and integrity check."""
    print("\n" + "=" * 92)
    print(" [PHASE 0] WORKSPACE SAFETY & INTEGRITY PRE-CHECK")
    print("=" * 92)

    # 1. Check rea git status
    rea_path = Path(r"C:\src\rea")
    rea_clean = False
    if rea_path.exists():
        res = subprocess.run(
            ["git", "-C", str(rea_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip() == "":
            print(" [*] C:\\src\\rea git working tree: 100% CLEAN (untouched)")
            rea_clean = True
        else:
            print(f" [!] C:\\src\\rea git working tree has modifications:\n{res.stdout}")
    else:
        print(" [*] C:\\src\\rea not present; skipping git status check.")
        rea_clean = True

    # 2. Check YM integrity
    ym_intact = verify_ym_integrity()
    if ym_intact:
        print(" [*] C:\\src\\reverse-imzinrok\\YM key files: 100% UNTOUCHED (SHA-256 match)")
    else:
        print(" [!] C:\\src\\reverse-imzinrok\\YM files modified or corrupted!")

    safety_ok = rea_clean and ym_intact
    status_str = "[PASS]" if safety_ok else "[FAIL]"
    print(f" [*] Safety Check Result: {status_str}")
    print("=" * 92)
    return safety_ok


def run_suite_module(module_name: str, verbose: bool = False) -> dict:
    """Load and execute a specific test module, returning summary metrics."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module_name)

    stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2 if verbose else 1,
        failfast=False,
    )

    start_time = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - start_time

    tests_run = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = tests_run - failures - errors

    output_log = stream.getvalue()

    return {
        "module": module_name,
        "tests": tests_run,
        "passed": passed,
        "failed": failures,
        "errors": errors,
        "elapsed": elapsed,
        "success": result.wasSuccessful(),
        "log": output_log,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run E2E test suite for Imjinrok 2+ Dawn Modding Toolkit."
    )
    parser.add_argument(
        "--suite",
        choices=["archive", "modding", "map", "assets", "e2e", "all"],
        default="all",
        help="Specify which test suite to execute (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Display detailed per-test execution output",
    )
    parser.add_argument(
        "--skip-safety",
        action="store_true",
        help="Skip pre-check safety audit",
    )

    args = parser.parse_args()

    print("+" + "=" * 90 + "+")
    print(f"| {'IMJINROK 2+ DAWN MODDING TOOLKIT — AUTOMATED E2E TEST RUNNER':^88} |")
    print(f"| {'Integrity Mode: Development | Non-destructive Verification':^88} |")
    print("+" + "=" * 90 + "+")

    # Safety Pre-Check
    if not args.skip_safety:
        safety_passed = run_safety_audit()
        if not safety_passed:
            print("\n[CRITICAL ERROR] Safety check failed! Aborting test suite execution.")
            sys.exit(1)

    # Filter suites to run
    if args.suite == "all":
        suites_to_run = TEST_SUITES
    else:
        suites_to_run = [s for s in TEST_SUITES if s["id"] == args.suite]

    print(f"\n[*] Executing {len(suites_to_run)} test suite(s)...")

    results = []
    for s_info in suites_to_run:
        suite_id = s_info["id"]
        suite_name = s_info["name"]
        mod_name = s_info["module"]

        if args.verbose:
            print(f"\n---> Running {suite_name} ({mod_name})...")

        res = run_suite_module(mod_name, verbose=args.verbose)
        res["id"] = suite_id
        res["display_name"] = suite_name
        results.append(res)

        if args.verbose and res["log"]:
            print(res["log"].strip())

    # Formatted Summary Table
    print("\n" + "=" * 92)
    print(f"| {'TEST SUITE SUMMARY RESULTS':^88} |")
    print("=" * 92)
    header = f"| {'Test Suite / Module':<30} | {'Tests':>6} | {'Passed':>6} | {'Failed':>6} | {'Errors':>6} | {'Time':>7} | {'Status':<8} |"
    divider = "+" + "-" * 32 + "+" + "-" * 8 + "+" + "-" * 8 + "+" + "-" * 8 + "+" + "-" * 8 + "+" + "-" * 9 + "+" + "-" * 10 + "+"
    print(divider)
    print(header)
    print(divider)

    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_time = 0.0
    all_success = True

    for r in results:
        total_tests += r["tests"]
        total_passed += r["passed"]
        total_failed += r["failed"]
        total_errors += r["errors"]
        total_time += r["elapsed"]
        if not r["success"]:
            all_success = False

        status_str = "[PASS]" if r["success"] else "[FAIL]"
        row = (
            f"| {r['display_name']:<30} | {r['tests']:>6} | {r['passed']:>6} | "
            f"{r['failed']:>6} | {r['errors']:>6} | {r['elapsed']:>6.2f}s | {status_str:<8} |"
        )
        print(row)

    print(divider)
    overall_status = "ALL PASS" if all_success else "FAILED"
    total_row = (
        f"| {'TOTAL':<30} | {total_tests:>6} | {total_passed:>6} | "
        f"{total_failed:>6} | {total_errors:>6} | {total_time:>6.2f}s | {overall_status:<8} |"
    )
    print(total_row)
    print(divider)

    # Post-run Safety Final Check
    print("\n[*] Performing post-test safety audit...")
    post_safety_ok = verify_ym_integrity()
    if post_safety_ok:
        print(" [*] [CONFIRMED] Source files in C:\\src\\reverse-imzinrok\\YM remained 100% untouched.")
    else:
        print(" [!] [ALERT] Source files in C:\\src\\reverse-imzinrok\\YM were modified!")
        all_success = False

    if all_success:
        print("\n" + "#" * 92)
        print(f"### [SUCCESS] ALL {total_tests} TESTS PASSED WITH ZERO FAILURES AND ZERO ERRORS! ###")
        print("#" * 92 + "\n")
        sys.exit(0)
    else:
        print("\n" + "!" * 92)
        print("!!! [FAILURE] ONE OR MORE TESTS FAILED. CHECK LOGS ABOVE. !!!")
        print("!" * 92 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
