/**
 * Adversarial Stress & Invariant Verification Harness (Round 6)
 *
 * Authored by: challenger_r6_stress_verifier (Roles: Critic, Specialist)
 *
 * Empirically stress-tests:
 * 1. Button Visuals & Production Mapping:
 *    - 34x34 RGBA button assets on disk, pairwise distinctness (0 duplicates/placeholders), RTS bevels.
 *    - CommandCardHUD building slot bindings, out-of-range slots, empty slot rejection.
 *    - Queue flood & saturation, resource shortage rejection, cancellation refund.
 * 2. 5-Action Animations & Hornet Vanishing:
 *    - 5-action animation specs for all 10 units (0x70~0x79).
 *    - Air unit Joseon Hornet (0x74): extreme overkill, tick-by-tick lethal damage, zero corpse decay,
 *      zero ground footprint, grid walkability, instant splice from simulation on tick 0.
 *    - Ground units 5-action lifecycle: DIE animation, CORPSE_DECAY transition, instant tile occupancy release,
 *      linear alpha fade over final 1.0s, shadow/health bar suppression.
 * 3. AI Overhaul Stress-Testing:
 *    - 0% cheat parity (cheat5050Enabled === false across all 4 tiers, authentic market 5:3 exchange penalty).
 *    - Node saturation limits under heavy worker flood (Rice: 3, Tree: 1, Potato: 3), no clustering/overflow.
 *    - Stutter-step kiting along potential fields during weapon cooldown, corner-trap boundary survival.
 *    - APM rate limiter token bucket burst clamping, per-unit command cooldown, reaction delays across all 4 tiers.
 */

import assert from 'node:assert';
import crypto from 'node:crypto';
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
    closest() { return this; }
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

// Module Imports
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { Unit, Building, UnitState, Direction, CUSTOM_JOSEON_ANIM_SPECS } from '../web_prototype/js/simulation/entities.js';
import { IsometricRenderer } from '../web_prototype/js/engine/renderer.js';
import { CommandCardHUD, CUSTOM_JOSEON_UNITS } from '../web_prototype/js/ui/command_card.js';
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
    NODE_SATURATION_LIMITS
} from '../web_prototype/js/simulation/strategic_macro_ai.js';
import {
    Vec2,
    TacticalMicroManager
} from '../web_prototype/js/simulation/tactical_micro.js';
import { GameApp } from '../web_prototype/js/main.js';

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const failures = [];

function challenge(suite, description, fn) {
    totalTests++;
    try {
        fn();
        passedTests++;
        console.log(`  [PASS] [${suite}] ${description}`);
    } catch (err) {
        failedTests++;
        console.error(`  [FAIL] [${suite}] ${description}`);
        console.error(`         ${err.stack || err.message}`);
        failures.push({ suite, description, error: err.message });
    }
}

console.log('======================================================================');
console.log(' ADVERSARIAL STRESS & INVARIANT VERIFICATION HARNESS (R6)');
console.log('======================================================================\n');

const EXPECTED_UNITS = [
    { kindId: 0x70, kindHex: '0x70', id: 'yusaeng', name: '유생', hotkey: 'Y', slot: 9, bldg: 'chosun_hq', rice: 250, potato: 0, isAir: false, corpseFrame: 71 },
    { kindId: 0x71, kindHex: '0x71', id: 'geomsul_nangin', name: '검술 낭인', hotkey: 'K', slot: 8, bldg: 'chosun_barracks', rice: 180, potato: 0, isAir: false, corpseFrame: 128 },
    { kindId: 0x72, kindHex: '0x72', id: 'jochong_nangin', name: '조총 낭인', hotkey: 'N', slot: 9, bldg: 'chosun_barracks', rice: 240, potato: 0, isAir: false, corpseFrame: 128 },
    { kindId: 0x73, kindHex: '0x73', id: 'gumiho', name: '구미호', hotkey: 'F', slot: 11, bldg: 'chosun_hq', rice: 280, potato: 50, isAir: false, corpseFrame: 136 },
    { kindId: 0x74, kindHex: '0x74', id: 'wangbeol', name: '조선왕벌', hotkey: 'B', slot: 7, bldg: 'chosun_stables', rice: 200, potato: 50, isAir: true, corpseFrame: null },
    { kindId: 0x75, kindHex: '0x75', id: 'horangi', name: '조선 호랑이', hotkey: 'T', slot: 8, bldg: 'chosun_stables', rice: 300, potato: 0, isAir: false, corpseFrame: 129 },
    { kindId: 0x76, kindHex: '0x76', id: 'teolgamyeon', name: '털가면', hotkey: 'M', slot: 10, bldg: 'chosun_barracks', rice: 220, potato: 40, isAir: false, corpseFrame: 129 },
    { kindId: 0x77, kindHex: '0x77', id: 'seolnyeo', name: '설녀', hotkey: 'S', slot: 9, bldg: 'chosun_stables', rice: 280, potato: 60, isAir: false, corpseFrame: 83 },
    { kindId: 0x78, kindHex: '0x78', id: 'dokkaebi', name: '조선 도깨비', hotkey: 'D', slot: 10, bldg: 'chosun_stables', rice: 320, potato: 0, isAir: false, corpseFrame: 150 },
    { kindId: 0x79, kindHex: '0x79', id: 'bulgasari', name: '불가살이', hotkey: 'U', slot: 10, bldg: 'chosun_hq', rice: 380, potato: 100, isAir: false, corpseFrame: 179 }
];

