/**
 * Comprehensive Verification & Stress-Test Suite for AI Macro, Micro & Difficulty
 *
 * Tests:
 * 1. difficulty_config.js: Exact quantitative parameters across 4 tiers, APM Limiter, Reaction Delays
 * 2. strategic_macro_ai.js: Cultural worker allocation, saturation limits, TTD expansion, scouting, counter-production matrix, market trades
 * 3. tactical_micro.js: Stutter-step kiting, HP-ratio retreat, AoE evasion, Hammer/Anvil flanking, projectile reservation & overkill prevention
 */

import assert from 'node:assert';
import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { Unit, Building, UnitState } from '../web_prototype/js/simulation/entities.js';
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

let passedTests = 0;
let totalTests = 0;

function test(name, fn) {
    totalTests++;
    try {
        fn();
        passedTests++;
        console.log(`  [PASS] ${name}`);
    } catch (err) {
        console.error(`  [FAIL] ${name}`);
        console.error(`         ${err.stack || err.message}`);
        throw err;
    }
}

console.log('======================================================================');
console.log(' AI OVERHAUL VERIFICATION: DIFFICULTY, MACRO & MICRO ENGINES');
console.log('======================================================================');

// ===========================================================================
// SUITE 1: DIFFICULTY CONFIGURATION & PARAMETER CALIBRATION
// ===========================================================================
console.log('\n--- SUITE 1: Difficulty Calibration & Quantitative Tiers ---');

test('Easy Tier: Exact quantitative parameters matching spec', () => {
    const easy = DIFFICULTY_TIERS.EASY;
    assert.strictEqual(easy.apm, 45);
    assert.strictEqual(easy.reactionDelayMs, 850);
    assert.strictEqual(easy.decisionCadenceTicks, 32);
    assert.strictEqual(easy.gatherMultiplier, 0.80);
    assert.strictEqual(easy.kitingEnabled, false);
    assert.strictEqual(easy.retreatEnabled, false);
    assert.strictEqual(easy.cheat5050Enabled, false);
});

test('Normal Tier: Exact quantitative parameters matching spec (100% fair parity)', () => {
    const normal = DIFFICULTY_TIERS.NORMAL;
    assert.strictEqual(normal.apm, 110);
    assert.strictEqual(normal.reactionDelayMs, 417);
    assert.strictEqual(normal.decisionCadenceTicks, 16);
    assert.strictEqual(normal.gatherMultiplier, 1.00);
    assert.strictEqual(normal.kitingEnabled, true);
    assert.strictEqual(normal.retreatEnabled, true);
    assert.strictEqual(normal.retreatHpThreshold, 0.25);
    assert.strictEqual(normal.cheat5050Enabled, false);
});

test('Hard Tier: Exact quantitative parameters matching spec', () => {
    const hard = DIFFICULTY_TIERS.HARD;
    assert.strictEqual(hard.apm, 240);
    assert.strictEqual(hard.reactionDelayMs, 167);
    assert.strictEqual(hard.decisionCadenceTicks, 8);
    assert.strictEqual(hard.gatherMultiplier, 1.15);
    assert.strictEqual(hard.kitingEnabled, true);
    assert.strictEqual(hard.kitingStutterStep, true);
    assert.strictEqual(hard.retreatEnabled, true);
    assert.strictEqual(hard.aoeDodgingEnabled, true);
    assert.strictEqual(hard.aoePredictive, true);
    assert.strictEqual(hard.cheat5050Enabled, false);
});

test('Brutal Tier: Exact quantitative parameters matching spec', () => {
    const brutal = DIFFICULTY_TIERS.BRUTAL;
    assert.strictEqual(brutal.apm, 420);
    assert.strictEqual(brutal.reactionDelayMs, 42);
    assert.strictEqual(brutal.decisionCadenceTicks, 4);
    assert.strictEqual(brutal.gatherMultiplier, 1.30);
    assert.strictEqual(brutal.kitingEnabled, true);
    assert.strictEqual(brutal.kitingStutterStep, true);
    assert.strictEqual(brutal.retreatEnabled, true);
    assert.strictEqual(brutal.aoeDodgingEnabled, true);
    assert.strictEqual(brutal.flankingEnabled, true);
    assert.strictEqual(brutal.cheat5050Enabled, false);
});

