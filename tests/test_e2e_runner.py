"""
End-to-End Acceptance Criteria Test Suite
Imjinrok 2+ Dawn Modding Toolkit

Verifies all Acceptance Criteria from ORIGINAL_REQUEST.md:
- AC 1: Archive & Data Table Round-Trip Verification (100% bit-exact across 109 files)
- AC 2: Unit Stat (Movement Speed) & New Unit Patching Verification
- AC 3: Asset Decoding (.spr / .ytl / .ypr / .YAV) Verification
- AC 4: .map File Parsing & Modification Verification
- AC 5: Integrity & Safety Check (YM & rea read-only preservation)
"""

import os
import subprocess
import unittest
import wave
from pathlib import Path
from PIL import Image

from tests.conftest import (
    BASE_DIR,
    YM_DIR,
    DAWN_DIR,
    DAWN_EXE,
    DATA_FILE,
    DATA_HQ_FILE,
    IMJIN2_PAL,
    DEFAULT_PAL,
    CUSMAP_DIR,
    EFT_DIR,
    MUSIC_DIR,
    CHAR_DIR,
    TILE_DIR,
    FNT_DIR,
    BATTLE_SPR,
    ORIGINAL_DATA_SIZE,
    ORIGINAL_DATA_HQ_SIZE,
    ORIGINAL_MAP_SIZE,
    ORIGINAL_DAWN_EXE_SIZE,
    get_temp_dir,
    clone_dawn_exe,
    clone_map_file,
    sha256_file,
    verify_ym_integrity,
)

# Subsystem tools
from tools.archive.unpacker import unpack_archive
from tools.archive.repacker import repack_archive, verify_bit_exact, verify_archive_pair
from tools.archive.catalog import build_catalog
from tools.modding.unit_catalog import load_unit_catalog
from tools.modding.binary_patcher import BinaryPatcher, check_binary_integrity
from tools.modding.command_card import decode_cave_hooks, inject_command_card_button
from tools.map.parser import parse_map, save_map
from tools.map.renderer import render_minimap
from tools.map.modder import modify_map
from tools.assets.palette import convert_pal_to_rgba
from tools.assets.audio import convert_yav_to_wav, YAVAudio
from tools.assets.sprite_rle import decode_spr
from tools.assets.tile_rle import decode_ytl, decode_ypr


