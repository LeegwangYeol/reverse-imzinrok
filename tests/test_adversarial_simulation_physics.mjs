/**
 * Empirical Adversarial Challenge & Stress-Test Suite:
 * Simulation Engine, A* Pathfinding, Dynamic Move Speed Physics,
 * Entity Scaling & Combat Elevation Mechanics.
 *
 * Invoked by: challenger_simulation_physics
 * Working Directory: C:\src\reverse-imzinrok
 */

import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { PathFinder, BinaryHeap } from '../web_prototype/js/simulation/pathfinding.js';
import { Unit, Building, Projectile, UnitState, Direction } from '../web_prototype/js/simulation/entities.js';
import { CombatSystem } from '../web_prototype/js/simulation/combat.js';
import { IsometricMath } from '../web_prototype/js/engine/isometric.js';

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const findings = [];

function test(name, fn) {
    totalTests++;
    try {
        fn();
        passedTests++;
        console.log(`  [PASS] ${name}`);
    } catch (err) {
        failedTests++;
        console.error(`  [FAIL] ${name}`);
        console.error(`         ${err.message}`);
        findings.push({ name, error: err.message });
    }
}

console.log('======================================================================');
console.log(' EMPIRICAL ADVERSARIAL STRESS-TEST SUITE: SIMULATION & PHYSICS');
console.log('======================================================================');

// ===========================================================================
// SUITE 1: COMPLEX MAZE & LABYRINTH GRIDS (ADVERSARIAL PATHFINDING)
// ===========================================================================
console.log('\n--- SUITE 1: Complex Maze & Labyrinth Pathfinding ---');

test('A* solves deep U-shaped horseshoe cul-de-sac dead end', () => {
    const grid = new GameGrid(40, 40);

    // Build a deep U-shaped trap:
    // Left wall: x=10, y=10..30
    // Bottom wall: y=30, x=10..30
    // Right wall: x=30, y=10..30
    // Start inside at (20, 25), target outside at (20, 35) (directly below the bottom wall)
    for (let y = 10; y <= 30; y++) {
        grid.setWalkability(10, y, 1);
        grid.setWalkability(30, y, 1);
    }
    for (let x = 10; x <= 30; x++) {
        grid.setWalkability(x, 30, 1);
    }

    const startGx = 20, startGy = 25;
    const targetGx = 20, targetGy = 35;

    const path = PathFinder.findPath(grid, startGx, startGy, targetGx, targetGy, { smooth: false });

    assert.ok(path.length > 0, 'Path should be found by escaping out the top of the U-trap');
    const finalPt = path[path.length - 1];
    assert.strictEqual(finalPt.gx, targetGx);
    assert.strictEqual(finalPt.gy, targetGy);

    // Verify the path exited through the open top (y < 10) before moving to y=35
    let reachedTopExit = false;
    for (const pt of path) {
        if (pt.gy < 10) reachedTopExit = true;
        assert.ok(grid.isWalkable(pt.gx, pt.gy), `Path walked through obstacle at (${pt.gx}, ${pt.gy})`);
    }
    assert.ok(reachedTopExit, 'Path must exit via open top (y < 10)');
});

test('A* navigates a tight 1-tile wide serpentine labyrinth', () => {
    const grid = new GameGrid(30, 30);

    // Create a 5-layer horizontal serpentine maze between x=5 and x=25
    // Wall 1: y=5, x=5..23 (gap at x=24..25)
    // Wall 2: y=9, x=7..25 (gap at x=5..6)
    // Wall 3: y=13, x=5..23 (gap at x=24..25)
    // Wall 4: y=17, x=7..25 (gap at x=5..6)
    for (let x = 5; x <= 23; x++) grid.setWalkability(x, 5, 1);
    for (let x = 7; x <= 25; x++) grid.setWalkability(x, 9, 1);
    for (let x = 5; x <= 23; x++) grid.setWalkability(x, 13, 1);
    for (let x = 7; x <= 25; x++) grid.setWalkability(x, 17, 1);

    const path = PathFinder.findPath(grid, 5, 2, 5, 20, { smooth: false });

    assert.ok(path.length > 0, 'Path through serpentine labyrinth should exist');
    assert.strictEqual(path[path.length - 1].gx, 5);
    assert.strictEqual(path[path.length - 1].gy, 20);

    for (const pt of path) {
        assert.ok(grid.isWalkable(pt.gx, pt.gy), `Stepped on wall at (${pt.gx}, ${pt.gy})`);
    }
});

