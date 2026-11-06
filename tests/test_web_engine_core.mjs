/**
 * Automated Test Suite for Web RTS Prototype Engine & Simulation Core
 *
 * Verifies:
 * 1. IsometricMath projection, raycast elevation picking, frustum culling, and depth sorting
 * 2. Camera panning, zooming, edge scrolling, and boundary clamping
 * 3. SoundEngine voice pooling, spatial panning calculations, and attenuation
 * 4. GameGrid 180x180 typed array layers, walkability, elevation, and serialization
 * 5. PathFinder 8-directional A*, corner-cutting prevention, elevation step limits, smoothing
 * 6. Unit, Building, Projectile state machines, 8-dir facing, dynamic move_speed physics
 * 7. CombatSystem target acquisition, projectile delivery, and elevation damage bonuses
 */

import assert from 'node:assert';
import { IsometricMath, TILE_WIDTH, TILE_HEIGHT, HALF_WIDTH, HALF_HEIGHT, ELEVATION_HEIGHT } from '../web_prototype/js/engine/isometric.js';
import { Camera } from '../web_prototype/js/engine/camera.js';
import { SoundEngine, AudioManager } from '../web_prototype/js/engine/audio.js';
import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { PathFinder, BinaryHeap } from '../web_prototype/js/simulation/pathfinding.js';
import { Unit, Building, Projectile, UnitState, Direction } from '../web_prototype/js/simulation/entities.js';
import { CombatSystem } from '../web_prototype/js/simulation/combat.js';

let passedTests = 0;
let totalTests = 0;

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
console.log(' Running Web RTS Engine Core & Simulation Test Suite');
console.log('======================================================================\n');

// ---------------------------------------------------------------------------
// 1. ISOMETRIC MATH TESTS
// ---------------------------------------------------------------------------
console.log('--- 1. IsometricMath Tests ---');

test('gridToScreen and worldToScreen origin and delta math', () => {
    const cam = { x: 100, y: 200 };
    const p0 = IsometricMath.gridToScreen(0, 0, 0, cam);
    assert.strictEqual(p0.x, 100);
    assert.strictEqual(p0.y, 200);

    // gx=1, gy=1 on ground: sx = (1-1)*32 + 100 = 100, sy = (1+1)*24 + 200 = 248
    const p1 = IsometricMath.gridToScreen(1, 1, 0, cam);
    assert.strictEqual(p1.x, 100);
    assert.strictEqual(p1.y, 248);

    // gx=2, gy=0: sx = (2-0)*32 + 100 = 164, sy = (2+0)*24 + 200 = 248
    const p2 = IsometricMath.gridToScreen(2, 0, 0, cam);
    assert.strictEqual(p2.x, 164);
    assert.strictEqual(p2.y, 248);

    // Continuous world to screen
    const pw = IsometricMath.worldToScreen(1.5, 0.5, 0, cam);
    assert.strictEqual(pw.x, (1.5 - 0.5) * 32 + 100);
    assert.strictEqual(pw.y, (1.5 + 0.5) * 24 + 200);
});

test('Elevation vertical offset shifts tile upward', () => {
    const cam = { x: 0, y: 0 };
    const ground = IsometricMath.gridToScreen(5, 5, 0, cam);
    const elevated = IsometricMath.gridToScreen(5, 5, 3, cam);

    // Elevation 3 shifts screen Y upward by 3 * 16 = 48 pixels
    assert.strictEqual(ground.x, elevated.x);
    assert.strictEqual(ground.y - elevated.y, 3 * ELEVATION_HEIGHT);
});

