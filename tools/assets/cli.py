"""
Command-Line Interface for Imjinrok 2+ Proprietary Asset Conversion.

Supported Commands:
- convert-pal: Convert 768-byte 6-bit .pal file to RGBA JSON or swatch PNG.
- convert-yav: Convert 26-byte header .YAV audio file to standard RIFF .wav.
- decode-spr: Decode Version 9 .spr file into transparent PNG frames & metadata JSON.
- decode-ytl: Decode Version 9 .ytl / .ypr tile file into transparent PNG frames & metadata JSON.
- batch-convert: Batch convert directory tree of assets to web-ready formats.
"""

from __future__ import annotations
import argparse
import os
import sys
import glob
from typing import List, Optional

from tools.assets.palette import convert_pal_to_rgba, Palette
from tools.assets.audio import convert_yav_to_wav, YAVAudio
from tools.assets.sprite_rle import decode_spr, SpriteMetadata, SpriteDecoder
from tools.assets.tile_rle import decode_ytl, decode_ypr, decode_tile, TileMetadata


def cmd_convert_pal(args: argparse.Namespace) -> int:
    pal_path = args.pal_file
    if not os.path.isfile(pal_path):
        print(f"Error: Palette file not found: {pal_path}", file=sys.stderr)
        return 1

    try:
        palette = Palette.from_file(pal_path)
        out_path = args.output
        fmt = args.format.lower() if args.format else "json"

        if not out_path:
            base = os.path.splitext(pal_path)[0]
            out_path = f"{base}_swatch.png" if fmt == "swatch" else f"{base}_rgba.json"

        if fmt == "swatch":
            palette.save_swatch_image(out_path, cell_size=args.cell_size)
            print(f"Palette swatch PNG saved to: {out_path}")
        else:
            palette.save_json(out_path)
            print(f"Palette RGBA JSON saved to: {out_path}")

        print(f"Successfully converted {pal_path} (256 colors, index 0 transparent).")
        return 0
    except Exception as e:
        print(f"Error converting palette {pal_path}: {e}", file=sys.stderr)
        return 1


def cmd_convert_yav(args: argparse.Namespace) -> int:
    yav_path = args.yav_file
    if not os.path.isfile(yav_path):
        print(f"Error: YAV audio file not found: {yav_path}", file=sys.stderr)
        return 1

    out_path = args.output
    if not out_path:
        base = os.path.splitext(yav_path)[0]
        out_path = f"{base}.wav"

    try:
        audio = YAVAudio.from_file(yav_path)
        if not audio.verify_with_wave():
            print(f"Error: Generated WAV failed verification for {yav_path}", file=sys.stderr)
            return 1
        audio.save_wav(out_path)
        print(
            f"Successfully converted {yav_path} -> {out_path} "
            f"({audio.channels}ch, {audio.sample_rate}Hz, {audio.bits_per_sample}bit, "
            f"{audio.sample_count} samples, {audio.duration_seconds:.2f}s)"
        )
        return 0
    except Exception as e:
        print(f"Error converting YAV audio {yav_path}: {e}", file=sys.stderr)
        return 1


def cmd_decode_spr(args: argparse.Namespace) -> int:
    spr_path = args.spr_file
    pal_path = args.pal
    if not os.path.isfile(spr_path):
        print(f"Error: SPR file not found: {spr_path}", file=sys.stderr)
        return 1
    if not os.path.isfile(pal_path):
        print(f"Error: Palette file not found: {pal_path}", file=sys.stderr)
        return 1

    out_dir = args.output_dir
    if not out_dir:
        stem = os.path.splitext(os.path.basename(spr_path))[0]
        out_dir = os.path.join(os.path.dirname(spr_path), f"{stem}_decoded")

    try:
        meta = decode_spr(
            spr_path=spr_path,
            pal_path=pal_path,
            output_dir=out_dir,
            export_atlas=not args.no_atlas,
            export_frames=not args.no_frames,
        )
        print(
            f"Successfully decoded SPR: {spr_path} -> {out_dir}\n"
            f"  Resolution: {meta.width}x{meta.height}, Frames: {meta.frame_count}\n"
            f"  Atlas: {meta.atlas_file or 'None'}, Data Size: {meta.data_size} bytes"
        )
        return 0
    except Exception as e:
        print(f"Error decoding SPR {spr_path}: {e}", file=sys.stderr)
        return 1


def cmd_decode_ytl(args: argparse.Namespace) -> int:
    tile_path = args.tile_file
    pal_path = args.pal
    if not os.path.isfile(tile_path):
        print(f"Error: Tile file not found: {tile_path}", file=sys.stderr)
        return 1
    if not os.path.isfile(pal_path):
        print(f"Error: Palette file not found: {pal_path}", file=sys.stderr)
        return 1

    out_dir = args.output_dir
    if not out_dir:
        stem = os.path.splitext(os.path.basename(tile_path))[0]
        out_dir = os.path.join(os.path.dirname(tile_path), f"{stem}_decoded")

    try:
        meta = decode_tile(
            tile_path=tile_path,
            pal_path=pal_path,
            output_dir=out_dir,
            export_atlas=not args.no_atlas,
            export_frames=not args.no_frames,
        )
        print(
            f"Successfully decoded {meta.tile_type.upper()}: {tile_path} -> {out_dir}\n"
            f"  Resolution: {meta.width}x{meta.height}, Frames/Variants: {meta.frame_count}\n"
            f"  Atlas: {meta.atlas_file or 'None'}, Data Size: {meta.data_size} bytes"
        )
        return 0
    except Exception as e:
        print(f"Error decoding tile {tile_path}: {e}", file=sys.stderr)
        return 1