test('Unreachable completely walled-off target terminates within node budget', () => {
    const grid = new GameGrid(50, 50);

    // Create an impenetrable sealed fortress enclosing (25, 25)
    for (let x = 20; x <= 30; x++) {
        for (let y = 20; y <= 30; y++) {
            if (x === 20 || x === 30 || y === 20 || y === 30) {
                grid.setWalkability(x, y, 1);
            }
        }
    }

    const t0 = performance.now();
    const path = PathFinder.findPath(grid, 5, 5, 25, 25, { maxSearchNodes: 1500 });
    const elapsed = performance.now() - t0;

    // Because (25, 25) is surrounded by a sealed wall with distance > 4 tiles to any opening,
    // findNearestWalkable will pick an interior walkable tile (e.g. 24, 25) which is also unreachable!
    // A* must exhaust search budget and return [] without infinite loop or excessive latency (< 200ms)
    assert.ok(elapsed < 200, `Search took too long (${elapsed.toFixed(1)}ms)`);
    assert.strictEqual(path.length, 0, 'Must return empty path for unreachable sealed target');
});

test('Extreme boundaries and out-of-bounds coordinates safety', () => {
    const grid = new GameGrid(180, 180);

    // Extreme corners
    const pathCorners = PathFinder.findPath(grid, 0, 0, 179, 179, { maxSearchNodes: 500 });
    assert.ok(Array.isArray(pathCorners));

    // Clamping out-of-bounds inputs: (-50, -50) to (500, 500)
    const pathOOB = PathFinder.findPath(grid, -50, -50, 500, 500, { maxSearchNodes: 100 });
    assert.ok(Array.isArray(pathOOB));

    // start == target
    const pathSame = PathFinder.findPath(grid, 42, 42, 42, 42);
    assert.deepStrictEqual(pathSame, [], 'Zero-length path when start equals target');
});

test('Dynamic obstacle mutation: unit circumvents newly placed obstacle', () => {
    const grid = new GameGrid(30, 30);
    const unit = new Unit(1, { move_speed: 12 }, 5, 5);

    // Issue initial order across clear terrain
    unit.moveTo(25, 5, grid, false);
    assert.ok(unit.waypoints.length > 0);

    // Place an obstacle directly in the unit's path at x=15
    for (let y = 0; y <= 10; y++) {
        grid.setWalkability(15, y, 1);
    }

    // Re-issue move command to target (25, 5)
    unit.moveTo(25, 5, grid, false);

    assert.ok(unit.waypoints.length > 0, 'New path around obstacle must be found');
    for (const pt of unit.waypoints) {
        assert.ok(grid.isWalkable(pt.gx, pt.gy), `New path stepped on obstacle at (${pt.gx}, ${pt.gy})`);
    }
});

// ===========================================================================
// SUITE 2: DIAGONAL CORNER CUTTING & CLIFF CORNER PASSAGE
// ===========================================================================
console.log('\n--- SUITE 2: Diagonal Corner Cutting & Cliff Passage ---');

test('Diagonal walkability pinch: disallows stepping diagonally between touching obstacle corners', () => {
    const grid = new GameGrid(20, 20);

    // Pinch 1: Obstacles at (5, 5) and (6, 6)
    grid.setWalkability(5, 5, 1);
    grid.setWalkability(6, 6, 1);

    const path1 = PathFinder.findPath(grid, 5, 6, 6, 5, { smooth: false });
    assert.ok(path1.length > 0);
    for (let i = 0; i < path1.length - 1; i++) {
        const cur = path1[i], next = path1[i + 1];
        const isCut = (cur.gx === 5 && cur.gy === 6 && next.gx === 6 && next.gy === 5) ||
                      (cur.gx === 6 && cur.gy === 5 && next.gx === 5 && next.gy === 6);
        assert.strictEqual(isCut, false, 'A* must not cut through (5,5)-(6,6) obstacle pinch');
    }

    // Pinch 2: Inverted obstacles at (10, 11) and (11, 10)
    grid.setWalkability(10, 11, 1);
    grid.setWalkability(11, 10, 1);

    const path2 = PathFinder.findPath(grid, 10, 10, 11, 11, { smooth: false });
    assert.ok(path2.length > 0);
    for (let i = 0; i < path2.length - 1; i++) {
        const cur = path2[i], next = path2[i + 1];
        const isCut = (cur.gx === 10 && cur.gy === 10 && next.gx === 11 && next.gy === 11) ||
                      (cur.gx === 11 && cur.gy === 11 && next.gx === 10 && next.gy === 10);
        assert.strictEqual(isCut, false, 'A* must not cut through (10,11)-(11,10) obstacle pinch');
    }
});

