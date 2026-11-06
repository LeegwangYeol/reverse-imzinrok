# TEST READY: Joseon 15-Unit & 5 New Infantry E2E Test Suite

**Date**: 2026-11-04  
**Test Suite Architect**: `test_writer_e2e`  
**Status**: **100% PASS** (46/46 Tests Passing, 0 Failures, 0 Errors)  
**Safety & Integrity**: **100% Intact** (YM 204/204 key files and C:\src\rea repository clean)

---

## 1. Test Suite Executive Summary

The automated End-to-End (E2E) test suite for the **15 Joseon Custom Units** (10 existing units `0x70 ~ 0x79` + 5 new 무예24기 infantry units `0x7A ~ 0x7E`) in 《임진록 2+ 조선의 반격: 여명》 (*Imjinrok 2+ Chosun's Counterattack: Dawn*) has been implemented, validated, and published.

All tests execute in isolated memory simulations and non-destructive binary verification, strictly honoring the 204 pristine game files and zero-regression constraints.

```
+==========================================================================================+
|               JOSEON 15-UNIT & 5 INFANTRY E2E TEST SUITE — PYTEST RUNNER                |
|               Target Binary: YM/dawn/dawn.exe | Non-destructive Verification            |
+==========================================================================================+
+--------------------------------+--------+--------+--------+--------+---------+----------+
| Test Module                    |  Tests | Passed | Failed | Errors |    Time | Status   |
+--------------------------------+--------+--------+--------+--------+---------+----------+
| tests/test_joseon_new_unit.py  |     46 |     46 |      0 |      0 |   0.68s | [PASS]   |
+--------------------------------+--------+--------+--------+--------+---------+----------+
| TOTAL                          |     46 |     46 |      0 |      0 |   0.68s | ALL PASS |
+--------------------------------+--------+--------+--------+--------+---------+----------+
```

---

## 2. Test Execution Command

```bash
python -m pytest tests/test_joseon_new_unit.py -v
```

### Safety and Repository Integrity Command
```bash
python tools/verify_safety.py
```

---

## 3. Tiered Coverage Matrix (Tiers 1–4)

| Test Tier | Focus & Scope | Key Tests | Result |
| :--- | :--- | :--- | :---: |
| **Tier 1: Unit & Binary Integrity** | PE section alignments, byte-for-byte pristine backup hash, calling conventions (cdecl/stdcall), register preservation across all caves. | `test_backup_exists_and_matches_original_sha256`<br>`test_r1_binary_diff_cluster_audit`<br>`test_r1_register_preservation`<br>`test_r1_x86_stack_balance_and_calling_conventions` | **PASS** |
| **Tier 2: Boundary & Specification** | All 15 units (`0x70~0x7E`) coexistence matrix, KindInfo geometry, CP949 string encoding, Archer voice cloning, extended melee ranges. | `test_all_15_units_coexistence_matrix`<br>`test_joseon_5_infantry_specification_matrix`<br>`test_joseon_5_infantry_archer_sound_binding`<br>`test_joseon_5_infantry_range_and_combat_gimmicks` | **PASS** |
| **Tier 3: Integration & Memory Safety** | Zero memory conflicts with syw2x.dll, universal engine 200-unit limit (`0x009E1DD0`), dxwrapper token audit, CmdTable `cmd_type=8` (`CMD_TRAIN`). | `test_code_cave_safety_authorized_zones`<br>`test_r3_syw2x_memory_non_overlap`<br>`test_r5_array_bounds_audit`<br>`test_joseon_5_infantry_cmdtable_train_type` | **PASS** |
| **Tier 4: Live Skirmish & Gameplay** | Joseon Barracks & AdvBarracks command card routing, F1 debug dialog treeview limit (`0x7E`), retail & fallback skirmish tab selection, knockback assembly simulation. | `test_joseon_5_infantry_building_command_cards`<br>`test_r5_f1_debug_dialog_unit_check`<br>`test_r4_skirmish_state_machine_tab_selection`<br>`test_knockback_assembly_cave_simulation` | **PASS** |

---

## 4. 5 New Joseon Infantry Units Specification & Verification

All 5 units are verified against the authoritative specifications from `ORIGINAL_REQUEST.md` and `PROJECT.md`:

| Unit Name (한글) | KindID | CmdID | BtnID | Production Building | Slot | HP / Atk / Def / Spd | Cost (쌀/감자/철) | Range & Special Mechanics |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :--- |
| **등패수** (Dengpaesu) | `0x7A` | `0xB5` | `0x4E` | 조선 훈련소 (Kind `0x31`) | 11 | 800 / 40 / 5 / 18 | 160 / 0 / 30 | Range1 = 1, Melee Tanker |
| **쌍수도병** (Ssangsudobyeong) | `0x7B` | `0xB6` | `0x4F` | 조선 훈련도감 (Kind `0x57`) | 8 | 600 / 85 / 2 / 21 | 220 / 0 / 60 | Range1 = 1, High Shock DPS |
| **장창수** (Jangchangsu) | `0x7C` | `0xB7` | `0x50` | 조선 훈련도감 (Kind `0x57`) | 9 | 500 / 55 / 3 / 19 | 180 / 0 / 50 | **Range1 = 2** (Extended Stab) |
| **월도병** (Woldobyeong) | `0x7D` | `0xB8` | `0x52` | 조선 훈련도감 (Kind `0x57`) | 10 | 700 / 65 / 4 / 19 | 240 / 20 / 70 | Range1 = 1, Balanced Shock |
| **낭선병** (Nangseonbyeong) | `0x7E` | `0xB9` | `0x54` | 조선 훈련도감 (Kind `0x57`) | 11 | 550 / 50 / 3 / 18 | 200 / 50 / 40 | **Range1 = 2**, **Knockback Hook** (`0x00470CD5` -> Zone D `0x00421A20`) |

### Archer Sound Clone Verification
All 5 units clone the authentic Joseon Archer sound bindings extracted from `dawn.exe` `UnitDef::Init` (`0x0049BFB2`):
- `SelectSfx` = **164** (`0x00A4`)
- `DyingSfx` = **223** (`0x00DF`)
- `MoveSfx` = **254** (`0x00FE`)
- `TryAttackSfx` = **314** (`0x013A`)

### Building Command Card Slot Non-Collision
- **Joseon Barracks (훈련소, Kind `0x31`)**: Slot 11 is assigned to 등패수 (slots 0~7 native, 8~10 R5 custom units, slot 11 completely vacant).
- **Joseon AdvBarracks (훈련도감, Kind `0x57`)**: Slots 8, 9, 10, 11 assigned to 쌍수도병, 장창수, 월도병, 낭선병 (slots 0~6 native, zero collisions).

### Code Cave Memory Safety Bounds
- **Zone A (.text Slack)**: `0x004E4C70` .. `0x004E5000` (within .text allocated section `0x00401000`..`0x004E6000`).
- **Zone B (AI Cheat Bypass)**: `0x0043F8C3` .. `0x0043F8EF` (45 bytes).
- **Zone C (Order Debug Bypasses)**: `0x0043C8F5` .. `0x0043C92B`, `0x0043CB45` .. `0x0043CBF0`.
- **Zone D (Dead CD-Check Cave)**: `0x00421A20` .. `0x00421AA0` (128 bytes, 낭선병 knockback hook resume at `0x00470CE3`).
- **Universal Engine Limit**: KindInfo for all 15 units strictly < `0x009E1DD0` (200-unit universal engine boundary).

---

## 5. Backward Compatibility & Coexistence Checklist

- [x] Existing 10 custom units (`0x70 ~ 0x79`) intact and verified across all test assertions.
- [x] Total 15 units (`0x70 ~ 0x7E`) have strictly distinct `KindID`, `CmdID`, and `ButtonID` values.
- [x] Dual-mode compatibility: Tests pass both in simulation of the extended 15-unit allocation and baseline 10-unit environments.
- [x] Original asset safety: `python tools/verify_safety.py` passes with **204/204 key files bit-exact** and `C:\src\rea` 100% clean.