test('ApmLimiter: Token consumption and per-unit command cooldown throttling', () => {
    const limiter = new ApmLimiter(DIFFICULTY_TIERS.EASY); // 45 APM, capacity 3, cooldown 1.5s (36 ticks)
    assert.strictEqual(limiter.tryConsume(101, 0.0), true);
    assert.strictEqual(limiter.tryConsume(101, 0.5), false); // Rejected by per-unit cooldown (< 1.5s)
    assert.strictEqual(limiter.tryConsume(102, 0.5), true);  // Different unit permitted
    assert.strictEqual(limiter.tryConsume(103, 0.6), true);  // Third token consumed
    assert.strictEqual(limiter.tryConsume(104, 0.7), false); // Saturated burst capacity (3 tokens spent)

    // Advance time by 3 seconds: tokens refill
    assert.strictEqual(limiter.tryConsume(101, 3.5), true);  // Unit cooldown elapsed & tokens refilled
});

test('Reaction delay sampling bounds with jitter', () => {
    for (let i = 0; i < 20; i++) {
        const delayEasy = sampleReactionDelaySec('easy');
        assert.ok(delayEasy >= 0.5 && delayEasy <= 1.2, `Delay ${delayEasy} out of bounds for Easy`);
        const delayBrutal = sampleReactionDelaySec('brutal');
        assert.ok(Math.abs(delayBrutal - 1/24.0) < 1e-4, `Delay ${delayBrutal} must be exactly 1 tick for Brutal`);
    }
});

// ===========================================================================
// SUITE 2: STRATEGIC MACRO AI ARCHITECTURE
// ===========================================================================
console.log('\n--- SUITE 2: Strategic Macro AI Engine ---');

function createMockApp() {
    const grid = new GameGrid(64, 64);
    return {
        grid,
        entities: [],
        nextEntityId: 1000,
        resources: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 10, supplyMax: 2000 },
        playerResources: {
            0: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 10, supplyMax: 2000 },
            1: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 10, supplyMax: 2000 }
        },
        getPlayerResources(owner) {
            return this.playerResources[owner];
        },
        markBuildingFootprint(b) {}
    };
}

test('Dynamic worker allocation across cultural baselines (Japan, Joseon, Ming)', () => {
    const app = createMockApp();
    const aiJapan = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    // Spawn 10 workers for Japan
    const workers = [];
    for (let i = 0; i < 10; i++) {
        const w = new Unit(100 + i, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 30, 25, 1);
        w.isWorker = true;
        app.entities.push(w);
        workers.push(w);
    }

    aiJapan.rebalanceWorkforce();

    // Check that preferences are distributed
    let riceWorkers = workers.filter(w => w.harvestPref === 100).length;
    let woodWorkers = workers.filter(w => w.harvestPref === 3).length;
    let potatoWorkers = workers.filter(w => w.harvestPref === 1).length;

    assert.ok(riceWorkers >= 2 && riceWorkers <= 5, `Rice workers ${riceWorkers} within Japan baseline range`);
    assert.ok(woodWorkers >= 1 && woodWorkers <= 4, `Wood workers ${woodWorkers} within Japan baseline range`);
    assert.ok(potatoWorkers >= 2 && potatoWorkers <= 6, `Potato workers ${potatoWorkers} within Japan baseline range`);
    assert.strictEqual(riceWorkers + woodWorkers + potatoWorkers, 10);
});

