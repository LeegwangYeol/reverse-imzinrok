"""
tools.modding.cli
~~~~~~~~~~~~~~~~~
Command Line Interface (CLI) for Imjinrok 2+: Dawn Unit Reverse Engineering & Modding Toolkit.
Commands:
  - list: List units/buildings with optional faction and patch filters.
  - export: Export unit database to CSV or JSON.
  - modify-stat: Safely patch a unit stat in a cloned Dawn binary.
  - set-speed: Safely patch a unit's movement speed in a cloned Dawn binary.
  - add-button: Inject a new command card button hook into available code cave slack space.
  - decode-cave: Disassemble and display the 6 Dawn code cave hooks and injected stubs.
  - verify-binary: Run exhaustive PE binary integrity verification between original and patched binaries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tools.modding.binary_patcher import (
    check_binary_integrity,
    modify_unit_stat,
    patch_movement_speed,
)
from tools.modding.command_card import (
    BUILDING_HOOK_PRESETS,
    decode_cave_hooks,
    inject_command_card_button,
)
from tools.modding.unit_catalog import load_unit_catalog


def cmd_list(args: argparse.Namespace) -> int:
    """Handle `list` command."""
    cat = load_unit_catalog(args.dataset)
    units = cat.list_units(filter_patched=args.filter_patched, faction=args.faction)

    if args.search:
        q = args.search.strip()
        units = [u for u in units if q in u.get("korean_name", "") or q.upper() in u.get("sprite_name", "").upper()]

    print(f"Total units matching criteria: {len(units)}")
    print(f"{'Idx':>3} | {'Korean Name':<18} | {'Sprite':<22} | {'Speed':<6} | {'HP':<6} | {'Attack':<6} | {'Patched':<7}")
    print("-" * 80)
    for u in units:
        idx = u.get("index", 0)
        kn = u.get("korean_name", "UNKNOWN")
        sn = u.get("sprite_name", "UNKNOWN")
        spd = str(u.get("speed_field", {}).get("dawn_val", "-"))
        hp = str(u.get("hp_field", {}).get("dawn_val", "-"))
        atk = str(u.get("attack_field", {}).get("dawn_val", "-"))
        patches = u.get("total_patches_in_unit", 0)
        patched_str = f"Yes ({patches})" if patches > 0 else "No"
        print(f"{idx:>3} | {kn:<18} | {sn:<22} | {spd:<6} | {hp:<6} | {atk:<6} | {patched_str:<7}")

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Handle `export` command."""
    cat = load_unit_catalog(args.dataset)
    out_path = os.path.abspath(args.output)
    fmt = args.format.lower().strip()

    if fmt == "csv":
        cat.export_to_csv(out_path)
        print(f"Successfully exported {len(cat)} units to CSV: {out_path}")
    elif fmt in ("json", "yaml"):
        cat.export_to_json(out_path)
        print(f"Successfully exported {len(cat)} units to JSON: {out_path}")
    else:
        print(f"Unsupported export format: {args.format}", file=sys.stderr)
        return 1

    return 0


def cmd_modify_stat(args: argparse.Namespace) -> int:
    """Handle `modify-stat` command."""
    val = int(args.value, 16) if str(args.value).startswith("0x") else int(args.value)
    res = modify_unit_stat(args.binary, args.unit, args.stat, val)
    print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    return 0 if res.success else 1


def cmd_set_speed(args: argparse.Namespace) -> int:
    """Handle `set-speed` command."""
    spd = int(args.speed, 16) if str(args.speed).startswith("0x") else int(args.speed)
    res = patch_movement_speed(args.binary, args.unit, spd)
    print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    return 0 if res.success else 1


def cmd_add_button(args: argparse.Namespace) -> int:
    """Handle `add-button` command."""
    slot = int(args.slot)
    cmd_id = int(args.cmd_id, 16) if str(args.cmd_id).startswith("0x") else int(args.cmd_id)
    reqs = None
    if args.requirements:
        reqs = [int(r.strip()) for r in args.requirements.split(",")]

    res = inject_command_card_button(args.binary, args.hook, slot, cmd_id, requirements=reqs)
    print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    return 0 if res.success else 1


def cmd_decode_cave(args: argparse.Namespace) -> int:
    """Handle `decode-cave` command."""
    hooks = decode_cave_hooks(args.binary)
    print(f"--- Decoded {len(hooks)} Dawn Code Cave Hooks ---")
    for h in hooks:
        hook_va_str = f"0x{h['hook_va']:08x}"
        cave_va_str = f"0x{h['cave_va']:08x}"
        print(f"Hook #{h['hook_id']} at VA {hook_va_str} -> Cave {cave_va_str}")
        print(f"  Target: {h['target_unit_name']} (Unit ID {h['target_unit_id']})")
        print(f"  Sprite: {h['sprite']}")
        for btn in h["injected_buttons"]:
            print(f"  Injected Button: Slot {btn['slot']}, cmdId 0x{btn['cmd_id']:x} ({btn['cmd_id']}) - {btn['description']}")
        print(f"  Logic: {h['logic']}")
        if "hooked" in h:
            print(f"  Binary Status: Hook Active={h['hooked']} (Target VA: {h.get('actual_cave_target')})")
        print()
    return 0