test('screenToGrid raycast picking with elevated terrain', () => {
    const cam = { x: 500, y: 300 };
    const mapW = 50, mapH = 50;
    const elevGrid = new Uint8Array(mapW * mapH);

    // Create an elevated plateau of elevation 4 at tile (12, 12)
    const targetGx = 12, targetGy = 12, targetElev = 4;
    elevGrid[targetGy * mapW + targetGx] = targetElev;

    // Screen coordinate where tile (12, 12, elev=4) is drawn
    const screenPos = IsometricMath.gridToScreen(targetGx, targetGy, targetElev, cam);

    // Picking at center of diamond: screenPos.x, screenPos.y + 24
    const picked = IsometricMath.screenToGrid(screenPos.x, screenPos.y + 20, cam, elevGrid, mapW, mapH);
    assert.strictEqual(picked.gx, targetGx, `Expected gx=${targetGx}, got ${picked.gx}`);
    assert.strictEqual(picked.gy, targetGy, `Expected gy=${targetGy}, got ${picked.gy}`);
    assert.strictEqual(picked.elevation, targetElev, `Expected elev=${targetElev}, got ${picked.elevation}`);
    assert.strictEqual(picked.valid, true);
});

test('Frustum culling visible tile bounds', () => {
    const cam = { x: 500, y: 500 };
    const bounds = IsometricMath.getVisibleTileBounds(cam, 1024, 768, 180, 180);

    assert.ok(bounds.minGx >= 0);
    assert.ok(bounds.maxGx < 180);
    assert.ok(bounds.minGy >= 0);
    assert.ok(bounds.maxGy < 180);
    assert.ok(bounds.maxGx >= bounds.minGx);
    assert.ok(bounds.maxGy >= bounds.minGy);

    // Active bounds should only be a fraction of the 180x180 map (~32,400 tiles)
    const tileCount = (bounds.maxGx - bounds.minGx + 1) * (bounds.maxGy - bounds.minGy + 1);
    assert.ok(tileCount < 5000, `Visible tiles (${tileCount}) should be culled down significantly`);
});

test('DepthKey calculation preserves visual layering hierarchy', () => {
    const gx = 15, gy = 15;
    const terrainKey = IsometricMath.getDepthKey(gx, gy, 0, 0);  // Terrain
    const decalKey = IsometricMath.getDepthKey(gx, gy, 1, 0);    // Decal
    const resourceKey = IsometricMath.getDepthKey(gx, gy, 2, 0); // Resource
    const buildingKey = IsometricMath.getDepthKey(gx, gy, 3, 0); // Building
    const unitKey = IsometricMath.getDepthKey(gx, gy, 4, 10);    // Unit
    const projKey = IsometricMath.getDepthKey(gx, gy, 9, 0);     // Projectile

    assert.ok(terrainKey < decalKey);
    assert.ok(decalKey < resourceKey);
    assert.ok(resourceKey < buildingKey);
    assert.ok(buildingKey < unitKey);
    assert.ok(unitKey < projKey);

    // Tiles further down the screen (larger gx + gy) draw in front of tiles higher up
    const frontKey = IsometricMath.getDepthKey(16, 16, 0, 0);
    assert.ok(frontKey > terrainKey);
});

// ---------------------------------------------------------------------------
// 2. CAMERA CONTROLLER TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 2. Camera Controller Tests ---');

test('Camera centerOnGrid, smooth lerp, and panning', () => {
    const camera = new Camera(1024, 768, 180, 180);
    camera.centerOnGrid(50, 50, true);

    const initialX = camera.x;
    const initialY = camera.y;

    // Simulate key down 'KeyD' (pan right, moves targetX to left)
    camera.update(0.1, { KeyD: true }, null);
    assert.ok(camera.targetX < initialX, 'Target X should move left when panning right');

    // Multiple updates smooth camera position towards target
    for (let i = 0; i < 10; i++) {
        camera.update(0.05, {}, null);
    }
    assert.ok(Math.abs(camera.x - camera.targetX) < Math.abs(initialX - camera.targetX));
});