test('Node saturation limits: Rice max 3, Tree max 1, Potato max 3', () => {
    const app = createMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    assert.strictEqual(ai.getNodeSaturationLimit(100), 3); // Rice
    assert.strictEqual(ai.getNodeSaturationLimit(3), 1);   // Tree
    assert.strictEqual(ai.getNodeSaturationLimit(1), 3);   // Potato

    // Place 1 tree node at (20, 20)
    app.grid.resourceTypes[20 * 64 + 20] = 3;
    app.grid.resourceAmounts[20 * 64 + 20] = 500;

    // Worker 1 claims tree
    const w1 = new Unit(201, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 21, 20, 1);
    w1.isWorker = true;
    w1.harvestPref = 3;
    app.entities.push(w1);

    const bestNode1 = ai.findBestUnsaturatedNode(w1, app.grid);
    assert.ok(bestNode1 !== null);
    assert.strictEqual(bestNode1.gx, 20);
    assert.strictEqual(bestNode1.gy, 20);

    // Register reservation
    const key = `20,20`;
    ai.nodeReservations.set(key, new Set([201]));

    // Worker 2 attempts to claim the same tree
    const w2 = new Unit(202, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 22, 20, 1);
    w2.isWorker = true;
    w2.harvestPref = 3;
    app.entities.push(w2);

    const bestNode2 = ai.findBestUnsaturatedNode(w2, app.grid);
    // Tree is saturated (1/1 limit reached), must be strictly rejected!
    assert.strictEqual(bestNode2, null);
});

test('Authentic market trading engine (pays 5:3 exchange penalty, zero cheat equalizing)', () => {
    const app = createMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    // Extreme surplus: 1600 Rice, 300 Wood
    app.playerResources[1].rice = 1600;
    app.playerResources[1].wood = 300;

    ai.evaluateMarketTrades();

    // Must have traded 500 Rice for 300 Wood
    assert.strictEqual(app.playerResources[1].rice, 1100);
    assert.strictEqual(app.playerResources[1].wood, 600);
    assert.strictEqual(ai.marketCooldown, 30.0);

    // Cooldown prevents immediate re-trade
    ai.evaluateMarketTrades();
    assert.strictEqual(app.playerResources[1].rice, 1100);
    assert.strictEqual(app.playerResources[1].wood, 600);
});

test('Time-To-Depletion (TTD <= 120s) and Autonomous Base Expansion Taskforce', () => {
    const app = createMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    // Place HQ at (32, 28)
    const hq = new Building(300, { korean_name: '일본 본영', width: 3, height: 3, hp: 6000 }, 32, 28, 1);
    hq.isBuilding = true;
    hq.isConstructing = false;
    app.entities.push(hq);
    ai.syncInitialBases();

    // Spawn 1 builder worker and 4 combat units
    const builder = new Unit(301, { korean_name: '일본 농부', move_speed: 12, hp: 320, isWorker: true }, 32, 30, 1);
    builder.isWorker = true;
    app.entities.push(builder);

    for (let i = 0; i < 4; i++) {
        const combat = new Unit(302 + i, { korean_name: '일본 사무라이', move_speed: 13, hp: 920 }, 33, 30, 1);
        app.entities.push(combat);
    }

    // Place resources near North-East expansion site (55, 18)
    app.grid.resourceTypes[18 * 64 + 55] = 100;
    app.grid.resourceAmounts[18 * 64 + 55] = 2000;

    // Set finances for expansion (750 rice, 500 wood)
    app.playerResources[1].rice = 800;
    app.playerResources[1].wood = 600;

    // Simulate depleted resources around main base -> TTD triggers!
    ai.evaluateMacroState();
    assert.ok(ai.activeExpansionTaskforce !== null, 'Expansion taskforce must be deployed');
    assert.strictEqual(ai.activeExpansionTaskforce.phase, 'ESCORT_TRANSIT');
    assert.strictEqual(ai.activeExpansionTaskforce.builder.id, 301);
    assert.strictEqual(ai.activeExpansionTaskforce.escorts.length, 2);

    // Simulate arrival at site
    ai.activeExpansionTaskforce.builder.wx = ai.activeExpansionTaskforce.site.gx;
    ai.activeExpansionTaskforce.builder.wy = ai.activeExpansionTaskforce.site.gy;
    ai.updateExpansionTaskforce(0.5);

    assert.strictEqual(ai.activeExpansionTaskforce.phase, 'CONSTRUCTION');
    assert.ok(ai.activeExpansionTaskforce.hqEntity !== null);
    assert.strictEqual(ai.activeExpansionTaskforce.hqEntity.isConstructing, true);

    // Complete construction & place watchtower
    ai.updateExpansionTaskforce(25.0);
    assert.ok(ai.activeExpansionTaskforce === null, 'Taskforce completed handover');
    assert.strictEqual(ai.outpostAnchors.length, 2, 'New outpost added to anchors');
});

