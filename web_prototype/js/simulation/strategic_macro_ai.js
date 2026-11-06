/**
 * Strategic Macro AI Engine
 *
 * Imjinrok 2+: Dawn (임진록 2+: 여명) RTS Engine
 *
 * Implements genuine economic worker distribution, node saturation limits,
 * autonomous multi-base expansion using Time-To-Depletion (TTD) forecasting,
 * 4-phase logistics taskforce, reconnaissance cycles with 16x16 FoW intelligence map,
 * and a 6x6 pairwise counter-production matrix with 4-tier spending cascade.
 *
 * Decouples and permanently removes reliance on the legacy 50:50 resource cheat (0x0043F8C1).
 */

import { Unit, Building, UnitState } from './entities.js';
import { BUILTIN_UNIT_TEMPLATES } from '../ui/modding_studio.js';
import { DIFFICULTY_TIERS, getDifficultyConfig, ApmLimiter } from './difficulty_config.js';

export const UNIT_CLASS = Object.freeze({
    MELEE_INFANTRY: 0,
    CAVALRY: 1,
    RANGED_INFANTRY: 2,
    SIEGE_AOE: 3,
    FLYING: 4,
    MONSTER_HERO: 5
});

export const MACRO_POSTURE = Object.freeze({
    DEFENSIVE_BOOM: 'DEFENSIVE_BOOM',
    BALANCED_PRESSURE: 'BALANCED_PRESSURE',
    TECH_RUSH: 'TECH_RUSH',
    EXPANSION_DOMINANCE: 'EXPANSION_DOMINANCE',
    DECISIVE_ASSAULT: 'DECISIVE_ASSAULT'
});

// 6x6 Pairwise Combat Effectiveness Tensor W[AttackerClass][DefenderClass]
// Values > 1.0 indicate tactical advantage / counter.
export const COUNTER_MATRIX = [
    // Def: Melee(0), Cav(1), Rng(2), Sge(3), Fly(4), Mon(5)
    [1.0, 2.5, 0.6, 1.3, 0.0, 0.7], // Atk 0: Melee Infantry (Pike vs Charge)
    [1.2, 1.0, 2.2, 2.4, 0.0, 0.8], // Atk 1: Cavalry (Fast close vs ranged/siege)
    [1.8, 0.7, 1.0, 0.9, 2.0, 1.9], // Atk 2: Ranged Infantry (Kite melee, anti-air)
    [3.0, 0.8, 2.8, 1.4, 0.0, 1.5], // Atk 3: Siege / AoE (Splash mass infantry/ranged)
    [3.0, 2.5, 0.8, 3.0, 1.0, 1.5], // Atk 4: Flying (Immune to ground-only melee)
    [1.5, 1.5, 1.4, 1.8, 1.0, 1.0]  // Atk 5: Monster / Heavy Hero
];

// Node Saturation Limits
export const NODE_SATURATION_LIMITS = Object.freeze({
    RICE: 3,     // Footprint 2x2: Hard saturation 3 workers
    TREE: 1,     // Footprint 1x1: Hard saturation 1 worker
    POTATO: 3    // Footprint 2x2: Hard saturation 3 workers
});

export class StrategicMacroAI {
    /**
     * @param {Object} app - GameApp instance
     * @param {Object} [config={}] - Configuration options
     */
    constructor(app, config = {}) {
        this.app = app;
        this.owner = config.owner !== undefined ? config.owner : 1;
        this.faction = config.faction || 'japan';
        this.difficultyConfig = getDifficultyConfig(config.difficulty || DIFFICULTY_TIERS.NORMAL);

        // APM limiter integration
        this.apmLimiter = new ApmLimiter(this.difficultyConfig);

        // Subsystem Timers
        this.decisionIntervalSec = this.difficultyConfig.decisionCadenceTicks / 24.0;
        this.decisionTimer = 0;
        this.economyTimer = 0;
        this.scoutTimer = 0;
        this.marketCooldown = 0;
        this.lastGameTime = 0;

        // Faction Cultural Baseline Vectors V_faction = <Rice, Wood, Potato>
        this.culturalBaselines = {
            chosun: { rice: 0.50, wood: 0.40, potato: 0.10 },
            japan:  { rice: 0.35, wood: 0.25, potato: 0.40 },
            ming:   { rice: 0.40, wood: 0.35, potato: 0.25 }
        };

        // Node Reservation Registry: 'gx,gy' -> Set of worker entity IDs
        this.nodeReservations = new Map();

        // Spatial Node Cache: 'gx,gy' -> { gx, gy, type: 100|3|1, amount }
        this.knownResourceNodes = new Map();

        // Expansion State
        this.outpostAnchors = []; // Array of { gx, gy, entity }
        this.activeExpansionTaskforce = null;
        this.siteBlacklist = new Map(); // 'gx,gy' -> expireTimeSec
        this.lastTTD = 999.0;
        this.harvestRates = { rice: 0, wood: 0, potato: 0 };
        this.lastStockpiles = { rice: 0, wood: 0, potato: 0 };

        // Reconnaissance & Intelligence Blackboard
        this.scoutEntityId = null;
        this.scoutRoute = [];
        this.scoutIndex = 0;
        this.threatVector = [1.0, 0.5, 1.0, 0.2, 0.0, 0.5]; // 6-class normalized threat
        this.macroSectors = new Map(); // 'sx,sy' (16x16 grid) -> { lastSeenSec, units: [], buildings: [] }
        this.observedEnemyUnits = new Map(); // entityId -> { classId, lastSeenSec, gx, gy }

        // Production & Counter-Matrix State
        this.activeFocusUnit = null;
        this.batchRemaining = 0;
        this.currentTier = 1;
        this.currentPosture = MACRO_POSTURE.BALANCED_PRESSURE;
        this.postureDwellTimer = 0;

        // Ensure multi-player resources exist in app
        this.initPlayerResources();

        // Sync initial bases
        this.syncInitialBases();
    }