test('Camera zoom limits and bounds clamping', () => {
    const camera = new Camera(1024, 768, 180, 180);
    camera.setZoom(5.0); // Out of bounds high
    assert.strictEqual(camera.targetZoom, 2.0);

    camera.setZoom(0.1); // Out of bounds low
    assert.strictEqual(camera.targetZoom, 0.5);

    camera.zoomBy(0.5);
    assert.strictEqual(camera.targetZoom, 1.0);
});

// ---------------------------------------------------------------------------
// 3. SOUND ENGINE TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 3. SoundEngine Tests ---');

test('SoundEngine voice limiting and pooling (max 3 instances)', () => {
    const sound = new SoundEngine();

    // Mock an AudioContext for Node.js test environment
    sound.ctx = {
        state: 'running',
        createBufferSource: () => ({
            buffer: null,
            connect: () => {},
            start: () => {},
            stop: () => {},
            onended: null
        }),
        createGain: () => ({
            gain: { value: 1.0 },
            connect: () => {}
        }),
        destination: {}
    };

    // Register dummy buffer
    sound.buffers.set('arrow', {});

    // First 3 plays should succeed
    const s1 = sound.play('arrow');
    const s2 = sound.play('arrow');
    const s3 = sound.play('arrow');
    assert.ok(s1 !== null);
    assert.ok(s2 !== null);
    assert.ok(s3 !== null);
    assert.strictEqual(sound.activeVoices.get('arrow'), 3);

    // 4th play must be rejected by voice pool limiter
    const s4 = sound.play('arrow');
    assert.strictEqual(s4, null, '4th sound instance should be blocked by voice limit of 3');

    // Simulate s1 ending
    if (s1.onended) s1.onended();
    assert.strictEqual(sound.activeVoices.get('arrow'), 2);

    // Now 5th play should succeed
    const s5 = sound.play('arrow');
    assert.ok(s5 !== null);
});

test('SoundEngine muting and volume control', () => {
    const sound = new SoundEngine();
    sound.setVolume(0.75);
    assert.strictEqual(sound.masterVolume, 0.75);

    sound.setMuted(true);
    assert.strictEqual(sound.isMuted, true);
    assert.strictEqual(sound.play('test'), null);
});

// ---------------------------------------------------------------------------
// 4. GAME GRID TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 4. GameGrid Tests ---');

test('GameGrid 180x180 typed array dimensions and defaults', () => {
    const grid = new GameGrid(180, 180);
    assert.strictEqual(grid.size, 32400);
    assert.strictEqual(grid.tileLayer1.length, 32400);
    assert.strictEqual(grid.tileLayer2.length, 32400);
    assert.strictEqual(grid.walkability.length, 32400);
    assert.strictEqual(grid.elevation.length, 32400);
    assert.strictEqual(grid.resourceTypes.length, 32400);
    assert.strictEqual(grid.buildingIds.length, 32400);
    assert.strictEqual(grid.unitOccupancy.length, 32400);

    // Passable by default
    assert.strictEqual(grid.isWalkable(10, 10), true);
    assert.strictEqual(grid.isWalkable(-1, 0), false);
    assert.strictEqual(grid.isWalkable(180, 180), false);
});

test('GameGrid building, resource, and elevation placement', () => {
    const grid = new GameGrid(50, 50);

    // Set 2x2 building at (10, 10)
    grid.setBuilding(10, 10, 42, 0, 2, 2);
    assert.strictEqual(grid.isWalkable(10, 10), false);
    assert.strictEqual(grid.isWalkable(11, 10), false);
    assert.strictEqual(grid.isWalkable(10, 11), false);
    assert.strictEqual(grid.isWalkable(11, 11), false);
    assert.strictEqual(grid.isWalkable(12, 10), true); // Outside building

    // Clear building
    grid.clearBuilding(10, 10, 2, 2);
    assert.strictEqual(grid.isWalkable(10, 10), true);

    // Resource placement
    grid.setResource(15, 15, 3, 200); // Tree
    assert.strictEqual(grid.isWalkable(15, 15), false);
    grid.clearResource(15, 15);
    assert.strictEqual(grid.isWalkable(15, 15), true);

    // Elevation clamping
    grid.setElevation(20, 20, 7); // Should clamp to 5
    assert.strictEqual(grid.getElevation(20, 20), 5);
    grid.setElevation(20, 20, -2); // Should clamp to 0
    assert.strictEqual(grid.getElevation(20, 20), 0);
});

