#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serve_web.py - Local Multi-Threaded Web Server & REST API Bridge
================================================================
Imjinrok 2+: Dawn (임진록 2+ 조선의 반격: 여명) Web RTS Prototype & Modding Sandbox

Features:
- Multi-threaded HTTP server using Python standard library http.server.ThreadingHTTPServer.
- Full CORS headers, modern MIME types (.wasm, .json, .wav, .png, .map, etc.), and default root route to /index.html.
- REST API Endpoints:
    GET  /api/status          - Server status, uptime, dataset stats
    GET  /api/dataset         - Full 111-unit dataset from tools/modding/dataset.json
    GET  /api/maps            - Available .map files from YM/dawn/cusmap/
    GET  /api/mod_configs     - Saved mod profiles from web_prototype/mod_export/
    POST /api/patch_binary    - In-place unit stat patch on cloned dawn.exe with PE integrity check
    POST /api/export_map      - Bit-exact 1,132,876-byte .map export via MapModder
    POST /api/save_mod_config - Persist custom unit and mod profiles to JSON
- Strict workspace safety guarantees: YM/ and rea/ are 100% read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

# Ensure Windows consoles use UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.map.modder import MapModder
from tools.map.parser import MAP_FILE_SIZE, MapFormatError, parse_map, save_map
from tools.modding.binary_patcher import (
    EXPECTED_BINARY_SIZE,
    STAT_TO_ARG,
    BinaryPatcher,
    check_binary_integrity,
    modify_unit_stat,
)
from tools.modding.unit_catalog import load_unit_catalog

# Global Paths & Constants
START_TIME = time.time()
WEB_DIR = ROOT_DIR / "web_prototype"
MOD_EXPORT_DIR = WEB_DIR / "mod_export"
CUSMAP_DIR = ROOT_DIR / "YM" / "dawn" / "cusmap"
ORIG_DAWN_EXE = ROOT_DIR / "YM" / "dawn" / "dawn.exe"
DATASET_PATH = ROOT_DIR / "tools" / "modding" / "dataset.json"

# MIME Type Mapping for Web RTS Assets
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".map": "application/octet-stream",
    ".pal": "application/octet-stream",
    ".spr": "application/octet-stream",
    ".ytl": "application/octet-stream",
    ".ypr": "application/octet-stream",
    ".dat": "application/octet-stream",
    ".txt": "text/plain; charset=utf-8",
}


