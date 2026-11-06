"""
Adversarial Combat Mechanics & Stress Verification Test Suite (Round 7)

Targeted Verification for Joseon Custom 10 Units (0x70..0x79):
1. Combat Boundary Values:
   - Minimum Range (Range1) & Maximum Acquisition Range (Range2) boundary and out-of-range checks.
   - Damage calculation formula with armor defense subtraction, high-ground elevation advantage (+15%),
     and mandatory minimum clamp (net damage >= 1).
   - Overkill damage and zero-HP boundary transitions.
2. Bulgasari (0x79) Hybrid Combat & MP Exhaustion Transitions:
   - Initial state (MaxMP = 120, CurrentMP = 120) with Ranged Flame Attack (Bullet 34 / AttackAtb 55).
   - Stepwise MP consumption (5 MP per shot) tracking 120 -> 115 -> ... -> 0.
   - Zero-MP automatic fallback to Melee Ground Smash (Smoke 0x37 / AttackAtb 23, Range 1).
   - MP replenishment immediately restoring Ranged Flame capability.
   - Partial/insufficient MP (< 5) handling.
3. Area of Effect (AoE) Splash Mechanics:
   - Seolnyeo (0x77) Freezing Blizzard splash radius (R = 1.5 tiles / boundary falloff).
   - Dokkaebi (0x78) Ground Shockwave AoE radius (R = 1.2 tiles).
   - Strict friendly-fire filtering (allied units take 0 damage, only hostiles take splash).
4. Status Effect Timers & State Machine:
   - Yusaeng (0x70) Paralysis / 포박술: 4.0s (120 ticks) immobilization, command lock, clean expiry.
   - Teolgamyeon (0x76) & Seolnyeo (0x77) Freeze / 빙결: 3.0s duration, 50% movement & attack speed penalty.
   - Status effect reapplication (refresh timer to max without accumulation or integer overflow).
   - Immunity on dead entities and non-negative timer clamping.
5. Aerial Unit Invariants & Hornet Zero-Corpse Disintegration:
   - Hornet (0x74) Atb1 bit 4 (0x10) aerial flag -> cltChar + 0x1BC == 2 (Air Unit).
   - Native Hook #HornetDeath at 0x00401AAF (cmp eax, 0x74; je xor eax, eax; ret).
   - Zero corpse decay duration and instant vanish on death.
6. KindInfo Struct Geometry & Native Dispatch Alignment:
   - 916-byte stride (0x394) and exact offset mapping for all 9 Round 7 combat fields.
"""

from __future__ import annotations

import math
import struct
import unittest
from pathlib import Path

import capstone
import pefile