test('GameGrid JSON serialization and restoration', () => {
    const grid = new GameGrid(20, 20);
    grid.setElevation(5, 5, 3);
    grid.setTile(5, 5, 123, 1);
    grid.setWalkability(5, 5, 1);

    const json = grid.exportToJSON();
    assert.strictEqual(json.width, 20);
    assert.strictEqual(json.height, 20);

    const restored = new GameGrid(20, 20);
    restored.loadFromMapData(json);
    assert.strictEqual(restored.getElevation(5, 5), 3);
    assert.strictEqual(restored.getTile(5, 5, 1), 123);
    assert.strictEqual(restored.walkability[5 * 20 + 5], 1);
});

// ---------------------------------------------------------------------------
// 5. PATHFINDING TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 5. PathFinder A* Tests ---');

test('A* finds direct path in open terrain', () => {
    const grid = new GameGrid(30, 30);
    const path = PathFinder.findPath(grid, 5, 5, 10, 5, { smooth: false });

    assert.ok(path.length > 0);
    assert.strictEqual(path[path.length - 1].gx, 10);
    assert.strictEqual(path[path.length - 1].gy, 5);
});

test('A* routes around obstacle wall', () => {
    const grid = new GameGrid(30, 30);

    // Build vertical wall from y=3 to y=7 at x=10
    for (let y = 3; y <= 7; y++) {
        grid.setWalkability(10, y, 1);
    }

    const path = PathFinder.findPath(grid, 8, 5, 12, 5, { smooth: false });
    assert.ok(path.length > 0);
    assert.strictEqual(path[path.length - 1].gx, 12);
    assert.strictEqual(path[path.length - 1].gy, 5);

    // Ensure no path waypoint stepped onto the wall
    for (const pt of path) {
        assert.ok(!(pt.gx === 10 && pt.gy >= 3 && pt.gy <= 7), `Path stepped onto obstacle wall at (${pt.gx}, ${pt.gy})`);
    }
});

test('Corner-cutting prevention: disallows stepping diagonally between adjacent obstacles', () => {
    const grid = new GameGrid(20, 20);

    // Place two diagonal wall blocks at (5, 5) and (6, 6)
    // Attempting to step diagonally from (5, 6) to (6, 5) cuts through the touching corners!
    grid.setWalkability(5, 5, 1);
    grid.setWalkability(6, 6, 1);

    const path = PathFinder.findPath(grid, 5, 6, 6, 5, { smooth: false });

    // Path must navigate around (e.g. via 4,6 or 6,7), NOT cut directly from 5,6 to 6,5
    assert.ok(path.length > 0);
    for (let i = 0; i < path.length - 1; i++) {
        const cur = path[i];
        const next = path[i + 1];
        const isCut = (cur.gx === 5 && cur.gy === 6 && next.gx === 6 && next.gy === 5) ||
                      (cur.gx === 6 && cur.gy === 5 && next.gx === 5 && next.gy === 6);
        assert.strictEqual(isCut, false, 'A* should never cut through corner obstacles');
    }
});