test('Diagonal cliff corner cutting: units must NEVER step diagonally through cliff corners (Elevation Delta > 1)', () => {
    const grid = new GameGrid(20, 20);

    // Scenario:
    // Tile (10, 10) has elevation 3 (high cliff plateau, walkability=0)
    // Tile (11, 11) has elevation 3 (high cliff plateau, walkability=0)
    // Tile (10, 11) has elevation 0 (low ground canyon, walkability=0)
    // Tile (11, 10) has elevation 0 (low ground canyon, walkability=0)
    grid.setElevation(10, 10, 3);
    grid.setElevation(11, 11, 3);
    grid.setElevation(10, 11, 0);
    grid.setElevation(11, 10, 0);

    // A unit at (10, 11, elev 0) is ordered to move to (11, 10, elev 0)
    // The two elevation 3 cliffs touch at the diagonal vertex (10.5, 10.5).
    // Moving diagonally directly from (10, 11) to (11, 10) cuts right through the touching cliff walls!
    const path = PathFinder.findPath(grid, 10, 11, 11, 10, { smooth: false });

    // Check whether the first step is directly (11, 10)
    let cutCliffCorner = false;
    if (path.length > 0 && path[0].gx === 11 && path[0].gy === 10) {
        cutCliffCorner = true;
    }

    // Invert: High ground unit at (10, 10, elev 3) ordered to move to (11, 11, elev 3) across the canyon pinch
    const pathHigh = PathFinder.findPath(grid, 10, 10, 11, 11, { smooth: false });
    let cutChasmPinch = false;
    if (pathHigh.length > 0 && pathHigh[0].gx === 11 && pathHigh[0].gy === 11) {
        cutChasmPinch = true;
    }

    // Line of sight check
    const los = PathFinder.hasLineOfSight(grid, { gx: 10, gy: 11 }, { gx: 11, gy: 10 });

    if (cutCliffCorner || cutChasmPinch || los) {
        throw new Error(
            `CLIFF CORNER CUTTING VULNERABILITY DETECTED!\n` +
            `         Low-to-low diagonal cut through cliff corner: ${cutCliffCorner}\n` +
            `         High-to-high diagonal cut across chasm pinch: ${cutChasmPinch}\n` +
            `         Line-of-sight reports unobstructed: ${los}\n` +
            `         Reason: pathfinding.js checks grid.isWalkable() on adjacent tiles, but does NOT check if adjacent corner tiles have an impassable elevation delta (> 1)!`
        );
    }
});

test('Diagonal single cliff corner clipping: unit stepping diagonally past an adjacent cliff wall', () => {
    const grid = new GameGrid(20, 20);

    // Single cliff wall at (10, 10) with elevation 4.
    // Surroundings (10, 11), (11, 10), (11, 11) have elevation 0.
    grid.setElevation(10, 10, 4);
    grid.setElevation(10, 11, 0);
    grid.setElevation(11, 10, 0);
    grid.setElevation(11, 11, 0);

    // Moving diagonally from (10, 11) to (11, 10) grazes corner of (10, 10)
    // In A*, dx = 1, dy = -1. Intermediate tiles are (11, 11) [elev 0] and (10, 10) [elev 4 cliff].
    const path = PathFinder.findPath(grid, 10, 11, 11, 10, { smooth: false });

    // If (10, 10) is a vertical cliff of height 4 adjacent to the diagonal step,
    // stepping diagonally grazes right through the cliff volume.
    if (path.length > 0 && path[0].gx === 11 && path[0].gy === 10) {
        throw new Error(
            `SINGLE CLIFF CORNER CLIPPING DETECTED: Path steps directly from (10,11) to (11,10) grazing the corner of elevation 4 cliff at (10,10)!`
        );
    }
});

