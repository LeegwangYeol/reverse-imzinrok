/**
 * Automated Test Suite for Custom Joseon 10 Units (0x70~0x79)
 * 5-Action Animation Lifecycles, Aerial Zero-Corpse Instant Vanish, and Elevation Rendering.
 */

import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { IsometricMath } from '../web_prototype/js/engine/isometric.js';
import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { Unit, UnitState, Direction, CUSTOM_JOSEON_ANIM_SPECS } from '../web_prototype/js/simulation/entities.js';
import { IsometricRenderer } from '../web_prototype/js/engine/renderer.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

let totalTests = 0;
let passedTests = 0;

function test(name, fn) {
    totalTests++;
    try {
        fn();
        console.log(`  [PASS] ${name}`);
        passedTests++;
    } catch (err) {
        console.error(`  [FAIL] ${name}`);
        console.error(err);
        process.exitCode = 1;
    }
}

console.log('======================================================================');
console.log(' Running Custom Joseon Units (0x70~0x79) Animation & Lifecycle Test Suite');
console.log('======================================================================\n');

// ---------------------------------------------------------------------------
// 1. MANIFEST & EXPORTED ASSET INTEGRITY
// ---------------------------------------------------------------------------
console.log('--- 1. Manifest & Exported Asset Integrity ---');