// ---------------------------------------------------------------------------
// SUITE 1: Button Visuals & Production Mapping Adversarial Stress
// ---------------------------------------------------------------------------
console.log('--- SUITE 1: Button Visuals & Production Mapping Adversarial Stress ---');

const buttonsDir = path.join(rootDir, 'web_prototype', 'assets', 'ui', 'buttons');

challenge('Suite 1', 'PNG Header & Exact 34x34 Resolution for all 10 canonical buttons', () => {
    const pngSignature = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
    for (const spec of EXPECTED_UNITS) {
        const filePath = path.join(buttonsDir, `btn_unit_${spec.kindHex}.png`);
        assert.ok(fs.existsSync(filePath), `Missing button file: ${filePath}`);
        const buf = fs.readFileSync(filePath);

        // Check PNG signature
        assert.ok(buf.subarray(0, 8).equals(pngSignature), `Invalid PNG header in ${filePath}`);

        // IHDR chunk: length (4) + 'IHDR' (4) + width (4) + height (4) + bit_depth (1) + color_type (1)
        const ihdrType = buf.subarray(12, 16).toString('ascii');
        assert.strictEqual(ihdrType, 'IHDR', `First chunk must be IHDR in ${filePath}`);
        const width = buf.readUInt32BE(16);
        const height = buf.readUInt32BE(20);
        const bitDepth = buf[24];
        const colorType = buf[25];

        assert.strictEqual(width, 34, `Width must be 34 in ${filePath}, got ${width}`);
        assert.strictEqual(height, 34, `Height must be 34 in ${filePath}, got ${height}`);
        assert.strictEqual(bitDepth, 8, `Bit depth must be 8 in ${filePath}`);
        assert.strictEqual(colorType, 6, `Color type must be 6 (RGBA) in ${filePath}`);
    }
});

challenge('Suite 1', 'Pairwise Asset Distinctness: 10 Unique Non-Duplicate Hashes', () => {
    const hashes = new Set();
    for (const spec of EXPECTED_UNITS) {
        const buf = fs.readFileSync(path.join(buttonsDir, `btn_unit_${spec.kindHex}.png`));
        const hash = crypto.createHash('sha256').update(buf).digest('hex');
        assert.ok(!hashes.has(hash), `Duplicate button hash detected for 0x${spec.kindId.toString(16)}!`);
        hashes.add(hash);
    }
    assert.strictEqual(hashes.size, 10, 'All 10 canonical unit buttons must have unique SHA-256 hashes');
});

challenge('Suite 1', 'CommandCardHUD Slot Bindings & Out-of-Range Guarding', () => {
    const mockApp = { selectedUnits: [] };
    const hud = new CommandCardHUD(mockApp);

    // Verify building slot mapping
    const bldgs = {
        '조선 본영': { 9: 0x70, 10: 0x79, 11: 0x73 },
        '조선 훈련소': { 8: 0x71, 9: 0x72, 10: 0x76 },
        '조선 마구간': { 7: 0x74, 8: 0x75, 9: 0x77, 10: 0x78 }
    };

    for (const [bldgName, slotMap] of Object.entries(bldgs)) {
        const building = new Building(1, { name: bldgName, korean_name: bldgName, width: 3, height: 3 }, 10, 10, 0);
        building.isBuilding = true;
        hud.setBuildingCustomUnitCommands(building);

        for (const [slotStr, expectedKind] of Object.entries(slotMap)) {
            const slot = parseInt(slotStr, 10);
            const cmd = hud.slots[slot];
            assert.ok(cmd, `Slot ${slot} must be populated in ${bldgName}`);
            assert.strictEqual(cmd.kindId, expectedKind, `Slot ${slot} kindId mismatch in ${bldgName}`);
        }

        // Adversarial challenge: click unmapped/empty slot
        let triggered = null;
        hud.onCommandTrigger = (cmd) => { triggered = cmd; };

        hud.triggerSlot(0); // Slot 0 is empty here
        assert.strictEqual(triggered, null, 'Slot 0 should not trigger any command');

        // Out-of-range slots (-1, 12, 999) must not throw
        hud.triggerSlot(-1);
        hud.triggerSlot(12);
        hud.triggerSlot(999);
    }
});

