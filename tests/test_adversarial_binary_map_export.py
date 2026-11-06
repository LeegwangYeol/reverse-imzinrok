#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_adversarial_binary_map_export
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adversarial stress-testing suite for serve_web.py, binary patcher, and map export.
Authored by Teamwork empirical-challenger agent.

Coverage:
1. Binary Patch Stress:
   - Sequential stat patches on cloned dawn.exe (single unit & multi-unit).
   - Extreme values: speed=30, hp=9999, negative/overflow values.
   - PE header preservation (first 0x1000 section alignment boundary).
   - Bit-exact 1,032,192-byte file size verification.
   - Immutability of original YM/dawn/dawn.exe (SHA-256 preserved).
2. Map Export Stress:
   - Zero-modification export bit-exactness and size.
   - Heavy modification export: 8 player starts changed, 50 resources placed/removed,
     terrain/cliff edits, theme change.
   - Strict 1,132,876-byte file size verification.
   - Clean re-parse with parse_map() with 0 format errors and content verification.
3. Concurrency & Invalid Request Robustness:
   - 50 concurrent requests across GET and POST endpoints.
   - Malformed JSON payloads, non-dict payloads, empty bodies, missing fields.
   - Path traversal handling.
   - Proper HTTP 400 Bad Request error handling without server crash.
   - End-to-end server survival and liveness check.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from serve_web import (
    CUSMAP_DIR,
    DATASET_PATH,
    MOD_EXPORT_DIR,
    ORIG_DAWN_EXE,
    WEB_DIR,
    create_server,
)
from tools.map.modder import MapModder
from tools.map.parser import (
    MAP_FILE_SIZE,
    MapData,
    MapFormatError,
    parse_map,
    save_map,
)
from tools.modding.binary_patcher import (
    EXPECTED_BINARY_SIZE,
    BinaryPatcher,
    check_binary_integrity,
    modify_unit_stat,
)
from tools.verify_safety import YM_KEY_MANIFEST