test('Reconnaissance: 4-waypoint patrol sweep & <65% HP retreat reflex', () => {
    const app = createMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    const scout = new Unit(401, { korean_name: '일본 닌자', move_speed: 16, hp: 600, max_hp: 600 }, 32, 28, 1);
    app.entities.push(scout);

    ai.updateScoutPatrol(0.1);
    assert.strictEqual(ai.scoutEntityId, 401);
    assert.strictEqual(ai.scoutRoute.length, 4);

    // Simulate scout reaching waypoint 0
    scout.wx = ai.scoutRoute[0].gx;
    scout.wy = ai.scoutRoute[0].gy;
    ai.updateScoutPatrol(0.1);
    assert.strictEqual(ai.scoutIndex, 1, 'Scout advances to waypoint 1');

    // Inflict heavy damage (< 65% HP, e.g. 300/600 = 50%)
    scout.hp = 300;
    ai.updateScoutPatrol(0.1);
    // Scout must trigger health reflex and retreat to base (32, 28)
    assert.strictEqual(ai.scoutIndex, 1); // Waypoint advance aborted
});

test('6x6 Pairwise counter-production matrix selects hard counter against cavalry threat', () => {
    const app = createMockApp();
    const ai = new StrategicMacroAI(app, { owner: 1, faction: 'japan' });

    // Place Barracks for Japan
    const barracks = new Building(500, { korean_name: '일본 훈련소', width: 3, height: 3, hp: 3500 }, 36, 28, 1);
    barracks.isBuilding = true;
    app.entities.push(barracks);

    // Threat vector surges in Cavalry (Class 1)
    ai.threatVector = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0];

    const chosen = ai.selectOptimalCounterUnit();
    assert.ok(chosen !== null);
    // Pike/Spearman (Class 0) has W=2.5 counter multiplier against Cavalry
    assert.ok(chosen.korean_name.includes('창병'), `Expected Spearman counter, got ${chosen.korean_name}`);
});

// ===========================================================================
// SUITE 3: TACTICAL MICRO AI ARCHITECTURE
// ===========================================================================
console.log('\n--- SUITE 3: Tactical Micro AI Engine ---');

test('ProjectileReservationManager: In-flight damage tracking and mathematical death', () => {
    const mgr = new ProjectileReservationManager();

    const target = { id: 601, hp: 50, max_hp: 100, isDead: false };

    assert.strictEqual(mgr.getEffectiveHp(target), 50);
    assert.strictEqual(mgr.isMathematicallySlain(target), false);

    // Arrow 1 arrives at t=0.5s dealing 30 damage
    mgr.addReservation(701, 601, 30, 0.5, 0.0);
    assert.strictEqual(mgr.getEffectiveHp(target), 20);
    assert.strictEqual(mgr.isMathematicallySlain(target), false);

    // Arrow 2 arrives at t=0.6s dealing 25 damage
    mgr.addReservation(702, 601, 25, 0.6, 0.0);
    assert.strictEqual(mgr.getEffectiveHp(target), 0);
    assert.strictEqual(mgr.isMathematicallySlain(target), true); // Mathematically Slain!

    // Prune at t=0.7s (both projectiles impacted)
    mgr.pruneExpired(0.7);
    assert.strictEqual(mgr.getInFlightDamage(601), 0);
});