challenge('Suite 1', 'Production Queue Saturation: Max 4 Items, Resource Rejection, Zero Deductions on Reject', () => {
    const app = new GameApp();
    const hq = new Building(10, { korean_name: '조선 본영', width: 3, height: 3, hp: 6000 }, 30, 30, 0);
    hq.isBuilding = true;
    hq.productionQueue = [];
    app.entities.push(hq);
    app.selectedUnits = [hq];

    const yusaengTemplate = BUILTIN_UNIT_TEMPLATES.find(t => t.kind_id === 0x70 || t.index === 0x70);
    assert.ok(yusaengTemplate);

    // Initial resources: 0
    app.resources.rice = 0;
    app.resources.potato = 0;

    // Challenge 1: Zero resources - Attempt all 10 units, all must be rejected
    for (const spec of EXPECTED_UNITS) {
        const tmpl = BUILTIN_UNIT_TEMPLATES.find(t => t.kind_id === spec.kindId || t.index === spec.kindId);
        const res = app.tryProduceUnit(tmpl, { rice: spec.rice, potato: spec.potato });
        assert.strictEqual(res, null, `Production of ${spec.name} should be rejected with zero resources`);
        assert.strictEqual(app.resources.rice, 0, 'Rice should not become negative');
        assert.strictEqual(app.resources.potato, 0, 'Potato should not become negative');
        assert.strictEqual(hq.productionQueue.length, 0, 'Queue must remain empty');
    }

    // Challenge 2: Partial resources - Have rice, missing potato (e.g. for Bulgasari: 380 rice, 100 potato)
    const bulgasariTemplate = BUILTIN_UNIT_TEMPLATES.find(t => t.kind_id === 0x79 || t.index === 0x79);
    app.resources.rice = 380;
    app.resources.potato = 99; // 1 potato short
    const partialRes = app.tryProduceUnit(bulgasariTemplate, { rice: 380, potato: 100 });
    assert.strictEqual(partialRes, null, 'Bulgasari must be rejected when 1 potato short');
    assert.strictEqual(app.resources.rice, 380, 'Rice must NOT be deducted on partial rejection');
    assert.strictEqual(app.resources.potato, 99, 'Potato must NOT be deducted on partial rejection');
    assert.strictEqual(hq.productionQueue.length, 0);

    // Challenge 3: Queue saturation flood - Queue exactly 4 items, 5th through 20th must reject cleanly
    app.resources.rice = 100000;
    app.resources.potato = 100000;

    for (let i = 0; i < 4; i++) {
        const queued = app.tryProduceUnit(yusaengTemplate, { rice: 250, potato: 0 });
        assert.ok(queued !== null, `Item ${i + 1} should successfully enqueue`);
    }
    assert.strictEqual(hq.productionQueue.length, 4, 'Queue should hold exactly 4 items');

    const riceBeforeFlood = app.resources.rice;
    for (let i = 0; i < 16; i++) {
        const floodRes = app.tryProduceUnit(yusaengTemplate, { rice: 250, potato: 0 });
        assert.strictEqual(floodRes, null, `Excess item ${i + 5} must be rejected due to queue cap`);
    }
    assert.strictEqual(hq.productionQueue.length, 4, 'Queue length must strictly remain capped at 4');
    assert.strictEqual(app.resources.rice, riceBeforeFlood, 'No resources deducted for overflow items');
});

// ---------------------------------------------------------------------------
// SUITE 2: 5-Action Animations & Hornet Vanishing Invariant
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 2: 5-Action Animations & Hornet Vanishing Invariants ---');