def cmd_batch_convert(args: argparse.Namespace) -> int:
    in_dir = args.input_dir
    out_dir = args.output_dir
    pal_path = args.pal

    if not os.path.isdir(in_dir):
        print(f"Error: Input directory not found: {in_dir}", file=sys.stderr)
        return 1
    if not os.path.isfile(pal_path):
        print(f"Error: Palette file not found: {pal_path}", file=sys.stderr)
        return 1

    palette = Palette.from_file(pal_path)
    types = [t.strip().lower() for t in args.types.split(",")]
    all_types = "all" in types

    os.makedirs(out_dir, exist_ok=True)
    success_count = 0
    error_count = 0

    max_files = args.max_files

    for root, _, files in os.walk(in_dir):
        for f in files:
            if max_files and success_count >= max_files:
                break

            ext = os.path.splitext(f)[1].lower().lstrip(".")
            src_path = os.path.join(root, f)
            rel_dir = os.path.relpath(root, in_dir)
            target_sub_dir = os.path.join(out_dir, rel_dir) if rel_dir != "." else out_dir

            try:
                if (all_types or "yav" in types) and ext == "yav":
                    dest_wav = os.path.join(target_sub_dir, f"{os.path.splitext(f)[0]}.wav")
                    convert_yav_to_wav(src_path, dest_wav)
                    success_count += 1
                elif (all_types or "spr" in types) and ext == "spr":
                    stem = os.path.splitext(f)[0]
                    dest_spr_dir = os.path.join(target_sub_dir, stem)
                    decode_spr(src_path, palette, dest_spr_dir)
                    success_count += 1
                elif (all_types or "ytl" in types) and ext == "ytl":
                    stem = os.path.splitext(f)[0]
                    dest_ytl_dir = os.path.join(target_sub_dir, stem)
                    decode_ytl(src_path, palette, dest_ytl_dir)
                    success_count += 1
                elif (all_types or "ypr" in types) and ext == "ypr":
                    stem = os.path.splitext(f)[0]
                    dest_ypr_dir = os.path.join(target_sub_dir, stem)
                    decode_ypr(src_path, palette, dest_ypr_dir)
                    success_count += 1
                elif (all_types or "pal" in types) and ext == "pal":
                    stem = os.path.splitext(f)[0]
                    dest_json = os.path.join(target_sub_dir, f"{stem}_rgba.json")
                    p = Palette.from_file(src_path)
                    p.save_json(dest_json)
                    success_count += 1
            except Exception as e:
                print(f"Error processing {src_path}: {e}", file=sys.stderr)
                error_count += 1

    print(f"Batch conversion completed: {success_count} assets processed, {error_count} errors.")
    return 0 if error_count == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imjinrok-asset-tool",
        description="Proprietary Asset Decoder & Web-Ready Converter for Imjinrok 2+",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # convert-pal
    p_pal = subparsers.add_parser("convert-pal", help="Convert 6-bit VGA .pal file to RGBA JSON or swatch PNG")
    p_pal.add_argument("pal_file", help="Path to input .pal file")
    p_pal.add_argument("-o", "--output", help="Path to output file")
    p_pal.add_argument("--format", choices=["json", "swatch"], default="json", help="Output format")
    p_pal.add_argument("--cell-size", type=int, default=16, help="Swatch cell size in pixels")
    p_pal.set_defaults(func=cmd_convert_pal)

    # convert-yav
    p_yav = subparsers.add_parser("convert-yav", help="Convert .YAV audio file to standard RIFF .wav")
    p_yav.add_argument("yav_file", help="Path to input .YAV file")
    p_yav.add_argument("-o", "--output", help="Path to output .wav file")
    p_yav.set_defaults(func=cmd_convert_yav)

    # decode-spr
    p_spr = subparsers.add_parser("decode-spr", help="Decode Version 9 .spr file into transparent PNGs")
    p_spr.add_argument("spr_file", help="Path to input .spr file")
    p_spr.add_argument("-p", "--pal", required=True, help="Path to .pal palette file")
    p_spr.add_argument("-o", "--output-dir", help="Directory to save decoded PNG frames and metadata")
    p_spr.add_argument("--no-atlas", action="store_true", help="Do not generate composite atlas sprite sheet")
    p_spr.add_argument("--no-frames", action="store_true", help="Do not export individual frame PNG files")
    p_spr.set_defaults(func=cmd_decode_spr)

    # decode-ytl
    p_ytl = subparsers.add_parser("decode-ytl", help="Decode Version 9 .ytl / .ypr tile file into PNGs")
    p_ytl.add_argument("tile_file", help="Path to input .ytl or .ypr file")
    p_ytl.add_argument("-p", "--pal", required=True, help="Path to .pal palette file")
    p_ytl.add_argument("-o", "--output-dir", help="Directory to save decoded PNG frames and metadata")
    p_ytl.add_argument("--no-atlas", action="store_true", help="Do not generate composite atlas sheet")
    p_ytl.add_argument("--no-frames", action="store_true", help="Do not export individual frame PNG files")
    p_ytl.set_defaults(func=cmd_decode_ytl)

    # batch-convert
    p_batch = subparsers.add_parser("batch-convert", help="Batch convert game assets in directory")
    p_batch.add_argument("-i", "--input-dir", required=True, help="Directory containing source assets")
    p_batch.add_argument("-o", "--output-dir", required=True, help="Directory to output converted files")
    p_batch.add_argument("-p", "--pal", required=True, help="Path to .pal palette file")
    p_batch.add_argument(
        "--types", default="all", help="Comma-separated asset types: all, spr, ytl, ypr, yav, pal"
    )
    p_batch.add_argument("-m", "--max-files", type=int, default=None, help="Maximum files to process")
    p_batch.set_defaults(func=cmd_batch_convert)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