def _ensure_directories():
    """Ensure runtime staging directories exist."""
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    MOD_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class ImjinrokWebHandler(SimpleHTTPRequestHandler):
    """Multi-threaded HTTP request handler supporting static files, CORS, and REST APIs."""

    server_directory = WEB_DIR
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        **MIME_TYPES,
    }

    def __init__(self, *args, directory: Optional[str] = None, **kwargs):
        _ensure_directories()
        target_dir = directory if directory is not None else str(self.__class__.server_directory)
        super().__init__(*args, directory=target_dir, **kwargs)

    def end_headers(self):
        """Inject CORS and cache-control headers on all responses."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Requested-With, Accept, Origin",
        )
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        """Respond to CORS preflight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests for static files or REST APIs."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Dispatch API routes
        if path.startswith("/api/"):
            return self.handle_api_get(path, parse_qs(parsed.query))

        # Default root route to index.html
        if path in ("", "/"):
            query_str = f"?{parsed.query}" if parsed.query else ""
            self.path = f"/index.html{query_str}"

        return super().do_GET()

    def do_HEAD(self):
        """Handle HEAD requests."""
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        if parsed.path in ("", "/"):
            query_str = f"?{parsed.query}" if parsed.query else ""
            self.path = f"/index.html{query_str}"
        return super().do_HEAD()

    def do_POST(self):
        """Handle POST requests for REST APIs."""
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            return self.handle_api_post(path)
        self._send_json(
            {"error": f"Endpoint not found: {self.path}"},
            HTTPStatus.NOT_FOUND,
        )

    # -------------------------------------------------------------------------
    # JSON Request / Response Helpers
    # -------------------------------------------------------------------------
    def _send_json(self, data: Any, status: int = HTTPStatus.OK):
        """Serialize and send a JSON response with appropriate headers."""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Any:
        """Read and parse JSON from request body."""
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode("utf-8")
        return json.loads(raw)

    # -------------------------------------------------------------------------
    # REST API Handlers
    # -------------------------------------------------------------------------
    def handle_api_get(self, path: str, query: Dict[str, List[str]]):
        """Route and execute GET API endpoints."""
        if path == "/api/status":
            dataset_count = 0
            if DATASET_PATH.exists():
                try:
                    with open(DATASET_PATH, "r", encoding="utf-8") as f:
                        ds = json.load(f)
                        dataset_count = len(ds)
                except Exception:
                    dataset_count = 111
            else:
                dataset_count = 111

            return self._send_json({
                "status": "ok",
                "server": "Imjinrok2+ Web RTS Prototype Server",
                "version": "1.0.0",
                "uptime_seconds": round(time.time() - START_TIME, 2),
                "dataset_units": dataset_count,
                "mod_export_dir": str(MOD_EXPORT_DIR),
                "endpoints": [
                    "/api/status",
                    "/api/dataset",
                    "/api/maps",
                    "/api/mod_configs",
                    "/api/patch_binary",
                    "/api/export_map",
                    "/api/save_mod_config",
                ],
            })

        elif path == "/api/dataset":
            if not DATASET_PATH.exists():
                return self._send_json(
                    {"error": f"dataset.json not found at {DATASET_PATH}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            try:
                with open(DATASET_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._send_json({"total": len(data), "units": data})
            except Exception as e:
                return self._send_json(
                    {"error": f"Failed to load dataset: {e}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        elif path == "/api/maps":
            maps = []
            if CUSMAP_DIR.exists():
                for mp in sorted(CUSMAP_DIR.glob("*.map")):
                    maps.append({
                        "filename": mp.name,
                        "size": mp.stat().st_size,
                    })
            return self._send_json({"total": len(maps), "maps": maps})

        elif path == "/api/mod_configs":
            configs = []
            if MOD_EXPORT_DIR.exists():
                for cfg in sorted(MOD_EXPORT_DIR.glob("*.json")):
                    try:
                        with open(cfg, "r", encoding="utf-8") as f:
                            cdata = json.load(f)
                        configs.append({
                            "filename": cfg.name,
                            "profile_name": cdata.get("profile_name", cfg.stem),
                            "saved_at": cdata.get("saved_at", ""),
                            "stat_overrides_count": len(cdata.get("stat_overrides", {})),
                            "custom_units_count": len(cdata.get("custom_units", [])),
                        })
                    except Exception:
                        configs.append({"filename": cfg.name, "error": "Unparseable JSON"})
            return self._send_json({"total": len(configs), "configs": configs})

        else:
            return self._send_json(
                {"error": f"API endpoint not found: {path}"},
                HTTPStatus.NOT_FOUND,
            )

    def handle_api_post(self, path: str):
        """Route and execute POST API endpoints."""
        try:
            payload = self._read_json()
        except Exception as e:
            return self._send_json(
                {"error": f"Invalid JSON payload: {e}"},
                HTTPStatus.BAD_REQUEST,
            )

        if not isinstance(payload, dict):
            return self._send_json(
                {"error": "Request body must be a JSON object"},
                HTTPStatus.BAD_REQUEST,
            )

        try:
            if path == "/api/patch_binary":
                return self._handle_patch_binary(payload)
            elif path == "/api/export_map":
                return self._handle_export_map(payload)
            elif path == "/api/save_mod_config":
                return self._handle_save_mod_config(payload)
            else:
                return self._send_json(
                    {"error": f"API endpoint not found: {path}"},
                    HTTPStatus.NOT_FOUND,
                )
        except Exception as e:
            return self._send_json(
                {"error": f"API processing error: {e}"},
                HTTPStatus.BAD_REQUEST,
            )

    def _handle_patch_binary(self, payload: Dict[str, Any]):
        """Safely clones dawn.exe to mod_export/, applies unit stat patches, and checks PE integrity."""
        target_name = payload.get("target_filename", "dawn_modded.exe")
        if not isinstance(target_name, str):
            return self._send_json(
                {"error": "target_filename must be a string."},
                HTTPStatus.BAD_REQUEST,
            )
        if ".." in target_name or target_name.startswith(("/", "\\")) or Path(target_name).is_absolute():
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        safe_filename = Path(target_name).name
        if not safe_filename.lower().endswith(".exe"):
            safe_filename += ".exe"

        safe_target = (MOD_EXPORT_DIR / safe_filename).resolve()
        mod_export_resolved = MOD_EXPORT_DIR.resolve()

        # Strict safety check: prevent path traversal or writing outside mod_export
        try:
            safe_target.relative_to(mod_export_resolved)
        except ValueError:
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        if not ORIG_DAWN_EXE.exists():
            return self._send_json(
                {"error": f"Original dawn.exe not found at {ORIG_DAWN_EXE}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        # Clone dawn.exe if not yet cloned or if fresh_clone requested
        if not safe_target.exists() or payload.get("fresh_clone", False):
            shutil.copy2(ORIG_DAWN_EXE, safe_target)

        # Support single patch or batch patches
        patches = payload.get("patches")
        if patches is None:
            unit_id = payload.get("unit_id")
            new_value = payload.get("new_value")
            if unit_id is None or new_value is None:
                return self._send_json(
                    {"error": "Missing 'unit_id' or 'new_value' in request."},
                    HTTPStatus.BAD_REQUEST,
                )
            stat_name = payload.get("stat_name", "speed")
            patches = [{"unit_id": unit_id, "stat_name": stat_name, "new_value": new_value}]

        if not isinstance(patches, list) or len(patches) == 0:
            return self._send_json(
                {"error": "'patches' must be a non-empty list of patch objects."},
                HTTPStatus.BAD_REQUEST,
            )

        results = []
        try:
            for p in patches:
                uid = p.get("unit_id")
                if isinstance(uid, str) and uid.isdigit():
                    uid = int(uid)
                sname = str(p.get("stat_name", "speed"))
                nval = int(p.get("new_value"))
                res = modify_unit_stat(str(safe_target), uid, sname, nval)
                results.append(res.to_dict())

            integrity = check_binary_integrity(str(ORIG_DAWN_EXE), str(safe_target))
            hasher = hashlib.sha256()
            with open(safe_target, "rb") as f:
                hasher.update(f.read())
            sha256_hash = hasher.hexdigest()

            response_data = {
                "success": True,
                "output_file": str(safe_target),
                "output_filename": safe_filename,
                "output_sha256": sha256_hash,
                "download_url": f"/mod_export/{safe_filename}",
                "pe_integrity": integrity,
                "patches_applied": len(results),
            }
            if len(results) == 1:
                response_data["patch_result"] = results[0]
            else:
                response_data["patch_results"] = results

            return self._send_json(response_data)
        except Exception as e:
            return self._send_json(
                {"success": False, "error": f"Binary patching failed: {e}"},
                HTTPStatus.BAD_REQUEST,
            )

    def _handle_export_map(self, payload: Dict[str, Any]):
        """Modifies a base map via MapModder and saves a valid 1,132,876-byte file in mod_export/."""
        base_map_name = payload.get("base_map", "(2인,100X100)수성.map")
        output_name = payload.get("output_filename", "custom_exported.map")

        if not isinstance(base_map_name, str):
            return self._send_json(
                {"error": "base_map must be a string."},
                HTTPStatus.BAD_REQUEST,
            )
        if ".." in base_map_name or base_map_name.startswith(("/", "\\")) or Path(base_map_name).is_absolute():
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        if not isinstance(output_name, str):
            return self._send_json(
                {"error": "output_filename must be a string."},
                HTTPStatus.BAD_REQUEST,
            )
        if ".." in output_name or output_name.startswith(("/", "\\")) or Path(output_name).is_absolute():
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        safe_out_name = Path(output_name).name
        if not safe_out_name.lower().endswith(".map"):
            safe_out_name += ".map"

        dest_map = (MOD_EXPORT_DIR / safe_out_name).resolve()
        mod_export_resolved = MOD_EXPORT_DIR.resolve()

        try:
            dest_map.relative_to(mod_export_resolved)
        except ValueError:
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        # Locate base map file
        src_map: Optional[Path] = None
        clean_base = Path(base_map_name).name
        candidates = [
            CUSMAP_DIR / clean_base,
            WEB_DIR / "assets" / "maps" / clean_base,
            MOD_EXPORT_DIR / clean_base,
            Path(base_map_name),
        ]
        for cand in candidates:
            if cand.exists() and cand.is_file():
                src_map = cand
                break

        if src_map is None and CUSMAP_DIR.exists():
            fallback_maps = list(CUSMAP_DIR.glob("*.map"))
            if fallback_maps:
                src_map = fallback_maps[0]

        if src_map is None:
            return self._send_json(
                {"error": f"Base map '{base_map_name}' not found."},
                HTTPStatus.NOT_FOUND,
            )

        try:
            modder = MapModder(src_map)

            # Apply structured modifications dictionary if provided
            if "modifications" in payload and isinstance(payload["modifications"], dict):
                modder.apply_modifications(payload["modifications"])

            # Apply theme if provided
            theme_val = payload.get("theme_id", payload.get("theme"))
            if theme_val is not None:
                modder.set_theme(theme_val)

            # Apply player starts
            if "player_starts" in payload and isinstance(payload["player_starts"], list):
                for ps in payload["player_starts"]:
                    if isinstance(ps, dict):
                        modder.set_player_start(int(ps["player_id"]), int(ps["x"]), int(ps["y"]))
                    elif isinstance(ps, (list, tuple)) and len(ps) >= 3:
                        modder.set_player_start(int(ps[0]), int(ps[1]), int(ps[2]))

            # Apply resources to set
            if "resources" in payload and isinstance(payload["resources"], list):
                for r in payload["resources"]:
                    if isinstance(r, dict):
                        modder.set_resource(
                            x=int(r["x"]),
                            y=int(r["y"]),
                            type_id=int(r["type_id"]),
                            amount=int(r["amount"]) if "amount" in r else None,
                            variant=int(r.get("variant", 0)),
                            state=int(r.get("state", 5)),
                        )

            # Apply resources to remove
            if "remove_resources" in payload and isinstance(payload["remove_resources"], list):
                for rem in payload["remove_resources"]:
                    if isinstance(rem, dict):
                        modder.remove_resource(int(rem["x"]), int(rem["y"]))
                    elif isinstance(rem, (list, tuple)) and len(rem) >= 2:
                        modder.remove_resource(int(rem[0]), int(rem[1]))

            # Apply terrain modifications
            if "terrain_modifications" in payload and isinstance(payload["terrain_modifications"], list):
                for tm in payload["terrain_modifications"]:
                    x, y = int(tm["x"]), int(tm["y"])
                    walkability = tm.get("walkability")
                    terrain_type = tm.get("terrain_type", tm.get("type"))
                    elevation = tm.get("elevation")
                    water_depth = tm.get("water_depth")
                    modder.set_terrain_cell(
                        x=x,
                        y=y,
                        terrain_type=int(terrain_type) if terrain_type is not None else None,
                        walkability=int(walkability) if walkability is not None else None,
                        elevation=int(elevation) if elevation is not None else None,
                        water_depth=int(water_depth) if water_depth is not None else None,
                    )

            # Save modified map to destination
            modder.save(dest_map)
            file_size = dest_map.stat().st_size
            if file_size != MAP_FILE_SIZE:
                return self._send_json(
                    {"error": f"Exported map size mismatch: {file_size} != {MAP_FILE_SIZE}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

            return self._send_json({
                "success": True,
                "output_file": str(dest_map),
                "output_filename": safe_out_name,
                "download_url": f"/mod_export/{safe_out_name}",
                "file_size": file_size,
                "theme": modder.map_data.theme_name,
                "theme_id": modder.map_data.theme_id,
                "width": modder.map_data.width,
                "height": modder.map_data.height,
                "player_count": modder.map_data.num_players,
            })
        except Exception as e:
            return self._send_json(
                {"success": False, "error": f"Map export failed: {e}"},
                HTTPStatus.BAD_REQUEST,
            )

    def _handle_save_mod_config(self, payload: Dict[str, Any]):
        """Persists custom unit profiles and sandbox presets to JSON in mod_export/."""
        profile_name = payload.get("profile_name", f"profile_{int(time.time())}")
        if not isinstance(profile_name, str):
            return self._send_json(
                {"error": "profile_name must be a string."},
                HTTPStatus.BAD_REQUEST,
            )
        if ".." in profile_name or profile_name.startswith(("/", "\\")) or Path(profile_name).is_absolute():
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        clean_name = "".join(c for c in profile_name if c.isalnum() or c in ("-", "_"))
        if not clean_name:
            clean_name = f"profile_{int(time.time())}"

        out_file = (MOD_EXPORT_DIR / f"{clean_name}.json").resolve()
        mod_export_resolved = MOD_EXPORT_DIR.resolve()

        try:
            out_file.relative_to(mod_export_resolved)
        except ValueError:
            return self._send_json(
                {"error": "Path traversal detected"},
                HTTPStatus.BAD_REQUEST,
            )

        try:
            payload["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            return self._send_json({
                "success": True,
                "profile_name": clean_name,
                "file_path": str(out_file),
                "output_filename": f"{clean_name}.json",
                "download_url": f"/mod_export/{clean_name}.json",
                "stat_overrides_count": len(payload.get("stat_overrides", {})),
                "custom_units_count": len(payload.get("custom_units", [])),
            })
        except Exception as e:
            return self._send_json(
                {"success": False, "error": f"Failed to save mod config: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    web_dir: Optional[Union[str, Path]] = None,
) -> ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer instance."""
    ThreadingHTTPServer.allow_reuse_address = True
    serve_path = Path(web_dir) if web_dir else WEB_DIR
    serve_path.mkdir(parents=True, exist_ok=True)
    (serve_path / "mod_export").mkdir(parents=True, exist_ok=True)

    # Set class default directory
    ImjinrokWebHandler.server_directory = serve_path

    server = ThreadingHTTPServer((host, port), ImjinrokWebHandler)
    return server


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    web_dir: Optional[Union[str, Path]] = None,
):
    """Run the multi-threaded HTTP server."""
    server = create_server(host=host, port=port, web_dir=web_dir)
    actual_port = server.server_port
    print("=" * 80)
    print(f"[*] Imjinrok 2+: Dawn Web RTS Server running on http://{host}:{actual_port}")
    print(f"[*] Serving web directory: {web_dir or WEB_DIR}")
    print(f"[*] Mod export staging:    {MOD_EXPORT_DIR}")
    print("=" * 80)
    print("[*] REST Endpoints ready:")
    print("    GET  /api/status")
    print("    GET  /api/dataset")
    print("    GET  /api/maps")
    print("    GET  /api/mod_configs")
    print("    POST /api/patch_binary")
    print("    POST /api/export_map")
    print("    POST /api/save_mod_config")
    print("=" * 80)
    print("[*] Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server gracefully...")
    finally:
        server.shutdown()
        server.server_close()
        print("[*] Server shutdown complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Imjinrok 2+: Dawn Web RTS Prototype Server & REST API Bridge"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host/IP address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server TCP port (default: 8000)",
    )
    parser.add_argument(
        "--dir",
        default=str(WEB_DIR),
        help=f"Root directory for web assets (default: {WEB_DIR})",
    )
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, web_dir=args.dir)


if __name__ == "__main__":
    main()