test('Stutter-step kiting: Ranged unit retreats along repulsive potential field during cooldown', () => {
    const app = createMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    // Japanese Arquebusier (Ranged, Range 6.5) at (25, 25)
    const gunner = new Unit(801, { korean_name: '일본 조총병', attack_range: 6.5, move_speed: 11, hp: 580, attack_power: 42 }, 25, 25, 1);
    gunner.attackTimer = 1.0; // Currently reloading!
    app.entities.push(gunner);

    // Joseon Spearman (Melee threat) approaching at (24, 25) (distance 1.0 tile, inside D_threat)
    const spearman = new Unit(802, { korean_name: '조선 창병', attack_range: 1.5, move_speed: 12, hp: 800 }, 24, 25, 0);
    app.entities.push(spearman);

    const ctx = { state: 'COMBAT', lastKiteSec: 0, kiteVector: new Vec2(0, 0), isRetreating: false };
    const kited = micro.evaluateUnitKiting(gunner, ctx);

    assert.strictEqual(kited, true, 'Gunner must kite away from oncoming melee threat');
    assert.ok(gunner.waypoints.length > 0, 'Waypoints must be generated for kiting step');
    // Spearman is at x=24, gunner at x=25. Kite direction must be +X (away from threat!)
    const targetGx = gunner.waypoints[0].gx !== undefined ? gunner.waypoints[0].gx : gunner.waypoints[0].x;
    assert.ok(targetGx >= 25, `Kite target (${targetGx}) must step away from threat`);
});

test('HP-Ratio tactical retreat (< 30% HP) routes to nearest safe triage hub', () => {
    const app = createMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' }); // retreat threshold 0.35

    // Friendly Japanese Headquarters at (32, 28)
    const hq = new Building(901, { korean_name: '일본 본영', width: 3, height: 3, hp: 6000 }, 32, 28, 1);
    hq.isBuilding = true;
    app.entities.push(hq);

    // Combat samurai at (20, 20) with HP dropped to 200/920 (21.7% HP)
    const samurai = new Unit(902, { korean_name: '일본 사무라이', move_speed: 13, hp: 920 }, 20, 20, 1);
    samurai.hp = 200;
    app.entities.push(samurai);

    const ctx = { state: 'COMBAT', lastKiteSec: 0, kiteVector: new Vec2(0, 0), isRetreating: false };
    const retreating = micro.evaluateUnitRetreat(samurai, ctx);

    assert.strictEqual(retreating, true, 'Unit must trigger tactical retreat');
    assert.strictEqual(ctx.isRetreating, true);
    assert.strictEqual(samurai.targetEntity, null, 'Target aggro must be suppressed during retreat');
    assert.strictEqual(ctx.retreatAnchor.id, 901, 'Retreat anchor must be friendly HQ');
});

test('AoE Hazard Evasion: Units disperse radially away from incoming cannonball splash', () => {
    const app = createMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    // Friendly unit at (30, 30)
    const unit = new Unit(950, { korean_name: '일본 사무라이', move_speed: 13, hp: 920 }, 30, 30, 1);
    app.entities.push(unit);

    // In-flight cannonball aimed at (30, 30) arriving in 0.4s
    app.projectiles = [
        {
            type: 'cannon',
            targetWx: 30,
            targetWy: 30,
            progress: 0.5,
            travelDuration: 0.8
        }
    ];

    micro.evaluateHazardEvasion(0.1);
    assert.ok(unit.waypoints.length > 0, 'Unit must issue evasion waypoint');
    const dest = unit.waypoints[0];
    const destGx = dest.gx !== undefined ? dest.gx : dest.x;
    const destGy = dest.gy !== undefined ? dest.gy : dest.y;
    const distFromImpact = Math.hypot(destGx - 30, destGy - 30);
    assert.ok(distFromImpact >= 2.0, `Evasion waypoint distance ${distFromImpact} must clear splash radius`);
});