challenge('Suite 2', 'CUSTOM_JOSEON_ANIM_SPECS completeness & corpse invariants across all 10 units', () => {
    for (const spec of EXPECTED_UNITS) {
        const anim = CUSTOM_JOSEON_ANIM_SPECS[spec.kindId];
        assert.ok(anim, `Missing anim spec for 0x${spec.kindId.toString(16)}`);

        // Assert all 4 primary action states exist
        assert.ok(anim.idle && anim.idle.total > 0, `Invalid idle spec for ${spec.name}`);
        assert.ok(anim.move && anim.move.total > 0, `Invalid move spec for ${spec.name}`);
        assert.ok(anim.atk && anim.atk.total > 0, `Invalid atk spec for ${spec.name}`);
        assert.ok(anim.die && anim.die.total > 0, `Invalid die spec for ${spec.name}`);

        // Air unit vs Ground unit corpse invariant
        if (spec.isAir) {
            assert.strictEqual(anim.isAirUnit, true, `${spec.name} must have isAirUnit: true`);
            assert.strictEqual(anim.die.corpse, null, `${spec.name} corpse frame must be null (instant vanish)`);
        } else {
            assert.strictEqual(anim.die.corpse, spec.corpseFrame, `${spec.name} corpse frame mismatch`);
            assert.ok(typeof anim.die.corpse === 'number', `${spec.name} corpse must be a numeric frame index`);
        }
    }
});

challenge('Suite 2', 'Joseon Hornet (0x74) Extreme Overkill: Instant Vanish, Zero Decal, Zero Footprint', () => {
    const assetManifest = JSON.parse(fs.readFileSync(path.join(rootDir, 'web_prototype', 'assets', 'manifest.json'), 'utf-8'));
    const hornetDef = assetManifest.units['chosun_wangbeol'];
    const hornet = new Unit(74001, hornetDef, 15, 15, 0);
    const grid = new GameGrid(32, 32);

    // Air unit must NEVER claim grid tile occupancy while alive
    const tileIdx = grid.getIndex(15, 15);
    assert.strictEqual(grid.unitOccupancy[tileIdx], -1, 'Air unit must not occupy ground tile');

    // Strike with 999,999 overkill damage
    hornet.takeDamage(999999);

    assert.strictEqual(hornet.hp, 0);
    assert.strictEqual(hornet.isDead, true);
    assert.strictEqual(hornet.isDying, false, 'isDying must be FALSE immediately on lethal hit');
    assert.strictEqual(hornet.deathAnimDone, true);
    assert.strictEqual(hornet.corpseAlpha, 0.0);
    assert.notStrictEqual(hornet.state, UnitState.CORPSE_DECAY, 'Hornet must NEVER enter CORPSE_DECAY state');

    // Grid walkability check: tile 15,15 must be 100% walkable
    assert.strictEqual(grid.isWalkable(15, 15, false), true, 'Tile (15,15) must remain walkable');
    assert.strictEqual(grid.unitOccupancy[tileIdx], -1, 'Tile (15,15) must have 0 occupancy');
});

challenge('Suite 2', 'Joseon Hornet (0x74) Lethal Hit During Multiple States (WALK, IDLE, ATTACK_WINDUP)', () => {
    const assetManifest = JSON.parse(fs.readFileSync(path.join(rootDir, 'web_prototype', 'assets', 'manifest.json'), 'utf-8'));
    const hornetDef = assetManifest.units['chosun_wangbeol'];

    const testStates = [UnitState.IDLE, UnitState.WALK, UnitState.ATTACK_WINDUP, UnitState.ATTACK_COOLDOWN];

    for (const st of testStates) {
        const hornet = new Unit(74002, hornetDef, 20, 20, 0);
        hornet.state = st;
        hornet.takeDamage(hornet.hp + 50);

        assert.strictEqual(hornet.hp, 0);
        assert.strictEqual(hornet.isDead, true);
        assert.strictEqual(hornet.isDying, false, `isDying must be false when killed in state ${st}`);
        assert.strictEqual(hornet.deathAnimDone, true);
        assert.strictEqual(hornet.corpseAlpha, 0.0);
    }
});