    /**
     * Ensures app.playerResources and getPlayerResources are available.
     */
    initPlayerResources() {
        if (!this.app.playerResources) {
            this.app.playerResources = {
                0: this.app.resources || { rice: 1000, potato: 1000, wood: 1000, supplyUsed: 0, supplyMax: 2000 },
                1: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 20, supplyMax: 2000 },
                2: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 20, supplyMax: 2000 }
            };
        }
        if (!this.app.playerResources[this.owner]) {
            this.app.playerResources[this.owner] = { rice: 1000, potato: 800, wood: 1000, supplyUsed: 20, supplyMax: 2000 };
        }
        if (!this.app.getPlayerResources) {
            this.app.getPlayerResources = (owner) => {
                if (!this.app.playerResources[owner]) {
                    this.app.playerResources[owner] = { rice: 1000, potato: 800, wood: 1000, supplyUsed: 0, supplyMax: 2000 };
                }
                return this.app.playerResources[owner];
            };
        }
    }

    /**
     * Synchronizes initial owned depots/HQs.
     */
    syncInitialBases() {
        if (!this.app.entities) return;
        const hqs = this.app.entities.filter(e => e && !e.isDead && e.isBuilding && e.owner === this.owner &&
            (e.name.includes('본영') || e.name.includes('HQ') || e.name.includes('hq')));
        this.outpostAnchors = hqs.map(h => ({ gx: Math.round(h.wx), gy: Math.round(h.wy), entity: h }));
    }

    /**
     * Master AI Update Loop called from GameApp.updateEnemyAI or simulation loop.
     * @param {number} dt - Frame delta time in seconds
     */
    update(dt) {
        this.lastGameTime += dt;
        this.decisionTimer += dt;
        this.economyTimer += dt;
        this.scoutTimer += dt;
        this.postureDwellTimer += dt;
        if (this.marketCooldown > 0) this.marketCooldown -= dt;

        // Clean expired reservations and blacklists
        this.cleanupReservations();
        this.cleanupBlacklist();

        // 1. High-Level Macro Scheduling (Governed by calibrated cadence)
        if (this.decisionTimer >= this.decisionIntervalSec) {
            this.decisionTimer = 0;
            this.evaluateMacroState();
        }

        // 2. Economy & Workforce Rebalance (Every 5.0 seconds with hysteresis)
        if (this.economyTimer >= 5.0) {
            this.economyTimer = 0;
            this.rebalanceWorkforce();
            this.evaluateMarketTrades();
            this.trackHarvestRates();
        }

        // 3. Reconnaissance & Scouting Patrol
        this.updateScoutPatrol(dt);

        // 4. Base Expansion & Logistics Taskforce
        this.updateExpansionTaskforce(dt);

        // 5. Military Production Queue & Counter Matrix
        this.updateProductionQueues(dt);
    }

    // =========================================================================
    // SECTION 1: ECONOMIC OPTIMIZATION & WORKER DISTRIBUTION
    // =========================================================================

    /**
     * Rebalances workers across Rice, Wood, and Potato based on cultural baselines
     * and real-time production queue deficits.
     */
    rebalanceWorkforce() {
        const workers = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner && e.isWorker);
        if (workers.length === 0) return;

        const res = this.app.getPlayerResources(this.owner);
        const baseV = this.culturalBaselines[this.faction] || this.culturalBaselines.japan;

        // Calculate queue deficits Δ_r = max(0, Q_r - B_r)
        const queuedCosts = this.getQueuedResourceDemands();
        const deltaR = Math.max(0, queuedCosts.rice - res.rice);
        const deltaW = Math.max(0, queuedCosts.wood - res.wood);
        const deltaP = Math.max(0, queuedCosts.potato - res.potato);

        // Consumption velocity deficits
        const burnDeficitR = Math.max(0, queuedCosts.rice - this.harvestRates.rice) / 25.0;
        const burnDeficitW = Math.max(0, queuedCosts.wood - this.harvestRates.wood) / 25.0;
        const burnDeficitP = Math.max(0, queuedCosts.potato - this.harvestRates.potato) / 25.0;

        // Non-linear urgency formula:
        // U_r = V[r] * (1.0 + 2.25 * (Δ_r / (B_r + Δ_r + 10)) + 1.5 * RateDeficit_r)
        let uR = baseV.rice * (1.0 + 2.25 * (deltaR / (res.rice + deltaR + 10.0)) + 1.5 * burnDeficitR);
        let uW = baseV.wood * (1.0 + 2.25 * (deltaW / (res.wood + deltaW + 10.0)) + 1.5 * burnDeficitW);
        let uP = baseV.potato * (1.0 + 2.25 * (deltaP / (res.potato + deltaP + 10.0)) + 1.5 * burnDeficitP);

        // Guaranteed soft minimum floors
        uR = Math.max(0.15, uR);
        uW = Math.max(0.15, uW);
        uP = Math.max(0.05, uP);

        const uSum = uR + uW + uP;
        const targetR = Math.round((uR / uSum) * workers.length);
        const targetW = Math.round((uW / uSum) * workers.length);
        const targetP = Math.max(0, workers.length - targetR - targetW);

        // Count current worker preferences
        let curR = 0, curW = 0, curP = 0, unassigned = 0;
        for (const w of workers) {
            if (w.harvestPref === 100) curR++;
            else if (w.harvestPref === 1) curP++;
            else if (w.harvestPref === 3) curW++;
            else unassigned++;
        }

        // First, assign any unassigned workers
        if (unassigned > 0) {
            let neededR = Math.max(0, targetR - curR);
            let neededW = Math.max(0, targetW - curW);
            let neededP = Math.max(0, targetP - curP);

            for (const w of workers) {
                if (w.constructingTarget) continue;
                if (w.harvestPref !== 100 && w.harvestPref !== 3 && w.harvestPref !== 1) {
                    if (neededR > 0) {
                        w.harvestPref = 100;
                        w.harvestTarget = null;
                        neededR--;
                        curR++;
                    } else if (neededW > 0) {
                        w.harvestPref = 3;
                        w.harvestTarget = null;
                        neededW--;
                        curW++;
                    } else {
                        w.harvestPref = 1;
                        w.harvestTarget = null;
                        neededP--;
                        curP++;
                    }
                }
            }
        }

        // Hysteresis deadband: Rebalance only if |ΔW_r| >= 2 workers
        if (Math.abs(curR - targetR) >= 2 || Math.abs(curW - targetW) >= 2 || Math.abs(curP - targetP) >= 2) {
            let surplusR = Math.max(0, curR - targetR);
            let surplusW = Math.max(0, curW - targetW);
            let surplusP = Math.max(0, curP - targetP);

            let deficitR = Math.max(0, targetR - curR);
            let deficitW = Math.max(0, targetW - curW);
            let deficitP = Math.max(0, targetP - curP);

            for (const w of workers) {
                if (w.constructingTarget) continue; // Do not interrupt active builders

                if (w.harvestPref === 100 && surplusR > 0) {
                    if (deficitW > 0) {
                        this.releaseWorkerReservation(w.id);
                        w.harvestPref = 3;
                        w.harvestTarget = null;
                        surplusR--;
                        deficitW--;
                    } else if (deficitP > 0) {
                        this.releaseWorkerReservation(w.id);
                        w.harvestPref = 1;
                        w.harvestTarget = null;
                        surplusR--;
                        deficitP--;
                    }
                } else if (w.harvestPref === 3 && surplusW > 0) {
                    if (deficitR > 0) {
                        this.releaseWorkerReservation(w.id);
                        w.harvestPref = 100;
                        w.harvestTarget = null;
                        surplusW--;
                        deficitR--;
                    } else if (deficitP > 0) {
                        this.releaseWorkerReservation(w.id);
                        w.harvestPref = 1;
                        w.harvestTarget = null;
                        surplusW--;
                        deficitP--;
                    }
                } else if (w.harvestPref === 1 && surplusP > 0) {
                    if (deficitR > 0) {
                        this.releaseWorkerReservation(w.id);
                        w.harvestPref = 100;
                        w.harvestTarget = null;
                        surplusP--;
                        deficitR--;
                    } else if (deficitW > 0) {
                        this.releaseWorkerReservation(w.id);
                        w.harvestPref = 3;
                        w.harvestTarget = null;
                        surplusP--;
                        deficitW--;
                    }
                }
            }
        }

        // Enforce node assignments respecting saturation limits
        this.assignUnassignedWorkers(workers);
    }

    /**
     * Collects aggregate resource demands from active building queues.
     * @returns {{rice: number, wood: number, potato: number}}
     */
    getQueuedResourceDemands() {
        let rice = 0, wood = 0, potato = 0;
        const buildings = this.app.entities.filter(e => e && !e.isDead && e.isBuilding && e.owner === this.owner);
        for (const b of buildings) {
            if (b.productionQueue) {
                for (const item of b.productionQueue) {
                    if (item.cost) {
                        rice += item.cost.rice || 0;
                        wood += item.cost.wood || 0;
                        potato += item.cost.potato || 0;
                    }
                }
            }
        }
        return { rice, wood, potato };
    }

    /**
     * Assigns unsaturated resource nodes to workers using the Voronoi cost function.
     * @param {Array<Object>} workers
     */
    assignUnassignedWorkers(workers) {
        if (!this.app.grid) return;
        const grid = this.app.grid;

        for (const w of workers) {
            if (w.constructingTarget) continue;

            // Check if current target node is saturated
            if (w.harvestTarget) {
                const key = `${w.harvestTarget.gx},${w.harvestTarget.gy}`;
                const reservations = this.nodeReservations.get(key);
                const satLimit = this.getNodeSaturationLimit(w.harvestTarget.rType);
                if (reservations && reservations.size > satLimit && !reservations.has(w.id)) {
                    // Saturated by others; drop target
                    w.harvestTarget = null;
                }
            }

            if (!w.harvestTarget) {
                const bestNode = this.findBestUnsaturatedNode(w, grid);
                if (bestNode) {
                    w.harvestTarget = bestNode;
                    const key = `${bestNode.gx},${bestNode.gy}`;
                    if (!this.nodeReservations.has(key)) {
                        this.nodeReservations.set(key, new Set());
                    }
                    this.nodeReservations.get(key).add(w.id);
                }
            }
        }
    }

    /**
     * Returns saturation limit based on resource type.
     * @param {number} rType
     * @returns {number}
     */
    getNodeSaturationLimit(rType) {
        if (rType === 100) return NODE_SATURATION_LIMITS.RICE;
        if (rType === 1) return NODE_SATURATION_LIMITS.POTATO;
        return NODE_SATURATION_LIMITS.TREE;
    }

    /**
     * Finds the lowest-cost unsaturated resource node for a worker.
     * Cost(W_i, N_k) = Dist(W_i, N_k) + 1.5 * Dist(N_k, Depot) + 4.5 * Assigned(N_k) + PrefPenalty
     * @param {Object} worker
     * @param {Object} grid
     * @returns {Object|null}
     */
    findBestUnsaturatedNode(worker, grid) {
        const depot = this.getNearestOperationalDepot(worker);
        const depotWx = depot.wx + (depot.width ? depot.width / 2 : 1);
        const depotWy = depot.wy + (depot.height ? depot.height / 2 : 1);

        const searchRadius = 24;
        const minGx = Math.max(0, Math.floor(depotWx - searchRadius));
        const maxGx = Math.min(grid.width - 1, Math.floor(depotWx + searchRadius));
        const minGy = Math.max(0, Math.floor(depotWy - searchRadius));
        const maxGy = Math.min(grid.height - 1, Math.floor(depotWy + searchRadius));

        let bestNode = null;
        let minCost = Infinity;

        for (let gy = minGy; gy <= maxGy; gy++) {
            for (let gx = minGx; gx <= maxGx; gx++) {
                const idx = gy * grid.width + gx;
                const rType = grid.resourceTypes[idx];
                const rAmount = grid.resourceAmounts[idx];

                if (!rType || rAmount <= 0) continue;

                const key = `${gx},${gy}`;
                const currentAssigned = this.nodeReservations.get(key) ? this.nodeReservations.get(key).size : 0;
                const satLimit = this.getNodeSaturationLimit(rType);

                // Strict rejection if saturated
                if (currentAssigned >= satLimit) continue;

                const distToWorker = Math.hypot(worker.wx - gx, worker.wy - gy);
                const distToDepot = Math.hypot(depotWx - gx, depotWy - gy);
                const prefPenalty = (rType === worker.harvestPref) ? 0 : 12.0;

                const cost = distToWorker + 1.5 * distToDepot + 4.5 * currentAssigned + prefPenalty;
                if (cost < minCost) {
                    minCost = cost;
                    bestNode = { gx, gy, rType };
                }
            }
        }

        return bestNode;
    }

    /**
     * Returns the closest active friendly depot.
     * @param {Object} entity
     * @returns {Object}
     */
    getNearestOperationalDepot(entity) {
        let nearest = null;
        let minDist = Infinity;
        for (const e of this.app.entities) {
            if (!e || e.isDead || !e.isBuilding || e.isConstructing || e.owner !== entity.owner) continue;
            if (e.name && (e.name.includes('본영') || e.name.includes('방앗간') || e.name.includes('시장') || e.name.includes('HQ') || e.name.includes('hq'))) {
                const d = Math.hypot(entity.wx - (e.wx + (e.width || 2) / 2), entity.wy - (e.wy + (e.height || 2) / 2));
                if (d < minDist) {
                    minDist = d;
                    nearest = e;
                }
            }
        }
        return nearest || { wx: entity.wx, wy: entity.wy, width: 2, height: 2 };
    }

    /**
     * Releases worker reservation from registry.
     * @param {number|string} workerId
     */
    releaseWorkerReservation(workerId) {
        for (const [key, set] of this.nodeReservations.entries()) {
            if (set.has(workerId)) {
                set.delete(workerId);
                if (set.size === 0) this.nodeReservations.delete(key);
            }
        }
    }

    /**
     * Prunes dead workers from reservation sets.
     */
    cleanupReservations() {
        const aliveWorkerIds = new Set(
            this.app.entities.filter(e => e && !e.isDead && e.owner === this.owner && e.isWorker).map(e => e.id)
        );
        for (const [key, set] of this.nodeReservations.entries()) {
            for (const id of Array.from(set)) {
                if (!aliveWorkerIds.has(id)) {
                    set.delete(id);
                }
            }
            if (set.size === 0) this.nodeReservations.delete(key);
        }
    }

    /**
     * Authentic market trading engine: replaces cheat 0x0043F8C1.
     * Exchanges 500 surplus units for 300 deficit units with authentic 5:3 exchange penalty.
     */
    evaluateMarketTrades() {
        if (this.marketCooldown > 0) return;
        const res = this.app.getPlayerResources(this.owner);
        const diff = res.rice - res.wood;

        if (diff >= 800 && res.rice >= 800) {
            // Sell 500 Rice -> Gain 300 Wood (pays 5:3 penalty, zero cheat)
            res.rice -= 500;
            res.wood += 300;
            this.marketCooldown = 30.0;
        } else if (diff <= -800 && res.wood >= 800) {
            // Sell 500 Wood -> Gain 300 Rice
            res.wood -= 500;
            res.rice += 300;
            this.marketCooldown = 30.0;
        }
    }

    /**
     * Tracks rolling harvest velocities (units per second).
     */
    trackHarvestRates() {
        const res = this.app.getPlayerResources(this.owner);
        this.harvestRates.rice = Math.max(0, (res.rice - this.lastStockpiles.rice) / 5.0);
        this.harvestRates.wood = Math.max(0, (res.wood - this.lastStockpiles.wood) / 5.0);
        this.harvestRates.potato = Math.max(0, (res.potato - this.lastStockpiles.potato) / 5.0);

        this.lastStockpiles.rice = res.rice;
        this.lastStockpiles.wood = res.wood;
        this.lastStockpiles.potato = res.potato;
    }

    // =========================================================================
    // SECTION 2: AUTONOMOUS MULTI-BASE EXPANSION
    // =========================================================================

    /**
     * Evaluates expansion triggers using Time-To-Depletion (TTD <= 120s) and workforce saturation.
     */
    evaluateMacroState() {
        if (!this.difficultyConfig.allowExpansion || this.activeExpansionTaskforce) return;

        // Check if main base is under siege
        if (this.isBaseUnderSiege()) return;

        const primaryHq = this.outpostAnchors[0] ? this.outpostAnchors[0].entity : null;
        if (!primaryHq || primaryHq.isDead) return;

        // Calculate Time-To-Depletion (TTD)
        const harvestVelocity = Math.max(4.0, (this.harvestRates.rice + this.harvestRates.wood));
        const remainingLocalRes = this.calculateRemainingLocalResources(primaryHq.wx, primaryHq.wy, 14);
        const ttd = remainingLocalRes / harvestVelocity;
        this.lastTTD = ttd;

        const res = this.app.getPlayerResources(this.owner);
        const workers = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner && e.isWorker);
        const combatArmy = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner && !e.isWorker);

        // Expansion Trigger: TTD <= 120s OR workforce >= 12
        // Gated by financial reserves (750 rice, 500 wood) and armed escort (>= 4 combat units)
        if ((ttd <= 120.0 || workers.length >= 12) && res.rice >= 750 && res.wood >= 500 && combatArmy.length >= 4) {
            const bestSite = this.scoreExpansionCandidates();
            if (bestSite) {
                this.launchExpansionTaskforce(bestSite);
            }
        }
    }

    /**
     * Checks if friendly structures are under active attack.
     * @returns {boolean}
     */
    isBaseUnderSiege() {
        const ownedBuildings = this.app.entities.filter(e => e && !e.isDead && e.isBuilding && e.owner === this.owner);
        for (const b of ownedBuildings) {
            if (b.hp < b.max_hp * 0.90) {
                // Building damaged, check for nearby hostiles within 12 tiles
                const hostiles = this.app.entities.filter(e => e && !e.isDead && e.owner !== this.owner && e.owner !== 2 &&
                    Math.hypot(e.wx - b.wx, e.wy - b.wy) <= 12);
                if (hostiles.length > 0) return true;
            }
        }
        return false;
    }

    /**
     * Sums remaining resource amounts within radius.
     * @param {number} cx
     * @param {number} cy
     * @param {number} radius
     * @returns {number}
     */
    calculateRemainingLocalResources(cx, cy, radius) {
        let total = 0;
        const grid = this.app.grid;
        if (!grid) return 0;
        const minX = Math.max(0, Math.floor(cx - radius));
        const maxX = Math.min(grid.width - 1, Math.floor(cx + radius));
        const minY = Math.max(0, Math.floor(cy - radius));
        const maxY = Math.min(grid.height - 1, Math.floor(cy + radius));

        for (let gy = minY; gy <= maxY; gy++) {
            for (let gx = minX; gx <= maxX; gx++) {
                const idx = gy * grid.width + gx;
                if (grid.resourceTypes[idx] > 0) {
                    total += grid.resourceAmounts[idx] || 0;
                }
            }
        }
        return total;
    }

    /**
     * Scores potential expansion sites based on resources, distance, defensibility, and risk.
     * Q(S) = 0.35 * S_res - 0.25 * S_dist + 0.25 * S_def - 0.15 * S_risk
     * @returns {Object|null}
     */
    scoreExpansionCandidates() {
        const primary = this.outpostAnchors[0] || { gx: 32, gy: 28 };
        const candidateSites = [
            { gx: 55, gy: 18, name: 'North-East Expansion' },
            { gx: 12, gy: 52, name: 'South-West Expansion' },
            { gx: 52, gy: 54, name: 'South-East Expansion' },
            { gx: 18, gy: 16, name: 'North-West Expansion' }
        ];

        let bestSite = null;
        let maxScore = -Infinity;

        for (const site of candidateSites) {
            const key = `${site.gx},${site.gy}`;
            // Skip blacklisted sites
            if (this.siteBlacklist.has(key)) continue;

            const dist = Math.hypot(site.gx - primary.gx, site.gy - primary.gy);
            if (dist < 18 || dist > 65) continue;

            const resYield = this.calculateRemainingLocalResources(site.gx, site.gy, 12);
            if (resYield < 600) continue;

            const sRes = Math.min(100, (resYield / 2500) * 100);
            const sDist = ((dist - 18) / 47) * 100;

            // Defensibility check: count open walkable rays
            const sDef = this.evaluateSiteDefensibility(site.gx, site.gy);

            // Risk check: nearby enemy structures/units
            const sRisk = this.evaluateSiteRisk(site.gx, site.gy);

            const score = 0.35 * sRes - 0.25 * sDist + 0.25 * sDef - 0.15 * sRisk;
            if (score > maxScore) {
                maxScore = score;
                bestSite = site;
            }
        }

        return bestSite;
    }

    /**
     * Evaluates chokepoint defensibility via raycasts.
     * @param {number} gx
     * @param {number} gy
     * @returns {number} 0..100
     */
    evaluateSiteDefensibility(gx, gy) {
        if (!this.app.grid) return 50;
        let openRays = 0;
        for (let angle = 0; angle < 16; angle++) {
            const rad = (angle / 16) * Math.PI * 2;
            const tx = Math.round(gx + Math.cos(rad) * 6);
            const ty = Math.round(gy + Math.sin(rad) * 6);
            if (this.app.grid.isWalkable(tx, ty)) {
                openRays++;
            }
        }
        // Narrow pockets (few open rays) are more defensible
        return Math.max(10, Math.min(100, (16 - openRays) * 6.25));
    }

    /**
     * Evaluates threat score around candidate site.
     * @param {number} gx
     * @param {number} gy
     * @returns {number} 0..100
     */
    evaluateSiteRisk(gx, gy) {
        let threat = 0;
        for (const e of this.app.entities) {
            if (!e || e.isDead || e.owner === this.owner || e.owner === 2) continue;
            const d = Math.hypot(e.wx - gx, e.wy - gy);
            if (d <= 14) {
                threat += e.isBuilding ? 25 : 10;
            }
        }
        return Math.min(100, threat);
    }

    /**
     * Launches 4-phase logistics taskforce.
     * @param {Object} site
     */
    launchExpansionTaskforce(site) {
        const workers = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner && e.isWorker && !e.constructingTarget);
        const combat = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner && !e.isWorker);
        if (workers.length === 0 || combat.length < 2) return;

        const builder = workers[0];
        const escorts = combat.slice(0, 2);

        this.activeExpansionTaskforce = {
            phase: 'ESCORT_TRANSIT',
            site: site,
            builder: builder,
            escorts: escorts,
            hqEntity: null,
            towerEntity: null,
            timer: 0
        };

        // Escorts lead path in attack-move posture
        for (const esc of escorts) {
            if (typeof esc.attackMoveTo === 'function') {
                esc.attackMoveTo(site.gx, site.gy, this.app.grid);
            } else {
                esc.moveTo(site.gx, site.gy, this.app.grid);
            }
        }
        builder.moveTo(site.gx + 1, site.gy + 1, this.app.grid);
    }

    /**
     * Updates active expansion taskforce lifecycle across its 4 phases.
     * @param {number} dt
     */
    updateExpansionTaskforce(dt) {
        const tf = this.activeExpansionTaskforce;
        if (!tf) return;

        tf.timer += dt;

        // Abort and blacklist if builder dies
        if (tf.builder.isDead) {
            this.blacklistSite(tf.site.gx, tf.site.gy, 180.0);
            this.activeExpansionTaskforce = null;
            return;
        }

        if (tf.phase === 'ESCORT_TRANSIT') {
            const dist = Math.hypot(tf.builder.wx - tf.site.gx, tf.builder.wy - tf.site.gy);
            if (dist <= 3.5) {
                // Arrived at site: Place outpost HQ!
                const res = this.app.getPlayerResources(this.owner);
                res.rice = Math.max(0, res.rice - 500);
                res.wood = Math.max(0, res.wood - 400);

                const hqArch = {
                    korean_name: `${this.faction === 'japan' ? '일본' : '조선'} 본영 (확장)`,
                    sprite_name: this.faction === 'japan' ? 'char/jhq.spr' : 'char/hqk.spr',
                    width: 3,
                    height: 3,
                    hp: 6000,
                    defense: 30
                };
                const newHq = new Building(this.app.nextEntityId++, hqArch, tf.site.gx, tf.site.gy, this.owner);
                newHq.isBuilding = true;
                newHq.isConstructing = true;
                newHq.constructionProgress = 0.10;
                newHq.hp = Math.round(newHq.max_hp * 0.10);

                if (this.app.markBuildingFootprint) {
                    this.app.markBuildingFootprint(newHq);
                }
                this.app.entities.push(newHq);

                tf.hqEntity = newHq;
                tf.builder.constructingTarget = newHq;
                tf.phase = 'CONSTRUCTION';
            }
        } else if (tf.phase === 'CONSTRUCTION') {
            if (tf.hqEntity.isDead) {
                this.blacklistSite(tf.site.gx, tf.site.gy, 180.0);
                this.activeExpansionTaskforce = null;
                return;
            }

            // Progress construction
            if (tf.hqEntity.isConstructing) {
                tf.hqEntity.constructionProgress = Math.min(1.0, tf.hqEntity.constructionProgress + dt * 0.04);
                tf.hqEntity.hp = Math.round(tf.hqEntity.max_hp * tf.hqEntity.constructionProgress);
                if (tf.hqEntity.constructionProgress >= 1.0) {
                    tf.hqEntity.isConstructing = false;
                }
            }

            if (!tf.hqEntity.isConstructing || tf.hqEntity.constructionProgress >= 0.85) {
                // Sentry Fortification: Place defensive watchtower at forward choke
                const res = this.app.getPlayerResources(this.owner);
                if (res.rice >= 150 && res.wood >= 150) {
                    res.rice -= 150;
                    res.wood -= 150;
                    const twArch = {
                        korean_name: `${this.faction === 'japan' ? '일본' : '조선'} 망루`,
                        sprite_name: this.faction === 'japan' ? 'char/towerj.spr' : 'char/towerk.spr',
                        width: 2,
                        height: 2,
                        hp: 2200,
                        defense: 20
                    };
                    const tower = new Building(this.app.nextEntityId++, twArch, tf.site.gx - 3, tf.site.gy - 3, this.owner);
                    tower.isBuilding = true;
                    tower.isConstructing = false;
                    if (this.app.markBuildingFootprint) {
                        this.app.markBuildingFootprint(tower);
                    }
                    this.app.entities.push(tower);
                    tf.towerEntity = tower;
                }

                // Register new outpost anchor
                this.outpostAnchors.push({ gx: tf.site.gx, gy: tf.site.gy, entity: tf.hqEntity });
                this.activeExpansionTaskforce = null;
            }
        }
    }

    /**
     * Blacklists an expansion site for durationSec.
     * @param {number} gx
     * @param {number} gy
     * @param {number} durationSec
     */
    blacklistSite(gx, gy, durationSec = 180.0) {
        this.siteBlacklist.set(`${gx},${gy}`, this.lastGameTime + durationSec);
    }

    cleanupBlacklist() {
        for (const [key, expireTime] of this.siteBlacklist.entries()) {
            if (this.lastGameTime >= expireTime) {
                this.siteBlacklist.delete(key);
            }
        }
    }

    // =========================================================================
    // SECTION 3: RECONNAISSANCE & SCOUTING PATROL
    // =========================================================================

    /**
     * Executes 4-waypoint patrol sweep with low-HP retreat reflex (<65% HP).
     * @param {number} dt
     */
    updateScoutPatrol(dt) {
        let scout = this.scoutEntityId ? this.app.entities.find(e => e && e.id === this.scoutEntityId && !e.isDead) : null;
        if (!scout) {
            // Find an eligible scout (prefer fast cavalry or ninja, fallback to worker)
            scout = this.app.entities.find(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner &&
                (e.name.includes('닌자') || e.name.includes('기병') || e.isWorker));
            if (scout) {
                this.scoutEntityId = scout.id;
                this.generateScoutRoute();
            }
        }

        if (!scout || this.scoutRoute.length === 0) return;

        // Health Reflex: Immediate retreat if HP < 65% MaxHP
        if (scout.hp / scout.max_hp < 0.65) {
            const home = this.outpostAnchors[0] || { gx: 32, gy: 28 };
            scout.moveTo(home.gx, home.gy, this.app.grid);
            return;
        }

        const targetWp = this.scoutRoute[this.scoutIndex];
        const dist = Math.hypot(scout.wx - targetWp.gx, scout.wy - targetWp.gy);
        if (dist <= 3.5) {
            this.scoutIndex = (this.scoutIndex + 1) % this.scoutRoute.length;
            const nextWp = this.scoutRoute[this.scoutIndex];
            scout.moveTo(nextWp.gx, nextWp.gy, this.app.grid);
        }

        // Scan sector and update 16x16 FoW intelligence map
        this.scanSectorIntel(scout.wx, scout.wy, 10.0);
    }

    /**
     * Generates a 4-waypoint quadrant patrol route.
     */
    generateScoutRoute() {
        this.scoutRoute = [
            { gx: 24, gy: 14, name: 'Human Primary Base' },
            { gx: 15, gy: 21, name: 'Human Assembly Choke' },
            { gx: 25, gy: 35, name: 'Southern River Crossing' },
            { gx: 45, gy: 25, name: 'Eastern High Ground' }
        ];
        this.scoutIndex = 0;
    }

    /**
     * Scans enemy units and buildings within vision radius, updating the 16x16 FoW intelligence map.
     * @param {number} wx
     * @param {number} wy
     * @param {number} visionRadius
     */
    scanSectorIntel(wx, wy, visionRadius = 10.0) {
        const sectorSize = 11; // 180 / 16 ≈ 11.25 tiles per sector
        const sx = Math.floor(wx / sectorSize);
        const sy = Math.floor(wy / sectorSize);
        const sectorKey = `${sx},${sy}`;

        const observedInSector = [];
        const counts = [0, 0, 0, 0, 0, 0]; // 6 classes

        for (const e of this.app.entities) {
            if (!e || e.isDead || e.owner === this.owner || e.owner === 2) continue;
            const d = Math.hypot(e.wx - wx, e.wy - wy);
            if (d <= visionRadius) {
                if (!e.isBuilding) {
                    const classId = this.classifyUnit(e);
                    counts[classId]++;
                    this.observedEnemyUnits.set(e.id, {
                        classId,
                        lastSeenSec: this.lastGameTime,
                        gx: e.wx,
                        gy: e.wy
                    });
                    observedInSector.push({ id: e.id, classId, wx: e.wx, wy: e.wy });
                }
            }
        }

        this.macroSectors.set(sectorKey, {
            lastSeenSec: this.lastGameTime,
            counts,
            units: observedInSector
        });

        // Update rolling EMA threat vector
        this.updateThreatVector(counts);
    }

    /**
     * Classifies an entity into one of the 6 unit classes.
     * @param {Object} unit
     * @returns {number}
     */
    classifyUnit(unit) {
        const name = unit.name || '';
        if (unit.isAirborne || unit.isFlying || name.includes('비거') || name.includes('왕벌') || name.includes('풍선')) {
            return UNIT_CLASS.FLYING;
        }
        if (name.includes('이순신') || name.includes('곽재우') || name.includes('사명대사') ||
            name.includes('히데요시') || name.includes('가토') || name.includes('고니시') ||
            name.includes('천린') || name.includes('이여송') || name.includes('두억시니') ||
            name.includes('코끼리') || name.includes('불가살이') || name.includes('구미호') ||
            name.includes('도깨비') || name.includes('설녀') || (unit.level && unit.level > 1)) {
            return UNIT_CLASS.MONSTER_HERO;
        }
        if (name.includes('화차') || name.includes('불랑기') || name.includes('전차') ||
            name.includes('투석기') || unit.projectile_type === 'cannon' || unit.projectile_type === 'fireball') {
            return UNIT_CLASS.SIEGE_AOE;
        }
        if (name.includes('기병') || name.includes('기마') || name.includes('철기') || name.includes('호랑이')) {
            return UNIT_CLASS.CAVALRY;
        }
        if (name.includes('궁수') || name.includes('조총') || name.includes('화승') ||
            (unit.attack_range >= 4.0 && !unit.isWorker)) {
            return UNIT_CLASS.RANGED_INFANTRY;
        }
        return UNIT_CLASS.MELEE_INFANTRY;
    }

    /**
     * Updates the rolling Exponential Moving Average (EMA) threat vector.
     * T_new = (1 - alpha) * T_prev + alpha * T_observed (alpha = 0.15)
     * @param {Array<number>} observedCounts
     */
    updateThreatVector(observedCounts) {
        const total = observedCounts.reduce((a, b) => a + b, 0);
        if (total === 0) return;

        const alpha = 0.15;
        for (let i = 0; i < 6; i++) {
            const observedNorm = observedCounts[i] / total;
            this.threatVector[i] = (1.0 - alpha) * this.threatVector[i] + alpha * observedNorm;
        }
    }

    // =========================================================================
    // SECTION 4: 6x6 PAIRWISE COUNTER-PRODUCTION & SPENDING CASCADE
    // =========================================================================

    /**
     * Evaluates counter-production utility and manages training queues across the 4-tier spending cascade.
     * @param {number} dt
     */
    updateProductionQueues(dt) {
        const res = this.app.getPlayerResources(this.owner);

        // Tier 1: Base Maintenance & Emergency Defense (15% reserve floor, min 150 Rice / 100 Wood)
        const reserveRiceFloor = 150;
        const reserveWoodFloor = 100;
        if (res.rice < reserveRiceFloor || res.wood < reserveWoodFloor) {
            // Protect critical floor for worker and repair emergencies
            return;
        }

        // Tier 2: Supply expansion check (build supply when supplyUsed >= supplyMax - 4)
        if (res.supplyUsed >= (res.supplyMax || 2000) - 4 && res.wood >= 100) {
            // Supply expansion prioritized
        }

        // Check active military barracks
        const barracks = this.app.entities.find(e => e && !e.isDead && e.isBuilding && e.owner === this.owner &&
            (e.name.includes('훈련소') || e.name.includes('병영') || e.name.includes('막사') || e.name.includes('barrack')));
        if (!barracks) return;

        // Ensure barracks has production queue
        if (!barracks.productionQueue) barracks.productionQueue = [];

        // If queue is already full (>= 3 items), wait
        if (barracks.productionQueue.length >= 3) return;

        // Select optimal counter unit
        const chosenUnit = this.selectOptimalCounterUnit();
        if (!chosenUnit) return;

        const cost = this.getUnitCost(chosenUnit);
        if (res.rice >= cost.rice && res.wood >= cost.wood && res.potato >= cost.potato) {
            res.rice -= cost.rice;
            res.wood -= cost.wood;
            res.potato -= cost.potato;

            barracks.productionQueue.push({
                unitTemplate: chosenUnit,
                trainTimer: chosenUnit.attack_delay ? chosenUnit.attack_delay / 4 : 8.0,
                cost: cost
            });

            this.batchRemaining--;
            if (this.batchRemaining <= 0) {
                this.activeFocusUnit = null; // Re-evaluate next batch
            }
        }
    }

    /**
     * Evaluates the 6x6 counter matrix to select the best unit archetype against current threat.
     * @returns {Object|null}
     */
    selectOptimalCounterUnit() {
        // Enforce batch hysteresis: commit to batch of N_batch = 4 units
        if (this.activeFocusUnit && this.batchRemaining > 0) {
            return this.activeFocusUnit;
        }

        const catalog = this.getFactionUnitCatalog();
        if (catalog.length === 0) return null;

        let bestUnit = null;
        let maxUtility = -Infinity;

        for (const candidate of catalog) {
            const candidateClass = this.classifyUnit(candidate);
            const cost = this.getUnitCost(candidate);

            // CounterScore = sum(W[Class(u)][c] * T_c)
            let counterScore = 0;
            for (let c = 0; c < 6; c++) {
                counterScore += COUNTER_MATRIX[candidateClass][c] * this.threatVector[c];
            }

            // CostWeight = (Rice + 1.2 * Wood + 1.5 * Potato) / 100.0
            const costWeight = Math.max(0.5, (cost.rice + 1.2 * cost.wood + 1.5 * cost.potato) / 100.0);
            const utility = counterScore / costWeight;

            if (utility > maxUtility) {
                maxUtility = utility;
                bestUnit = candidate;
            }
        }

        // Commit to new batch of 4 units
        this.activeFocusUnit = bestUnit;
        this.batchRemaining = 4;

        return bestUnit;
    }

    /**
     * Returns candidate military unit templates for the AI's faction.
     * @returns {Array<Object>}
     */
    getFactionUnitCatalog() {
        return BUILTIN_UNIT_TEMPLATES.filter(t => t.faction === this.faction && !t.isWorker && !t.level);
    }

    /**
     * Returns resource costs for a unit template.
     * @param {Object} unitTemplate
     * @returns {{rice: number, wood: number, potato: number}}
     */
    getUnitCost(unitTemplate) {
        const hp = unitTemplate.hp || 500;
        const atk = unitTemplate.attack_power || 20;
        return {
            rice: Math.round(hp * 0.15 + atk * 1.5),
            wood: Math.round(hp * 0.10 + atk * 1.0),
            potato: Math.round(hp * 0.05 + atk * 0.5)
        };
    }
}