class TestE2EAcceptanceCriteria(unittest.TestCase):
    """Full acceptance criteria verification against real game data."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = get_temp_dir("e2e_ac_")
        cls.pal_path = IMJIN2_PAL if IMJIN2_PAL.exists() else DEFAULT_PAL

    def test_ac1_archive_roundtrip_bit_exact(self):
        """
        AC 1: Unpacking YM\\dawn\\Data + Data.hq and immediately repacking produces
        a Data and Data.hq pair whose byte contents match 100% with zero data loss.
        All 109 files extracted, and structured catalog generated.
        """
        unpacked_dir = self.temp_dir / "ac1_unpacked"
        repacked_dir = self.temp_dir / "ac1_repacked"

        # 1. Unpack all 109 files
        extracted = unpack_archive(
            archive_path=DATA_FILE,
            hq_path=DATA_HQ_FILE,
            output_dir=unpacked_dir,
            write_manifest=True,
            export_utf8=True,
        )
        self.assertEqual(len(extracted), 109, "Must extract exactly 109 files")
        total_size = sum(f.size for f in extracted)
        self.assertEqual(total_size, ORIGINAL_DATA_SIZE)

        # 2. Generate structured catalog
        catalog_path = unpacked_dir / "catalog.json"
        cat_data = build_catalog(unpacked_dir, catalog_path)
        self.assertTrue(catalog_path.exists())
        self.assertEqual(cat_data["total_files"], 109)
        self.assertGreater(len(cat_data["parsed_tables"].get("img_file_dat", [])), 200)
        self.assertGreater(len(cat_data["parsed_tables"].get("text_kor_dat", [])), 500)

        # 3. Immediately repack
        rep_data = repacked_dir / "Data"
        rep_hq = repacked_dir / "Data.hq"
        success = repack_archive(
            input_dir=unpacked_dir,
            output_archive_path=rep_data,
            output_hq_path=rep_hq,
        )
        self.assertTrue(success)

        # 4. 100% Bit-exact match verification
        is_identical, details = verify_archive_pair(
            orig_data=DATA_FILE,
            orig_hq=DATA_HQ_FILE,
            repacked_data=rep_data,
            repacked_hq=rep_hq,
        )
        self.assertTrue(is_identical, f"Bit-exact match failed: {details}")
        self.assertTrue(verify_bit_exact(DATA_FILE, rep_data))
        self.assertTrue(verify_bit_exact(DATA_HQ_FILE, rep_hq))
        self.assertEqual(sha256_file(rep_data), sha256_file(DATA_FILE))
        self.assertEqual(sha256_file(rep_hq), sha256_file(DATA_HQ_FILE))

    def test_ac2_unit_stats_and_binary_modding(self):
        """
        AC 2: Unit Stat (Movement Speed) & New Unit Patching Verification:
        - Structured dataset with >= 40 units/heroes/buildings mapped to Korean names,
          exact binary VA / file offset, movement speed, HP, attack, cost.
        - Complete diff table showing what Dawn changed compared to UseMap.
        - Automated patch test modifying movement speed and stats on cloned dawn.exe.
        - Re-read binary to verify exact operand bytes changed while PE headers remain intact.
        - Decode 6 command-card hooks in code cave and inject an additional button slot.
        """
        catalog = load_unit_catalog()
        # Verify >= 40 units
        self.assertGreaterEqual(len(catalog), 40)

        # Verify diff table
        diffs = catalog.get_diff_summary()
        self.assertGreater(len(diffs), 10, "Expected diff table with > 10 modified units")

        # Patch test on cloned binary
        test_exe = clone_dawn_exe(self.temp_dir)
        orig_sha = sha256_file(test_exe)
        patcher = BinaryPatcher(str(test_exe), catalog=catalog)

        # Modify unit 50 (일본 농부) movement speed from 7 to 12
        patch_speed = patcher.patch_unit_stat(50, "speed", 12)
        self.assertTrue(patch_speed.success)
        self.assertEqual(patch_speed.new_value, 12)

        # Modify HP to 1500
        patch_hp = patcher.patch_unit_stat(50, "hp", 1500)
        self.assertTrue(patch_hp.success)
        self.assertEqual(patch_hp.new_value, 1500)

        # Re-read and verify bytes in binary
        with open(test_exe, "rb") as f:
            f.seek(patch_speed.file_offset)
            read_speed_bytes = f.read(len(patch_speed.new_bytes))
        self.assertEqual(read_speed_bytes, patch_speed.new_bytes)

        # Verify PE headers and alignments intact
        report = check_binary_integrity(str(DAWN_EXE), str(test_exe))
        self.assertTrue(report["pe_headers_intact"])
        self.assertTrue(report["size_valid"])
        self.assertEqual(test_exe.stat().st_size, ORIGINAL_DAWN_EXE_SIZE)

        # Decode 6 cave hooks
        hooks = decode_cave_hooks(str(DAWN_EXE))
        self.assertEqual(len(hooks), 6)
        all_cmd_ids = set()
        for h in hooks:
            self.assertTrue(h["hooked"])
            for b in h["injected_buttons"]:
                all_cmd_ids.add(b["cmd_id"])

        # Check required command IDs from request: 0x27, 0x28, 0x69, 0x6f, 0x114
        for expected_cmd in [0x27, 0x28, 0x69, 0x6F, 0x114]:
            self.assertIn(expected_cmd, all_cmd_ids)

        # Inject additional button slot into slack space
        btn_res = inject_command_card_button(
            binary_path=str(test_exe),
            target_building_or_va="조선 훈련도감",
            slot=11,
            cmd_id=0xAA,
            requirements=[0, 0, 0, 0, 0, 0],
        )
        self.assertTrue(btn_res.success)
        self.assertEqual(test_exe.stat().st_size, ORIGINAL_DAWN_EXE_SIZE)

    def test_ac3_asset_decoding(self):
        """
        AC 3: Proprietary Asset (.spr / .ytl / .YAV) Decoding Verification:
        - Decode at least 10 distinct .spr/.ytl/.ypr files using Imjin2.pal into non-empty PNGs
          with verified dimensions matching .spr header.
        - Convert at least 5 .YAV files from dawn\\eft and dawn\\music into playable RIFF .wav files.
        """
        # 1. Audio conversions (>= 5 .YAV files)
        audio_dir = self.temp_dir / "ac3_audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        yav_candidates = list(EFT_DIR.glob("*.yav"))
        if MUSIC_DIR.exists():
            yav_candidates += list(MUSIC_DIR.glob("*.yav"))
        self.assertGreaterEqual(len(yav_candidates), 5)

        converted_wavs = 0
        for yav_file in yav_candidates[:5]:
            out_wav = audio_dir / f"{yav_file.stem}.wav"
            success = convert_yav_to_wav(yav_file, out_wav)
            self.assertTrue(success, f"Failed converting {yav_file.name}")
            self.assertTrue(out_wav.exists())

            # Validate RIFF header and sample count
            with wave.open(str(out_wav), "rb") as wf:
                audio = YAVAudio.from_file(yav_file)
                self.assertEqual(wf.getnchannels(), audio.channels)
                self.assertEqual(wf.getframerate(), audio.sample_rate)
                self.assertEqual(wf.getnframes(), audio.sample_count)
            converted_wavs += 1
        self.assertGreaterEqual(converted_wavs, 5)

        # 2. Graphic decoders (>= 10 .spr / .ytl / .ypr files)
        graphics_dir = self.temp_dir / "ac3_graphics"
        assets_to_decode = [
            BATTLE_SPR,
            FNT_DIR / "mouse.spr",
            CHAR_DIR / "farmerk.spr",
            CHAR_DIR / "swordk.spr",
            CHAR_DIR / "arrowk.spr",
            CHAR_DIR / "monkk.spr",
        ]
        ytl_candidates = list(TILE_DIR.glob("**/*.ytl"))
        ypr_candidates = list(TILE_DIR.glob("**/*.ypr"))
        assets_to_decode.extend(ytl_candidates[:4])
        assets_to_decode.extend(ypr_candidates[:2])

        existing_assets = [p for p in assets_to_decode if p.exists()]
        self.assertGreaterEqual(len(existing_assets), 10)

        decoded_count = 0
        for asset in existing_assets[:10]:
            sub_out = graphics_dir / asset.stem
            ext = asset.suffix.lower()
            if ext == ".spr":
                meta = decode_spr(asset, self.pal_path, sub_out, export_atlas=False, export_frames=True)
            elif ext == ".ytl":
                meta = decode_ytl(asset, self.pal_path, sub_out, export_atlas=False, export_frames=True)
            elif ext == ".ypr":
                meta = decode_ypr(asset, self.pal_path, sub_out, export_atlas=False, export_frames=True)
            else:
                continue

            self.assertEqual(meta.version, 9)
            self.assertGreater(meta.width, 0)
            self.assertGreater(meta.height, 0)
            self.assertGreater(meta.frame_count, 0)

            frame_0_name = meta.frames[0].file_name or f"{meta.name}_000.png"
            f0_path = sub_out / frame_0_name
            self.assertTrue(f0_path.exists())
            with Image.open(f0_path) as img:
                self.assertEqual(img.size, (meta.width, meta.height))
                self.assertEqual(img.mode, "RGBA")
            decoded_count += 1

        self.assertGreaterEqual(decoded_count, 10)

    def test_ac4_map_parsing_and_minimap_rendering(self):
        """
        AC 4: .map File Parsing & Modification Verification:
        - Read at least 5 .map files from dawn\\cusmap\\*.map.
        - Extract dimensions, tile/unit/resource arrays.
        - Generate non-blank 2D minimap PNG previews for each.
        - Round-trip modification test producing a valid 1,132,876-byte .map file.
        """
        map_files = sorted(list(CUSMAP_DIR.glob("*.map")))[:5]
        self.assertGreaterEqual(len(map_files), 5, "Expected >= 5 cusmap files")

        minimap_dir = self.temp_dir / "ac4_minimaps"
        minimap_dir.mkdir(parents=True, exist_ok=True)

        for idx, map_p in enumerate(map_files):
            # 1. Parse .map
            map_data = parse_map(map_p)
            self.assertEqual(map_data.version, 1)
            self.assertTrue(70 <= map_data.width <= 180)
            self.assertTrue(70 <= map_data.height <= 180)
            self.assertIn(map_data.num_players, range(1, 9))

            # 2. Render 2D minimap preview
            out_png = minimap_dir / f"minimap_{idx}_{map_p.stem}.png"
            success = render_minimap(map_data, out_png, width=350, height=350)
            self.assertTrue(success)
            self.assertTrue(out_png.exists())

            with Image.open(out_png) as img:
                self.assertEqual(img.size, (350, 350))
                # Non-blank check
                extrema = img.getextrema()
                for c_min, c_max in extrema:
                    self.assertGreater(c_max - c_min, 15)

        # 3. Round-trip modification test
        cloned_map = clone_map_file(map_files[0], self.temp_dir)
        modified = modify_map(
            cloned_map,
            {
                "player_starts": [{"player_id": 0, "x": 30, "y": 40}],
                "resources": {"set": [{"x": 20, "y": 20, "type_id": 1, "amount": 100}]},
            },
        )
        saved_map_path = self.temp_dir / "ac4_modified_roundtrip.map"
        success = save_map(modified, saved_map_path)
        self.assertTrue(success)
        self.assertEqual(saved_map_path.stat().st_size, ORIGINAL_MAP_SIZE)

        # Re-read and verify persistence
        re_read = parse_map(saved_map_path)
        p0 = [ps for ps in re_read.get_player_starts() if ps.player_id == 0][0]
        self.assertEqual(p0.x, 30)
        self.assertEqual(p0.y, 40)
        res = re_read.get_resource(20, 20)
        self.assertIsNotNone(res)
        self.assertEqual(res.type_id, 1)
        self.assertEqual(res.amount, 100)

    def test_ac5_workspace_safety_and_integrity(self):
        """
        AC 5: Integrity & Safety Check:
        - git status in C:\\src\\rea remains clean.
        - Every file in C:\\src\\reverse-imzinrok\\YM retains original byte size and SHA-256 hash.
        """
        # Check rea git status
        res = subprocess.run(
            ["git", "-C", r"C:\src\rea", "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"git status failed: {res.stderr}")
        self.assertEqual(
            res.stdout.strip(),
            "",
            f"Git repository C:\\src\\rea has uncommitted or dirty files: {res.stdout}",
        )

        # Run safety verification audit script
        safety_script = BASE_DIR / "tools" / "verify_safety.py"
        self.assertTrue(safety_script.exists())
        audit = subprocess.run(
            ["python", str(safety_script)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(audit.returncode, 0, f"Safety audit failed: {audit.stderr}\n{audit.stdout}")
        self.assertIn("AUDIT RESULT: PASSED", audit.stdout)

        # Also verify via conftest fixture
        self.assertTrue(verify_ym_integrity())


if __name__ == "__main__":
    unittest.main()