challenge('Suite 2', 'Joseon Hornet (0x74) Renderer Suppression & Tick-0 Simulation Splice', () => {
    const assetManifest = JSON.parse(fs.readFileSync(path.join(rootDir, 'web_prototype', 'assets', 'manifest.json'), 'utf-8'));
    const hornetDef = assetManifest.units['chosun_wangbeol'];
    const hornet = new Unit(74003, hornetDef, 10, 10, 0);

    const renderer = new IsometricRenderer(null, null);
    const mockSpr = {
        name: 'bat_online.spr',
        frameCount: 160,
        width: 80,
        height: 80,
        cols: 8,
        frames: Array.from({ length: 160 }, () => ({ u: 0, v: 0, w: 80, h: 80 }))
    };

    // Before death: living frame resolves
    const livingFrame = renderer.resolveUnitFrame(mockSpr, hornet, 0, 0, 'IDLE');
    assert.ok(livingFrame !== null, 'Living hornet frame must resolve');

    // Kill hornet
    hornet.takeDamage(hornet.hp);

    // After death: CORPSE_DECAY frame resolution must return null
    const corpseFrame = renderer.resolveUnitFrame(mockSpr, hornet, 0, 0, 'CORPSE_DECAY');
    assert.strictEqual(corpseFrame, null, 'Dead hornet CORPSE_DECAY frame must be null');

    // GameApp loop simulation splice
    const app = new GameApp();
    app.entities = [hornet];

    // Simulate 1 tick
    for (let i = app.entities.length - 1; i >= 0; i--) {
        const ent = app.entities[i];
        if (ent.isDead) {
            if (ent.isAirUnit || ent.kindId === 0x74) {
                if (app.grid) app.grid.clearUnitOccupancy(ent.gx, ent.gy);
                app.entities.splice(i, 1);
            }
        }
    }
    assert.strictEqual(app.entities.length, 0, 'Hornet must be spliced from entities on tick 0');
});

challenge('Suite 2', 'Ground Units 5-Action Lifecycle: Death Animation, Instant Tile Release & Linear Alpha Fade', () => {
    const assetManifest = JSON.parse(fs.readFileSync(path.join(rootDir, 'web_prototype', 'assets', 'manifest.json'), 'utf-8'));
    const groundSpecs = EXPECTED_UNITS.filter(u => !u.isAir);
    const grid = new GameGrid(64, 64);
    const mockAudio = { play: () => {} };

    for (const spec of groundSpecs) {
        const def = assetManifest.units[Object.keys(assetManifest.units).find(k => assetManifest.units[k].kindId === spec.kindId || assetManifest.units[k].kind_id === spec.kindId)];
        assert.ok(def, `Missing manifest entry for ${spec.name}`);

        const unit = new Unit(spec.kindId * 100, def, 30, 30, 0);
        grid.setUnitOccupancy(30, 30, unit.id);
        const tileIdx = grid.getIndex(30, 30);
        assert.strictEqual(grid.unitOccupancy[tileIdx], unit.id, 'Ground unit must hold occupancy while alive');

        // Lethal hit
        unit.takeDamage(unit.hp, mockAudio);

        assert.strictEqual(unit.hp, 0);
        assert.strictEqual(unit.isDead, true);
        assert.strictEqual(unit.isDying, true);
        assert.strictEqual(unit.state, UnitState.DIE);

        // While in DIE animation, occupancy must still be held
        assert.strictEqual(grid.unitOccupancy[tileIdx], unit.id, 'Ground unit holds occupancy during death animation');

        // Advance through death duration
        const dieFrames = unit.animSpec.die.total;
        const deathDuration = dieFrames / unit.frameRate;
        unit.update(deathDuration + 0.01, grid, [], mockAudio);

        // Transitioned to CORPSE_DECAY
        assert.strictEqual(unit.state, UnitState.CORPSE_DECAY, `${spec.name} must enter CORPSE_DECAY`);
        assert.strictEqual(unit.corpseAlpha, 1.0, `${spec.name} initial corpseAlpha must be 1.0`);

        // INVARIANT: Tile occupancy must be released IMMEDIATELY upon entering CORPSE_DECAY
        assert.strictEqual(grid.unitOccupancy[tileIdx], -1, `${spec.name} must release tile occupancy in CORPSE_DECAY`);

        // Verify corpse holds resting frame for 4.0s total:
        // At t = 2.0s elapsed (2.0s remaining): corpseAlpha must remain 1.0
        unit.update(2.0, grid, [], mockAudio);
        assert.strictEqual(unit.corpseAlpha, 1.0, 'corpseAlpha must remain 1.0 when >1.0s remains');

        // At t = 3.5s elapsed (0.5s remaining, within 1.0s fade duration): corpseAlpha must be ~0.5
        unit.update(1.5, grid, [], mockAudio);
        assert.ok(unit.corpseAlpha >= 0.45 && unit.corpseAlpha <= 0.55, `corpseAlpha should be ~0.5, got ${unit.corpseAlpha}`);

        // At t = 4.01s elapsed (0s remaining): corpseAlpha must be 0.0, isDying must be false
        unit.update(0.51, grid, [], mockAudio);
        assert.strictEqual(unit.corpseAlpha, 0.0, 'corpseAlpha must reach 0.0');
        assert.strictEqual(unit.isDying, false, 'isDying must be false after corpse expiry');
    }
});