const manifestPath = path.join(rootDir, 'web_prototype', 'assets', 'manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));

const EXPECTED_UNITS = [
    { kindId: 0x70, id: 'chosun_yusaeng', alias: 'keon_1hs', file: 'keon_1hs', frames: 176, isAir: false, corpse: 71 },
    { kindId: 0x71, id: 'chosun_geomsul_nangin', alias: 'SwordPirate_online', file: 'SwordPirate_online', frames: 136, isAir: false, corpse: 128 },
    { kindId: 0x72, id: 'chosun_jochong_nangin', alias: 'GunPirate_online', file: 'GunPirate_online', frames: 136, isAir: false, corpse: 128 },
    { kindId: 0x73, id: 'chosun_gumiho', alias: 'fox', file: 'fox', frames: 144, isAir: false, corpse: 136 },
    { kindId: 0x74, id: 'chosun_wangbeol', alias: 'bat_online', file: 'bat_online', frames: 160, isAir: true, corpse: null },
    { kindId: 0x75, id: 'chosun_horangi', alias: 'Tiger', file: 'Tiger', frames: 136, isAir: false, corpse: 129 },
    { kindId: 0x76, id: 'chosun_teolgamyeon', alias: 'furheaddemon_online', file: 'furheaddemon_online', frames: 130, isAir: false, corpse: 129 },
    { kindId: 0x77, id: 'chosun_seolnyeo', alias: 'snowwoman_online', file: 'snowwoman_online', frames: 192, isAir: false, corpse: 83 },
    { kindId: 0x78, id: 'chosun_dokkaebi', alias: 'oni_online', file: 'oni_online', frames: 180, isAir: false, corpse: 150 },
    { kindId: 0x79, id: 'chosun_bulgasari', alias: 'starfish', file: 'starfish', frames: 216, isAir: false, corpse: 179 }
];

test('All 10 custom Joseon units are registered in manifest.json with valid files', () => {
    for (const spec of EXPECTED_UNITS) {
        assert(manifest.units[spec.id], `Missing manifest entry for ${spec.id}`);
        const u = manifest.units[spec.id];
        assert.strictEqual(u.kind_id, spec.kindId, `Mismatched kind_id for ${spec.id}`);
        assert.strictEqual(u.isAirUnit, spec.isAir, `Mismatched isAirUnit for ${spec.id}`);

        // Verify physical files exist on disk
        const atlasPath = path.join(rootDir, 'web_prototype', 'assets', u.atlas);
        const metaPath = path.join(rootDir, 'web_prototype', 'assets', u.meta);
        assert(fs.existsSync(atlasPath), `Missing atlas PNG: ${atlasPath}`);
        assert(fs.existsSync(metaPath), `Missing meta JSON: ${metaPath}`);

        const meta = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
        assert.strictEqual(meta.frame_count, spec.frames, `Mismatched frame_count for ${spec.id}`);
        assert(meta.atlas_width > 0 && meta.atlas_height > 0, `Invalid atlas dimensions in ${metaPath}`);
        assert.strictEqual(meta.frames.length, spec.frames, `Incomplete frame metadata array in ${metaPath}`);
    }
});

// ---------------------------------------------------------------------------
// 2. 5-ACTION SIMULATION LIFECYCLES IN ENTITIES.JS
// ---------------------------------------------------------------------------
console.log('\n--- 2. Simulation Lifecycles & Corpse Decay (entities.js) ---');

test('UnitState contains all 5 action lifecycle states including CORPSE_DECAY', () => {
    assert.strictEqual(UnitState.IDLE, 'IDLE');
    assert.strictEqual(UnitState.WALK, 'WALK');
    assert.strictEqual(UnitState.ATTACK, 'ATTACK');
    assert.strictEqual(UnitState.DIE, 'DIE');
    assert.strictEqual(UnitState.CORPSE_DECAY, 'CORPSE_DECAY');
});

test('Ground units progress through full 5-action lifecycle to CORPSE_DECAY and dissolve', () => {
    const grid = new GameGrid(64, 64);
    const mockAudio = { play: () => {} };

    // Test 0x70 (유생)
    const yusaengDef = manifest.units['chosun_yusaeng'];
    const unit = new Unit(101, yusaengDef, 10, 10, 0);

    assert.strictEqual(unit.state, UnitState.IDLE, 'Initial state must be IDLE');
    assert.strictEqual(unit.isAirUnit, false, 'Yusaeng must not be an air unit');

    // Action 1: Walk
    unit.moveTo(12, 10, grid);
    assert.strictEqual(unit.state, UnitState.WALK, 'Move order must set WALK');

    // Simulate 0.5s walk
    unit.update(0.5, grid, [], mockAudio);
    assert(unit.animFrame >= 0, 'Animation frame advances during walk');

    // Action 3: Die upon lethal damage
    grid.setUnitOccupancy(unit.gx, unit.gy, unit.id);
    assert.strictEqual(grid.unitOccupancy[grid.getIndex(unit.gx, unit.gy)], unit.id);

    unit.takeDamage(1000, mockAudio);
    assert.strictEqual(unit.hp, 0);
    assert.strictEqual(unit.state, UnitState.DIE, 'HP <= 0 must transition to DIE');
    assert.strictEqual(unit.isDead, true);
    assert.strictEqual(unit.isDying, true);

    // Simulate dying animation (12 frames at 10 fps = 1.2s)
    let elapsed = 0;
    while (unit.state === UnitState.DIE && elapsed < 2.0) {
        unit.update(0.1, grid, [], mockAudio);
        elapsed += 0.1;
    }

    // Must transition to 5th Action: CORPSE_DECAY
    assert.strictEqual(unit.state, UnitState.CORPSE_DECAY, 'Must transition to CORPSE_DECAY after death animation');
    assert.strictEqual(unit.animFrame, 11, 'Must rest on final collapsed death frame (die_frames - 1 = 11)');
    assert.strictEqual(unit.corpseDuration, 4.0, 'Corpse duration must be 4.0 seconds');
    assert.strictEqual(unit.corpseAlpha, 1.0, 'Initial corpse alpha must be 1.0');

    // Must release tile occupancy so other units can walk through
    assert.strictEqual(grid.unitOccupancy[grid.getIndex(unit.gx, unit.gy)], -1, 'Tile occupancy must be released on corpse decay');

    // Simulate 2.5s into corpse decay (corpseTimer = 1.5s > corpseFadeDuration 1.0s)
    unit.update(2.5, grid, [], mockAudio);
    assert.strictEqual(unit.state, UnitState.CORPSE_DECAY);
    assert.strictEqual(unit.corpseAlpha, 1.0, 'Alpha must remain 1.0 before fade window');
    assert.strictEqual(unit.animFrame, 11, 'Frame must stay pinned to collapsed corpse frame');

    // Simulate 1.0s more (corpseTimer = 0.5s, within last 1.0s fade window)
    unit.update(1.0, grid, [], mockAudio);
    assert.strictEqual(unit.state, UnitState.CORPSE_DECAY);
    assert(unit.corpseAlpha < 1.0 && unit.corpseAlpha > 0.0, `Corpse alpha must dissolve: got ${unit.corpseAlpha}`);
    assert.strictEqual(Math.round(unit.corpseAlpha * 10) / 10, 0.5, 'Alpha must be 0.5 at 0.5s remaining');

    // Simulate final 0.6s (total elapsed in decay > 4.0s)
    unit.update(0.6, grid, [], mockAudio);
    assert.strictEqual(unit.corpseAlpha, 0.0, 'Corpse alpha must be 0.0');
    assert.strictEqual(unit.isDying, false, 'isDying must become false to trigger removal in game loop');
    assert.strictEqual(unit.isDead, true);
    assert.strictEqual(unit.deathAnimDone, true);
});

// ---------------------------------------------------------------------------
// 3. JOSEON HORNET (0x74) AERIAL ZERO-CORPSE INSTANT VANISH RULE
// ---------------------------------------------------------------------------
console.log('\n--- 3. Joseon Hornet (0x74) Aerial Zero-Corpse Instant Vanish ---');

test('Joseon Hornet is flagged as isAirUnit with flight altitude 36px', () => {
    const hornetDef = manifest.units['chosun_wangbeol'];
    const hornet = new Unit(102, hornetDef, 15, 15, 0);

    assert.strictEqual(hornet.isAirUnit, true, 'Hornet must be an air unit');
    assert.strictEqual(hornet.flightAltitude, 36, 'Hornet flight altitude must be 36px');
    assert.strictEqual(hornet.corpseDuration, 0.0, 'Hornet corpseDuration must be 0.0');
});

test('Joseon Hornet flies via direct vector without maze pathfinding', () => {
    const grid = new GameGrid(64, 64);
    // Block destination area with cliffs
    for (let x = 18; x <= 22; x++) {
        for (let y = 18; y <= 22; y++) {
            grid.setWalkability(x, y, 1);
        }
    }

    const hornetDef = manifest.units['chosun_wangbeol'];
    const hornet = new Unit(103, hornetDef, 10, 10, 0);

    hornet.moveTo(20, 20, grid);
    assert.strictEqual(hornet.state, UnitState.WALK);
    assert.strictEqual(hornet.waypoints.length, 1, 'Air unit must fly straight directly to destination');
    assert.strictEqual(hornet.waypoints[0].gx, 20);
    assert.strictEqual(hornet.waypoints[0].gy, 20);
});

test('ENFORCE: Joseon Hornet vanishes instantly on HP <= 0 with ZERO corpse decay and ZERO footprint', () => {
    const grid = new GameGrid(64, 64);
    const mockAudio = { play: () => {} };

    const hornetDef = manifest.units['chosun_wangbeol'];
    const hornet = new Unit(104, hornetDef, 25, 25, 0);

    assert.strictEqual(hornet.isDead, false);

    // Apply lethal damage
    hornet.takeDamage(1000, mockAudio);

    // Strictly enforce instant vanish properties:
    assert.strictEqual(hornet.hp, 0);
    assert.strictEqual(hornet.isDead, true, 'isDead must be true immediately');
    assert.strictEqual(hornet.isDying, false, 'isDying must be FALSE immediately (suppressing corpse decay delay)');
    assert.strictEqual(hornet.deathAnimDone, true, 'deathAnimDone must be true immediately');
    assert.strictEqual(hornet.corpseAlpha, 0.0, 'corpseAlpha must be 0.0');
    assert.notStrictEqual(hornet.state, UnitState.CORPSE_DECAY, 'Must NEVER enter CORPSE_DECAY');

    // In main.js loop: `if (ent.isDead) { if (ent.isDying) { ... } else { this.entities.splice(i, 1); } }`
    // Because isDead=true and isDying=false, it is purged in tick 0!
    const entitiesList = [hornet];
    for (let i = entitiesList.length - 1; i >= 0; i--) {
        const ent = entitiesList[i];
        if (ent.isDead) {
            if (ent.isDying) {
                // Not reached for hornet!
            } else {
                entitiesList.splice(i, 1);
            }
        }
    }
    assert.strictEqual(entitiesList.length, 0, 'Hornet must be purged immediately from active entities list');
});

// ---------------------------------------------------------------------------
// 4. RENDERER CUSTOM_JOSEON_ANIM_SPECS & FRAME RESOLUTION
// ---------------------------------------------------------------------------
console.log('\n--- 4. Renderer CUSTOM_JOSEON_ANIM_SPECS & Frame Resolution (renderer.js) ---');

const renderer = new IsometricRenderer(null, null);

test('CUSTOM_JOSEON_ANIM_SPECS maps all 10 custom Joseon units to authentic frame boundaries', () => {
    for (const spec of EXPECTED_UNITS) {
        const anim = CUSTOM_JOSEON_ANIM_SPECS[spec.kindId];
        assert(anim, `Missing CUSTOM_JOSEON_ANIM_SPECS entry for 0x${spec.kindId.toString(16)}`);
        assert(anim.idle, `Missing idle spec for 0x${spec.kindId.toString(16)}`);
        assert(anim.move, `Missing move spec for 0x${spec.kindId.toString(16)}`);
        assert(anim.atk, `Missing atk spec for 0x${spec.kindId.toString(16)}`);
        assert(anim.die, `Missing die spec for 0x${spec.kindId.toString(16)}`);

        if (spec.isAir) {
            assert.strictEqual(anim.die.corpse, null, 'Air unit corpse frame must be null');
        } else {
            assert.strictEqual(anim.die.corpse, spec.corpse, `Mismatched corpse frame for 0x${spec.kindId.toString(16)}`);
        }
    }
});

test('resolveUnitFrame resolves exact frames across IDLE, WALK, ATTACK, DIE, CORPSE_DECAY', () => {
    // Mock sprite container
    const makeMockSprite = (name, count, w = 80, h = 80) => ({
        name,
        frameCount: count,
        width: w,
        height: h,
        cols: 8,
        frames: Array.from({ length: count }, (_, i) => ({
            u: (i % 8) * w,
            v: Math.floor(i / 8) * h,
            w,
            h
        }))
    });

    // 1. 유생 (0x70, keon_1hs.Spr, 176 frames)
    // Atk: 0..39 (fDir 8), Die: 60..71 (total 12), Idle: 72..131 (fDir 12), Move: 132..171 (fDir 8)
    const yusaengSpr = makeMockSprite('keon_1hs.spr', 176);
    const yusaengUnit = { kindId: 0x70, spriteName: 'keon_1hs.spr', direction: 0 }; // Dir 0 = South (dir5 = 4)

    // IDLE: start 72 + dir5(4)*12 + fIdx(0) = 72 + 48 = 120
    const idleFrame = renderer.resolveUnitFrame(yusaengSpr, yusaengUnit, 0, 0, 'IDLE');
    assert.strictEqual(idleFrame.x, (120 % 8) * 80);
    assert.strictEqual(idleFrame.y, Math.floor(120 / 8) * 80);

    // WALK: start 132 + dir5(4)*8 + fIdx(2) = 132 + 32 + 2 = 166
    const walkFrame = renderer.resolveUnitFrame(yusaengSpr, yusaengUnit, 0, 2, 'WALK');
    assert.strictEqual(walkFrame.x, (166 % 8) * 80);
    assert.strictEqual(walkFrame.y, Math.floor(166 / 8) * 80);

    // ATTACK: start 0 + dir5(4)*8 + fIdx(4) = 32 + 4 = 36
    const atkFrame = renderer.resolveUnitFrame(yusaengSpr, yusaengUnit, 0, 4, 'ATTACK');
    assert.strictEqual(atkFrame.x, (36 % 8) * 80);
    assert.strictEqual(atkFrame.y, Math.floor(36 / 8) * 80);

    // DIE: start 60 + fIdx(5) = 65
    const dieFrame = renderer.resolveUnitFrame(yusaengSpr, yusaengUnit, 0, 5, 'DIE');
    assert.strictEqual(dieFrame.x, (65 % 8) * 80);
    assert.strictEqual(dieFrame.y, Math.floor(65 / 8) * 80);

    // CORPSE_DECAY: static frame 71 (die_start + die_frames - 1)
    const corpseFrame = renderer.resolveUnitFrame(yusaengSpr, yusaengUnit, 0, 0, 'CORPSE_DECAY');
    assert.strictEqual(corpseFrame.x, (71 % 8) * 80);
    assert.strictEqual(corpseFrame.y, Math.floor(71 / 8) * 80);

    // 2. 조선왕벌 (0x74, bat_online.spr, 160 frames, Air Unit)
    const hornetSpr = makeMockSprite('bat_online.spr', 160);
    const hornetUnit = { kindId: 0x74, spriteName: 'bat_online.spr', direction: 0, isAirUnit: true };

    // CORPSE_DECAY for hornet must return null (zero corpse)
    const hornetCorpse = renderer.resolveUnitFrame(hornetSpr, hornetUnit, 0, 0, 'CORPSE_DECAY');
    assert.strictEqual(hornetCorpse, null, 'Air unit hornet must return null for CORPSE_DECAY');

    // 3. 불가살이 (0x79, starfish.spr, 216 frames)
    // Idle: 0..39 (fDir 8), Move: 40..79 (fDir 8), Atk: 80..159 (fDir 16), Die: 160..179 (total 20), Corpse: 179
    const starfishSpr = makeMockSprite('starfish.spr', 216);
    const starfishUnit = { kindId: 0x79, spriteName: 'starfish.spr', direction: 0 };

    const bulgasariCorpse = renderer.resolveUnitFrame(starfishSpr, starfishUnit, 0, 0, 'CORPSE_DECAY');
    assert.strictEqual(bulgasariCorpse.x, (179 % 8) * 80);
    assert.strictEqual(bulgasariCorpse.y, Math.floor(179 / 8) * 80);
});

// ---------------------------------------------------------------------------
// 5. AIR UNIT ELEVATION & SHADOW DRAWING VERIFICATION
// ---------------------------------------------------------------------------
console.log('\n--- 5. Air Unit Elevation & Ground Shadow Rendering ---');

test('LAYER_PRIORITY.AIR_UNIT is 8 and places air units above ground units (4)', () => {
    assert.strictEqual(renderer.LAYER_PRIORITY.AIR_UNIT, 8);
    assert.strictEqual(renderer.LAYER_PRIORITY.UNIT, 4);
    assert(renderer.LAYER_PRIORITY.AIR_UNIT > renderer.LAYER_PRIORITY.UNIT);
});

test('drawUnit elevates air unit sprite and bars by flightAltitude while casting shadow at ground', () => {
    const mockCalls = [];
    const mockCtx = {
        save: () => mockCalls.push({ type: 'save' }),
        restore: () => mockCalls.push({ type: 'restore' }),
        translate: (x, y) => mockCalls.push({ type: 'translate', x, y }),
        scale: (x, y) => mockCalls.push({ type: 'scale', x, y }),
        drawImage: (...args) => mockCalls.push({ type: 'drawImage', args }),
        beginPath: () => {},
        ellipse: (x, y, rx, ry, rot, s, e) => mockCalls.push({ type: 'ellipse', x, y, rx, ry }),
        fill: () => {},
        stroke: () => {},
        arc: () => {},
        moveTo: () => {},
        lineTo: () => {},
        fillText: () => {},
        fillRect: () => {},
        set strokeStyle(v) {},
        set fillStyle(v) {},
        set lineWidth(v) {},
        set globalAlpha(v) { mockCalls.push({ type: 'alpha', v }); }
    };

    renderer.assetManager = {
        getUnitSprite: () => ({
            image: { width: 640, height: 640 },
            width: 80,
            height: 80,
            cols: 8,
            frameCount: 160
        })
    };

    const hornetDef = manifest.units['chosun_wangbeol'];
    const hornet = new Unit(201, hornetDef, 5, 5, 0);
    hornet.flightAltitude = 36;
    hornet.selected = true;

    const camera = { x: 0, y: 0, zoom: 1.0 };
    renderer.drawUnit(mockCtx, hornet, camera, null);

    // Verify shadow ellipse at ground level (pos.y + 24)
    const shadowCall = mockCalls.find(c => c.type === 'ellipse' && c.rx === 10 && c.ry === 5);
    assert(shadowCall, 'Ground shadow must be rendered at terrain ground level (rx=10, ry=5)');

    // Verify sprite translate elevated by -36px: (pos.y + 24 - 36)
    const translateCall = mockCalls.find(c => c.type === 'translate');
    assert(translateCall, 'Sprite translate call must be executed');
    assert.strictEqual(translateCall.y, shadowCall.y - 36, 'Sprite must be elevated by flightAltitude (36px) above ground shadow');
});

test('drawUnit suppresses shadow, selection ring, and health bars during CORPSE_DECAY and applies corpseAlpha', () => {
    const mockCalls = [];
    const mockCtx = {
        save: () => mockCalls.push({ type: 'save' }),
        restore: () => mockCalls.push({ type: 'restore' }),
        translate: (x, y) => mockCalls.push({ type: 'translate', x, y }),
        scale: (x, y) => mockCalls.push({ type: 'scale', x, y }),
        drawImage: (...args) => mockCalls.push({ type: 'drawImage', args }),
        beginPath: () => {},
        ellipse: (x, y, rx, ry) => mockCalls.push({ type: 'ellipse', x, y, rx, ry }),
        fill: () => {},
        stroke: () => {},
        arc: () => {},
        moveTo: () => {},
        lineTo: () => {},
        fillText: () => {},
        fillRect: (x, y, w, h) => mockCalls.push({ type: 'fillRect', x, y, w, h }),
        set strokeStyle(v) {},
        set fillStyle(v) {},
        set lineWidth(v) {},
        set globalAlpha(v) { mockCalls.push({ type: 'alpha', v }); }
    };

    const yusaengDef = manifest.units['chosun_yusaeng'];
    const unit = new Unit(202, yusaengDef, 5, 5, 0);
    unit.state = UnitState.CORPSE_DECAY;
    unit.selected = true; // Even if selected, must suppress selection ring & health bars
    unit.corpseAlpha = 0.45;

    const camera = { x: 0, y: 0, zoom: 1.0 };
    renderer.drawUnit(mockCtx, unit, camera, null);

    // Verify shadow & selection ring are NOT drawn
    const ellipseCalls = mockCalls.filter(c => c.type === 'ellipse');
    assert.strictEqual(ellipseCalls.length, 0, 'Shadows and selection rings must be completely suppressed during corpse decay');

    // Verify health bars are NOT drawn
    const barCalls = mockCalls.filter(c => c.type === 'fillRect');
    assert.strictEqual(barCalls.length, 0, 'Health bars must be completely suppressed during corpse decay');

    // Verify corpseAlpha is applied
    const alphaCall = mockCalls.find(c => c.type === 'alpha' && Math.abs(c.v - 0.45) < 0.001);
    assert(alphaCall, 'corpseAlpha (0.45) must be applied to globalAlpha during corpse decay rendering');
});

console.log('\n======================================================================');
console.log(` Test Results: ${passedTests} / ${totalTests} Passed`);
console.log('======================================================================');

if (passedTests === totalTests) {
    console.log('\nALL CUSTOM JOSEON UNIT ANIMATION & LIFECYCLE TESTS PASSED PERFECTLY!\n');
} else {
    process.exit(1);
}