class TestAdversarialBinaryMapExport(unittest.TestCase):
    """Adversarial stress and robustness test suite."""

    server: Any
    server_thread: threading.Thread
    port: int = 8019
    base_url: str
    orig_dawn_hash: str

    @classmethod
    def setUpClass(cls):
        """Start local test server on dedicated port and record original dawn.exe hash."""
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = create_server(host="127.0.0.1", port=cls.port)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

        # Record hash of original dawn.exe
        with open(ORIG_DAWN_EXE, "rb") as f:
            cls.orig_dawn_hash = hashlib.sha256(f.read()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        """Shut down test server cleanly."""
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass

    def _get(self, path: str) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                headers = dict(res.headers.items())
                body = json.loads(res.read().decode("utf-8"))
                return res.status, body, headers
        except urllib.error.HTTPError as e:
            headers = dict(e.headers.items())
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"raw": "non-json error"}
            return e.code, body, headers

    def _post(
        self,
        path: str,
        payload: Any,
        raw_body: Optional[bytes] = None,
        content_type: str = "application/json",
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        url = f"{self.base_url}{path}"
        if raw_body is None:
            if isinstance(payload, bytes):
                data_bytes = payload
            elif isinstance(payload, str):
                data_bytes = payload.encode("utf-8")
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
        else:
            data_bytes = raw_body

        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": content_type, "Content-Length": str(len(data_bytes))},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                headers = dict(res.headers.items())
                body = json.loads(res.read().decode("utf-8"))
                return res.status, body, headers
        except urllib.error.HTTPError as e:
            headers = dict(e.headers.items())
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"raw": "non-json error"}
            return e.code, body, headers
        except http.client.RemoteDisconnected:
            # Server crash / unhandled exception in handler thread
            return -1, {"error": "RemoteDisconnected: server abruptly closed connection (crash)"}, {}

    def _assert_orig_dawn_untouched(self):
        """Verify original YM/dawn/dawn.exe has never been modified."""
        with open(ORIG_DAWN_EXE, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(
            current_hash,
            self.orig_dawn_hash,
            "CRITICAL VIOLATION: Original YM/dawn/dawn.exe was modified!",
        )

    # =========================================================================
    # 1. BINARY PATCH STRESS TESTING
    # =========================================================================
    def test_01_sequential_extreme_patches_single_unit(self):
        """Stress: Apply multiple sequential stat patches on the same cloned binary with extreme values."""
        target_name = "adv_dawn_seq_single_unit.exe"
        target_path = MOD_EXPORT_DIR / target_name

        # Patch 1: Extreme speed=30 (imm8 boundary check)
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": target_name,
                "fresh_clone": True,
                "unit_id": 50,  # 일본 농부
                "stat_name": "speed",
                "new_value": 30,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["success"])
        self.assertTrue(body["pe_integrity"]["valid"])
        self.assertTrue(body["pe_integrity"]["pe_headers_intact"])
        self.assertEqual(target_path.stat().st_size, EXPECTED_BINARY_SIZE)

        # Patch 2: Extreme hp=9999 (imm32 value) on the SAME binary
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": target_name,
                "fresh_clone": False,  # mutate existing clone
                "unit_id": 50,
                "stat_name": "hp",
                "new_value": 9999,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["success"])
        self.assertTrue(body["pe_integrity"]["valid"])
        self.assertTrue(body["pe_integrity"]["pe_headers_intact"])
        self.assertEqual(target_path.stat().st_size, EXPECTED_BINARY_SIZE)

        # Patch 3: Defense = 120
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": target_name,
                "fresh_clone": False,
                "unit_id": 50,
                "stat_name": "defense",
                "new_value": 120,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)

        # Patch 4: Attack = 250
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": target_name,
                "fresh_clone": False,
                "unit_id": 50,
                "stat_name": "attack",
                "new_value": 250,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)

        # Verify final file integrity
        final_integrity = check_binary_integrity(str(ORIG_DAWN_EXE), str(target_path))
        self.assertTrue(final_integrity["valid"])
        self.assertTrue(final_integrity["pe_headers_intact"])
        self.assertTrue(final_integrity["size_valid"])
        self.assertEqual(target_path.stat().st_size, 1_032_192)

        # Verify original binary untouched
        self._assert_orig_dawn_untouched()

    def test_02_sequential_patches_multi_unit(self):
        """Stress: Sequential patches across 5 distinct units/heroes on the same cloned binary."""
        target_name = "adv_dawn_seq_multi_unit.exe"
        target_path = MOD_EXPORT_DIR / target_name

        # Units and attributes verified to have immediate push instructions
        units_and_patches = [
            (50, "speed", 25),      # 일본 농부 (imm8 speed)
            (50, "hp", 9999),       # 일본 농부 (imm32 hp)
            (13, "hp", 5000),       # 조선 창병 (imm32 hp)
            (13, "attack", 85),     # 조선 창병 (imm8 attack)
            (49, "speed", 20),      # 조선 이순신 (imm8 speed)
            (49, "hp", 8888),       # 조선 이순신 (imm32 hp)
            (107, "speed", 22),     # 명 농부 (imm8 speed)
            (107, "hp", 4500),      # 명 농부 (imm32 hp)
        ]

        for i, (uid, stat, val) in enumerate(units_and_patches):
            status, body, _ = self._post(
                "/api/patch_binary",
                {
                    "target_filename": target_name,
                    "fresh_clone": (i == 0),
                    "unit_id": uid,
                    "stat_name": stat,
                    "new_value": val,
                },
            )
            self.assertEqual(status, HTTPStatus.OK, f"Failed patching unit {uid} {stat}={val}")
            self.assertTrue(body["success"])

        # Final verification
        final_integrity = check_binary_integrity(str(ORIG_DAWN_EXE), str(target_path))
        self.assertTrue(final_integrity["valid"])
        self.assertTrue(final_integrity["pe_headers_intact"])
        self.assertEqual(target_path.stat().st_size, 1_032_192)
        self._assert_orig_dawn_untouched()

    def test_03_batch_stat_patches_extreme(self):
        """Stress: Batch patch request modifying 8 attributes across 3 factions simultaneously."""
        target_name = "adv_dawn_batch_extreme.exe"
        target_path = MOD_EXPORT_DIR / target_name

        payload = {
            "target_filename": target_name,
            "fresh_clone": True,
            "patches": [
                {"unit_id": 50, "stat_name": "speed", "new_value": 28},
                {"unit_id": 50, "stat_name": "hp", "new_value": 8888},
                {"unit_id": 13, "stat_name": "attack", "new_value": 75},
                {"unit_id": 13, "stat_name": "defense", "new_value": 30},
                {"unit_id": 13, "stat_name": "hp", "new_value": 4500},
                {"unit_id": 49, "stat_name": "speed", "new_value": 18},
                {"unit_id": 49, "stat_name": "hp", "new_value": 9000},
                {"unit_id": 107, "stat_name": "speed", "new_value": 20},
            ],
        }

        status, body, _ = self._post("/api/patch_binary", payload)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["success"])
        self.assertEqual(body["patches_applied"], 8)
        self.assertTrue(body["pe_integrity"]["valid"])
        self.assertEqual(target_path.stat().st_size, 1_032_192)
        self._assert_orig_dawn_untouched()

    def test_04_register_push_stat_returns_400(self):
        """Adversarial: Patching a register-pushed stat (e.g. Unit 11 권율 speed) must return 400."""
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": "adv_reg_speed.exe",
                "unit_id": 11,  # 권율 uses 'push esi' for speed
                "stat_name": "speed",
                "new_value": 22,
            },
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertFalse(body.get("success", True))
        self.assertIn("error", body)
        self.assertIn("not an immediate push", body["error"])

    def test_05_adversarial_binary_patch_boundary_errors(self):
        """Adversarial: Test invalid parameters, imm8 overflow, bad unit_id."""
        # 1. imm8 overflow on speed (e.g. speed=500, max allowed is 255)
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": "adv_overflow.exe",
                "unit_id": 50,
                "stat_name": "speed",
                "new_value": 500,
            },
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertFalse(body.get("success", False))
        self.assertIn("error", body)

        # 2. Invalid non-existent unit_id
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": "adv_invalid_unit.exe",
                "unit_id": 99999,
                "stat_name": "speed",
                "new_value": 10,
            },
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertIn("error", body)

        # 3. Invalid stat_name
        status, body, _ = self._post(
            "/api/patch_binary",
            {
                "target_filename": "adv_invalid_stat.exe",
                "unit_id": 50,
                "stat_name": "non_existent_stat_xyz",
                "new_value": 10,
            },
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

        # 4. Path traversal handling: check that original YM dawn.exe is never overwritten
        traversal_attempts = [
            "../../YM/dawn/dawn.exe",
            r"..\..\YM\dawn\dawn.exe",
        ]
        for trav in traversal_attempts:
            status, body, _ = self._post(
                "/api/patch_binary",
                {
                    "target_filename": trav,
                    "unit_id": 50,
                    "stat_name": "speed",
                    "new_value": 10,
                },
            )
            # The server must NOT modify YM/dawn/dawn.exe under any circumstance!
            self._assert_orig_dawn_untouched()

    # =========================================================================
    # 2. MAP EXPORT STRESS TESTING
    # =========================================================================
    def test_06_map_export_zero_modifications(self):
        """Map Export: Zero modifications should preserve exact structure and 1,132,876 bytes."""
        base_name = "(2인,100X100)수성.map"
        out_name = "adv_export_zero_mod.map"
        out_path = MOD_EXPORT_DIR / out_name

        status, body, _ = self._post(
            "/api/export_map",
            {
                "base_map": base_name,
                "output_filename": out_name,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["success"])
        self.assertEqual(body["file_size"], MAP_FILE_SIZE)
        self.assertEqual(out_path.stat().st_size, MAP_FILE_SIZE)

        # Re-parse cleanly with parse_map
        reparsed = parse_map(out_path)
        self.assertEqual(len(reparsed.raw_data), MAP_FILE_SIZE)
        self.assertEqual(reparsed.width, 100)
        self.assertEqual(reparsed.height, 100)

    def test_07_map_export_heavy_modifications(self):
        """Stress: Heavy modifications with 8 player starts, 50 resources placed, 50 removed, terrain edits."""
        base_name = "(2인,100X100)수성.map"
        out_name = "adv_export_heavy_mod.map"
        out_path = MOD_EXPORT_DIR / out_name

        # 8 player starting positions changed across the grid
        new_starts = [
            {"player_id": 0, "x": 10, "y": 10},
            {"player_id": 1, "x": 20, "y": 20},
            {"player_id": 2, "x": 30, "y": 30},
            {"player_id": 3, "x": 40, "y": 40},
            {"player_id": 4, "x": 50, "y": 50},
            {"player_id": 5, "x": 60, "y": 60},
            {"player_id": 6, "x": 70, "y": 70},
            {"player_id": 7, "x": 80, "y": 80},
        ]

        # 50 resources placed: 25 potatoes/rice (type 1 & 100) and 25 bamboo/trees (type 2 & 3)
        placed_resources = []
        for i in range(50):
            rx = 15 + (i % 10)
            ry = 15 + (i // 10)
            rtype = 1 if i < 25 else 3
            ramount = 10 + i * 4
            placed_resources.append({
                "x": rx,
                "y": ry,
                "type_id": rtype,
                "amount": min(255, ramount),
                "variant": i % 4,
                "state": 5,
            })

        # 50 resources to remove (coordinates in non-overlapping grid)
        remove_resources = []
        for i in range(50):
            remove_resources.append({"x": 45 + (i % 10), "y": 45 + (i // 10)})

        # 20 terrain modifications (cliff/walkability and elevations)
        terrain_mods = []
        for i in range(20):
            terrain_mods.append({
                "x": 5 + i,
                "y": 5,
                "walkability": 1,  # cliff obstacle
                "terrain_type": 2,  # ground
                "elevation": (i % 4),
            })

        payload = {
            "base_map": base_name,
            "output_filename": out_name,
            "theme_id": 1,  # Switch to snow theme
            "player_starts": new_starts,
            "resources": placed_resources,
            "remove_resources": remove_resources,
            "terrain_modifications": terrain_mods,
        }

        status, body, _ = self._post("/api/export_map", payload)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(body["success"])
        self.assertEqual(body["file_size"], MAP_FILE_SIZE)
        self.assertEqual(out_path.stat().st_size, MAP_FILE_SIZE)

        # Re-parse cleanly with parse_map() with 0 format errors
        reparsed = parse_map(out_path)
        self.assertEqual(len(reparsed.raw_data), MAP_FILE_SIZE)
        self.assertEqual(reparsed.theme_id, 1)
        self.assertEqual(reparsed.theme_name, "snow")

        # Verify all 8 player starts match
        starts_list = reparsed.get_player_starts()
        starts_by_id = {ps.player_id: (ps.x, ps.y) for ps in starts_list}
        for ps in new_starts:
            coord = starts_by_id.get(ps["player_id"])
            self.assertIsNotNone(coord)
            self.assertEqual(coord, (ps["x"], ps["y"]), f"Mismatch on player {ps['player_id']}")

        # Verify placed resources exist in re-parsed map
        for pr in placed_resources[:10]:  # spot-check first 10
            r_obj = reparsed.get_resource(pr["x"], pr["y"])
            self.assertIsNotNone(r_obj, f"Resource at ({pr['x']}, {pr['y']}) missing after re-parse")
            self.assertEqual(r_obj.type_id, pr["type_id"])
            self.assertEqual(r_obj.amount, pr["amount"])

        # Verify removed resources are gone
        for rem in remove_resources[:10]:
            r_obj = reparsed.get_resource(rem["x"], rem["y"])
            self.assertIsNone(r_obj, f"Resource at ({rem['x']}, {rem['y']}) was not removed")

        # Verify terrain walkability
        for tm in terrain_mods[:5]:
            self.assertEqual(reparsed.get_walkability(tm["x"], tm["y"]), 1)
            self.assertEqual(reparsed.get_elevation(tm["x"], tm["y"]), tm["elevation"])

    def test_08_map_export_safety_check(self):
        """Map Export Safety: Verify original cusmap files in YM remain completely untouched."""
        target_p = ROOT_DIR / "YM" / "dawn" / "cusmap" / "(2인,100X100)수성.map"
        self.assertEqual(target_p.stat().st_size, MAP_FILE_SIZE)
        safety_status = YM_KEY_MANIFEST.get("dawn/cusmap/(2인,100X100)수성.map")
        if safety_status:
            with open(target_p, "rb") as f:
                chash = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(chash, safety_status["sha256"])

    # =========================================================================
    # 3. CONCURRENT / HIGH-LOAD & INVALID REQUEST ROBUSTNESS
    # =========================================================================
    def test_09_concurrent_high_load_stress(self):
        """Concurrency Stress: 50 simultaneous mixed requests hitting GET and POST APIs."""
        def make_req(idx: int) -> Tuple[int, str]:
            op_type = idx % 5
            if op_type == 0:
                s, _, _ = self._get("/api/status")
                return s, "status"
            elif op_type == 1:
                s, _, _ = self._get("/api/dataset")
                return s, "dataset"
            elif op_type == 2:
                s, _, _ = self._get("/api/maps")
                return s, "maps"
            elif op_type == 3:
                # Concurrent binary patch with unique file per thread
                t_name = f"thread_dawn_{idx}.exe"
                s, _, _ = self._post(
                    "/api/patch_binary",
                    {
                        "target_filename": t_name,
                        "fresh_clone": True,
                        "unit_id": 50,
                        "stat_name": "speed",
                        "new_value": 10 + (idx % 15),
                    },
                )
                return s, "patch_binary"
            else:
                # Concurrent map export with unique file per thread
                m_name = f"thread_map_{idx}.map"
                s, _, _ = self._post(
                    "/api/export_map",
                    {
                        "base_map": "(2인,100X100)수성.map",
                        "output_filename": m_name,
                        "player_starts": [{"player_id": 0, "x": idx, "y": idx}],
                    },
                )
                return s, "export_map"

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(make_req, range(50)))

        self.assertEqual(len(results), 50)
        failures = [(code, tag) for code, tag in results if code != HTTPStatus.OK]
        self.assertEqual(failures, [], f"Concurrent request failures: {failures}")

    def test_10_syntax_malformed_json_returns_400(self):
        """Robustness: Broken JSON syntax returns HTTP 400 Bad Request."""
        syntax_errors = [
            b"{ broken json syntax : [",
            b"plain non-json text string",
            b'{"key": "unclosed string',
            b"\x00\x01\x02\x03\xff\xfe",
        ]
        for raw in syntax_errors:
            status, body, _ = self._post("/api/patch_binary", payload=None, raw_body=raw)
            self.assertEqual(status, HTTPStatus.BAD_REQUEST)
            self.assertIn("error", body)

    def test_11_missing_fields_returns_400(self):
        """Robustness: Missing required fields return HTTP 400 Bad Request."""
        bad_patch_payloads = [
            {},
            {"stat_name": "speed"},
            {"unit_id": 50},
            {"patches": []},
            {"patches": "not a list"},
            {"unit_id": "not_an_int", "new_value": "not_an_int"},
        ]
        for p in bad_patch_payloads:
            status, body, _ = self._post("/api/patch_binary", p)
            self.assertEqual(
                status,
                HTTPStatus.BAD_REQUEST,
                f"Patch binary with payload {p} returned {status} instead of 400",
            )
            self.assertIn("error", body)

    def test_12_non_dict_json_vulnerability_probe(self):
        """Vulnerability Probe: Non-dict JSON (e.g. list, string) probes server response.
        
        Empirically probes whether server handles non-dict JSON gracefully with 400
        or triggers an unhandled AttributeError resulting in RemoteDisconnected.
        """
        non_dict_payloads = [
            b"[1, 2, 3]",
            b'"just a string"',
            b"12345",
            b"true",
        ]
        results = {}
        for raw in non_dict_payloads:
            status, body, _ = self._post("/api/patch_binary", payload=None, raw_body=raw)
            results[raw.decode("latin1")] = (status, body.get("error", ""))

        # We record this finding for the adversarial handoff report:
        # If status == -1 (RemoteDisconnected), it proves the bug exists empirically!
        has_crash = any(status == -1 for status, _ in results.values())
        print(f"\n[EMPIRICAL PROBE] Non-dict JSON test results: {results} (has_crash={has_crash})")

    def test_13_server_survival_and_liveness_check(self):
        """Verification: After all aggressive stress testing, verify server is healthy and alive."""
        status, body, _ = self._get("/api/status")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(body["status"], "ok")
        self.assertGreater(body["uptime_seconds"], 0)
        self.assertEqual(body["dataset_units"], 111)

        # Verify dataset can still be read
        status, ds_body, _ = self._get("/api/dataset")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(ds_body["total"], 111)

        # Verify overall project safety remains 100% untouched
        self._assert_orig_dawn_untouched()


if __name__ == "__main__":
    unittest.main()