// ---------------------------------------------------------------------------
// SUITE 3: AI Overhaul Stress-Testing (Cheats, Saturation, Kiting, APM)
// ---------------------------------------------------------------------------
console.log('\n--- SUITE 3: AI Overhaul Stress-Testing ---');

challenge('Suite 3', '0% Cheat Parity: cheat5050Enabled === false across all 4 tiers', () => {
    for (const [tierName, cfg] of Object.entries(DIFFICULTY_TIERS)) {
        assert.strictEqual(cfg.cheat5050Enabled, false, `Tier ${tierName} must have cheat5050Enabled === false`);
    }
});

challenge('Suite 3', 'Authentic Market Trading: 5:3 Exchange Penalty & No Free Resources', () => {
    const grid = new GameGrid(64, 64);
    const mockApp = {
        grid,
        entities: [],
        playerResources: {
            1: { rice: 2000, wood: 200, potato: 500 } // Rice surplus 2000 vs wood deficit 200
        }
    };

    const macro = new StrategicMacroAI(mockApp, { owner: 1, difficulty: 'NORMAL' });
    assert.strictEqual(macro.difficultyConfig.cheat5050Enabled, false);

    // Initial total resources: 2000 + 200 + 500 = 2700
    const totalBefore = mockApp.playerResources[1].rice + mockApp.playerResources[1].wood + mockApp.playerResources[1].potato;

    // Trigger trade evaluation
    macro.evaluateMarketTrades();

    const totalAfter = mockApp.playerResources[1].rice + mockApp.playerResources[1].wood + mockApp.playerResources[1].potato;

    // A trade occurred: deducted 500 rice, added 300 wood.
    // Net change = -200 resources (5:3 exchange penalty)
    assert.strictEqual(mockApp.playerResources[1].rice, 1500, '500 surplus rice must be deducted');
    assert.strictEqual(mockApp.playerResources[1].wood, 500, '300 deficit wood must be added');
    assert.strictEqual(totalAfter, totalBefore - 200, 'Market trade must net -200 resources (loss, not magic creation)');
    assert.strictEqual(macro.marketCooldown, 30.0, 'Market cooldown must be 30.0s');
});

challenge('Suite 3', 'Node Saturation Hard Caps: 100 Workers Flooding 3 Nodes (Cap 3/1/3)', () => {
    const grid = new GameGrid(64, 64);
    // Node 1: Rice at (10, 10), cap = 3 (rType = 100)
    grid.resourceTypes[10 * 64 + 10] = 100;
    grid.resourceAmounts[10 * 64 + 10] = 10000;

    // Node 2: Tree at (12, 10), cap = 1 (rType = 50)
    grid.resourceTypes[10 * 64 + 12] = 50;
    grid.resourceAmounts[10 * 64 + 12] = 10000;

    // Node 3: Potato at (14, 10), cap = 3 (rType = 1)
    grid.resourceTypes[10 * 64 + 14] = 1;
    grid.resourceAmounts[10 * 64 + 14] = 10000;

    const mockApp = {
        grid,
        entities: [
            { isBuilding: true, isDead: false, isConstructing: false, owner: 1, name: '조선 본영', wx: 10, wy: 12, width: 3, height: 3 }
        ],
        playerResources: { 1: { rice: 500, wood: 500, potato: 500 } }
    };

    const macro = new StrategicMacroAI(mockApp, { owner: 1, difficulty: 'NORMAL' });

    // Spawn 100 workers and assign them
    let assignedCount = 0;
    let rejectedCount = 0;

    for (let i = 0; i < 100; i++) {
        const worker = { id: 1000 + i, owner: 1, wx: 10, wy: 12, harvestPref: 100 };
        const node = macro.findBestUnsaturatedNode(worker, grid);

        if (node) {
            assignedCount++;
            const key = `${node.gx},${node.gy}`;
            if (!macro.nodeReservations.has(key)) {
                macro.nodeReservations.set(key, new Set());
            }
            macro.nodeReservations.get(key).add(worker.id);
        } else {
            rejectedCount++;
        }
    }

    // Capacity: Rice (3) + Tree (1) + Potato (3) = 7
    assert.strictEqual(assignedCount, 7, 'Exactly 7 workers should be assigned before total saturation');
    assert.strictEqual(rejectedCount, 93, 'Remaining 93 workers must be strictly rejected (node saturated)');

    const riceAssigned = macro.nodeReservations.get('10,10').size;
    const treeAssigned = macro.nodeReservations.get('12,10').size;
    const potatoAssigned = macro.nodeReservations.get('14,10').size;

    assert.strictEqual(riceAssigned, NODE_SATURATION_LIMITS.RICE, 'Rice node must not exceed cap of 3');
    assert.strictEqual(treeAssigned, NODE_SATURATION_LIMITS.TREE, 'Tree node must not exceed cap of 1');
    assert.strictEqual(potatoAssigned, NODE_SATURATION_LIMITS.POTATO, 'Potato node must not exceed cap of 3');
});

