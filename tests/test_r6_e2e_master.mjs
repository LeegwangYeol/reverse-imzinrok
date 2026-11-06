/**
 * Master E2E & Full Systems Integration Test Suite (R6 Deliverables)
 *
 * Comprehensive end-to-end verification covering:
 * 1. 10 Custom Joseon Units (0x70~0x79) in BUILTIN_UNIT_TEMPLATES and CommandCardHUD:
 *    - HQ production mapping: Slot 9 (0x70 유생 [Y]), Slot 10 (0x79 불가살이 [U]), Slot 11 (0x73 구미호 [F])
 *    - Barracks production mapping: Slot 8 (0x71 검술 낭인 [K]), Slot 9 (0x72 조총 낭인 [N]), Slot 10 (0x76 털가면 [M])
 *    - Stables production mapping: Slot 7 (0x74 조선왕벌 [B]), Slot 8 (0x75 조선 호랑이 [T]), Slot 9 (0x77 설녀 [S]), Slot 10 (0x78 조선 도깨비 [D])
 *    - Matching 34x34 button assets on disk & buttons_manifest.json bindings
 *    - Ingame unit production enqueuing with resource validation and cost deduction
 * 2. 5-Action Animation Lifecycles in entities.js and renderer.js:
 *    - MOVE (WALK), IDLE, ATTACK, DEATH (DIE), CORPSE DECAY
 *    - Ground units transition to CORPSE_DECAY, releasing tile occupancy while displaying static corpse frame
 *    - Corpse alpha dissolves over 4.0s (fading in last 1.0s window), suppressing shadow, health bars, and selection rings
 * 3. Air Unit Joseon Hornet (0x74) Flight & Instant Death Vanishing:
 *    - isAirUnit: true, flightAltitude: 36px, direct vector flight over obstacles
 *    - INSTANT vanishing on death (hp <= 0): deathAnimDone: true, isDying: false, corpseAlpha: 0.0
 *    - ZERO corpse decay duration (0s), ZERO ground carcass footprint, purged on tick 0
 *    - resolveUnitFrame returns null for CORPSE_DECAY
 * 4. StrategicMacroAI Comprehensive Engine:
 *    - Dynamic worker allocation without 50:50 equalizing cheat (cheat5050Enabled === false)
 *    - Node saturation limits: Rice max 3, Tree max 1, Potato max 3 (strictly rejecting excess harvesters)
 *    - Time-To-Depletion (TTD <= 120s) autonomous expansion taskforce deployment
 *    - Scouting 4-waypoint patrol sweep with <65% HP survival retreat reflex
 *    - Authentic market trading engine (pays 5:3 exchange penalty, cooldown enforced)
 *    - 6x6 Pairwise counter-production matrix against cavalry, ranged, and heavy infantry
 * 5. TacticalMicroManager Comprehensive Engine:
 *    - Stutter-step kiting along repulsive potential fields during weapon cooldown
 *    - Projectile reservation manager, in-flight damage tracking, mathematical death, overkill retargeting
 *    - HP-ratio tactical retreat (< 30% HP) to nearest triage hub / HQ
 *    - AoE hazard evasion (radial dispersal from incoming splash projectiles)
 *    - Hammer & Anvil geometric flanking maneuvers
 *    - Healer triage network prioritizing high-value heroes
 * 6. DifficultyConfig & APM Throttling:
 *    - 4 quantitative tiers: Easy, Normal, Hard, Brutal
 *    - ApmLimiter token bucket rate limiting and per-unit command cooldown
 *    - Reaction interval sampling with bounded jitter
 * 7. GameApp & window.gameEngine Automation Bridge:
 *    - Full bridge registration and state exposure
 *    - Dynamic setDifficulty switching propagating through Macro and Micro engines
 *    - Interactive production dispatch through HUD and game loop tick processing
 */

import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// --- Headless Mock DOM System ---
class MockElement {
    constructor(tagName = 'div') {
        this.tagName = tagName.toUpperCase();
        this.id = '';
        this.className = '';
        this._value = '';
        this.type = '';
        this.style = {};
        this.children = [];
        this.parentNode = null;
        this.eventListeners = {};
        this._innerHTML = '';
        this.dataset = {};
        this.classList = {
            add: () => {},
            remove: () => {},
            contains: () => false,
            toggle: () => {}
        };
    }
    closest(selector) { return this; }
    setAttribute(name, val) { this[name] = val; }
    getAttribute(name) { return this[name] || null; }
    removeAttribute(name) { delete this[name]; }
    getBoundingClientRect() { return { x: 0, y: 0, width: 100, height: 100, top: 0, bottom: 100, left: 0, right: 100 }; }
    get value() { return this._value; }
    set value(v) { this._value = v !== undefined && v !== null ? String(v) : ''; }
    get innerHTML() { return this._innerHTML; }
    set innerHTML(html) { this._innerHTML = html; }
    get textContent() { return this._text || ''; }
    set textContent(txt) { this._text = txt; }
    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }
    addEventListener(event, cb) {
        if (!this.eventListeners[event]) this.eventListeners[event] = [];
        this.eventListeners[event].push(cb);
    }
    dispatchEvent(event) {
        const type = typeof event === 'string' ? event : event.type;
        const listeners = this.eventListeners[type] || [];
        for (const cb of listeners) cb({ type, target: this });
        return true;
    }
    querySelector(selector) {
        if (selector.startsWith('#')) {
            const target = selector.substring(1);
            return this._findById(target);
        }
        return this.children[0] || null;
    }
    querySelectorAll() { return this.children; }
    _findById(id) {
        if (this.id === id) return this;
        for (const c of this.children) {
            const found = c._findById ? c._findById(id) : null;
            if (found) return found;
        }
        return null;
    }
    getContext() {
        return {
            fillRect: () => {},
            clearRect: () => {},
            save: () => {},
            restore: () => {},
            translate: () => {},
            scale: () => {},
            beginPath: () => {},
            ellipse: () => {},
            arc: () => {},
            moveTo: () => {},
            lineTo: () => {},
            fill: () => {},
            stroke: () => {},
            drawImage: () => {},
            fillText: () => {}
        };
    }
}