// ===========================================================================
// SUITE 3: DYNAMIC MOVE_SPEED PHYSICS VERIFICATION
// ===========================================================================
console.log('\n--- SUITE 3: Dynamic move_speed Physics Verification ---');

test('Linearity: distance D strictly proportional to move_speed * time', () => {
    const grid = new GameGrid(150, 150);
    const testSpeeds = [4, 8, 12, 16, 20, 24, 28];
    const duration = 2.0; // seconds
    const dt = 0.05;      // 20 ticks/sec
    const steps = Math.round(duration / dt);

    for (const speed of testSpeeds) {
        const unit = new Unit(speed, { move_speed: speed }, 10, speed * 4);
        unit.moveTo(120, speed * 4, grid, false);

        for (let s = 0; s < steps; s++) {
            unit.update(dt, grid);
        }

        // Expected distance: (speed / 4) * duration
        const expectedDist = (speed / 4) * duration;
        const actualDist = unit.totalDistanceMoved;
        const error = Math.abs(actualDist - expectedDist);

        assert.ok(
            error < 0.001,
            `Speed ${speed}: Expected ${expectedDist.toFixed(4)}, got ${actualDist.toFixed(4)} (diff: ${error})`
        );
    }
});

test('Mid-walk acceleration (5 -> 25) without position warping', () => {
    const grid = new GameGrid(100, 100);
    const unit = new Unit(1, { move_speed: 5 }, 10, 10);
    unit.moveTo(80, 10, grid, false);

    // Walk for 2.0s at speed 5 -> expected 2.5 tiles moved
    for (let s = 0; s < 40; s++) unit.update(0.05, grid);
    const posAtSwitch = unit.wx;
    const distAtSwitch = unit.totalDistanceMoved;
    assert.ok(Math.abs(distAtSwitch - 2.5) < 0.001);

    // Instant live mod slider change: 5 -> 25
    unit.move_speed = 25;

    // Simulate 1 single tick (0.05s) at speed 25
    unit.update(0.05, grid);
    const tickMove = unit.wx - posAtSwitch;
    const expectedTickMove = (25 / 4) * 0.05; // 0.3125 tiles

    assert.ok(
        Math.abs(tickMove - expectedTickMove) < 0.001,
        `Expected tick step ${expectedTickMove}, got ${tickMove} (position warping detected!)`
    );

    // Walk another 2.0s at speed 25 -> expected 12.5 tiles moved
    for (let s = 0; s < 39; s++) unit.update(0.05, grid);
    const totalDistAfter = unit.totalDistanceMoved;
    const expectedTotal = 2.5 + (25 / 4) * 2.0; // 2.5 + 12.5 = 15.0

    assert.ok(
        Math.abs(totalDistAfter - expectedTotal) < 0.001,
        `Expected ${expectedTotal}, got ${totalDistAfter}`
    );
});

test('Mid-walk deceleration (25 -> 2) without position warping', () => {
    const grid = new GameGrid(100, 100);
    const unit = new Unit(1, { move_speed: 25 }, 10, 10);
    unit.moveTo(80, 10, grid, false);

    for (let s = 0; s < 20; s++) unit.update(0.05, grid); // 1.0s at speed 25 -> 6.25 tiles
    const posAtSwitch = unit.wx;

    // Decelerate to 2
    unit.move_speed = 2;
    unit.update(0.05, grid);
    const step = unit.wx - posAtSwitch;
    const expectedStep = (2 / 4) * 0.05; // 0.025 tiles

    assert.ok(
        Math.abs(step - expectedStep) < 0.001,
        `Expected step ${expectedStep}, got ${step}`
    );
});

test('Boundary speed: speed = 0 completely halts movement', () => {
    const grid = new GameGrid(50, 50);
    const unit = new Unit(1, { move_speed: 0 }, 10, 10);
    unit.moveTo(30, 10, grid, false);

    const initialWx = unit.wx;
    const initialWy = unit.wy;

    // Update 100 steps (5.0 seconds)
    for (let s = 0; s < 100; s++) unit.update(0.05, grid);

    assert.strictEqual(unit.wx, initialWx, 'Unit with speed=0 must not move wx');
    assert.strictEqual(unit.wy, initialWy, 'Unit with speed=0 must not move wy');
    assert.strictEqual(unit.totalDistanceMoved, 0, 'Distance moved must be strictly 0');
});