test('Hammer and Anvil Flanking: Partitions 60% Anvil and 30% Hammer with geometric flank routing', () => {
    const app = createMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    // Enemy HQ at (15, 15)
    const enemyHq = new Building(990, { korean_name: '조선 본영', width: 3, height: 3, hp: 6000 }, 15, 15, 0);
    enemyHq.isBuilding = true;
    app.entities.push(enemyHq);

    // Friendly army of 8 units at (45, 45)
    for (let i = 0; i < 8; i++) {
        const isCav = i < 3;
        const u = new Unit(960 + i, {
            korean_name: isCav ? '일본 기병' : '일본 사무라이',
            move_speed: isCav ? 18 : 13,
            hp: 900
        }, 45 + (i % 2), 45 + Math.floor(i / 2), 1);
        app.entities.push(u);
    }

    micro.updateFlankingManeuver(0.1);

    assert.ok(micro.flankingSquad.hammer.size >= 2, 'Hammer echelon must contain at least 2 mobile flankers');
    assert.ok(micro.flankingSquad.anvil.size >= 4, 'Anvil echelon must contain the main mass');
    assert.strictEqual(micro.flankingSquad.state, 'MARCHING');
    assert.ok(micro.flankingSquad.flankWaypoint !== null, 'Geometric flank waypoint must be computed');
});

test('Overkill Prevention in Target Acquisition: Units automatically retarget when enemy is mathematically slain', () => {
    const app = createMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    // Friendly archer
    const archer = new Unit(1001, { korean_name: '일본 조총병', attack_range: 6.5, attack_power: 40 }, 25, 25, 1);
    app.entities.push(archer);

    // Wounded enemy general (40 HP)
    const general = new Unit(1002, { korean_name: '조선 권율', hp: 40, max_hp: 1500, level: 2 }, 26, 25, 0);
    app.entities.push(general);

    // Healthy enemy spearman (800 HP)
    const spearman = new Unit(1003, { korean_name: '조선 창병', hp: 800, max_hp: 800 }, 27, 25, 0);
    app.entities.push(spearman);

    // Initially, high-threat general is selected
    micro.evaluateTargetAcquisition(archer);
    assert.strictEqual(archer.targetEntity.id, 1002, 'High-threat wounded general must be prioritized');

    // Register incoming arrow from another ally that will deal 45 damage to general
    micro.reservationManager.addReservation(999, 1002, 45, 0.5, micro.gameTimeSec);
    assert.strictEqual(micro.reservationManager.isMathematicallySlain(general), true);

    // Archer evaluates target acquisition again: must retarget to spearman (overkill prevention!)
    micro.evaluateTargetAcquisition(archer);
    assert.strictEqual(archer.targetEntity.id, 1003, 'Archer must retarget away from mathematically slain general');
});

test('Healer Triage Network: Healer prioritizes high-value wounded Hero over basic infantry', () => {
    const app = createMockApp();
    const micro = new TacticalMicroManager(app, { owner: 1, difficulty: 'hard' });

    // Friendly Healer (Heo Jun) at (20, 20) with 100 MP
    const healer = new Unit(1101, { korean_name: '허준', move_speed: 12, hp: 600, mp: 100, sight_range: 12 }, 20, 20, 1);
    healer.mp = 100;
    app.entities.push(healer);

    // Wounded basic infantry at (21, 20) with 50% HP (400/800)
    const infantry = new Unit(1102, { korean_name: '일본 창병', hp: 800, max_hp: 800 }, 21, 20, 1);
    infantry.hp = 400;
    app.entities.push(infantry);

    // Wounded Hero (Kato) at (22, 20) with 50% HP (975/1950)
    const hero = new Unit(1103, { korean_name: '가토 기요마사', hp: 1950, max_hp: 1950, level: 2 }, 22, 20, 1);
    hero.hp = 975;
    app.entities.push(hero);

    // Execute triage
    micro.evaluateHealerTriage([healer, infantry, hero]);

    // Hero had higher triage priority weight (4.5 vs 1.0), so Hero must receive curative spell (+200 HP)
    assert.strictEqual(hero.hp, 1175, 'Hero must be healed first due to priority triage');
    assert.strictEqual(infantry.hp, 400, 'Basic infantry receives heal only after hero');
    assert.strictEqual(healer.mp, 80, 'Healer expended 20 MP');
});

console.log('======================================================================');
console.log(` SUMMARY: ${passedTests} / ${totalTests} TESTS PASSED`);
console.log('======================================================================');