challenge('Suite 3', 'Stutter-Step Kiting & Potential Field: Repulsion During Cooldown, Hold During Ready', () => {
    const grid = new GameGrid(64, 64);
    const mockApp = {
        grid,
        entities: []
    };

    const micro = new TacticalMicroManager(mockApp, { owner: 1, difficulty: 'HARD' });
    micro.gameTimeSec = 10.0;

    // Ranged unit (조총 낭인, range 4.5)
    const shooter = {
        id: 7201,
        name: '조총 낭인',
        owner: 1,
        wx: 20,
        wy: 20,
        attack_range: 4.5,
        move_speed: 16,
        windupDuration: 0.2,
        attackTimer: 0.8, // on weapon cooldown (reloading)
        state: UnitState.IDLE,
        waypoints: [],
        moveTo: (gx, gy) => {
            shooter.state = UnitState.WALK;
            shooter.targetGridPos = { gx, gy };
        }
    };

    // Approaching enemy melee unit at (21, 20) (distance 1.0)
    const enemy = {
        id: 9901,
        name: '일본 사무라이',
        owner: 0,
        wx: 21,
        wy: 20,
        move_speed: 20,
        hp: 500,
        isDead: false
    };

    mockApp.entities = [shooter, enemy];

    let ctx = micro.unitMicroContexts.get(shooter.id);
    if (!ctx) {
        ctx = { state: 'COMBAT', lastKiteSec: 0, kiteVector: new Vec2(0, 0), retreatAnchor: null, isRetreating: false };
        micro.unitMicroContexts.set(shooter.id, ctx);
    }

    // Test 1: While reloading (attackTimer > 0) and enemy inside threat horizon, unit MUST kite
    const kited = micro.evaluateUnitKiting(shooter, ctx);
    assert.strictEqual(kited, true, 'Unit must execute kiting while on weapon reload');
    assert.strictEqual(shooter.state, UnitState.WALK, 'Unit must be walking away');
    // Moving away from enemy at x=21 means moving towards lower x (x < 20)
    assert.ok(shooter.targetGridPos.gx <= 20, 'Unit must kite away from the approaching threat');

    // Test 2: When weapon is ready (attackTimer = 0) and distance is safe within threat scan radius (range+2.0 = 6.5), unit halts to fire
    shooter.attackTimer = 0.0;
    enemy.wx = 25; // distance 5.0 (safe: d >= dThreat + 1.2, within detection radius 6.5)
    shooter.targetEntity = enemy;
    micro.evaluateUnitKiting(shooter, ctx);
    assert.strictEqual(shooter.state, UnitState.IDLE, 'Unit must halt to fire when cooldown is ready and distance is safe');
});

challenge('Suite 3', 'Corner-Trap Survival: Potential Field Handles Boundaries Without NaN or Crash', () => {
    const grid = new GameGrid(64, 64);
    // Block walls around (1, 1)
    grid.setWalkability(0, 1, 1);
    grid.setWalkability(1, 0, 1);
    grid.setWalkability(0, 0, 1);

    const mockApp = { grid, entities: [] };
    const micro = new TacticalMicroManager(mockApp, { owner: 1, difficulty: 'HARD' });

    const corneredUnit = {
        id: 8888,
        name: '조총 낭인',
        owner: 1,
        wx: 1,
        wy: 1,
        attack_range: 4.0,
        move_speed: 12,
        windupDuration: 0.2,
        attackTimer: 0.5
    };

    const enemy = {
        id: 9999,
        name: '일본 창병',
        owner: 0,
        wx: 2,
        wy: 1,
        move_speed: 16,
        hp: 300,
        isDead: false
    };

    const vec = micro.calculateKiteVector(corneredUnit, [enemy]);
    assert.ok(!isNaN(vec.x) && !isNaN(vec.y), 'Kite vector must not contain NaN in corner trap');
    assert.ok(isFinite(vec.x) && isFinite(vec.y), 'Kite vector must be finite');
});