test('Boundary speed: speed = 30 high-speed traversal does NOT skip corner waypoints', () => {
    const grid = new GameGrid(50, 50);

    // Build an obstacle L-shape forcing unit to turn:
    // Unit moves from (10, 10) to (10, 20) to (20, 20)
    // Wall at (11, 10..18)
    for (let y = 10; y <= 18; y++) {
        grid.setWalkability(11, y, 1);
    }

    const unit = new Unit(1, { move_speed: 30 }, 10, 10);
    unit.moveTo(15, 10, grid, false); // Destination is on the other side of the wall

    // Step with relatively large delta (0.1s = 0.75 tiles per tick)
    for (let s = 0; s < 50; s++) {
        unit.update(0.1, grid);
        // At every tick, verify unit is NOT inside the obstacle wall
        const currentTileX = Math.floor(unit.wx);
        const currentTileY = Math.floor(unit.wy);
        assert.ok(
            grid.isWalkable(currentTileX, currentTileY),
            `High speed unit clipped into obstacle at (${currentTileX}, ${currentTileY})!`
        );
    }
});

// ===========================================================================
// SUITE 4: ENTITY SCALING & PROJECTILE ARCS
// ===========================================================================
console.log('\n--- SUITE 4: Entity Scaling & Projectile Arcs ---');

test('Entity scaling: 0.5x to 2.5x preserves scale and does not corrupt movement physics', () => {
    const grid = new GameGrid(60, 60);

    const scales = [0.5, 0.8, 1.0, 1.5, 2.0, 2.5];
    for (const sc of scales) {
        const unit = new Unit(sc, { move_speed: 12 }, 5, 5);
        unit.scale = sc;
        assert.strictEqual(unit.scale, sc);

        unit.moveTo(25, 5, grid, false);
        unit.update(1.0, grid);

        // Scale should NOT alter ground speed (12 / 4 * 1.0 = 3.0 tiles)
        assert.ok(
            Math.abs(unit.totalDistanceMoved - 3.0) < 0.001,
            `Scale ${sc} corrupted distance moved: ${unit.totalDistanceMoved}`
        );
    }
});

test('Projectile parabolic arc trajectory reaches apex at midpoint and hits target', () => {
    const target = new Unit(2, { hp: 200, defense: 4 }, 25, 10);
    const speed = 10;
    const damage = 30;

    const proj = new Projectile(101, 'arrow', 10, 10, target, speed, damage);

    const dist = Math.hypot(25.5 - 10, 10.5 - 10);
    assert.ok(Math.abs(proj.travelDuration - (dist / speed)) < 0.01);

    // Initial position
    const p0 = proj.getCurrentPos();
    assert.strictEqual(p0.arcZ, 0);

    // Step to midpoint (progress = 0.5)
    proj.update(proj.travelDuration * 0.5);
    const pMid = proj.getCurrentPos();
    // Parabolic arc: Math.sin(0.5 * PI) * 40 = 40
    assert.ok(
        Math.abs(pMid.arcZ - 40) < 0.1,
        `Expected peak arcZ = 40, got ${pMid.arcZ}`
    );

    // Complete trajectory
    proj.update(proj.travelDuration * 0.6);
    assert.strictEqual(proj.isArrived, true);
    assert.strictEqual(target.hp, 200 - (30 - 4)); // 174
});

// ===========================================================================
// SUITE 5: ELEVATION ADVANTAGE & COMBAT PIPELINE VULNERABILITY
// ===========================================================================
console.log('\n--- SUITE 5: Elevation Advantage & Combat Pipeline ---');

test('CombatSystem.calculateDamage applies +15% high ground bonus when called directly', () => {
    const grid = new GameGrid(20, 20);
    grid.setElevation(5, 5, 3); // High ground
    grid.setElevation(6, 5, 0); // Low ground

    const highAttacker = new Unit(1, { attack_power: 40 }, 5, 5);
    const lowAttacker = new Unit(2, { attack_power: 40 }, 6, 5);
    const highTarget = new Unit(3, { hp: 200, defense: 0 }, 5, 5);
    const lowTarget = new Unit(4, { hp: 200, defense: 0 }, 6, 5);

    // High attacker attacking low target: 40 * 1.15 = 46
    const highDmg = CombatSystem.calculateDamage(highAttacker, lowTarget, grid);
    assert.strictEqual(highDmg, 46);

    // Low attacker attacking high target: 40 (no bonus)
    const lowDmg = CombatSystem.calculateDamage(lowAttacker, highTarget, grid);
    assert.strictEqual(lowDmg, 40);
});