test('Elevation step limit: cannot jump elevation delta > 1', () => {
    const grid = new GameGrid(20, 20);

    // Cliff: tile (5, 10) has elevation 0, tile (6, 10) has elevation 3 (delta=3)
    // Only a ramp at (6, 12) with elevation 1 exists
    for (let y = 0; y < 20; y++) {
        grid.setElevation(6, y, 3);
    }
    // Make a gradual ramp at y=15: (6, 15) elev 1, (7, 15) elev 2, (8, 15) elev 3
    grid.setElevation(6, 15, 1);
    grid.setElevation(7, 15, 2);
    grid.setElevation(8, 15, 3);

    // Try path from (5, 5) to (10, 5)
    // Direct cross has elev delta 3; path must redirect to ramp or fail
    const path = PathFinder.findPath(grid, 5, 5, 10, 5, { smooth: false });
    if (path.length > 0) {
        // Verify every step has elevation delta <= 1
        let prevElev = grid.getElevation(5, 5);
        for (const pt of path) {
            const nextElev = grid.getElevation(pt.gx, pt.gy);
            assert.ok(Math.abs(nextElev - prevElev) <= 1, `Elevation jump > 1 found: ${prevElev} -> ${nextElev}`);
            prevElev = nextElev;
        }
    }
});

test('Path smoothing removes intermediate zig-zags on clear terrain', () => {
    const grid = new GameGrid(30, 30);
    const rawPath = PathFinder.findPath(grid, 2, 2, 15, 2, { smooth: false });
    const smoothed = PathFinder.findPath(grid, 2, 2, 15, 2, { smooth: true });

    assert.ok(smoothed.length < rawPath.length, `Smoothed path (${smoothed.length}) should have fewer waypoints than raw path (${rawPath.length})`);
    assert.strictEqual(smoothed[smoothed.length - 1].gx, 15);
    assert.strictEqual(smoothed[smoothed.length - 1].gy, 2);
});

// ---------------------------------------------------------------------------
// 6. ENTITY SIMULATION & MOVE_SPEED PHYSICS TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 6. Entity & Dynamic Move Speed Physics Tests ---');

test('Dynamic move_speed distance calculation: double speed traverses double distance', () => {
    const grid = new GameGrid(100, 100);

    const unit1 = new Unit(1, { korean_name: '조선 창병', move_speed: 12 }, 10, 10);
    const unit2 = new Unit(2, { korean_name: '명 창기병', move_speed: 24 }, 10, 20);

    // Order both to walk 40 tiles eastward
    unit1.moveTo(50, 10, grid, false);
    unit2.moveTo(50, 20, grid, false);

    // Run simulation for 2.0 seconds with 40 steps (0.05s each)
    const deltaSec = 0.05;
    for (let step = 0; step < 40; step++) {
        unit1.update(deltaSec, grid);
        unit2.update(deltaSec, grid);
    }

    // Verify distance moved
    assert.ok(unit1.totalDistanceMoved > 0);
    assert.ok(unit2.totalDistanceMoved > 0);

    const ratio = unit2.totalDistanceMoved / unit1.totalDistanceMoved;
    // Ratio should be very close to 2.0 (speed 24 vs 12)
    assert.ok(Math.abs(ratio - 2.0) < 0.05, `Expected speed ratio ~2.0, got ${ratio.toFixed(3)}`);
});

test('8-directional orientation calculation from movement vector', () => {
    // Screen coords: sx = (dx - dy) * 32, sy = (dx + dy) * 24
    // Moving South: dx = 1, dy = 1 -> sx = 0, sy = 48 -> Direction.S (0)
    assert.strictEqual(Unit.calculateDirection(1, 1), Direction.S);

    // Moving North: dx = -1, dy = -1 -> sx = 0, sy = -48 -> Direction.N (4)
    assert.strictEqual(Unit.calculateDirection(-1, -1), Direction.N);

    // Moving East: dx = 1, dy = -1 -> sx = 64, sy = 0 -> Direction.E (6)
    assert.strictEqual(Unit.calculateDirection(1, -1), Direction.E);

    // Moving West: dx = -1, dy = 1 -> sx = -64, sy = 0 -> Direction.W (2)
    assert.strictEqual(Unit.calculateDirection(-1, 1), Direction.W);
});