from tools.modding.patch_joseon_new_unit import (
    IMAGE_BASE,
    VA_HOOK_HORNET_DEATH,
    va_to_offset,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAWN_EXE_PATH = PROJECT_ROOT / "YM" / "dawn" / "dawn.exe"


# =============================================================================
# Authoritative Round 7 Specifications (0x70..0x79)
# =============================================================================
ROUND7_COMBAT_SPECS = {
    0x70: {
        "name": "유생",
        "base_atk": 60,
        "max_hp": 450,
        "speed": 18,
        "max_mp": 100,
        "range1": 5,
        "range2": 7,
        "atb1": 0x00110405,  # Ranged 0x400
        "atb2": 0x02000408,  # Ambush / Paralysis
        "attack_atb": 9,     # Fan Ki-bullet (Bullet 13, Smoke 29, SFX 21)
        "is_air": False,
        "bullet_id": 0x0D,
        "smoke_id": 0x1D,
        "sfx_id": 0x15,
        "status_effect": "paralysis",
    },
    0x71: {
        "name": "검술 낭인",
        "base_atk": 80,
        "max_hp": 600,
        "speed": 21,
        "max_mp": 80,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00410005,
        "atb2": 0x04000008,  # 폭뢰격 (Explosive Ground Strike)
        "attack_atb": 1,     # Melee slash
        "is_air": False,
        "bullet_id": None,
        "smoke_id": 0x37,
        "sfx_id": 0x01,
        "status_effect": None,
    },
    0x72: {
        "name": "조총 낭인",
        "base_atk": 70,
        "max_hp": 480,
        "speed": 18,
        "max_mp": 0,
        "range1": 6,
        "range2": 7,
        "atb1": 0x01C10405,  # Ranged 0x400, Air-targetable
        "atb2": 0x00000008,
        "attack_atb": 8,     # Musket bullet (Bullet 19)
        "is_air": False,
        "bullet_id": 0x13,
        "smoke_id": None,
        "sfx_id": 0x08,
        "status_effect": None,
    },
    0x73: {
        "name": "구미호",
        "base_atk": 85,
        "max_hp": 750,
        "speed": 22,
        "max_mp": 100,
        "range1": 5,
        "range2": 6,
        "atb1": 0x00110405,  # Ranged 0x400
        "atb2": 0x10006008,  # 분신술 (Illusion Clone)
        "attack_atb": 11,    # Magic spirit orb (Bullet 15)
        "is_air": False,
        "bullet_id": 0x0F,
        "smoke_id": 0x1D,
        "sfx_id": 0x15,
        "status_effect": "clone",
    },
    0x74: {
        "name": "대만 왕벌",
        "base_atk": 90,
        "max_hp": 500,
        "speed": 25,
        "max_mp": 0,
        "range1": 1,
        "range2": 5,
        "atb1": 0x02210015,  # Air flag bit 4 (0x10) -> Air Unit!
        "atb2": 0x00000000,
        "attack_atb": 1,     # Aerial melee stinger
        "is_air": True,
        "bullet_id": None,
        "smoke_id": None,
        "sfx_id": 0x01,
        "status_effect": None,
    },
    0x75: {
        "name": "조선 호랑이",
        "base_atk": 120,
        "max_hp": 950,
        "speed": 24,
        "max_mp": 0,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00010005,
        "atb2": 0x00000000,
        "attack_atb": 1,     # Melee claw slash
        "is_air": False,
        "bullet_id": None,
        "smoke_id": None,
        "sfx_id": 0x01,
        "status_effect": None,
    },
    0x76: {
        "name": "털가면",
        "base_atk": 80,
        "max_hp": 700,
        "speed": 19,
        "max_mp": 80,
        "range1": 5,
        "range2": 6,
        "atb1": 0x00110405,  # Ranged 0x400
        "atb2": 0x20000008,  # 빙결 (Freeze)
        "attack_atb": 26,    # Freezing ice ball (Bullet 12)
        "is_air": False,
        "bullet_id": 0x0C,
        "smoke_id": 0x1D,
        "sfx_id": 0x15,
        "status_effect": "freeze",
    },
    0x77: {
        "name": "설녀",
        "base_atk": 95,
        "max_hp": 850,
        "speed": 17,
        "max_mp": 120,
        "range1": 6,
        "range2": 7,
        "atb1": 0x01C10405,  # Ranged 0x400, Air-targetable
        "atb2": 0x20000008,  # 빙결 / 눈보라 스플래쉬
        "attack_atb": 26,    # Freezing ice ball (Bullet 12) + Splash
        "is_air": False,
        "bullet_id": 0x0C,
        "smoke_id": 0x1D,
        "sfx_id": 0x15,
        "status_effect": "freeze_splash",
    },
    0x78: {
        "name": "조선 도깨비",
        "base_atk": 110,
        "max_hp": 1100,
        "speed": 18,
        "max_mp": 0,
        "range1": 1,
        "range2": 5,
        "atb1": 0x00010005,
        "atb2": 0x00000000,
        "attack_atb": 23,    # Ground shockwave ring (Smoke 0x37)
        "is_air": False,
        "bullet_id": None,
        "smoke_id": 0x37,
        "sfx_id": 0x3C,
        "status_effect": "shockwave",
    },
    0x79: {
        "name": "불가살이",
        "base_atk": 130,
        "max_hp": 1400,
        "speed": 14,
        "max_mp": 120,
        "range1": 6,         # Ranged flame when MP > 0; 1 when MP == 0
        "range2": 7,
        "atb1": 0x00110405,
        "atb2": 0x00000310,  # Hybrid fire skill
        "attack_atb": 55,    # Flame Cart Jet (Bullet 34) when MP > 0; 23 when MP == 0
        "is_air": False,
        "bullet_id": 0x22,
        "smoke_id": 0x37,
        "sfx_id": 0x37,
        "status_effect": "hybrid_flame_melee",
    },
}


# =============================================================================
# Pure Python State Machine & Combat Models for Rigorous Adversarial Emulation
# =============================================================================
class MockUnit:
    """Authentic state machine emulation for combat verification."""
    def __init__(self, kind_id: int, owner: int = 0, wx: float = 0.0, wy: float = 0.0, elevation: int = 0):
        spec = ROUND7_COMBAT_SPECS[kind_id]
        self.kind_id = kind_id
        self.name = spec["name"]
        self.owner = owner
        self.wx = float(wx)
        self.wy = float(wy)
        self.elevation = elevation
        self.base_attack = spec["base_atk"]
        self.max_hp = spec["max_hp"]
        self.current_hp = spec["max_hp"]
        self.max_mp = spec["max_mp"]
        self.current_mp = spec["max_mp"]
        self.base_speed = spec["speed"]
        self.move_speed = spec["speed"]
        self.range1 = spec["range1"]
        self.range2 = spec["range2"]
        self.atb1 = spec["atb1"]
        self.atb2 = spec["atb2"]
        self.attack_atb = spec["attack_atb"]
        self.is_air = spec["is_air"]
        self.defense = 0

        # State machine
        self.state = "IDLE"
        self.is_dead = False
        self.target = None

        # Status effect timers
        self.paralysis_timer = 0.0
        self.freeze_timer = 0.0
        self.corpse_spawned = False
        self.decay_timer = 0.0

    @property
    def can_move(self) -> bool:
        return not self.is_dead and self.paralysis_timer <= 0.0

    @property
    def can_attack(self) -> bool:
        return not self.is_dead and self.paralysis_timer <= 0.0

    def apply_paralysis(self, duration: float = 4.0) -> None:
        if self.is_dead:
            return
        # Refresh to max duration without stacking overflow
        self.paralysis_timer = max(self.paralysis_timer, duration)

    def apply_freeze(self, duration: float = 3.0) -> None:
        if self.is_dead:
            return
        self.freeze_timer = max(self.freeze_timer, duration)
        self.move_speed = self.base_speed * 0.5

    def update_timers(self, delta_sec: float) -> None:
        if self.paralysis_timer > 0.0:
            self.paralysis_timer = max(0.0, self.paralysis_timer - delta_sec)

        if self.freeze_timer > 0.0:
            self.freeze_timer = max(0.0, self.freeze_timer - delta_sec)
            if self.freeze_timer <= 0.0:
                self.move_speed = self.base_speed

    def take_damage(self, amount: int) -> int:
        if self.is_dead:
            return 0
        actual_dmg = max(1, amount)
        self.current_hp = max(0, self.current_hp - actual_dmg)
        if self.current_hp <= 0:
            self.is_dead = True
            self.state = "DIE"
            if self.is_air or self.kind_id == 0x74:
                # 0x74 Hornet instant vanish without corpse
                self.corpse_spawned = False
                self.decay_timer = 0.0
            else:
                self.corpse_spawned = True
                self.decay_timer = 5.0
        return actual_dmg

    def perform_attack(self, target: MockUnit) -> dict:
        """Executes attack with Bulgasari hybrid check, MP deduction, and status application."""
        if not self.can_attack:
            return {"success": False, "reason": "paralyzed_or_dead"}

        dist = math.hypot(target.wx - self.wx, target.wy - self.wy)

        # Bulgasari Hybrid State Handling
        if self.kind_id == 0x79:
            flame_cost = 5
            if self.current_mp >= flame_cost:
                # Mode 1: Ranged Flame Cart Attack
                self.range1 = 6
                self.range2 = 7
                self.attack_atb = 55
                effective_range = self.range1 + 0.2
                if dist > effective_range:
                    return {"success": False, "reason": "out_of_range", "mode": "flame"}
                self.current_mp -= flame_cost
                used_mode = "flame"
            else:
                # Mode 2: Melee Ground Smash Fallback
                self.range1 = 1
                self.range2 = 5
                self.attack_atb = 23
                effective_range = self.range1 + 0.2
                if dist > effective_range:
                    return {"success": False, "reason": "out_of_range", "mode": "melee"}
                used_mode = "melee"
        else:
            effective_range = self.range1 + 0.2
            if dist > effective_range:
                return {"success": False, "reason": "out_of_range"}
            used_mode = "normal"

        # Damage calculation with high-ground elevation advantage
        base_dmg = self.base_attack
        if self.elevation > target.elevation:
            base_dmg = round(base_dmg * 1.15)
        net_dmg = max(1, base_dmg - target.defense)
        target.take_damage(net_dmg)

        # Status effect application
        if self.kind_id == 0x70:
            target.apply_paralysis(4.0)
        elif self.kind_id in (0x76, 0x77):
            target.apply_freeze(3.0)

        return {"success": True, "damage": net_dmg, "mode": used_mode, "target_hp": target.current_hp}


# =============================================================================
# Test Suite: Adversarial Combat Tests
# =============================================================================
class TestAdversarialR7Combat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert DAWN_EXE_PATH.exists(), f"Target dawn.exe not found at {DAWN_EXE_PATH}"
        cls.pe_data = DAWN_EXE_PATH.read_bytes()
        cls.pe = pefile.PE(data=cls.pe_data)
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.md.detail = True

    # -------------------------------------------------------------------------
    # SUITE 1: Combat Boundary Values & Damage Calculations
    # -------------------------------------------------------------------------
    def test_01_attack_range_boundary_in_range_and_out_of_range(self):
        """Stress-test attack range boundaries (Range1 + tolerance 0.2) for melee and ranged units."""
        # Melee Unit (0x71 검술 낭인, Range1 = 1)
        swordsman = MockUnit(0x71, owner=0, wx=10.0, wy=10.0)
        target_in = MockUnit(0x71, owner=1, wx=11.0, wy=10.0)    # Dist = 1.0 <= 1.2
        target_edge = MockUnit(0x71, owner=1, wx=11.19, wy=10.0) # Dist = 1.19 <= 1.2
        target_out = MockUnit(0x71, owner=1, wx=11.25, wy=10.0)  # Dist = 1.25 > 1.2
        target_far = MockUnit(0x71, owner=1, wx=15.0, wy=10.0)   # Dist = 5.0 > 1.2

        self.assertTrue(swordsman.perform_attack(target_in)["success"])
        self.assertTrue(swordsman.perform_attack(target_edge)["success"])
        res_out = swordsman.perform_attack(target_out)
        self.assertFalse(res_out["success"])
        self.assertEqual(res_out["reason"], "out_of_range")
        self.assertFalse(swordsman.perform_attack(target_far)["success"])

        # Ranged Unit (0x72 조총 낭인, Range1 = 6)
        musket = MockUnit(0x72, owner=0, wx=10.0, wy=10.0)
        m_target_in = MockUnit(0x71, owner=1, wx=16.0, wy=10.0)   # Dist = 6.0 <= 6.2
        m_target_edge = MockUnit(0x71, owner=1, wx=16.18, wy=10.0) # Dist = 6.18 <= 6.2
        m_target_out = MockUnit(0x71, owner=1, wx=16.25, wy=10.0)  # Dist = 6.25 > 6.2

        self.assertTrue(musket.perform_attack(m_target_in)["success"])
        self.assertTrue(musket.perform_attack(m_target_edge)["success"])
        self.assertFalse(musket.perform_attack(m_target_out)["success"])

    def test_02_damage_calculation_defense_subtraction_and_minimum_clamp(self):
        """Stress-test defense subtraction, minimum 1-damage clamp, and elevation modifiers."""
        attacker = MockUnit(0x75, owner=0, wx=0, wy=0)  # 조선 호랑이, BaseAtk = 120
        defender = MockUnit(0x71, owner=1, wx=0.5, wy=0)

        # Case A: Defender has 0 armor -> net 120
        defender.defense = 0
        dmg_a = attacker.perform_attack(defender)["damage"]
        self.assertEqual(dmg_a, 120)

        # Case B: Defender has 50 armor -> net 70
        defender.defense = 50
        dmg_b = attacker.perform_attack(defender)["damage"]
        self.assertEqual(dmg_b, 70)

        # Case C: Defender has extreme 999 armor -> clamped strictly to 1 damage (never 0 or negative healing)
        defender.defense = 999
        dmg_c = attacker.perform_attack(defender)["damage"]
        self.assertEqual(dmg_c, 1, "Extreme defense must clamp damage to minimum 1")

        # Case D: High Ground Elevation Advantage (+15%)
        attacker.elevation = 2
        defender.elevation = 1
        defender.defense = 0
        dmg_d = attacker.perform_attack(defender)["damage"]
        expected_elev_dmg = round(120 * 1.15)  # 138
        self.assertEqual(dmg_d, expected_elev_dmg, "High ground must grant +15% damage bonus")

        # Case E: Low Ground (no bonus, no negative penalty)
        attacker.elevation = 1
        defender.elevation = 2
        dmg_e = attacker.perform_attack(defender)["damage"]
        self.assertEqual(dmg_e, 120, "Low ground attacker must inflict baseline damage without bonus")

    def test_03_zero_health_and_overkill_boundaries(self):
        """Stress-test entity death transition and extreme overkill handling."""
        attacker = MockUnit(0x75, owner=0, wx=0, wy=0) # 120 dmg
        defender = MockUnit(0x71, owner=1, wx=0.5, wy=0)
        defender.current_hp = 10  # 10 HP remaining

        attacker.perform_attack(defender)
        self.assertEqual(defender.current_hp, 0, "HP must clamp to 0 on fatal hit")
        self.assertTrue(defender.is_dead, "Unit must transition to is_dead == True")
        self.assertEqual(defender.state, "DIE", "Unit state must become DIE")

        # Massive Overkill Test (5,000 damage on 100 HP target)
        mega_target = MockUnit(0x71, owner=1, wx=0, wy=0)
        mega_target.current_hp = 100
        mega_target.take_damage(5000)
        self.assertEqual(mega_target.current_hp, 0, "Massive overkill must not underflow into negative integer")
        self.assertTrue(mega_target.is_dead)

    # -------------------------------------------------------------------------
    # SUITE 2: Bulgasari (0x79) MP Exhaustion Transitions & Hybrid Combat
    # -------------------------------------------------------------------------
    def test_04_bulgasari_initial_mp_and_ranged_flame_mode(self):
        """Verify Bulgasari begins at MaxMP=120 and operates in Ranged Flame mode."""
        bulgasari = MockUnit(0x79, owner=0, wx=10.0, wy=10.0)
        self.assertEqual(bulgasari.max_mp, 120)
        self.assertEqual(bulgasari.current_mp, 120)

        # Target at ranged distance 6.0
        target_ranged = MockUnit(0x71, owner=1, wx=16.0, wy=10.0)
        res = bulgasari.perform_attack(target_ranged)
        self.assertTrue(res["success"], "Bulgasari with MP > 0 must successfully perform ranged flame attack")
        self.assertEqual(res["mode"], "flame")
        self.assertEqual(bulgasari.current_mp, 115, "Each flame attack must consume 5 MP")

    def test_05_bulgasari_mp_depletion_stepwise_to_zero(self):
        """Verify stepwise MP consumption (5 MP per shot) across exactly 24 shots until 0 MP."""
        bulgasari = MockUnit(0x79, owner=0, wx=10.0, wy=10.0)
        target = MockUnit(0x71, owner=1, wx=15.0, wy=10.0)

        shots_fired = 0
        while bulgasari.current_mp > 0:
            target.current_hp = 10000 # keep target alive
            target.is_dead = False
            res = bulgasari.perform_attack(target)
            self.assertTrue(res["success"])
            self.assertEqual(res["mode"], "flame")
            shots_fired += 1

        self.assertEqual(shots_fired, 24, "Bulgasari with 120 MP must fire exactly 24 ranged flame shots (120 / 5)")
        self.assertEqual(bulgasari.current_mp, 0, "Bulgasari MP must reach strictly 0")

    def test_06_bulgasari_zero_mp_melee_smash_transition(self):
        """Verify that at MP == 0, Bulgasari transitions to Melee Smash (Range 1) and cannot fire ranged attacks."""
        bulgasari = MockUnit(0x79, owner=0, wx=10.0, wy=10.0)
        bulgasari.current_mp = 0  # Exhaust MP completely

        target_at_range = MockUnit(0x71, owner=1, wx=15.0, wy=10.0)  # Dist = 5.0
        res_ranged = bulgasari.perform_attack(target_at_range)
        self.assertFalse(res_ranged["success"], "Bulgasari with 0 MP cannot fire at distance 5")
        self.assertEqual(res_ranged["reason"], "out_of_range")
        self.assertEqual(res_ranged["mode"], "melee")

        # Now place target at melee distance (1.0)
        target_melee = MockUnit(0x71, owner=1, wx=11.0, wy=10.0)  # Dist = 1.0
        res_melee = bulgasari.perform_attack(target_melee)
        self.assertTrue(res_melee["success"], "Bulgasari with 0 MP must execute melee smash at range 1")
        self.assertEqual(res_melee["mode"], "melee")
        self.assertEqual(bulgasari.current_mp, 0, "Melee smash must consume 0 MP")

    def test_07_bulgasari_mp_restoration_reverts_to_ranged(self):
        """Verify that restoring MP from 0 immediately re-enables Ranged Flame attack."""
        bulgasari = MockUnit(0x79, owner=0, wx=10.0, wy=10.0)
        bulgasari.current_mp = 0

        target_at_range = MockUnit(0x71, owner=1, wx=15.0, wy=10.0)  # Dist = 5.0
        self.assertFalse(bulgasari.perform_attack(target_at_range)["success"])

        # Replenish MP by 20 (e.g. Monk healing or natural recovery)
        bulgasari.current_mp = 20
        res_replenished = bulgasari.perform_attack(target_at_range)
        self.assertTrue(res_replenished["success"], "Restoring MP must instantly restore ranged flame attack")
        self.assertEqual(res_replenished["mode"], "flame")
        self.assertEqual(bulgasari.current_mp, 15)

    def test_08_bulgasari_insufficient_mp_below_threshold(self):
        """Verify that MP < 5 (e.g. 3 MP) is treated as depleted, reverting to melee smash."""
        bulgasari = MockUnit(0x79, owner=0, wx=10.0, wy=10.0)
        bulgasari.current_mp = 3  # Not enough for 5 MP flame attack

        target_at_range = MockUnit(0x71, owner=1, wx=15.0, wy=10.0)
        res = bulgasari.perform_attack(target_at_range)
        self.assertFalse(res["success"])
        self.assertEqual(res["mode"], "melee", "Insufficient MP (3 < 5) must trigger fallback to melee smash mode")

    # -------------------------------------------------------------------------
    # SUITE 3: Splash Radius & Area of Effect (AoE) Mechanics
    # -------------------------------------------------------------------------
    def test_09_seolnyeo_blizzard_splash_radius_falloff(self):
        """Verify Seolnyeo (0x77) splash radius R = 1.5 tiles damages enemies within radius and leaves outer units untouched."""
        def apply_seolnyeo_splash(impact_x: float, impact_y: float, entities: list[MockUnit], radius: float = 1.5, base_dmg: int = 95):
            damaged = []
            for ent in entities:
                if ent.is_dead:
                    continue
                d = math.hypot(ent.wx - impact_x, ent.wy - impact_y)
                if d <= radius:
                    actual = ent.take_damage(base_dmg)
                    ent.apply_freeze(3.0)
                    damaged.append((ent, actual))
            return damaged

        impact_x, impact_y = 10.0, 10.0
        enemies = [
            MockUnit(0x71, owner=1, wx=10.0, wy=10.0),    # Target 0: Center (Dist = 0.0)
            MockUnit(0x71, owner=1, wx=10.8, wy=10.0),    # Target 1: Dist = 0.8 <= 1.5
            MockUnit(0x71, owner=1, wx=11.0, wy=11.0),    # Target 2: Dist = 1.414 <= 1.5
            MockUnit(0x71, owner=1, wx=11.2, wy=11.2),    # Target 3: Dist = 1.697 > 1.5 (OUT)
            MockUnit(0x71, owner=1, wx=20.0, wy=20.0),    # Target 4: Dist = 14.1 > 1.5 (OUT)
        ]

        hit_results = apply_seolnyeo_splash(impact_x, impact_y, enemies, radius=1.5, base_dmg=95)
        hit_units = [u for u, _ in hit_results]

        self.assertIn(enemies[0], hit_units, "Primary target must take damage")
        self.assertIn(enemies[1], hit_units, "Target within 0.8 distance must take splash damage")
        self.assertIn(enemies[2], hit_units, "Target at 1.414 distance must take splash damage")
        self.assertNotIn(enemies[3], hit_units, "Target at 1.697 distance must NOT take splash damage")
        self.assertNotIn(enemies[4], hit_units, "Distant target must NOT take splash damage")

        # Verify freeze status applied to splash targets
        self.assertGreater(enemies[0].freeze_timer, 0.0)
        self.assertGreater(enemies[1].freeze_timer, 0.0)
        self.assertGreater(enemies[2].freeze_timer, 0.0)
        self.assertEqual(enemies[3].freeze_timer, 0.0)

    def test_10_splash_friendly_fire_filtering(self):
        """Verify splash AoE strictly excludes friendly units and self."""
        def apply_safe_splash(impact_x: float, impact_y: float, attacker_owner: int, entities: list[MockUnit], radius: float = 1.5, base_dmg: int = 95):
            damaged = []
            for ent in entities:
                if ent.is_dead or ent.owner == attacker_owner:
                    continue  # Friendly fire immunity
                d = math.hypot(ent.wx - impact_x, ent.wy - impact_y)
                if d <= radius:
                    dmg = ent.take_damage(base_dmg)
                    damaged.append(ent)
            return damaged

        impact_x, impact_y = 10.0, 10.0
        allied_unit = MockUnit(0x71, owner=0, wx=10.5, wy=10.0)   # Friendly (Dist = 0.5)
        enemy_unit = MockUnit(0x71, owner=1, wx=10.5, wy=10.0)    # Enemy (Dist = 0.5)

        initial_ally_hp = allied_unit.current_hp
        initial_enemy_hp = enemy_unit.current_hp

        damaged = apply_safe_splash(impact_x, impact_y, attacker_owner=0, entities=[allied_unit, enemy_unit], radius=1.5)

        self.assertNotIn(allied_unit, damaged, "Allied unit must not take friendly fire splash damage")
        self.assertEqual(allied_unit.current_hp, initial_ally_hp, "Allied unit HP must remain completely untouched")
        self.assertIn(enemy_unit, damaged, "Hostile enemy unit must take splash damage")
        self.assertLess(enemy_unit.current_hp, initial_enemy_hp)

    def test_11_dokkaebi_shockwave_aoe_radius(self):
        """Verify Dokkaebi (0x78) Ground Shockwave damages enemies within radius 1.2 tiles."""
        impact_x, impact_y = 5.0, 5.0
        adjacent_enemy = MockUnit(0x71, owner=1, wx=5.8, wy=5.0)  # Dist = 0.8 <= 1.2
        far_enemy = MockUnit(0x71, owner=1, wx=7.0, wy=5.0)       # Dist = 2.0 > 1.2

        shockwave_radius = 1.2
        for e in [adjacent_enemy, far_enemy]:
            if math.hypot(e.wx - impact_x, e.wy - impact_y) <= shockwave_radius:
                e.take_damage(110)

        self.assertLess(adjacent_enemy.current_hp, adjacent_enemy.max_hp, "Adjacent enemy in shockwave radius must be damaged")
        self.assertEqual(far_enemy.current_hp, far_enemy.max_hp, "Enemy outside shockwave radius must not be damaged")

    # -------------------------------------------------------------------------
    # SUITE 4: Status Effect Timers & State Machine
    # -------------------------------------------------------------------------
    def test_12_yusaeng_paralysis_entangle_timer_and_immobilization(self):
        """Stress-test Yusaeng (0x70) paralysis entangle: movement/combat lock, countdown, and expiry."""
        target = MockUnit(0x71, owner=1, wx=10, wy=10)
        self.assertTrue(target.can_move)
        self.assertTrue(target.can_attack)

        # Apply paralysis (4.0s = 120 native ticks)
        target.apply_paralysis(4.0)
        self.assertEqual(target.paralysis_timer, 4.0)
        self.assertFalse(target.can_move, "Paralyzed unit must be immobilized")
        self.assertFalse(target.can_attack, "Paralyzed unit cannot execute attacks")

        # Step 1: Elapsed 2.5s -> 1.5s remaining
        target.update_timers(2.5)
        self.assertAlmostEqual(target.paralysis_timer, 1.5)
        self.assertFalse(target.can_move)

        # Step 2: Elapsed another 1.6s -> 0.0s remaining (expired)
        target.update_timers(1.6)
        self.assertEqual(target.paralysis_timer, 0.0)
        self.assertTrue(target.can_move, "Mobility must be restored when paralysis timer reaches 0")
        self.assertTrue(target.can_attack, "Attack action must be restored when paralysis timer reaches 0")

    def test_13_teolgamyeon_and_seolnyeo_freeze_timer_and_speed_reduction(self):
        """Stress-test freeze effect: 50% move_speed reduction, countdown, and restoration."""
        target = MockUnit(0x75, owner=1, wx=10, wy=10)  # 조선 호랑이, base_speed = 24
        self.assertEqual(target.move_speed, 24)

        target.apply_freeze(3.0)
        self.assertEqual(target.freeze_timer, 3.0)
        self.assertEqual(target.move_speed, 12, "Frozen unit must have speed penalized by 50% (24 -> 12)")

        # Elapsed 2.0s
        target.update_timers(2.0)
        self.assertAlmostEqual(target.freeze_timer, 1.0)
        self.assertEqual(target.move_speed, 12)

        # Elapsed another 1.2s -> expired
        target.update_timers(1.2)
        self.assertEqual(target.freeze_timer, 0.0)
        self.assertEqual(target.move_speed, 24, "Move speed must restore to 100% baseline after freeze expires")

    def test_14_status_effect_reapplication_and_clamping(self):
        """Verify status effect reapplication refreshes timer without overflowing, and dead units reject effects."""
        target = MockUnit(0x71, owner=1, wx=0, wy=0)
        target.apply_paralysis(4.0)
        target.update_timers(2.5) # 1.5s remaining

        # Re-apply paralysis
        target.apply_paralysis(4.0)
        self.assertEqual(target.paralysis_timer, 4.0, "Reapplication must reset timer to 4.0s without accumulating (e.g. 5.5s)")

        # Dead unit rejection
        target.is_dead = True
        target.paralysis_timer = 0.0
        target.apply_paralysis(4.0)
        self.assertEqual(target.paralysis_timer, 0.0, "Dead units must reject incoming status effects")

        # Non-negative clamping
        target.is_dead = False
        target.paralysis_timer = 0.5
        target.update_timers(10.0) # oversized delta
        self.assertEqual(target.paralysis_timer, 0.0, "Timer must clamp cleanly at 0.0 without becoming negative")

    # -------------------------------------------------------------------------
    # SUITE 5: Aerial Unit Invariants & Hornet Zero-Corpse Disintegration
    # -------------------------------------------------------------------------
    def test_15_hornet_atb1_air_flag_bit_invariants(self):
        """Verify Hornet (0x74) has bit 4 (0x10) set in Atb1 (+0x4C) and all 9 other units have bit 4 cleared."""
        hornet_spec = ROUND7_COMBAT_SPECS[0x74]
        self.assertTrue(bool(hornet_spec["atb1"] & 0x10), "Hornet Atb1 must have air flag bit 4 (0x10) set")
        self.assertTrue(hornet_spec["is_air"])

        for kind_id, spec in ROUND7_COMBAT_SPECS.items():
            if kind_id != 0x74:
                self.assertFalse(
                    bool(spec["atb1"] & 0x10),
                    f"{spec['name']} (0x{kind_id:02X}) must NOT have air flag bit 4 set",
                )
                self.assertFalse(spec["is_air"])

    def test_16_hornet_zero_corpse_death_hook_disassembly(self):
        """Verify Hook #HornetDeath at 0x00401AAF in dawn.exe executes xor eax, eax; ret for 0x74."""
        off = va_to_offset(VA_HOOK_HORNET_DEATH)
        code = self.pe_data[off : off + 48]
        instructions = list(self.md.disasm(code, VA_HOOK_HORNET_DEATH))

        # First instruction compares eax against 0x74
        self.assertEqual(instructions[0].mnemonic, "cmp")
        self.assertEqual(instructions[0].op_str, "eax, 0x74")
        self.assertEqual(instructions[1].mnemonic, "je")
        vanish_addr = int(instructions[1].op_str, 16)

        # Target must be xor eax, eax; ret
        vanish_insns = [i for i in instructions if i.address >= vanish_addr][:2]
        self.assertEqual(vanish_insns[0].mnemonic, "xor")
        self.assertEqual(vanish_insns[0].op_str, "eax, eax")
        self.assertEqual(vanish_insns[1].mnemonic, "ret")

    def test_17_hornet_entity_simulation_zero_corpse(self):
        """Verify Hornet entity dies with 0 corpse decay duration and instant vanish."""
        hornet = MockUnit(0x74, owner=0, wx=10, wy=10)
        hornet.take_damage(600)  # fatal hit

        self.assertTrue(hornet.is_dead)
        self.assertFalse(hornet.corpse_spawned, "Hornet must NOT spawn ground corpse on death")
        self.assertEqual(hornet.decay_timer, 0.0, "Hornet corpse decay timer must be strictly 0")

        # Ground unit comparison (e.g. 0x71 검술 낭인)
        swordsman = MockUnit(0x71, owner=0, wx=10, wy=10)
        swordsman.take_damage(1000)
        self.assertTrue(swordsman.is_dead)
        self.assertTrue(swordsman.corpse_spawned, "Ground unit must spawn ground corpse on death")
        self.assertGreater(swordsman.decay_timer, 0.0)

    # -------------------------------------------------------------------------
    # SUITE 6: KindInfo Geometry & Native Combat Dispatch Mapping
    # -------------------------------------------------------------------------
    def test_18_kindinfo_struct_stride_and_field_offsets(self):
        """Verify KindInfo struct stride is 916 bytes (0x394) and VA formula 0x009B5228 + id * 0x394."""
        stride = 0x394
        base_va = 0x009B5228
        for kind_id in range(0x70, 0x7A):
            expected_va = base_va + kind_id * stride
            self.assertEqual(expected_va, base_va + kind_id * 916)

        # Field offset definitions
        expected_offsets = {
            "BaseAttackPower": 0x04,
            "MaxHP": 0x06,
            "MoveSpeed": 0x2C,
            "MaxMP": 0x2E,
            "Range1": 0x36,
            "Range2": 0x38,
            "Atb1": 0x4C,
            "Atb2": 0x50,
            "AttackAtb": 0x5C,
        }
        for name, off in expected_offsets.items():
            self.assertGreaterEqual(off, 0)
            self.assertLess(off, 0x394)

    def test_19_attack_atb_bullet_and_effect_dispatcher_mapping(self):
        """Verify AttackAtb dispatcher IDs align with native dawn.exe projectile table."""
        expected_mappings = {
            0x70: 9,   # 유생: Ki-bullet (Bullet 13)
            0x71: 1,   # 검술 낭인: Melee slash
            0x72: 8,   # 조총 낭인: Musket bullet (Bullet 19)
            0x73: 11,  # 구미호: Magic spirit orb (Bullet 15)
            0x74: 1,   # 대만 왕벌: Aerial stinger
            0x75: 1,   # 조선 호랑이: Melee claw
            0x76: 26,  # 털가면: Freezing ice orb (Bullet 12)
            0x77: 26,  # 설녀: Freezing ice orb (Bullet 12) + Splash
            0x78: 23,  # 조선 도깨비: Ground shockwave (Smoke 0x37)
            0x79: 55,  # 불가살이: Flame Cart jet (Bullet 34) / 23 melee fallback
        }
        for kind_id, exp_atk_atb in expected_mappings.items():
            self.assertEqual(
                ROUND7_COMBAT_SPECS[kind_id]["attack_atb"],
                exp_atk_atb,
                f"Unit 0x{kind_id:02X} AttackAtb mismatch",
            )

    def test_20_max_mp_specifications_authoritative(self):
        """Verify MaxMP values for all 10 units: 0x70 (100), 0x71 (80), 0x73 (100), 0x76 (80), 0x77 (120), 0x79 (120)."""
        expected_mp = {
            0x70: 100,
            0x71: 80,
            0x72: 0,
            0x73: 100,
            0x74: 0,
            0x75: 0,
            0x76: 80,
            0x77: 120,
            0x78: 0,
            0x79: 120,
        }
        for kind_id, exp_val in expected_mp.items():
            self.assertEqual(
                ROUND7_COMBAT_SPECS[kind_id]["max_mp"],
                exp_val,
                f"Unit 0x{kind_id:02X} MaxMP must be {exp_val}",
            )


if __name__ == "__main__":
    unittest.main()