def cmd_verify_binary(args: argparse.Namespace) -> int:
    """Handle `verify-binary` command."""
    report = check_binary_integrity(args.orig, args.patched)
    print("--- Binary Integrity Verification Report ---")
    print(f"Valid: {report.get('valid')}")
    print(f"Size Valid: {report.get('size_valid')}")
    print(f"PE Headers Intact: {report.get('pe_headers_intact')}")
    print(f"Total Changed Bytes: {report.get('diff_count')}")
    if report.get("diff_ranges"):
        print(f"Contiguous Diff Ranges: {report.get('diff_ranges')}")
    print(f"Message: {report.get('message')}")
    return 0 if report.get("valid") else 1


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for modding CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.modding.cli",
        description="Imjinrok 2+: Dawn Unit, Building, and Skill Binary Modding Toolkit",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # list
    p_list = subparsers.add_parser("list", help="List all units/buildings in catalog")
    p_list.add_argument("--dataset", help="Path to dataset.json (optional)", default=None)
    p_list.add_argument("--filter-patched", action="store_true", help="Only show units with balance patches")
    p_list.add_argument("--faction", choices=["조선", "일본", "명"], help="Filter by faction")
    p_list.add_argument("--search", help="Search substring in unit or sprite name")

    # export
    p_export = subparsers.add_parser("export", help="Export unit database to CSV or JSON")
    p_export.add_argument("--format", choices=["csv", "json"], default="csv", help="Output format")
    p_export.add_argument("--output", "-o", required=True, help="Output destination file path")
    p_export.add_argument("--dataset", help="Path to dataset.json (optional)", default=None)

    # modify-stat
    p_mod = subparsers.add_parser("modify-stat", help="Patch unit stat in cloned Dawn executable")
    p_mod.add_argument("--binary", "-b", required=True, help="Path to cloned copy of dawn.exe")
    p_mod.add_argument("--unit", "-u", required=True, help="Unit index, Korean name, or sprite name")
    p_mod.add_argument("--stat", "-s", required=True, help="Stat name (speed, hp, mp, attack, delay, range, defense, rice, potato, money)")
    p_mod.add_argument("--value", "-v", required=True, help="New integer value (decimal or 0x hex)")

    # set-speed
    p_spd = subparsers.add_parser("set-speed", help="Convenience shortcut to set unit movement speed")
    p_spd.add_argument("--binary", "-b", required=True, help="Path to cloned copy of dawn.exe")
    p_spd.add_argument("--unit", "-u", required=True, help="Unit index, Korean name, or sprite name")
    p_spd.add_argument("--speed", required=True, help="New base movement speed integer")

    # add-button
    p_btn = subparsers.add_parser("add-button", help="Inject new command card button into slack code cave")
    p_btn.add_argument("--binary", "-b", required=True, help="Path to cloned copy of dawn.exe")
    p_btn.add_argument("--hook", required=True, help="Hook site VA (hex/int) or preset building name")
    p_btn.add_argument("--slot", required=True, type=int, choices=range(0, 12), help="Button slot index (0..11)")
    p_btn.add_argument("--cmd-id", required=True, help="New command ID (decimal or 0x hex)")
    p_btn.add_argument("--requirements", help="Comma-separated prerequisite IDs (e.g. '0,0,0,0,0,0')")

    # decode-cave
    p_cave = subparsers.add_parser("decode-cave", help="Inspect and disassemble Dawn code cave hooks")
    p_cave.add_argument("--binary", "-b", help="Path to dawn.exe (optional)", default=None)

    # verify-binary
    p_ver = subparsers.add_parser("verify-binary", help="Verify PE binary integrity between original and patched")
    p_ver.add_argument("--orig", required=True, help="Path to original YM/dawn/dawn.exe")
    p_ver.add_argument("--patched", required=True, help="Path to modified cloned executable")

    # patch-binary (alias for modify-stat)
    p_patch = subparsers.add_parser("patch-binary", help="Patch unit stat in cloned Dawn executable (alias for modify-stat)")
    p_patch.add_argument("--binary", "-b", required=True, help="Path to cloned copy of dawn.exe")
    p_patch.add_argument("--unit", "-u", required=True, help="Unit index, Korean name, or sprite name")
    p_patch.add_argument("--stat", "-s", required=True, help="Stat name (speed, hp, mp, attack, delay, range, defense, rice, potato, money)")
    p_patch.add_argument("--value", "-v", required=True, help="New integer value (decimal or 0x hex)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI Entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "list": cmd_list,
        "export": cmd_export,
        "modify-stat": cmd_modify_stat,
        "patch-binary": cmd_modify_stat,
        "set-speed": cmd_set_speed,
        "add-button": cmd_add_button,
        "decode-cave": cmd_decode_cave,
        "verify-binary": cmd_verify_binary,
    }

    handler = commands.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except Exception as e:
        print(f"Error executing '{args.command}': {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