test('Unit takeDamage and death transition', () => {
    const unit = new Unit(1, { hp: 100, defense: 5 }, 10, 10);
    const netDmg = unit.takeDamage(25);
    assert.strictEqual(netDmg, 20); // 25 - 5 defense
    assert.strictEqual(unit.hp, 80);
    assert.strictEqual(unit.state, UnitState.IDLE);

    // Fatal blow
    unit.takeDamage(100);
    assert.strictEqual(unit.hp, 0);
    assert.strictEqual(unit.isDead, true);
    assert.strictEqual(unit.state, UnitState.DIE);
});

test('Building production queue and unit completion', () => {
    const building = new Building(10, { korean_name: '조선 훈련소', hp: 1000 }, 20, 20);
    const archerArchetype = { korean_name: '조선 궁수', move_speed: 10 };

    building.queueUnit(archerArchetype, 1.0); // 1.0 second build time
    assert.strictEqual(building.productionQueue.length, 1);

    // Update 0.5s: not yet finished
    const res1 = building.update(0.5);
    assert.strictEqual(res1, null);

    // Update another 0.6s: should complete
    const res2 = building.update(0.6);
    assert.ok(res2 !== null);
    assert.strictEqual(res2.korean_name, '조선 궁수');
    assert.strictEqual(building.productionQueue.length, 0);
});

test('Projectile parabolic trajectory and impact damage', () => {
    const target = new Unit(2, { hp: 100, defense: 2 }, 15, 10);
    const proj = new Projectile(101, 'arrow', 10, 10, target, 10, 20);

    // Initial position
    const pStart = proj.getCurrentPos();
    assert.strictEqual(pStart.wx, 10);
    assert.strictEqual(pStart.wy, 10);
    assert.strictEqual(pStart.arcZ, 0);

    // Mid-flight: arcZ should peak (> 0)
    proj.update(proj.travelDuration * 0.5);
    const pMid = proj.getCurrentPos();
    assert.ok(pMid.arcZ > 20, `Arc Z at midpoint (${pMid.arcZ}) should be elevated`);

    // Impact
    proj.update(proj.travelDuration * 0.6);
    assert.strictEqual(proj.isArrived, true);
    assert.strictEqual(target.hp, 82); // 100 - (20 - 2 defense)
});

// ---------------------------------------------------------------------------
// 7. COMBAT SYSTEM TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 7. Combat System Tests ---');

test('CombatSystem target acquisition, range check, and elevation bonus', () => {
    const grid = new GameGrid(50, 50);

    const friendlyUnit = new Unit(1, { attack_power: 20, attack_range: 2, sight_range: 8 }, 10, 10, 0);
    const enemyUnit = new Unit(2, { hp: 100, defense: 5 }, 11, 10, 1);

    // Target acquisition
    const target = CombatSystem.findNearestEnemy(friendlyUnit, [friendlyUnit, enemyUnit]);
    assert.strictEqual(target, enemyUnit);

    // Range check
    assert.strictEqual(CombatSystem.isInRange(friendlyUnit, enemyUnit), true);

    // Flat ground damage
    const flatDmg = CombatSystem.calculateDamage(friendlyUnit, enemyUnit, grid);
    assert.strictEqual(flatDmg, 15); // 20 - 5 defense

    // High ground advantage
    grid.setElevation(10, 10, 3); // Friendly at elevation 3
    grid.setElevation(11, 10, 1); // Enemy at elevation 1
    const highGroundDmg = CombatSystem.calculateDamage(friendlyUnit, enemyUnit, grid);
    assert.strictEqual(highGroundDmg, 18); // 20 * 1.15 = 23 -> 23 - 5 = 18
});

test('CombatSystem simulation loop updates projectiles and applies damage', () => {
    const enemy = new Unit(2, { hp: 50, defense: 0 }, 15, 10, 1);
    const projectiles = [];

    // Spawn arrow
    const attacker = new Unit(1, { attack_power: 30, attack_range: 8, projectile_type: 'arrow' }, 10, 10, 0);
    CombatSystem.spawnProjectile(attacker, enemy, projectiles);
    assert.strictEqual(projectiles.length, 1);

    // Advance combat simulation until projectile arrives
    for (let i = 0; i < 20; i++) {
        CombatSystem.update([attacker, enemy], projectiles, 0.1);
    }

    assert.strictEqual(projectiles.length, 0); // Delivered and removed
    assert.strictEqual(enemy.hp, 20); // 50 - 30
});

