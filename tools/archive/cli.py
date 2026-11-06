"""Command-line interface for Imjinrok 2+ Dawn archive tools.

Subcommands:
  unpack   - Unpack files from Data using Data.hq index
  repack   - Repack unpacked files into Data and Data.hq archives
  verify   - Verify bit-exact equality between original and repacked archives
  catalog  - Generate structured JSON catalog of all 109 internal files
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Optional

from tools.archive.catalog import build_catalog
from tools.archive.repacker import repack_archive, verify_archive_pair
from tools.archive.unpacker import unpack_archive


def cmd_unpack(args: argparse.Namespace) -> int:
    """Handle unpack subcommand."""
    data_p = Path(args.data)
    hq_p = Path(args.hq)
    out_dir = Path(args.output)

    if not args.quiet:
        print(f"[*] Unpacking archive:")
        print(f"    Data:   {data_p}")
        print(f"    Index:  {hq_p}")
        print(f"    Output: {out_dir}")

    try:
        file_infos = unpack_archive(
            archive_path=data_p,
            hq_path=hq_p,
            output_dir=out_dir,
            write_manifest=not args.no_manifest,
            export_utf8=args.export_utf8,
        )
    except Exception as e:
        print(f"[!] Unpack failed: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        total_bytes = sum(f.size for f in file_infos)
        print(f"[+] Successfully unpacked {len(file_infos)} files ({total_bytes:,} bytes).")
        if not args.no_manifest:
            print(f"    Manifest written to: {out_dir / 'manifest.json'}")
        if args.export_utf8:
            print(f"    UTF-8 text exported to: {out_dir / 'utf8'}")
    return 0


def cmd_repack(args: argparse.Namespace) -> int:
    """Handle repack subcommand."""
    in_dir = Path(args.input)
    data_out = Path(args.data_out)
    hq_out = Path(args.hq_out)
    manifest_p = Path(args.manifest) if args.manifest else None

    if not args.quiet:
        print(f"[*] Repacking archive:")
        print(f"    Input dir: {in_dir}")
        print(f"    Data out:  {data_out}")
        print(f"    HQ out:    {hq_out}")

    try:
        success = repack_archive(
            input_dir=in_dir,
            output_archive_path=data_out,
            output_hq_path=hq_out,
            manifest_path=manifest_p,
        )
    except Exception as e:
        print(f"[!] Repack failed: {e}", file=sys.stderr)
        return 1

    if success and not args.quiet:
        print(f"[+] Successfully repacked archives:")
        print(f"    {data_out} ({data_out.stat().st_size:,} bytes)")
        print(f"    {hq_out} ({hq_out.stat().st_size:,} bytes)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Handle verify subcommand."""
    orig_data = Path(args.orig_data)
    orig_hq = Path(args.orig_hq)
    rep_data = Path(args.repacked_data)
    rep_hq = Path(args.repacked_hq)

    if not args.quiet and not args.json:
        print(f"[*] Verifying archives:")
        print(f"    Original Data: {orig_data}")
        print(f"    Original HQ:   {orig_hq}")
        print(f"    Repacked Data: {rep_data}")
        print(f"    Repacked HQ:   {rep_hq}")

    try:
        overall_match, details = verify_archive_pair(
            orig_data=orig_data,
            orig_hq=orig_hq,
            repacked_data=rep_data,
            repacked_hq=rep_hq,
        )
    except Exception as e:
        print(f"[!] Verification error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(details, indent=2))
        return 0 if overall_match else 1

    if not args.quiet:
        print("\n--- Verification Report ---")
        d_info = details["data"]
        h_info = details["hq"]

        d_status = "MATCH (100% bit-exact)" if d_info["bit_exact"] else "MISMATCH"
        h_status = "MATCH (100% bit-exact)" if h_info["bit_exact"] else "MISMATCH"

        print(f"Data archive: {d_status}")
        print(f"  Orig SHA256:     {d_info['orig_sha256']}")
        print(f"  Repacked SHA256: {d_info['repacked_sha256']}")
        print(f"  Size:            {d_info['orig_size']} bytes")

        print(f"\nData.hq index: {h_status}")
        print(f"  Orig SHA256:     {h_info['orig_sha256']}")
        print(f"  Repacked SHA256: {h_info['repacked_sha256']}")
        print(f"  Size:            {h_info['orig_size']} bytes")

        if overall_match:
            print("\n[+] OVERALL: 100% BIT-EXACT PASS!")
        else:
            print("\n[!] OVERALL: VERIFICATION FAILED!", file=sys.stderr)

    return 0 if overall_match else 1


def cmd_catalog(args: argparse.Namespace) -> int:
    """Handle catalog subcommand."""
    out_json = Path(args.output)

    if args.input:
        in_dir = Path(args.input)
    else:
        # If input dir not given, temporarily unpack into a temp directory or require it
        print("[!] Please specify unpacked directory with -i / --input", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[*] Building catalog from: {in_dir}")
        print(f"    Output JSON: {out_json}")

    try:
        catalog_data = build_catalog(unpacked_dir=in_dir, output_catalog_path=out_json)
    except Exception as e:
        print(f"[!] Catalog generation failed: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[+] Catalog successfully generated with {catalog_data['total_files']} files.")
        print(f"    Saved to: {out_json}")
    return 0


def main(argv: Optional[list] = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="archive_tool",
        description="Imjinrok 2+ Dawn Archive & Index Management Tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: unpack
    p_unpack = subparsers.add_parser("unpack", help="Unpack files from Data and Data.hq")
    p_unpack.add_argument("--data", default="YM/dawn/Data", help="Path to Data archive")
    p_unpack.add_argument("--hq", default="YM/dawn/Data.hq", help="Path to Data.hq index")
    p_unpack.add_argument("-o", "--output", required=True, help="Output directory")
    p_unpack.add_argument("--export-utf8", action="store_true", help="Also export UTF-8 copies of text files")
    p_unpack.add_argument("--no-manifest", action="store_true", help="Do not write manifest.json")
    p_unpack.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    p_unpack.set_defaults(func=cmd_unpack)

    # Subcommand: repack
    p_repack = subparsers.add_parser("repack", help="Repack files into Data and Data.hq")
    p_repack.add_argument("-i", "--input", required=True, help="Input directory containing unpacked files")
    p_repack.add_argument("--data-out", required=True, help="Path for repacked Data archive")
    p_repack.add_argument("--hq-out", required=True, help="Path for repacked Data.hq index")
    p_repack.add_argument("--manifest", default=None, help="Explicit path to manifest.json")
    p_repack.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    p_repack.set_defaults(func=cmd_repack)

    # Subcommand: verify
    p_verify = subparsers.add_parser("verify", help="Verify bit-exact match between archives")
    p_verify.add_argument("--orig-data", required=True, help="Original Data path")
    p_verify.add_argument("--orig-hq", required=True, help="Original Data.hq path")
    p_verify.add_argument("--repacked-data", required=True, help="Repacked Data path")
    p_verify.add_argument("--repacked-hq", required=True, help="Repacked Data.hq path")
    p_verify.add_argument("--json", action="store_true", help="Output results as JSON")
    p_verify.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    p_verify.set_defaults(func=cmd_verify)

    # Subcommand: catalog
    p_cat = subparsers.add_parser("catalog", help="Generate structured JSON catalog")
    p_cat.add_argument("-i", "--input", required=True, help="Directory containing unpacked files")
    p_cat.add_argument("-o", "--output", required=True, help="Output JSON catalog path")
    p_cat.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    p_cat.set_defaults(func=cmd_catalog)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