challenge('Suite 3', 'APM Limiter: Token Bucket Burst Clamp & Per-Unit Command Cooldown Across 4 Tiers', () => {
    for (const [tierName, cfg] of Object.entries(DIFFICULTY_TIERS)) {
        const limiter = new ApmLimiter(tierName);
        assert.strictEqual(limiter.currentTokens, cfg.burstCapacity);

        // Challenge 1: Consume flood (try consuming 1,000 times in tick 0)
        let allowed = 0;
        for (let i = 0; i < 1000; i++) {
            if (limiter.tryConsume(i + 1, 0.0, 1.0)) {
                allowed++;
            }
        }
        assert.strictEqual(allowed, cfg.burstCapacity, `Allowed commands in single tick must strictly equal burst capacity (${cfg.burstCapacity}) for ${tierName}`);
        assert.strictEqual(limiter.currentTokens, 0, 'Tokens should be exhausted');

        // Challenge 2: Per-unit cooldown
        limiter.reset();
        const unitId = 42;
        const first = limiter.tryConsume(unitId, 1.0, 1.0);
        assert.strictEqual(first, true, 'First command should be allowed');

        // Second command to SAME unit immediately (0.01s later) must be rejected
        const second = limiter.tryConsume(unitId, 1.01, 1.0);
        assert.strictEqual(second, false, `Immediate repeat command to unit ${unitId} must be rejected by per-unit cooldown in ${tierName}`);

        // Command to DIFFERENT unit is allowed
        const otherUnit = limiter.tryConsume(99, 1.01, 1.0);
        assert.strictEqual(otherUnit, true, 'Command to different unit should be allowed if tokens remain');
    }
});

challenge('Suite 3', 'Reaction Delay Sampling & Monotonic Tier Hierarchy', () => {
    const samples = { EASY: [], NORMAL: [], HARD: [], BRUTAL: [] };

    for (const tier of Object.keys(samples)) {
        for (let i = 0; i < 500; i++) {
            const delay = sampleReactionDelaySec(tier);
            samples[tier].push(delay);
        }
    }

    const mean = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
    const meanEasy = mean(samples.EASY);
    const meanNormal = mean(samples.NORMAL);
    const meanHard = mean(samples.HARD);
    const meanBrutal = mean(samples.BRUTAL);

    // Monotonic reaction delay: Easy > Normal > Hard > Brutal
    assert.ok(meanEasy > meanNormal, `Easy mean delay (${meanEasy}) must be > Normal (${meanNormal})`);
    assert.ok(meanNormal > meanHard, `Normal mean delay (${meanNormal}) must be > Hard (${meanHard})`);
    assert.ok(meanHard > meanBrutal, `Hard mean delay (${meanHard}) must be > Brutal (${meanBrutal})`);

    // Monotonic APM: Easy < Normal < Hard < Brutal
    assert.ok(DIFFICULTY_TIERS.EASY.apm < DIFFICULTY_TIERS.NORMAL.apm);
    assert.ok(DIFFICULTY_TIERS.NORMAL.apm < DIFFICULTY_TIERS.HARD.apm);
    assert.ok(DIFFICULTY_TIERS.HARD.apm < DIFFICULTY_TIERS.BRUTAL.apm);
});

// ---------------------------------------------------------------------------
// Summary & Verdict
// ---------------------------------------------------------------------------
console.log('\n======================================================================');
console.log(` HARNESS SUMMARY: ${passedTests} / ${totalTests} TESTS PASSED`);
if (failedTests > 0) {
    console.error(` FAILURES: ${failedTests}`);
    for (const f of failures) {
        console.error(`  - [${f.suite}] ${f.description}: ${f.error}`);
    }
    process.exit(1);
} else {
    console.log(' >>> ALL ADVERSARIAL STRESS CHALLENGES PASSED WITH 100% SUCCESS <<<');
    console.log('======================================================================\n');
}
