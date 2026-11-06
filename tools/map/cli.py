"""Imjinrok 2+ Dawn Map Management CLI Tool.

Supports:
- info: Inspect map dimensions, theme, player starts, and resource statistics.
- render-minimap: Render high-quality 2D minimap PNG previews with player & resource markers.
- export-json: Export structured metadata or full resource/building grids to JSON.
- modify: Programmatically edit start coordinates, resources, terrain, or theme, and save back to 1,132,876-byte files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tools.map.modder import MapModder, modify_map
from tools.map.parser import (
    DEFAULT_RESOURCE_AMOUNTS,
    MAP_FILE_SIZE,
    RESOURCE_NAMES,
    THEME_NAMES,
    MapData,
    parse_map,
    save_map,
)
from tools.map.renderer import render_minimap


def cmd_info(args: argparse.Namespace) -> int:
    """Displays detailed map metadata and resource/player stats."""
    map_data = parse_map(args.map_file)

    if args.json:
        print(map_data.to_json(indent=2))
        return 0

    print("=" * 60)
    print(f"Map File: {Path(args.map_file).name}")
    print("=" * 60)
    print(f"Version:      {map_data.version}")
    print(f"Dimensions:   {map_data.width} x {map_data.height} cells (pitch: 180)")
    print(f"Player Slots: {map_data.num_players} max players")
    print(f"Theme:        ID {map_data.theme_id} ({map_data.theme_name})")
    print(f"Map Mode:     {map_data.map_mode}")
    print(f"File Size:    {len(map_data.raw_data):,} bytes (valid: {len(map_data.raw_data) == MAP_FILE_SIZE})")

    print("\n--- Player Start Locations ---")
    active_starts = map_data.get_active_player_starts()
    for ps in active_starts:
        print(f"  Player {ps.player_id}: ({ps.x}, {ps.y})")
    if not active_starts:
        print("  (No active player starts found)")

    print("\n--- Resource Summary ---")
    summary = map_data.resource_summary()
    if summary:
        for name, data in summary.items():
            print(f"  {name:15s} (ID {data['type_id']:3d}): {data['count']:5d} nodes, total: {data['total_amount']:,}")
    else:
        print("  (No resources placed)")

    buildings = map_data.get_all_buildings()
    print(f"\n--- Pre-placed Buildings ---")
    print(f"  Total building blocks: {len(buildings)}")

    return 0


def cmd_render_minimap(args: argparse.Namespace) -> int:
    """Renders 2D PNG minimap preview."""
    map_data = parse_map(args.map_file)
    out_path = Path(args.output)

    render_minimap(
        map_data=map_data,
        output_png_path=out_path,
        width=args.width,
        height=args.height,
        show_players=not args.no_players,
        show_resources=not args.no_resources,
        show_buildings=not args.no_buildings,
    )
    print(f"Minimap preview rendered successfully to: {out_path} ({args.width}x{args.height})")
    return 0


def cmd_export_json(args: argparse.Namespace) -> int:
    """Exports structured metadata to a JSON file."""
    map_data = parse_map(args.map_file)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = map_data.to_json(indent=2, include_grids=args.include_grids)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    print(f"Map metadata exported successfully to: {out_path}")
    return 0


def cmd_modify(args: argparse.Namespace) -> int:
    """Programmatically edits map fields and writes back a valid 1,132,876-byte map."""
    modder = MapModder(args.map_file)

    # Apply external JSON modifications first if specified
    if args.json_mods:
        with open(args.json_mods, "r", encoding="utf-8") as f:
            mods_dict = json.load(f)
        modder.apply_modifications(mods_dict)

    # CLI option overrides
    if args.theme is not None:
        modder.set_theme(args.theme)

    if args.player_start:
        for pid_str, x_str, y_str in args.player_start:
            modder.set_player_start(int(pid_str), int(x_str), int(y_str))

    if args.set_resource_amount:
        for tid_str, amt_str in args.set_resource_amount:
            modder.set_all_resources_of_type(int(tid_str), int(amt_str))

    if args.scale_resources is not None:
        factor = float(args.scale_resources)
        tid = int(args.scale_resource_type) if args.scale_resource_type is not None else None
        modder.scale_resources(factor, type_id=tid)

    out_path = Path(args.output)
    modder.save(out_path)
    print(f"Modified map saved successfully to: {out_path} (exact size: {out_path.stat().st_size:,} bytes)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="imzinrok-map",
        description="Imjinrok 2+ Dawn .map File Toolkit: Parser, Renderer, and Modder",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. info
    p_info = subparsers.add_parser("info", help="Inspect map header, player starts, and resources")
    p_info.add_argument("map_file", help="Path to .map file")
    p_info.add_argument("--json", action="store_true", help="Output in JSON format")

    # 2. render-minimap
    p_render = subparsers.add_parser("render-minimap", help="Render 2D minimap PNG preview")
    p_render.add_argument("map_file", help="Path to .map file")
    p_render.add_argument("-o", "--output", required=True, help="Output PNG path")
    p_render.add_argument("--width", type=int, default=400, help="Minimap width in pixels (default: 400)")
    p_render.add_argument("--height", type=int, default=400, help="Minimap height in pixels (default: 400)")
    p_render.add_argument("--no-players", action="store_true", help="Hide player start markers")
    p_render.add_argument("--no-resources", action="store_true", help="Hide resource nodes")
    p_render.add_argument("--no-buildings", action="store_true", help="Hide pre-placed buildings")

    # 3. export-json
    p_export = subparsers.add_parser("export-json", help="Export map metadata to JSON")
    p_export.add_argument("map_file", help="Path to .map file")
    p_export.add_argument("-o", "--output", required=True, help="Output JSON path")
    p_export.add_argument("--include-grids", action="store_true", help="Include full cell list for resources and buildings")

    # 4. modify
    p_modify = subparsers.add_parser("modify", help="Modify map and save valid 1,132,876-byte file")
    p_modify.add_argument("map_file", help="Source .map file")
    p_modify.add_argument("-o", "--output", required=True, help="Destination .map file path")
    p_modify.add_argument(
        "--player-start",
        nargs=3,
        action="append",
        metavar=("PLAYER_ID", "X", "Y"),
        help="Update player start coordinate (e.g. --player-start 0 25 30)",
    )
    p_modify.add_argument(
        "--set-resource-amount",
        nargs=2,
        action="append",
        metavar=("TYPE_ID", "AMOUNT"),
        help="Set amount for all resources of a type (e.g. --set-resource-amount 1 250)",
    )
    p_modify.add_argument(
        "--scale-resources",
        type=float,
        help="Multiply resource amounts by factor (e.g. 2.0)",
    )
    p_modify.add_argument(
        "--scale-resource-type",
        type=int,
        help="Specific resource type to scale (1=potato, 2=bamboo, 3=tree, 100=rice)",
    )
    p_modify.add_argument(
        "--set-theme",
        dest="theme",
        help="Set theme ID (0..6) or theme name ('normal', 'snow', 'green', etc.)",
    )
    p_modify.add_argument(
        "--json-mods",
        help="Path to JSON file containing structured modifications",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "info":
        return cmd_info(args)
    elif args.command == "render-minimap":
        return cmd_render_minimap(args)
    elif args.command == "export-json":
        return cmd_export_json(args)
    elif args.command == "modify":
        return cmd_modify(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