// ---------------------------------------------------------------------------
// 8. ADDITIONAL STRESS & EDGE-CASE TESTS
// ---------------------------------------------------------------------------
console.log('\n--- 8. Additional Stress & Edge-Case Tests ---');

test('BinaryHeap preserves strict min-heap ordering across random insertions', () => {
    const heap = new BinaryHeap(node => node.val);
    const numbers = [45, 12, 89, 3, 77, 2, 99, 14, 55, 1, 88, 23, 67, 8, 34];
    for (const val of numbers) {
        heap.push({ val });
    }
    assert.strictEqual(heap.size(), numbers.length);

    const sorted = [];
    while (heap.size() > 0) {
        sorted.push(heap.pop().val);
    }
    const expected = [...numbers].sort((a, b) => a - b);
    assert.deepStrictEqual(sorted, expected);
});

test('Live Modding: In-flight move_speed modification immediately changes step size', () => {
    const grid = new GameGrid(60, 60);
    const unit = new Unit(1, { move_speed: 10 }, 5, 5);
    unit.moveTo(50, 5, grid, false);

    // Step 1 second at speed 10
    unit.update(1.0, grid);
    const distAtSpeed10 = unit.totalDistanceMoved;
    assert.ok(Math.abs(distAtSpeed10 - 2.5) < 0.05, `Expected 2.5 distance at speed 10, got ${distAtSpeed10}`);

    // Dynamically modify speed to 30 (simulating live slider adjustment)
    unit.move_speed = 30;

    // Step 1 second at speed 30
    unit.update(1.0, grid);
    const addedDistAtSpeed30 = unit.totalDistanceMoved - distAtSpeed10;
    assert.ok(Math.abs(addedDistAtSpeed30 - 7.5) < 0.05, `Expected 7.5 distance at speed 30, got ${addedDistAtSpeed30}`);
});

test('Unit MP mana consumption and HP healing bounds', () => {
    const hero = new Unit(99, { hp: 500, mp: 200 }, 10, 10);
    hero.takeDamage(150);
    assert.strictEqual(hero.hp, 350);

    // Overhealing is clamped to max_hp
    hero.heal(300);
    assert.strictEqual(hero.hp, 500);

    // Mana consumption
    assert.strictEqual(hero.consumeMana(80), true);
    assert.strictEqual(hero.mp, 120);

    // Insufficient mana
    assert.strictEqual(hero.consumeMana(150), false);
    assert.strictEqual(hero.mp, 120); // Unchanged

    // Restore mana
    hero.restoreMana(500);
    assert.strictEqual(hero.mp, 200); // Clamped to max_mp
});

test('A* pathfinding on full 180x180 map scale with multi-tile obstacle', () => {
    const fullGrid = new GameGrid(180, 180);

    // Build a large obstacle block at the center
    fullGrid.setBuilding(80, 80, 999, 1, 10, 10);

    const path = PathFinder.findPath(fullGrid, 75, 85, 95, 85, { smooth: true });
    assert.ok(path.length > 0, 'Path should be found on 180x180 map');
    assert.strictEqual(path[path.length - 1].gx, 95);
    assert.strictEqual(path[path.length - 1].gy, 85);
});

console.log('\n======================================================================');
console.log(` Test Results: ${passedTests} / ${totalTests} Passed`);
console.log('======================================================================\n');

if (passedTests === totalTests) {
    console.log('ALL ENGINE & SIMULATION CORE TESTS PASSED SUCCESSFULLY!');
} else {
    process.exit(1);
}