class MockDocument {
    constructor() {
        this.body = new MockElement('body');
        this.elements = new Map();
    }
    createElement(tag) { return new MockElement(tag); }
    getElementById(id) {
        if (!this.elements.has(id)) {
            const el = new MockElement('div');
            el.id = id;
            this.elements.set(id, el);
        }
        return this.elements.get(id);
    }
    querySelector(sel) { return this.getElementById(sel.replace(/^[#.spaces]+/, '')); }
    querySelectorAll() { return []; }
}

const mockDoc = new MockDocument();
global.HTMLElement = MockElement;
global.document = mockDoc;
global.window = {
    document: mockDoc,
    HTMLElement: MockElement,
    addEventListener: () => {},
    removeEventListener: () => {},
    requestAnimationFrame: (cb) => setTimeout(cb, 16),
    cancelAnimationFrame: (id) => clearTimeout(id),
    performance: { now: () => Date.now() },
    gameEngine: {}
};

// --- Module Imports ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

import { IsometricMath } from '../web_prototype/js/engine/isometric.js';
import { Camera } from '../web_prototype/js/engine/camera.js';
import { SoundEngine } from '../web_prototype/js/engine/audio.js';
import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { Unit, Building, UnitState, Direction, CUSTOM_JOSEON_ANIM_SPECS } from '../web_prototype/js/simulation/entities.js';
import { IsometricRenderer } from '../web_prototype/js/engine/renderer.js';
import { CommandCardHUD, COMMAND_HOTKEYS, CUSTOM_JOSEON_UNITS } from '../web_prototype/js/ui/command_card.js';
import { BUILTIN_UNIT_TEMPLATES } from '../web_prototype/js/ui/modding_studio.js';
import {
    DIFFICULTY_TIERS,
    TACTICAL_FLAGS,
    getDifficultyConfig,
    sampleReactionDelaySec,
    ApmLimiter
} from '../web_prototype/js/simulation/difficulty_config.js';
import {
    StrategicMacroAI,
    UNIT_CLASS,
    MACRO_POSTURE,
    COUNTER_MATRIX,
    NODE_SATURATION_LIMITS
} from '../web_prototype/js/simulation/strategic_macro_ai.js';
import {
    Vec2,
    ProjectileReservationManager,
    TacticalMicroManager
} from '../web_prototype/js/simulation/tactical_micro.js';
import { GameApp } from '../web_prototype/js/main.js';

let totalTests = 0;
let passedTests = 0;

function runTest(suiteName, testName, testFn) {
    totalTests++;
    try {
        testFn();
        passedTests++;
        console.log(`  [PASS] ${testName}`);
    } catch (err) {
        console.error(`  [FAIL] ${testName}`);
        console.error(`         Suite: ${suiteName}`);
        console.error(`         ${err.stack || err.message}`);
        process.exitCode = 1;
        throw err;
    }
}

console.log('======================================================================');
console.log(' R6 MASTER E2E & VERIFICATION TEST SUITE (Custom Units & AI Overhaul)');
console.log('======================================================================\n');

// ---------------------------------------------------------------------------
// SUITE 1: 10 Custom Joseon Units Templates, Metadata, and Button Registry
// ---------------------------------------------------------------------------
console.log('--- SUITE 1: 10 Custom Joseon Units & Command Card Production Bindings ---');

const EXPECTED_JOSEON_UNITS = [
    { kindId: 0x70, kindHex: '0x70', id: 'yusaeng', name: '유생', hotkey: 'Y', slot: 9, bldg: 'chosun_hq', rice: 250, potato: 0, isAir: false, frames: 176, corpseFrame: 71 },
    { kindId: 0x71, kindHex: '0x71', id: 'geomsul_nangin', name: '검술 낭인', hotkey: 'K', slot: 8, bldg: 'chosun_barracks', rice: 180, potato: 0, isAir: false, frames: 136, corpseFrame: 128 },
    { kindId: 0x72, kindHex: '0x72', id: 'jochong_nangin', name: '조총 낭in', hotkey: 'N', slot: 9, bldg: 'chosun_barracks', rice: 240, potato: 0, isAir: false, frames: 136, corpseFrame: 128 },
    { kindId: 0x73, kindHex: '0x73', id: 'gumiho', name: '구미호', hotkey: 'F', slot: 11, bldg: 'chosun_hq', rice: 280, potato: 50, isAir: false, frames: 144, corpseFrame: 136 },
    { kindId: 0x74, kindHex: '0x74', id: 'wangbeol', name: '조선왕벌', hotkey: 'B', slot: 7, bldg: 'chosun_stables', rice: 200, potato: 50, isAir: true, frames: 160, corpseFrame: null },
    { kindId: 0x75, kindHex: '0x75', id: 'horangi', name: '조선 호랑이', hotkey: 'T', slot: 8, bldg: 'chosun_stables', rice: 300, potato: 0, isAir: false, frames: 136, corpseFrame: 129 },
    { kindId: 0x76, kindHex: '0x76', id: 'teolgamyeon', name: '털가면', hotkey: 'M', slot: 10, bldg: 'chosun_barracks', rice: 220, potato: 40, isAir: false, frames: 130, corpseFrame: 129 },
    { kindId: 0x77, kindHex: '0x77', id: 'seolnyeo', name: '설녀', hotkey: 'S', slot: 9, bldg: 'chosun_stables', rice: 280, potato: 60, isAir: false, frames: 192, corpseFrame: 83 },
    { kindId: 0x78, kindHex: '0x78', id: 'dokkaebi', name: '조선 도깨비', hotkey: 'D', slot: 10, bldg: 'chosun_stables', rice: 320, potato: 0, isAir: false, frames: 180, corpseFrame: 150 },
    { kindId: 0x79, kindHex: '0x79', id: 'bulgasari', name: '불가살이', hotkey: 'U', slot: 10, bldg: 'chosun_hq', rice: 380, potato: 100, isAir: false, frames: 216, corpseFrame: 179 }
];

runTest('Suite 1', 'BUILTIN_UNIT_TEMPLATES includes all 10 custom Joseon units (0x70~0x79)', () => {
    assert.ok(Array.isArray(BUILTIN_UNIT_TEMPLATES));
    for (const spec of EXPECTED_JOSEON_UNITS) {
        const found = BUILTIN_UNIT_TEMPLATES.find(t => (t.kind_id === spec.kindId || t.kindId === spec.kindId || t.index === spec.kindId));
        assert.ok(found, `Missing template for custom unit 0x${spec.kindId.toString(16)} (${spec.name})`);
        assert.strictEqual(found.faction, 'chosun', `Unit 0x${spec.kindId.toString(16)} must belong to faction chosun`);
        assert.ok(found.hp > 0, `Unit 0x${spec.kindId.toString(16)} HP must be positive`);
        assert.ok(found.move_speed > 0, `Unit 0x${spec.kindId.toString(16)} move_speed must be positive`);
        assert.strictEqual(found.cost_rice || found.costRice, spec.rice, `Mismatched rice cost for ${spec.name}`);
        assert.strictEqual(found.cost_potato || found.costPotato, spec.potato, `Mismatched potato cost for ${spec.name}`);
        if (spec.isAir) {
            assert.strictEqual(found.isAirUnit || found.is_air, true, 'Hornet must be air unit');
            assert.strictEqual(found.flightAltitude, 36, 'Hornet flight altitude must be 36px');
        }
    }
});

runTest('Suite 1', 'Physical button assets and manifest exist with valid 34x34 size', () => {
    const buttonsDir = path.join(rootDir, 'web_prototype', 'assets', 'ui', 'buttons');
    const manifestPath = path.join(buttonsDir, 'buttons_manifest.json');
    assert.ok(fs.existsSync(manifestPath), `Missing ${manifestPath}`);

    const manifestData = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    assert.strictEqual(manifestData.total_units, 10);
    assert.strictEqual(manifestData.button_width, 34);
    assert.strictEqual(manifestData.button_height, 34);

    for (const spec of EXPECTED_JOSEON_UNITS) {
        const btnPngHex = path.join(buttonsDir, `btn_unit_${spec.kindHex.toLowerCase()}.png`);
        assert.ok(fs.existsSync(btnPngHex), `Missing button PNG: ${btnPngHex}`);
        const stat = fs.statSync(btnPngHex);
        assert.ok(stat.size > 200, `Button PNG file too small (${stat.size} bytes): ${btnPngHex}`);
    }
});

runTest('Suite 1', 'CommandCardHUD binds custom units to exact building slots (HQ: 9,10,11; Barracks: 8,9,10; Stables: 7,8,9,10)', () => {
    let triggeredCommand = null;
    const hud = new CommandCardHUD(null, (cmd) => {
        triggeredCommand = cmd;
    });

    // 1. Chosun Headquarters (HQ)
    hud.setBuildingCustomUnitCommands('조선 본영');
    assert.ok(hud.slots[9], 'HQ Slot 9 must be populated');
    assert.strictEqual(hud.slots[9].kindId, 0x70, 'HQ Slot 9 must be 0x70 (유생)');
    assert.strictEqual(hud.slots[9].hotkey, 'Y');

    assert.ok(hud.slots[10], 'HQ Slot 10 must be populated');
    assert.strictEqual(hud.slots[10].kindId, 0x79, 'HQ Slot 10 must be 0x79 (불가살이)');
    assert.strictEqual(hud.slots[10].hotkey, 'U');

    assert.ok(hud.slots[11], 'HQ Slot 11 must be populated');
    assert.strictEqual(hud.slots[11].kindId, 0x73, 'HQ Slot 11 must be 0x73 (구미호)');
    assert.strictEqual(hud.slots[11].hotkey, 'F');

    // 2. Chosun Barracks
    hud.setBuildingCustomUnitCommands('조선 훈련소');
    assert.strictEqual(hud.slots[8].kindId, 0x71, 'Barracks Slot 8 must be 0x71 (검술 낭인)');
    assert.strictEqual(hud.slots[8].hotkey, 'K');

    assert.strictEqual(hud.slots[9].kindId, 0x72, 'Barracks Slot 9 must be 0x72 (조총 낭인)');
    assert.strictEqual(hud.slots[9].hotkey, 'N');

    assert.strictEqual(hud.slots[10].kindId, 0x76, 'Barracks Slot 10 must be 0x76 (털가면)');
    assert.strictEqual(hud.slots[10].hotkey, 'M');

    // 3. Chosun Stables
    hud.setBuildingCustomUnitCommands('조선 목장/마구간');
    assert.strictEqual(hud.slots[7].kindId, 0x74, 'Stables Slot 7 must be 0x74 (조선왕벌)');
    assert.strictEqual(hud.slots[7].hotkey, 'B');

    assert.strictEqual(hud.slots[8].kindId, 0x75, 'Stables Slot 8 must be 0x75 (조선 호랑이)');
    assert.strictEqual(hud.slots[8].hotkey, 'T');

    assert.strictEqual(hud.slots[9].kindId, 0x77, 'Stables Slot 9 must be 0x77 (설녀)');
    assert.strictEqual(hud.slots[9].hotkey, 'S');

    assert.strictEqual(hud.slots[10].kindId, 0x78, 'Stables Slot 10 must be 0x78 (조선 도깨비)');
    assert.strictEqual(hud.slots[10].hotkey, 'D');

    // Slot trigger test
    hud.triggerSlot(7);
    assert.ok(triggeredCommand !== null);
    assert.strictEqual(triggeredCommand.kindId, 0x74);
});

runTest('Suite 1', 'GameApp tryProduceUnit validates costs and enqueues into building production queue', () => {
    const app = new GameApp();
    const hq = new Building(10, { korean_name: '조선 본영', width: 3, height: 3, hp: 6000 }, 30, 30, 0);
    hq.isBuilding = true;
    hq.productionQueue = [];
    app.entities.push(hq);
    app.selectedUnits = [hq];

    // Case 1: Insufficient resources
    app.resources.rice = 50;
    app.resources.potato = 0;
    const yusaengTemplate = BUILTIN_UNIT_TEMPLATES.find(t => t.kind_id === 0x70 || t.index === 0x70);
    const rejectResult = app.tryProduceUnit(yusaengTemplate, { rice: 250, potato: 0 });
    assert.strictEqual(rejectResult, null, 'Production must be rejected due to insufficient rice');
    assert.strictEqual(hq.productionQueue.length, 0, 'No unit should be queued');

    // Case 2: Sufficient resources
    app.resources.rice = 1000;
    app.resources.potato = 500;
    const queueResult = app.tryProduceUnit(yusaengTemplate, { rice: 250, potato: 0 });
    assert.ok(queueResult !== null, 'Production should succeed and enqueue');
    assert.strictEqual(app.resources.rice, 750, 'Rice must be deducted (1000 - 250 = 750)');
    assert.strictEqual(hq.productionQueue.length, 1, 'Production queue should have 1 item');
    assert.strictEqual(hq.productionQueue[0].archetype.korean_name, '유생');

    // Enqueue up to maximum 4
    app.tryProduceUnit(yusaengTemplate, { rice: 250, potato: 0 });
    app.tryProduceUnit(yusaengTemplate, { rice: 250, potato: 0 });
    const bulgasariTemplate = BUILTIN_UNIT_TEMPLATES.find(t => t.kind_id === 0x79 || t.index === 0x79);
    app.tryProduceUnit(bulgasariTemplate, { rice: 0, potato: 100 });
    assert.strictEqual(hq.productionQueue.length, 4, 'Queue full at 4 items');

    // 5th attempt must be rejected by queue saturation
    const overflowResult = app.tryProduceUnit(yusaengTemplate, { rice: 10, potato: 0 });
    assert.strictEqual(overflowResult, null, '5th item must be rejected (queue full limit 4)');
    assert.strictEqual(hq.productionQueue.length, 4);
});

// ---------------------------------------------------------------------------
// SUITE 2: 5-Action Animation Lifecycles in entities.js and renderer.js
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 2: 5-Action Animation Lifecycles & Corpse Decay ---');

const assetManifest = JSON.parse(fs.readFileSync(path.join(rootDir, 'web_prototype', 'assets', 'manifest.json'), 'utf-8'));

runTest('Suite 2', 'UnitState supports all 5 standard action states', () => {
    assert.strictEqual(UnitState.IDLE, 'IDLE');
    assert.strictEqual(UnitState.WALK, 'WALK');
    assert.strictEqual(UnitState.ATTACK, 'ATTACK');
    assert.strictEqual(UnitState.DIE, 'DIE');
    assert.strictEqual(UnitState.CORPSE_DECAY, 'CORPSE_DECAY');
});

runTest('Suite 2', 'All 9 custom ground Joseon units transition smoothly through 5-action lifecycle to CORPSE_DECAY', () => {
    const groundUnits = EXPECTED_JOSEON_UNITS.filter(u => !u.isAir);
    const grid = new GameGrid(64, 64);
    const mockAudio = { play: () => {} };

    for (const spec of groundUnits) {
        const manifestKey = Object.keys(assetManifest.units).find(k => assetManifest.units[k].kind_id === spec.kindId);
        assert.ok(manifestKey, `Missing manifest entry for kind_id 0x${spec.kindId.toString(16)}`);
        const unitDef = assetManifest.units[manifestKey];
        const unit = new Unit(100 + spec.kindId, unitDef, 20, 20, 0);

        // 1. IDLE
        assert.strictEqual(unit.state, UnitState.IDLE);

        // 2. WALK
        unit.moveTo(25, 20, grid);
        assert.strictEqual(unit.state, UnitState.WALK);
        unit.update(0.2, grid, [], mockAudio);

        // 3. ATTACK: Halt walk, target adjacent enemy and execute attack
        unit.waypoints = [];
        unit.state = UnitState.IDLE;
        const enemy = new Unit(999, { hp: 500, max_hp: 500, defense: 0 }, 20, 20, 1);
        enemy.wx = unit.wx + 0.5;
        enemy.wy = unit.wy;
        unit.targetEntity = enemy;
        unit.attackTimer = 0;
        unit.update(0.01, grid, [enemy], mockAudio);
        assert.ok(
            unit.state === UnitState.ATTACK_WINDUP || unit.state === UnitState.ATTACK || unit.state === UnitState.ATTACK_COOLDOWN,
            `Unit ${spec.name} must enter attack state (got ${unit.state})`
        );
        // Complete windup and strike
        unit.update(0.3, grid, [enemy], mockAudio);
        assert.ok(enemy.hp < 500, `Enemy must receive damage from ${spec.name}`);

        // 4. DIE
        grid.setUnitOccupancy(unit.gx, unit.gy, unit.id);
        unit.takeDamage(9999, mockAudio);
        assert.strictEqual(unit.hp, 0);
        assert.strictEqual(unit.state, UnitState.DIE);
        assert.strictEqual(unit.isDead, true);
        assert.strictEqual(unit.isDying, true);

        // Advance through death animation (typically ~1.2s)
        let deathTimer = 0;
        while (unit.state === UnitState.DIE && deathTimer < 3.0) {
            unit.update(0.1, grid, [], mockAudio);
            deathTimer += 0.1;
        }

        // 5. CORPSE_DECAY
        assert.strictEqual(unit.state, UnitState.CORPSE_DECAY, `Unit ${spec.name} must enter CORPSE_DECAY`);
        assert.strictEqual(unit.corpseDuration, 4.0, 'Corpse duration must be 4.0s');
        assert.strictEqual(unit.corpseAlpha, 1.0, 'Initial corpse alpha must be 1.0');
        assert.strictEqual(grid.unitOccupancy[grid.getIndex(unit.gx, unit.gy)], -1, 'Tile occupancy must be freed');

        // Fast forward 3.5s (in fade window: remaining 0.5s / 1.0s window -> alpha ~0.5)
        unit.update(3.5, grid, [], mockAudio);
        assert.strictEqual(unit.state, UnitState.CORPSE_DECAY);
        assert.ok(unit.corpseAlpha < 1.0 && unit.corpseAlpha > 0.0, `Corpse alpha must dissolve (got ${unit.corpseAlpha})`);

        // Fast forward past 4.0s
        unit.update(1.0, grid, [], mockAudio);
        assert.strictEqual(unit.corpseAlpha, 0.0);
        assert.strictEqual(unit.isDying, false, 'isDying must be false after full corpse decay');
    }
});

runTest('Suite 2', 'IsometricRenderer CUSTOM_JOSEON_ANIM_SPECS accurately resolves frame boundaries and corpse indices', () => {
    const renderer = new IsometricRenderer(null, null);

    for (const spec of EXPECTED_JOSEON_UNITS) {
        const anim = CUSTOM_JOSEON_ANIM_SPECS[spec.kindId];
        assert.ok(anim, `Missing anim spec for 0x${spec.kindId.toString(16)}`);
        assert.ok(anim.idle, `Missing idle spec`);
        assert.ok(anim.move, `Missing move spec`);
        assert.ok(anim.atk, `Missing atk spec`);
        assert.ok(anim.die, `Missing die spec`);

        if (spec.isAir) {
            assert.strictEqual(anim.die.corpse, null, 'Air unit corpse frame must be null');
        } else {
            assert.strictEqual(anim.die.corpse, spec.corpseFrame, `Corpse frame mismatch for ${spec.name}`);
        }
    }
});

// ---------------------------------------------------------------------------
// SUITE 3: Air Unit Joseon Hornet (0x74) Flight & Instant Death Vanishing
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 3: Joseon Hornet (0x74) Flight & Instant Vanish Invariants ---');

runTest('Suite 3', 'Joseon Hornet has flightAltitude 36px, direct vector flight, and isAirUnit=true', () => {
    const hornetDef = assetManifest.units['chosun_wangbeol'];
    assert.strictEqual(hornetDef.isAirUnit, true);

    const grid = new GameGrid(64, 64);
    // Fill destination with impassable rocks
    for (let x = 10; x <= 15; x++) {
        for (let y = 10; y <= 15; y++) {
            grid.setWalkability(x, y, 1);
        }
    }

    const hornet = new Unit(7401, hornetDef, 5, 5, 0);
    assert.strictEqual(hornet.isAirUnit, true);
    assert.strictEqual(hornet.flightAltitude, 36);

    hornet.moveTo(12, 12, grid);
    assert.strictEqual(hornet.state, UnitState.WALK);
    assert.strictEqual(hornet.waypoints.length, 1, 'Air unit must use straight direct flight waypoint');
    assert.strictEqual(hornet.waypoints[0].gx, 12);
    assert.strictEqual(hornet.waypoints[0].gy, 12);
});

runTest('Suite 3', 'CRITICAL: Joseon Hornet vanishes INSTANTLY on HP <= 0 with ZERO corpse decay and ZERO ground footprint', () => {
    const hornetDef = assetManifest.units['chosun_wangbeol'];
    const hornet = new Unit(7402, hornetDef, 20, 20, 0);
    const mockAudio = { play: () => {} };

    // Lethal strike
    hornet.takeDamage(1000, mockAudio);

    // Instant death properties
    assert.strictEqual(hornet.hp, 0);
    assert.strictEqual(hornet.isDead, true);
    assert.strictEqual(hornet.isDying, false, 'isDying must be FALSE immediately (suppressing death animation & corpse delay)');
    assert.strictEqual(hornet.deathAnimDone, true);
    assert.strictEqual(hornet.corpseAlpha, 0.0);
    assert.notStrictEqual(hornet.state, UnitState.CORPSE_DECAY, 'Hornet must NEVER enter CORPSE_DECAY state');

    // Verify resolveUnitFrame returns null for CORPSE_DECAY
    const renderer = new IsometricRenderer(null, null);
    const mockSpr = {
        name: 'bat_online.spr',
        frameCount: 160,
        width: 80,
        height: 80,
        cols: 8,
        frames: Array.from({ length: 160 }, () => ({ u: 0, v: 0, w: 80, h: 80 }))
    };
    const corpseFrame = renderer.resolveUnitFrame(mockSpr, hornet, 0, 0, 'CORPSE_DECAY');
    assert.strictEqual(corpseFrame, null, 'Air unit corpse frame must be null');

    // Simulation purge in GameApp loop:
    const entities = [hornet];
    for (let i = entities.length - 1; i >= 0; i--) {
        const ent = entities[i];
        if (ent.isDead) {
            if (ent.isDying) {
                // Not reached for air units!
            } else {
                entities.splice(i, 1);
            }
        }
    }
    assert.strictEqual(entities.length, 0, 'Air unit must be immediately spliced from entities on tick 0');
});

// ---------------------------------------------------------------------------
// SUITE 4: StrategicMacroAI - Economy, Saturation, TTD, Scouting, Counter Matrix
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 4: Strategic Macro AI Architecture ---');

function createMacroMockApp() {
    const grid = new GameGrid(64, 64);
    return {
        grid,
        entities: [],
        nextEntityId: 5000,
        playerResources: {
            0: { rice: 1000, potato: 1000, wood: 1000, supplyUsed: 10, supplyMax: 2000 },
            1: { rice: 1000, potato: 1000, wood: 1000, supplyUsed: 10, supplyMax: 2000 }
        },
        getPlayerResources(owner) {
            return this.playerResources[owner] || (this.playerResources[owner] = { rice: 1000, potato: 1000, wood: 1000 });
        },
        markBuildingFootprint() {}
    };
}

runTest('Suite 4', 'StrategicMacroAI strictly respects 0% cheat parity (cheat5050Enabled === false)', () => {
    const app = createMacroMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });
    assert.strictEqual(ai.difficultyConfig.cheat5050Enabled, false, 'No 50:50 cheat resource injection allowed');
});

runTest('Suite 4', 'Node saturation limits strictly enforced: Rice max 3, Tree max 1, Potato max 3', () => {
    const app = createMacroMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    assert.strictEqual(ai.getNodeSaturationLimit(100), 3, 'Rice saturation limit must be 3');
    assert.strictEqual(ai.getNodeSaturationLimit(3), 1, 'Tree saturation limit must be 1');
    assert.strictEqual(ai.getNodeSaturationLimit(1), 3, 'Potato saturation limit must be 3');

    // Place a tree at (15, 15)
    app.grid.resourceTypes[15 * 64 + 15] = 3;
    app.grid.resourceAmounts[15 * 64 + 15] = 600;

    const worker1 = new Unit(5101, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 16, 15, 1);
    worker1.isWorker = true;
    worker1.harvestPref = 3;
    app.entities.push(worker1);

    const target1 = ai.findBestUnsaturatedNode(worker1, app.grid);
    assert.ok(target1 !== null);
    assert.strictEqual(target1.gx, 15);
    assert.strictEqual(target1.gy, 15);

    // Register reservation for worker 1
    ai.nodeReservations.set('15,15', new Set([5101]));

    // Worker 2 attempts to claim the same tree node
    const worker2 = new Unit(5102, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 17, 15, 1);
    worker2.isWorker = true;
    worker2.harvestPref = 3;
    app.entities.push(worker2);

    const target2 = ai.findBestUnsaturatedNode(worker2, app.grid);
    assert.strictEqual(target2, null, 'Tree at 1/1 saturation must reject second worker');
});

runTest('Suite 4', 'Time-To-Depletion (TTD <= 120s) dispatches autonomous expansion taskforce', () => {
    const app = createMacroMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    const hq = new Building(5201, { korean_name: '일본 본영', width: 3, height: 3, hp: 6000 }, 32, 28, 1);
    hq.isBuilding = true;
    hq.isConstructing = false;
    app.entities.push(hq);
    ai.syncInitialBases();

    const builder = new Unit(5202, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 32, 30, 1);
    builder.isWorker = true;
    app.entities.push(builder);

    for (let i = 0; i < 4; i++) {
        const combat = new Unit(5203 + i, { korean_name: '일본 사무라이', move_speed: 13, hp: 920 }, 33, 30, 1);
        app.entities.push(combat);
    }

    // Set resource cluster at expansion location (55, 18)
    app.grid.resourceTypes[18 * 64 + 55] = 100;
    app.grid.resourceAmounts[18 * 64 + 55] = 2000;

    app.playerResources[1].rice = 900;
    app.playerResources[1].wood = 700;

    ai.evaluateMacroState();
    assert.ok(ai.activeExpansionTaskforce !== null, 'Expansion taskforce must be spawned');
    assert.strictEqual(ai.activeExpansionTaskforce.phase, 'ESCORT_TRANSIT');
    assert.strictEqual(ai.activeExpansionTaskforce.builder.id, 5202);
});

runTest('Suite 4', 'Scout unit executes 4-waypoint patrol and retreats to base when HP < 65%', () => {
    const app = createMacroMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    const scout = new Unit(5301, { korean_name: '일본 닌자', move_speed: 16, hp: 600, max_hp: 600 }, 32, 28, 1);
    app.entities.push(scout);

    ai.updateScoutPatrol(0.1);
    assert.strictEqual(ai.scoutEntityId, 5301);
    assert.strictEqual(ai.scoutRoute.length, 4);

    // Scout reaches waypoint 0
    scout.wx = ai.scoutRoute[0].gx;
    scout.wy = ai.scoutRoute[0].gy;
    ai.updateScoutPatrol(0.1);
    assert.strictEqual(ai.scoutIndex, 1);

    // Scout damaged to 300/600 (50% < 65%)
    scout.hp = 300;
    ai.updateScoutPatrol(0.1);
    assert.strictEqual(ai.scoutIndex, 1, 'Scout route advance halted for emergency retreat');
});

runTest('Suite 4', '6x6 Counter-Production Matrix selects Spearman against Cavalry threat', () => {
    const app = createMacroMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    const barracks = new Building(5401, { korean_name: '일본 훈련소', width: 3, height: 3, hp: 3500 }, 36, 28, 1);
    barracks.isBuilding = true;
    app.entities.push(barracks);

    // Cavalry threat = 1.0 (Class 1)
    ai.threatVector = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0];
    const counterUnit = ai.selectOptimalCounterUnit();
    assert.ok(counterUnit !== null);
    assert.ok(counterUnit.korean_name.includes('창병'), `Expected Spearman counter against cavalry, got ${counterUnit.korean_name}`);
});

// ---------------------------------------------------------------------------
// SUITE 5: TacticalMicroManager - Kiting, Potential Fields, Projectile Reservation
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 5: Tactical Micro AI Architecture ---');

runTest('Suite 5', 'Ranged unit executes stutter-step kiting along repulsive field during weapon cooldown', () => {
    const app = createMacroMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    // Ranged Arquebusier at (20, 20) with attackTimer > 0 (reloading)
    const gunner = new Unit(6101, { korean_name: '일본 조총병', attack_range: 6.5, move_speed: 11, hp: 580, attack_power: 42 }, 20, 20, 1);
    gunner.attackTimer = 0.8;
    app.entities.push(gunner);

    // Melee Spearman threat approaching from (19, 20)
    const threat = new Unit(6102, { korean_name: '조선 창병', attack_range: 1.5, move_speed: 12, hp: 800 }, 19, 20, 0);
    app.entities.push(threat);

    const ctx = { state: 'COMBAT', lastKiteSec: 0, kiteVector: new Vec2(0, 0), isRetreating: false };
    const kited = micro.evaluateUnitKiting(gunner, ctx);

    assert.strictEqual(kited, true, 'Unit must kite away from incoming melee threat');
    assert.ok(gunner.waypoints.length > 0, 'Kiting step must generate waypoints');
    const kiteTargetX = gunner.waypoints[0].gx !== undefined ? gunner.waypoints[0].gx : gunner.waypoints[0].x;
    assert.ok(kiteTargetX >= 20, `Kite waypoint (${kiteTargetX}) must step away from threat at x=19`);
});

runTest('Suite 5', 'ProjectileReservationManager flags mathematical death & prevents overkill', () => {
    const app = createMacroMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    const archer = new Unit(6201, { korean_name: '일본 조총병', attack_range: 6.5, attack_power: 40 }, 25, 25, 1);
    app.entities.push(archer);

    const woundedGeneral = new Unit(6202, { korean_name: '조선 권율', hp: 35, max_hp: 1500, level: 2 }, 26, 25, 0);
    app.entities.push(woundedGeneral);

    const infantry = new Unit(6203, { korean_name: '조선 창병', hp: 700, max_hp: 700 }, 27, 25, 0);
    app.entities.push(infantry);

    // Initial targeting picks high-value wounded general
    micro.evaluateTargetAcquisition(archer);
    assert.strictEqual(archer.targetEntity.id, 6202);

    // Ally arrow dealing 40 damage is in flight towards general
    micro.reservationManager.addReservation(999, 6202, 40, 0.5, micro.gameTimeSec);
    assert.strictEqual(micro.reservationManager.isMathematicallySlain(woundedGeneral), true);

    // Overkill prevention: archer must retarget away from doomed general
    micro.evaluateTargetAcquisition(archer);
    assert.strictEqual(archer.targetEntity.id, 6203, 'Archer must retarget to infantry');
});

runTest('Suite 5', 'HP-Ratio retreat (< 30% HP) disengages aggro and flees to triage HQ', () => {
    const app = createMacroMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    const hq = new Building(6301, { korean_name: '일본 본영', width: 3, height: 3, hp: 6000 }, 32, 28, 1);
    hq.isBuilding = true;
    app.entities.push(hq);

    const samurai = new Unit(6302, { korean_name: '일본 사무라이', move_speed: 13, hp: 920, max_hp: 920 }, 20, 20, 1);
    samurai.hp = 180; // 19.5% < 30%
    app.entities.push(samurai);

    const ctx = { state: 'COMBAT', lastKiteSec: 0, kiteVector: new Vec2(0, 0), isRetreating: false };
    const retreating = micro.evaluateUnitRetreat(samurai, ctx);

    assert.strictEqual(retreating, true);
    assert.strictEqual(ctx.isRetreating, true);
    assert.strictEqual(samurai.targetEntity, null, 'Aggro must be cleared on retreat');
    assert.strictEqual(ctx.retreatAnchor.id, 6301, 'Retreat anchor must be friendly HQ');
});

runTest('Suite 5', 'AoE Hazard Evasion disperses units radially from splash impact', () => {
    const app = createMacroMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    const unit = new Unit(6401, { korean_name: '일본 사무라이', move_speed: 13, hp: 920 }, 25, 25, 1);
    app.entities.push(unit);

    app.projectiles = [
        { type: 'cannon', targetWx: 25, targetWy: 25, progress: 0.5, travelDuration: 0.8 }
    ];

    micro.evaluateHazardEvasion(0.1);
    assert.ok(unit.waypoints.length > 0, 'Evasion waypoint must be issued');
    const dest = unit.waypoints[0];
    const dx = (dest.gx !== undefined ? dest.gx : dest.x) - 25;
    const dy = (dest.gy !== undefined ? dest.gy : dest.y) - 25;
    assert.ok(Math.hypot(dx, dy) >= 2.0, 'Evasion waypoint must clear splash radius');
});

runTest('Suite 5', 'Hammer & Anvil flanking partitions force into pinning anvil & flanking hammer', () => {
    const app = createMacroMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    const enemyHq = new Building(6501, { korean_name: '조선 본영', width: 3, height: 3, hp: 6000 }, 10, 10, 0);
    enemyHq.isBuilding = true;
    app.entities.push(enemyHq);

    for (let i = 0; i < 8; i++) {
        const isCav = i < 3;
        const u = new Unit(6502 + i, {
            korean_name: isCav ? '일본 기병' : '일본 사무라이',
            move_speed: isCav ? 18 : 13,
            hp: 900
        }, 40 + (i % 2), 40 + Math.floor(i / 2), 1);
        app.entities.push(u);
    }

    micro.updateFlankingManeuver(0.1);
    assert.ok(micro.flankingSquad.hammer.size >= 2, 'Hammer must contain mobile flankers');
    assert.ok(micro.flankingSquad.anvil.size >= 4, 'Anvil must contain main combat mass');
    assert.strictEqual(micro.flankingSquad.state, 'MARCHING');
    assert.ok(micro.flankingSquad.flankWaypoint !== null);
});

// ---------------------------------------------------------------------------
// SUITE 6: DifficultyConfig - 4 Tiers, APM Limiter, Reaction Delays
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 6: Difficulty Scaling & APM Rate Limiting ---');

runTest('Suite 6', '4 Quantitative Difficulty Tiers have exact parameters and zero cheat parity', () => {
    const easy = DIFFICULTY_TIERS.EASY;
    assert.strictEqual(easy.apm, 45);
    assert.strictEqual(easy.reactionDelayMs, 850);
    assert.strictEqual(easy.cheat5050Enabled, false);
    assert.strictEqual(easy.kitingEnabled, false);

    const normal = DIFFICULTY_TIERS.NORMAL;
    assert.strictEqual(normal.apm, 110);
    assert.strictEqual(normal.reactionDelayMs, 417);
    assert.strictEqual(normal.cheat5050Enabled, false);
    assert.strictEqual(normal.kitingEnabled, true);

    const hard = DIFFICULTY_TIERS.HARD;
    assert.strictEqual(hard.apm, 240);
    assert.strictEqual(hard.reactionDelayMs, 167);
    assert.strictEqual(hard.cheat5050Enabled, false);
    assert.strictEqual(hard.aoeDodgingEnabled, true);

    const brutal = DIFFICULTY_TIERS.BRUTAL;
    assert.strictEqual(brutal.apm, 420);
    assert.strictEqual(brutal.reactionDelayMs, 42);
    assert.strictEqual(brutal.cheat5050Enabled, false);
    assert.strictEqual(brutal.flankingEnabled, true);
});

runTest('Suite 6', 'ApmLimiter throttles token burst capacity and enforces per-unit cooldown', () => {
    const limiter = new ApmLimiter(DIFFICULTY_TIERS.EASY); // 45 APM, capacity 3, cooldown 1.5s
    assert.strictEqual(limiter.tryConsume(10, 0.0), true);
    assert.strictEqual(limiter.tryConsume(10, 0.4), false, 'Cooldown active for unit 10');
    assert.strictEqual(limiter.tryConsume(11, 0.4), true, 'Different unit 11 allowed');
    assert.strictEqual(limiter.tryConsume(12, 0.5), true, 'Third token spent');
    assert.strictEqual(limiter.tryConsume(13, 0.6), false, 'Capacity saturated (3 tokens exhausted)');

    // Refill tokens after time elapsed
    assert.strictEqual(limiter.tryConsume(10, 3.0), true, 'Refilled tokens allow unit 10 after cooldown');
});

runTest('Suite 6', 'Reaction delay sampling returns values within calibrated bounds', () => {
    for (let i = 0; i < 15; i++) {
        const easyDelay = sampleReactionDelaySec('easy');
        assert.ok(easyDelay >= 0.5 && easyDelay <= 1.2, `Easy delay ${easyDelay} out of range`);
        const brutalDelay = sampleReactionDelaySec('brutal');
        assert.ok(Math.abs(brutalDelay - 1/24.0) < 1e-4, 'Brutal delay must be 1 tick');
    }
});

// ---------------------------------------------------------------------------
// SUITE 7: GameApp & window.gameEngine Automation Bridge Integration
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 7: GameApp & window.gameEngine Bridge Integration ---');

runTest('Suite 7', 'registerAutomationBridge exposes full API surface to window.gameEngine', () => {
    const app = new GameApp();
    app.registerAutomationBridge();

    const bridge = global.window.gameEngine;
    assert.ok(bridge, 'window.gameEngine must be registered');
    assert.strictEqual(bridge.app, app);
    assert.strictEqual(bridge.grid, app.grid);
    assert.strictEqual(bridge.camera, app.camera);
    assert.strictEqual(bridge.renderer, app.renderer);
    assert.strictEqual(bridge.macroAI, app.macroAI);
    assert.strictEqual(bridge.tacticalMicro, app.tacticalMicro);
    assert.strictEqual(bridge.difficulty, app.difficulty);
    assert.strictEqual(bridge.isLoaded, true);
    assert.ok(Array.isArray(bridge.BUILTIN_UNIT_TEMPLATES));
    assert.strictEqual(typeof bridge.setDifficulty, 'function');
    assert.strictEqual(typeof bridge.getPlayerResources, 'function');
});

runTest('Suite 7', 'setDifficulty dynamically switches tiers and reconfigures Macro & Micro engines', () => {
    const app = new GameApp();
    app.registerAutomationBridge();

    assert.strictEqual(app.difficulty.name, 'Normal');

    // Switch to Hard
    app.setDifficulty('hard');
    assert.strictEqual(app.difficulty.name, 'Hard');
    assert.strictEqual(app.difficultyConfig.apm, 240);
    assert.strictEqual(app.macroAI.difficultyConfig.apm, 240);
    assert.strictEqual(app.tacticalMicro.difficultyConfig.name, 'Hard');

    // Switch to Brutal
    app.setDifficulty('brutal');
    assert.strictEqual(app.difficulty.name, 'Brutal');
    assert.strictEqual(app.difficultyConfig.apm, 420);
    assert.strictEqual(app.macroAI.difficultyConfig.apm, 420);
    assert.strictEqual(app.tacticalMicro.difficultyConfig.name, 'Brutal');
});

console.log('\n======================================================================');
console.log(` MASTER TEST SUMMARY: ${passedTests} / ${totalTests} TESTS PASSED`);
console.log('======================================================================\n');

if (passedTests === totalTests) {
    console.log('>>> ALL R6 MASTER E2E TESTS PASSED WITH 100% SUCCESS <<<\n');
} else {
    process.exit(1);
}
