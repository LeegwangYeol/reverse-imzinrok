import os
import sys
import zipfile
import hashlib
from pathlib import Path

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

def build_package():
    print("=" * 70)
    print("  PACKAGING IMJINROK 2+ JOSEON EXPANSION STANDALONE RELEASE")
    print("=" * 70)

    workspace_root = Path(__file__).resolve().parent.parent
    ym_dir = workspace_root / "YM"
    release_dir = workspace_root / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    zip_path = release_dir / "Imjinrok2_Plus_Joseon_Expansion.zip"

    # User Guide Content
    readme_content = """================================================================================
  [임진록 2+ 조선 신규 10종 유닛 확장팩 (Joseon 10-Unit Expansion)]
================================================================================

본 패키지는 '임진록 2+ 조선의 반격'에 조선 신규 유닛 10종 및 최신 밸런스/AI 안정화
패치가 적용된 완전한 독립 실행(Standalone) 게임 패키지입니다.
별도의 추가 설치 없이 압축 해제 후 바로 플레이하실 수 있습니다.

--------------------------------------------------------------------------------
1. 게임 실행 방법
--------------------------------------------------------------------------------
1) 일반 전체화면 실행:
   - 폴더 내 '게임실행.bat' 또는 'dawn/dawn.exe'를 더블 클릭하여 실행합니다.

2) 윈도우 창모드 실행 (윈도우 10 / 11 권장):
   - 폴더 내 '창모드_실행(dxwnd).bat'을 실행하면 DirectDraw 색상 깨짐 없이
     쾌적한 고화질 창모드로 즐기실 수 있습니다.

3) 게임 모드:
   - '혼자하기' -> '임의 게임(스커미시)' 또는 '시나리오'에서 조선 진영을 선택합니다.
   - 단독 컴퓨터 AI와 대결 시 튕김 없이 안정적으로 자원 채취 및 교전이 진행됩니다.

--------------------------------------------------------------------------------
2. 조선 신규 유닛 10종 생산 건물 및 특수 능력
--------------------------------------------------------------------------------

[1] 조선 본영 (Joseon HQ)
  - 유생 (儒生) [단축키: Y]
    * 특수 능력: 부채 포박술 (사거리 5). 적 유닛에게 10초(150틱) 동안 완전 마비 부여.
    * 리셋 매커니즘: 포박된 적을 다시 공격하면 지속 시간이 즉시 10초로 초기화되어
      연속 스턴 락온 가능.
  - 불가살이 (不可殺伊) [단축키: U]
    * 특수 능력: MP 기반 자동 원/근거리 전환 듀얼 모드 유닛.
    * 마력 20 이상: 원거리 화차 불화살 투사체 발사 (사거리 6, -20 MP 소모).
    * 마력 20 미만: 근접 등가시 찌르기 모드로 자동 전환 (사거리 1, MP 소모 없음).
  - 구미호 (九尾狐) [단축키: F]
    * 특수 능력: 분신술 (C키). 전장에 자신과 동일한 구미호 분신을 소환하여 교란.

[2] 조선 병영 (Joseon Barracks)
  - 검술 낭인 (劍術浪人) [단축키: K]
    * 특수 능력: 높은 이동속도와 민첩한 발도술로 적 보병을 베어 넘기는 고속 근접 딜러.
  - 조총 낭인 (鳥銃浪人) [단축키: N]
    * 특수 능력: 조총을 신속하게 재장전하여 연사하는 원거리 타격 보병.
  - 털가면 (毛假面) [단축키: M]
    * 특수 능력: 냉기 탄환 발사. 적중 시 적에게 푸른색 결빙 시각 효과 및 6초(90틱) 빙결 부여.

[3] 조선 마구간 (Joseon Stables)
  - 대만 왕벌 (臺灣王蜂) [단축키: B]
    * 특수 능력: 공중 비행 자폭 공격. 적에게 돌진하여 자폭하며 강력한 폭발 피해를 입힘.
  - 조선 호랑이 (朝鮮虎) [단축키: T]
    * 특수 능력: 백두산 호랑이의 맹수 도약 및 날카로운 발톱 근접 연타 공격.
  - 설녀 (雪女) [단축키: S]
    * 특수 능력: 냉기 송곳 및 얼음 파편 공격으로 적들을 지속적으로 빙결/둔화.
  - 조선 도깨비 (朝鮮鬼) [단축키: D]
    * 특수 능력: 강력한 체력과 쇠방망이 강타 공격을 구사하는 돌파형 전위 괴수.

--------------------------------------------------------------------------------
3. 기술적 패치 및 안정화 내역
--------------------------------------------------------------------------------
- 네이티브 AI 일꾼 자원 채취(Order 3) 루틴 복구로 스커미시 튕김 현상 100% 해소.
- 유생(0x70) 의병 베이스의 건물 진입/변신 버그(Atb2 0x20) 완전 소멸 및 정상 커맨드카드 적용.
- 4대 안전 코드 동굴(.text 영역) 재배치로 0xC0000005 메모리 접근 위반 원천 차단.
- Windows 10/11 DirectDraw 호환 래퍼(ddraw.dll, dxwrapper.dll) 내장.

즐거운 플레이 되시길 바랍니다!
================================================================================
"""

    launcher_normal = """@echo off
chcp 65001 > nul
cd /d "%~dp0dawn"
start "" "dawn.exe"
"""

    launcher_dxwnd = """@echo off
chcp 65001 > nul
cd /d "%~dp0dxwnd"
start "" "dxwnd.exe" /R:1
"""

    # Exclude files/patterns to keep distribution clean
    exclude_prefixes = (
        "dawn/.agents",
        "dawn\\agents",
    )
    exclude_filenames = {
        "dawn_orig.exe",
        "dawn_test.exe",
        "temp.spr",
        "dueoksini_single_full_hp.png",
        "dueoksini_single_full_hp_open.png",
        "group_all4_full_hp.png",
        "group_all4_full_hp_open.png",
        "group_all4_full_hp_spawn.png",
        "screenshot_borderless_scaling.png",
        "screenshot_game_display.png",
        "screenshot_group_selected.png",
        "screenshot_ingame_battle.png",
        "screenshot_joseon_hq_selected.png",
        "screenshot_lobby_joseon_forced.png",
        "screenshot_skirmish_lobby.png",
        "screenshot_skirmish_scaling.png",
        "screenshot_units_moving.png",
        "screenshot_units_spawned.png",
        "dxwrapper-dawn.log",
        "dxwrapper-dawn.log.bak",
        "dxwrapper-dawn_orig.log",
        "dxwrapper-dawn_test.log",
        "ipxwrapper.log",
    }

    print(f"[*] Packaging files into: {zip_path}")
    file_count = 0
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 1. Add top-level launchers and readme
        root_dir_name = "Imjinrok2_Plus_Joseon_Expansion"
        zf.writestr(f"{root_dir_name}/게임_안내_및_조작법.txt", readme_content.encode("utf-8-sig"))
        zf.writestr(f"{root_dir_name}/게임실행.bat", launcher_normal.encode("euc-kr"))
        zf.writestr(f"{root_dir_name}/창모드_실행(dxwnd).bat", launcher_dxwnd.encode("euc-kr"))
        file_count += 3

        # 2. Add YM files (dawn, dxwnd, run_windows.bat)
        for root, dirs, files in os.walk(ym_dir):
            rel_dir = os.path.relpath(root, ym_dir).replace("\\", "/")
            if any(rel_dir.startswith(p) for p in exclude_prefixes):
                continue
            for f in files:
                rel_file = (f"{rel_dir}/{f}" if rel_dir != "." else f).replace("\\", "/")
                if any(rel_file.startswith(p) for p in exclude_prefixes):
                    continue
                if f in exclude_filenames or f.endswith((".log", ".bak")):
                    continue

                abs_path = os.path.join(root, f)
                arc_name = f"{root_dir_name}/{rel_file}"
                zf.write(abs_path, arc_name)
                sz = os.path.getsize(abs_path)
                total_uncompressed += sz
                file_count += 1
                if file_count % 300 == 0:
                    print(f"    -> Added {file_count} files ({total_uncompressed / 1024 / 1024:.1f} MB uncompressed)...")

    compressed_size = zip_path.stat().st_size
    print(f"\n[OK] Package created successfully!")
    print(f"     Destination : {zip_path}")
    print(f"     File Count  : {file_count:,} files")
    print(f"     Uncompressed: {total_uncompressed / 1024 / 1024:.2f} MB")
    print(f"     Compressed  : {compressed_size / 1024 / 1024:.2f} MB")
    
    # Calculate SHA-256
    hasher = hashlib.sha256()
    with open(zip_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    zip_sha256 = hasher.hexdigest()
    print(f"     SHA-256     : {zip_sha256}")

    # Copy to artifact directory for easy download
    art_dir = Path(r"C:\Users\bpsco_93p6pse\.gemini\antigravity\brain\012fe533-910e-484f-9444-ed8db88cb5d7")
    art_zip = art_dir / "Imjinrok2_Plus_Joseon_Expansion.zip"
    print(f"[*] Copying zip to artifact directory...")
    import shutil
    shutil.copy2(zip_path, art_zip)
    print(f"    [OK] Copied to: {art_zip}")

if __name__ == "__main__":
    build_package()