test('Live Combat Simulation Loop: Attacker on high ground must inflict elevation-boosted damage', () => {
    const grid = new GameGrid(30, 30);
    grid.setElevation(10, 10, 3); // High ground plateau (elevation 3)
    grid.setElevation(11, 10, 0); // Low ground valley (elevation 0)

    // Melee unit test
    const meleeAttacker = new Unit(1, {
        korean_name: '조선 창병',
        attack_power: 20,
        attack_range: 1.5,
        attack_delay: 10,
        projectile_type: null
    }, 10, 10, 0);

    const meleeTarget = new Unit(2, {
        korean_name: '일본 창병',
        hp: 100,
        defense: 0
    }, 11, 10, 1);

    meleeAttacker.targetEntity = meleeTarget;
    const entities = [meleeAttacker, meleeTarget];
    const projectiles = [];

    // Stop after exactly 1 strike (windup 0.25s = 5 ticks, strike happens on tick 6)
    for (let i = 0; i < 7; i++) {
        CombatSystem.update(entities, projectiles, 0.05, null, grid);
        meleeAttacker.update(0.05, grid, entities, null, projectiles);
    }

    const meleeDmg = 100 - meleeTarget.hp;
    if (meleeDmg === 20) {
        throw new Error(
            `COMBAT ELEVATION PIPELINE DISCONNECTED (Melee)!\n` +
            `         Expected high-ground damage: 23 (20 * 1.15)\n` +
            `         Actual damage dealt: ${meleeDmg}\n` +
            `         Reason: Unit.executeAttack() calls target.takeDamage(this.attack_power) directly, ignoring grid and CombatSystem.calculateDamage()!`
        );
    }
    assert.strictEqual(meleeDmg, 23);
});

// ===========================================================================
// SUITE 6: MAP DATA INGESTION WALKABILITY & ELEVATION LAYERS
// ===========================================================================
console.log('\n--- SUITE 6: Map Data Ingestion Layers ---');

test('GameGrid.loadFromMapData must ingest walkability and elevation from map.layers', () => {
    const mapFilePath = path.resolve('web_prototype/assets/maps/taegeuk.json');
    if (!fs.existsSync(mapFilePath)) {
        console.log('    [SKIP] taegeuk.json not found on disk');
        return;
    }

    const rawData = JSON.parse(fs.readFileSync(mapFilePath, 'utf8'));
    const grid = new GameGrid(100, 100);
    grid.loadFromMapData(rawData);

    // Count non-zero walkability and elevation
    let nonZeroWalkability = 0;
    let nonZeroElevation = 0;
    for (let i = 0; i < grid.size; i++) {
        if (grid.walkability[i] > 0) nonZeroWalkability++;
        if (grid.elevation[i] > 0) nonZeroElevation++;
    }

    if (nonZeroWalkability === 0 && rawData.layers && rawData.layers.walkability) {
        throw new Error(
            `MAP INGESTION FAILURE: GameGrid.loadFromMapData() failed to extract mapData.layers.walkability! (0 obstacles loaded, expected > 1000)`
        );
    }

    assert.ok(nonZeroWalkability > 0, 'Grid should have obstacle tiles loaded from map');
    assert.ok(nonZeroElevation > 0, 'Grid should have elevation tiles loaded from map');
});

// ===========================================================================
// SUMMARY & FINDINGS REPORT
// ===========================================================================
console.log('\n======================================================================');
console.log(` ADVERSARIAL STRESS TEST SUMMARY`);
console.log(` Tests Run: ${totalTests}`);
console.log(` Passed:    ${passedTests}`);
console.log(` Failed:    ${failedTests}`);
console.log('======================================================================\n');

if (findings.length > 0) {
    console.log('CRITICAL ADVERSARIAL FINDINGS / BUGS DISCOVERED:');
    findings.forEach((f, idx) => {
        console.log(`\n[Finding ${idx + 1}] ${f.name}`);
        console.log(`  ${f.error}`);
    });
    console.log('\nVERDICT: REQUEST_CHANGES (Defects confirmed empirically)');
} else {
    console.log('VERDICT: APPROVE (All adversarial tests passed)');
}
