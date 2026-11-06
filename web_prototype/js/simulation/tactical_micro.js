/**
 * Tactical Micro AI Engine
 *
 * Imjinrok 2+: Dawn (임진록 2+: 여명) RTS Engine
 *
 * Implements weapon-cooldown synchronized stutter-step kiting,
 * HP-ratio tactical retreat to healer triage hubs and defensive watchtowers,
 * predictive AoE artillery and splash hazard evasion,
 * multi-directional Hammer and Anvil flanking coordination,
 * and overkill prevention via in-flight projectile damage reservation tracking.
 */

import { Unit, Building, UnitState } from './entities.js';
import { PathFinder } from './pathfinding.js';
import { CombatSystem } from './combat.js';
import { DIFFICULTY_TIERS, getDifficultyConfig, ApmLimiter } from './difficulty_config.js';

/**
 * 2D Vector Mathematics Helper
 */
export class Vec2 {
    constructor(x = 0, y = 0) {
        this.x = x;
        this.y = y;
    }

    static fromEntity(ent) {
        return new Vec2(ent.wx, ent.wy);
    }

    dist(other) {
        return Math.hypot(this.x - other.x, this.y - other.y);
    }

    length() {
        return Math.hypot(this.x, this.y);
    }

    normalize() {
        const len = this.length();
        if (len < 1e-5) return new Vec2(0, 0);
        return new Vec2(this.x / len, this.y / len);
    }

    add(other) {
        return new Vec2(this.x + other.x, this.y + other.y);
    }

    sub(other) {
        return new Vec2(this.x - other.x, this.y - other.y);
    }

    mul(scalar) {
        return new Vec2(this.x * scalar, this.y * scalar);
    }

    dot(other) {
        return this.x * other.x + this.y * other.y;
    }

    perpendicular() {
        return new Vec2(-this.y, this.x);
    }
}

/**
 * Global In-Flight Projectile Reservation Manager
 * Eliminates salvo overkill by tracking damage arriving from projectiles in flight.
 */
export class ProjectileReservationManager {
    constructor() {
        this.reservations = []; // Array of { id, attackerId, targetId, damage, impactTimeSec }
        this.nextReservationId = 1;
        this.inFlightDamageMap = new Map(); // targetId -> total in-flight damage
    }

    /**
     * Registers a new in-flight projectile launch.
     * @param {number|string} attackerId
     * @param {number|string} targetId
     * @param {number} expectedDamage
     * @param {number} flightDurationSec
     * @param {number} currentTimeSec
     * @returns {number} Reservation ID
     */
    addReservation(attackerId, targetId, expectedDamage, flightDurationSec, currentTimeSec) {
        const id = this.nextReservationId++;
        const impactTimeSec = currentTimeSec + flightDurationSec;
        const res = { id, attackerId, targetId, damage: expectedDamage, impactTimeSec };
        this.reservations.push(res);

        const currentDmg = this.inFlightDamageMap.get(targetId) || 0;
        this.inFlightDamageMap.set(targetId, currentDmg + expectedDamage);

        return id;
    }

    /**
     * Returns total damage in flight toward target.
     * @param {number|string} targetId
     * @returns {number}
     */
    getInFlightDamage(targetId) {
        return this.inFlightDamageMap.get(targetId) || 0;
    }

    /**
     * Returns the target's effective HP after subtracting in-flight damage.
     * EffectiveHP(T) = T.hp - InFlightDamage(T)
     * @param {Object} target
     * @returns {number}
     */
    getEffectiveHp(target) {
        if (!target) return 0;
        const inflight = this.getInFlightDamage(target.id);
        return Math.max(0, target.hp - inflight);
    }

    /**
     * Returns true if target is already mathematically slain by incoming shots.
     * @param {Object} target
     * @returns {boolean}
     */
    isMathematicallySlain(target) {
        if (!target || target.isDead) return true;
        return this.getEffectiveHp(target) <= 0;
    }

    /**
     * Prunes expired projectile reservations.
     * @param {number} currentTimeSec
     */
    pruneExpired(currentTimeSec) {
        const remaining = [];
        this.inFlightDamageMap.clear();

        for (const res of this.reservations) {
            if (currentTimeSec < res.impactTimeSec) {
                remaining.push(res);
                const cur = this.inFlightDamageMap.get(res.targetId) || 0;
                this.inFlightDamageMap.set(res.targetId, cur + res.damage);
            }
        }
        this.reservations = remaining;
    }

    clear() {
        this.reservations = [];
        this.inFlightDamageMap.clear();
    }
}

/**
 * Tactical Micro Combat AI Manager
 * Governs combat positioning, stutter-step kiting, retreat, AoE evasion, and flanking.
 */
export class TacticalMicroManager {
    /**
     * @param {Object} app - GameApp instance
     * @param {Object} [config={}] - Configuration options
     */
    constructor(app, config = {}) {
        this.app = app;
        this.owner = config.owner !== undefined ? config.owner : 1;
        this.difficultyConfig = getDifficultyConfig(config.difficulty || DIFFICULTY_TIERS.NORMAL);

        // APM limiter
        this.apmLimiter = new ApmLimiter(this.difficultyConfig);

        // Projectile reservation manager
        this.reservationManager = new ProjectileReservationManager();

        // Scan Cadence Timer
        this.scanIntervalSec = this.difficultyConfig.tacticalScanTicks / 24.0;
        this.scanTimer = 0;
        this.gameTimeSec = 0;

        // Unit Micro States: unitId -> { state, lastKiteSec, kiteVector, retreatAnchor, isRetreating }
        this.unitMicroContexts = new Map();

        // Flanking Squad Echelons: { anvil: Set<unitId>, hammer: Set<unitId>, state, waypoint }
        this.flankingSquad = {
            anvil: new Set(),
            hammer: new Set(),
            state: 'STAGING', // 'STAGING' | 'MARCHING' | 'PINCER_COLLAPSE'
            flankWaypoint: null,
            targetObjective: null
        };
    }

    /**
     * Sets active difficulty tier.
     * @param {Object|string} tier
     */
    setDifficulty(tier) {
        this.difficultyConfig = getDifficultyConfig(tier);
        this.scanIntervalSec = this.difficultyConfig.tacticalScanTicks / 24.0;
        this.apmLimiter.setDifficulty(this.difficultyConfig);
    }

    /**
     * Master tactical micro update loop.
     * @param {number} dt
     */
    update(dt) {
        this.gameTimeSec += dt;
        this.scanTimer += dt;

        // Prune expired projectile reservations
        this.reservationManager.pruneExpired(this.gameTimeSec);

        // Periodic tactical combat evaluation
        if (this.scanTimer >= this.scanIntervalSec) {
            this.scanTimer = 0;
            this.evaluateCombatMicro();
        }

        // Projectile & Hazard Evasion (evaluated every tick for predictive dodging)
        if (this.difficultyConfig.aoeDodgingEnabled) {
            this.evaluateHazardEvasion(dt);
        }

        // Flanking Coordination
        if (this.difficultyConfig.flankingEnabled) {
            this.updateFlankingManeuver(dt);
        }
    }

    /**
     * Evaluates tactical micro for all friendly units.
     */
    evaluateCombatMicro() {
        const friendlyUnits = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner);
        if (friendlyUnits.length === 0) return;

        for (const unit of friendlyUnits) {
            let ctx = this.unitMicroContexts.get(unit.id);
            if (!ctx) {
                ctx = { state: 'COMBAT', lastKiteSec: 0, kiteVector: new Vec2(0, 0), retreatAnchor: null, isRetreating: false };
                this.unitMicroContexts.set(unit.id, ctx);
            }

            // 1. HP-Ratio Tactical Retreat Check
            if (this.difficultyConfig.retreatEnabled) {
                if (this.evaluateUnitRetreat(unit, ctx)) {
                    continue; // Unit is retreating; skip normal attack micro
                }
            }

            // 2. Weapon-Cooldown Synchronized Stutter-Step Kiting Check
            if (this.difficultyConfig.kitingEnabled && !unit.isWorker) {
                if (this.evaluateUnitKiting(unit, ctx)) {
                    continue;
                }
            }

            // 3. Multi-Factor Threat-Priority Target Acquisition
            this.evaluateTargetAcquisition(unit);
        }

        // Healer Triage Network
        this.evaluateHealerTriage(friendlyUnits);
    }

    // =========================================================================
    // SECTION 1: STUTTER-STEP KITING & POTENTIAL FIELDS
    // =========================================================================

    /**
     * Evaluates stutter-step kiting for ranged units.
     * Moves unit away along repulsive potential field during weapon reload (attackTimer > 0).
     * @param {Object} unit
     * @param {Object} ctx
     * @returns {boolean} True if kiting action was executed
     */
    evaluateUnitKiting(unit, ctx) {
        const range = unit.attack_range || 1.2;
        // Kiting applies strictly to ranged combat units (range >= 3.0)
        if (range < 3.0) return false;

        // Find approaching hostile threats
        const threats = this.findNearbyThreats(unit, range + 2.0);
        if (threats.length === 0) return false;

        // Calculate dynamic threat horizon D_threat
        const dThreat = this.calculateThreatHorizon(unit, threats);

        // Find closest enemy melee distance
        let closestDist = Infinity;
        for (const t of threats) {
            const d = Math.hypot(unit.wx - t.wx, unit.wy - t.wy);
            if (d < closestDist) closestDist = d;
        }

        // Schmitt-Trigger Distance Hysteresis:
        // Retreat when d <= D_threat AND attackTimer > 0 (reloading)
        const isReloading = unit.attackTimer > 0.05;
        const insideDangerZone = closestDist <= dThreat;

        if (insideDangerZone && isReloading) {
            // Check minimum dwell time (0.25s lock to prevent jitter)
            if (ctx.lastKiteSec > 0 && (this.gameTimeSec - ctx.lastKiteSec) < 0.25) {
                return true;
            }

            // APM check
            if (!this.apmLimiter.tryConsume(unit.id, this.gameTimeSec, 1.0)) {
                return false;
            }

            // Calculate repulsive composite kite vector
            const kiteVec = this.calculateKiteVector(unit, threats);
            if (kiteVec.length() > 0.01) {
                const stepDist = Math.max(1.5, (unit.move_speed / 8) || 1.5);
                const targetWx = Math.round(unit.wx + kiteVec.x * stepDist);
                const targetWy = Math.round(unit.wy + kiteVec.y * stepDist);

                if (this.app.grid && this.app.grid.isWalkable(targetWx, targetWy)) {
                    unit.moveTo(targetWx, targetWy, this.app.grid);
                    ctx.lastKiteSec = this.gameTimeSec;
                    ctx.kiteVector = kiteVec;
                    return true;
                }
            }
        } else if (closestDist >= dThreat + 1.2 && !isReloading) {
            // Safe & Cooldown Ready: Halt and resume fire!
            if (unit.state === UnitState.WALK && unit.targetEntity) {
                unit.waypoints = [];
                unit.state = UnitState.IDLE;
            }
        }

        return false;
    }

    /**
     * Calculates dynamic threat horizon D_threat = max(D_min, V_foe * (T_windup + T_reaction) + epsilon).
     * @param {Object} unit
     * @param {Array<Object>} threats
     * @returns {number}
     */
    calculateThreatHorizon(unit, threats) {
        let maxFoesSpeed = 3.0; // default tiles/sec
        for (const t of threats) {
            const spd = (t.move_speed || 12) / 4.0;
            if (spd > maxFoesSpeed) maxFoesSpeed = spd;
        }

        const windupSec = unit.windupDuration || 0.25;
        const reactionSec = this.difficultyConfig.reactionDelayMs / 1000.0;
        const epsilon = 0.6;

        return Math.max(2.4, maxFoesSpeed * (windupSec + reactionSec) + epsilon);
    }

    /**
     * Computes the normalized repulsive vector potential field V_kite.
     * V_composite = F_threat + 0.6 * F_sep + 1.4 * F_terrain
     * @param {Object} unit
     * @param {Array<Object>} threats
     * @returns {Vec2}
     */
    calculateKiteVector(unit, threats) {
        let fThreat = new Vec2(0, 0);

        // 1. Hostile Threat Repulsion (Inverse-square)
        for (const e of threats) {
            const dx = unit.wx - e.wx;
            const dy = unit.wy - e.wy;
            const distSq = dx * dx + dy * dy + 0.01;
            const dist = Math.sqrt(distSq);

            const weight = (e.name.includes('기병') || e.name.includes('사무라이')) ? 3.0 : 1.8;
            fThreat.x += (dx / dist) * (weight / distSq);
            fThreat.y += (dy / dist) * (weight / distSq);
        }

        // 2. Friendly Flocking Separation (Avoid crowding choke)
        let fSep = new Vec2(0, 0);
        for (const a of this.app.entities) {
            if (!a || a.isDead || a.owner !== unit.owner || a === unit) continue;
            const d = Math.hypot(unit.wx - a.wx, unit.wy - a.wy);
            if (d > 0.01 && d <= 1.5) {
                fSep.x += (unit.wx - a.wx) / (d + 0.01);
                fSep.y += (unit.wy - a.wy) / (d + 0.01);
            }
        }

        // 3. Terrain Clearance (8-ray probe against unwalkable tiles)
        let fTerrain = new Vec2(0, 0);
        if (this.app.grid) {
            for (let angle = 0; angle < 8; angle++) {
                const rad = (angle / 8) * Math.PI * 2;
                const probeX = Math.round(unit.wx + Math.cos(rad) * 2.0);
                const probeY = Math.round(unit.wy + Math.sin(rad) * 2.0);

                if (!this.app.grid.isWalkable(probeX, probeY)) {
                    // Push away from wall
                    fTerrain.x -= Math.cos(rad) * 2.0;
                    fTerrain.y -= Math.sin(rad) * 2.0;
                }
            }
        }

        const composite = new Vec2(
            fThreat.x + 0.6 * fSep.x + 1.4 * fTerrain.x,
            fThreat.y + 0.6 * fSep.y + 1.4 * fTerrain.y
        );

        return composite.normalize();
    }

    /**
     * Finds enemy threats within search radius.
     * @param {Object} unit
     * @param {number} radius
     * @returns {Array<Object>}
     */
    findNearbyThreats(unit, radius) {
        return this.app.entities.filter(e => e && !e.isDead && e.owner !== unit.owner && e.owner !== 2 &&
            !e.isBuilding && Math.hypot(unit.wx - e.wx, unit.wy - e.wy) <= radius);
    }

    // =========================================================================
    // SECTION 2: HP-RATIO TACTICAL RETREAT & HEALER TRIAGE
    // =========================================================================

    /**
     * Evaluates HP-ratio tactical retreat for a unit.
     * @param {Object} unit
     * @param {Object} ctx
     * @returns {boolean} True if retreating
     */
    evaluateUnitRetreat(unit, ctx) {
        const hpRatio = unit.hp / unit.max_hp;
        const retreatThreshold = this.difficultyConfig.retreatHpThreshold;

        // If unit is currently retreating
        if (ctx.isRetreating) {
            if (hpRatio >= 0.80) {
                // Healed! Re-engage in combat
                ctx.isRetreating = false;
                ctx.retreatAnchor = null;
                unit.targetEntity = null;
                return false;
            }
            // Continue retreat path if waypoints emptied
            if (!unit.waypoints || unit.waypoints.length === 0) {
                if (ctx.retreatAnchor) {
                    unit.moveTo(ctx.retreatAnchor.wx, ctx.retreatAnchor.wy, this.app.grid);
                }
            }
            return true;
        }

        // Trigger retreat if HP drops below threshold
        if (retreatThreshold > 0 && hpRatio < retreatThreshold && !unit.isWorker) {
            if (!this.apmLimiter.tryConsume(unit.id, this.gameTimeSec, 1.0)) {
                return false;
            }

            const safeAnchor = this.findOptimalSafeAnchor(unit);
            if (safeAnchor) {
                ctx.isRetreating = true;
                ctx.retreatAnchor = safeAnchor;
                unit.targetEntity = null; // Suppress auto-aggro
                unit.moveTo(Math.round(safeAnchor.wx), Math.round(safeAnchor.wy), this.app.grid);
                return true;
            }
        }

        return false;
    }

    /**
     * Finds the lowest-cost safe rally point:
     * S_safe(D) = Dist(P, D) + 6.0 * EnemiesNear(D) - B_facility(D)
     * @param {Object} unit
     * @returns {Object|null}
     */
    findOptimalSafeAnchor(unit) {
        const friendlyBuildings = this.app.entities.filter(e => e && !e.isDead && e.isBuilding && e.owner === unit.owner);
        const healers = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === unit.owner &&
            (e.name.includes('허준') || e.name.includes('사명') || e.name.includes('승병') || (e.mp && e.mp >= 20)));

        const candidates = [...healers, ...friendlyBuildings];
        if (candidates.length === 0) return null;

        let bestAnchor = null;
        let minScore = Infinity;

        for (const cand of candidates) {
            const dist = Math.hypot(unit.wx - cand.wx, unit.wy - cand.wy);
            let bFacility = 4.0;

            const name = cand.name || '';
            if (cand.mp !== undefined && cand.mp >= 20) {
                bFacility = 14.0; // Active healer hub
            } else if (name.includes('망루') || name.includes('tower')) {
                bFacility = 10.0; // Defensive watchtower
            } else if (name.includes('본영') || name.includes('HQ') || name.includes('hq')) {
                bFacility = 8.0;  // Main base HQ
            }

            // Count nearby enemies around destination
            const enemyCount = this.findNearbyThreats(cand, 8.0).length;
            const score = dist + 6.0 * enemyCount - bFacility;

            if (score < minScore) {
                minScore = score;
                bestAnchor = cand;
            }
        }

        return bestAnchor;
    }

    /**
     * Dedicated Healer Triage Network: Monks and Shamans prioritize wounded high-value targets.
     * @param {Array<Object>} friendlyUnits
     */
    evaluateHealerTriage(friendlyUnits) {
        const healers = friendlyUnits.filter(u => u && !u.isDead && (u.name.includes('허준') || u.name.includes('사명대사') ||
            u.name.includes('승병') || (u.mp && u.mp >= 20)));
        if (healers.length === 0) return;

        const woundedAllies = friendlyUnits.filter(u => u && !u.isDead && u.hp < u.max_hp * 0.85);
        if (woundedAllies.length === 0) return;

        for (const healer of healers) {
            let bestTarget = null;
            let maxTriagePriority = -Infinity;

            for (const ally of woundedAllies) {
                const dist = Math.hypot(healer.wx - ally.wx, healer.wy - ally.wy);
                if (dist > (healer.sight_range || 10.0)) continue;

                // Class weight
                let wClass = 1.0;
                const name = ally.name || '';
                if (name.includes('이순신') || name.includes('가토') || name.includes('권율') || ally.level > 1) {
                    wClass = 4.5; // Hero
                } else if (name.includes('화차') || name.includes('불랑기') || name.includes('전차')) {
                    wClass = 3.0; // Siege
                } else if (name.includes('기병') || name.includes('사무라이')) {
                    wClass = 2.0; // Cavalry / Elite
                } else if (ally.attack_range >= 4.0) {
                    wClass = 1.5; // Ranged
                }

                // TriagePriority = W_class * (1.0 + 3.0 * (1 - HP/MaxHP)) - 0.2 * Dist
                const priority = wClass * (1.0 + 3.0 * (1.0 - (ally.hp / ally.max_hp))) - 0.2 * dist;
                if (priority > maxTriagePriority) {
                    maxTriagePriority = priority;
                    bestTarget = ally;
                }
            }

            if (bestTarget) {
                const distToAlly = Math.hypot(healer.wx - bestTarget.wx, healer.wy - bestTarget.wy);
                if (distToAlly <= 3.0) {
                    // In cast range: Cast healing!
                    if (healer.mp >= 20) {
                        healer.mp -= 20;
                        bestTarget.hp = Math.min(bestTarget.max_hp, bestTarget.hp + 200);
                        if (this.app.addFloatingText) {
                            this.app.addFloatingText(bestTarget.wx, bestTarget.wy, '+200 치료', '#44ff88');
                        }
                    }
                } else {
                    // Path to wounded ally
                    healer.moveTo(Math.round(bestTarget.wx), Math.round(bestTarget.wy), this.app.grid);
                }
            }
        }
    }

    // =========================================================================
    // SECTION 3: AOE & ARTILLERY HAZARD EVASION
    // =========================================================================

    /**
     * Evaluates in-flight splash projectiles and ground hazards, dispersing units outward.
     * @param {number} dt
     */
    evaluateHazardEvasion(dt) {
        if (!this.app.projectiles && !this.app.groundFires) return;

        const hazards = [];

        // 1. Active In-Flight Projectiles (Cannonballs, Rockets, Mortars)
        if (this.app.projectiles) {
            for (const proj of this.app.projectiles) {
                if (proj.type === 'cannon' || proj.type === 'fireball' || proj.damage >= 50) {
                    const remainingProgress = 1.0 - (proj.progress || 0);
                    const remainingSec = remainingProgress * (proj.travelDuration || 0.8);

                    // Predictive detection: impact within 0.8s
                    if (remainingSec <= 0.8) {
                        hazards.push({
                            wx: proj.targetWx,
                            wy: proj.targetWy,
                            radius: proj.type === 'cannon' ? 3.0 : 2.5
                        });
                    }
                }
            }
        }

        // 2. Active Ground Fires
        if (this.app.groundFires) {
            for (const fire of this.app.groundFires) {
                if (fire.life > 0.5) {
                    hazards.push({
                        wx: fire.wx,
                        wy: fire.wy,
                        radius: fire.radius || 1.8
                    });
                }
            }
        }

        if (hazards.length === 0) return;

        // Disperse any friendly unit standing within hazard footprint
        const friendlyUnits = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner);
        for (const unit of friendlyUnits) {
            for (const h of hazards) {
                const dist = Math.hypot(unit.wx - h.wx, unit.wy - h.wy);
                if (dist <= h.radius + 0.5) {
                    // Stand in danger zone! Compute radial scatter vector
                    let scatterX = unit.wx - h.wx;
                    let scatterY = unit.wy - h.wy;
                    const len = Math.hypot(scatterX, scatterY);

                    if (len < 1e-4) {
                        scatterX = 1;
                        scatterY = 0;
                    } else {
                        scatterX /= len;
                        scatterY /= len;
                    }

                    const escapeDist = h.radius + 1.2;
                    const targetGx = Math.round(unit.wx + scatterX * escapeDist);
                    const targetGy = Math.round(unit.wy + scatterY * escapeDist);

                    if (this.app.grid && this.app.grid.isWalkable(targetGx, targetGy)) {
                        unit.moveTo(targetGx, targetGy, this.app.grid);
                    }
                    break;
                }
            }
        }
    }

    // =========================================================================
    // SECTION 4: MULTI-DIRECTIONAL FLANKING (HAMMER & ANVIL)
    // =========================================================================

    /**
     * Coordinates multi-echelon Hammer and Anvil pincer assaults.
     * @param {number} dt
     */
    updateFlankingManeuver(dt) {
        const army = this.app.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === this.owner && !e.isWorker);
        if (army.length < 6) {
            // Army mass too small for pincer
            this.flankingSquad.anvil.clear();
            this.flankingSquad.hammer.clear();
            this.flankingSquad.state = 'STAGING';
            return;
        }

        // Partition into Anvil (60% infantry/tanks) and Hammer (30% cavalry/mobile)
        if (this.flankingSquad.anvil.size === 0 && this.flankingSquad.hammer.size === 0) {
            this.partitionArmyEchelons(army);
        }

        // Find primary enemy base objective
        const enemyHq = this.app.entities.find(e => e && !e.isDead && e.isBuilding && e.owner !== this.owner && e.owner !== 2 &&
            (e.name.includes('본영') || e.name.includes('HQ') || e.name.includes('hq')));
        if (!enemyHq) return;

        const rallyPt = this.calculateCentroid(army);
        const targetPt = new Vec2(enemyHq.wx, enemyHq.wy);

        if (this.flankingSquad.state === 'STAGING') {
            // Calculate geometric flank waypoint W_flank = S + 0.5*D ± 0.35*L*n
            const dir = targetPt.sub(rallyPt);
            const dist = dir.length();
            if (dist > 15.0) {
                const u = dir.normalize();
                const n = u.perpendicular(); // Perpendicular normal

                // Flank waypoint offset
                const flankWp = rallyPt.add(u.mul(0.5 * dist)).add(n.mul(0.35 * dist));
                this.flankingSquad.flankWaypoint = flankWp;
                this.flankingSquad.targetObjective = targetPt;

                // Dispatch Hammer via flank waypoint
                for (const unitId of this.flankingSquad.hammer) {
                    const u = this.app.entities.find(e => e && e.id === unitId);
                    if (u && !u.isDead) {
                        if (typeof u.attackMoveTo === 'function') {
                            u.attackMoveTo(Math.round(flankWp.x), Math.round(flankWp.y), this.app.grid);
                        } else {
                            u.moveTo(Math.round(flankWp.x), Math.round(flankWp.y), this.app.grid);
                        }
                    }
                }

                // Dispatch Anvil along direct primary assault line
                for (const unitId of this.flankingSquad.anvil) {
                    const u = this.app.entities.find(e => e && e.id === unitId);
                    if (u && !u.isDead) {
                        if (typeof u.attackMoveTo === 'function') {
                            u.attackMoveTo(Math.round(targetPt.x), Math.round(targetPt.y), this.app.grid);
                        } else {
                            u.moveTo(Math.round(targetPt.x), Math.round(targetPt.y), this.app.grid);
                        }
                    }
                }

                this.flankingSquad.state = 'MARCHING';
            }
        } else if (this.flankingSquad.state === 'MARCHING') {
            // Check if Anvil has engaged enemy vanguard
            let anvilEngaged = false;
            for (const unitId of this.flankingSquad.anvil) {
                const u = this.app.entities.find(e => e && e.id === unitId);
                if (u && !u.isDead && u.targetEntity) {
                    anvilEngaged = true;
                    break;
                }
            }

            // Pincer Collapse: Hammer collapses inward on enemy rear
            if (anvilEngaged || this.checkHammerReachedFlank()) {
                for (const unitId of this.flankingSquad.hammer) {
                    const u = this.app.entities.find(e => e && e.id === unitId);
                    if (u && !u.isDead) {
                        if (typeof u.attackMoveTo === 'function') {
                            u.attackMoveTo(Math.round(targetPt.x), Math.round(targetPt.y), this.app.grid);
                        } else {
                            u.moveTo(Math.round(targetPt.x), Math.round(targetPt.y), this.app.grid);
                        }
                    }
                }
                this.flankingSquad.state = 'PINCER_COLLAPSE';
            }
        }
    }

    /**
     * Partitions the standing combat army into Anvil and Hammer echelons.
     * @param {Array<Object>} army
     */
    partitionArmyEchelons(army) {
        this.flankingSquad.anvil.clear();
        this.flankingSquad.hammer.clear();

        const cavalry = [];
        const infantry = [];

        for (const u of army) {
            const name = u.name || '';
            if (name.includes('기병') || name.includes('기마') || (u.move_speed >= 14)) {
                cavalry.push(u.id);
            } else {
                infantry.push(u.id);
            }
        }

        // Hammer takes cavalry, supplemented by fast infantry up to 35% of army
        const targetHammerCount = Math.max(2, Math.round(army.length * this.difficultyConfig.flankingRatio));
        for (const id of cavalry) {
            if (this.flankingSquad.hammer.size < targetHammerCount) {
                this.flankingSquad.hammer.add(id);
            } else {
                this.flankingSquad.anvil.add(id);
            }
        }
        for (const id of infantry) {
            if (this.flankingSquad.hammer.size < targetHammerCount) {
                this.flankingSquad.hammer.add(id);
            } else {
                this.flankingSquad.anvil.add(id);
            }
        }
    }

    calculateCentroid(units) {
        let sx = 0, sy = 0;
        for (const u of units) {
            sx += u.wx;
            sy += u.wy;
        }
        return new Vec2(sx / units.length, sy / units.length);
    }

    checkHammerReachedFlank() {
        if (!this.flankingSquad.flankWaypoint) return false;
        for (const unitId of this.flankingSquad.hammer) {
            const u = this.app.entities.find(e => e && e.id === unitId);
            if (u && !u.isDead) {
                const dist = Math.hypot(u.wx - this.flankingSquad.flankWaypoint.x, u.wy - this.flankingSquad.flankWaypoint.y);
                if (dist <= 4.0) return true;
            }
        }
        return false;
    }

    // =========================================================================
    // SECTION 5: THREAT-PRIORITY TARGETING & OVERKILL PREVENTION
    // =========================================================================

    /**
     * Evaluates candidate enemy targets using the multi-factor threat formula:
     * S(A, T) = (W_threat * Vulnerability * DamageEfficiency) / DistancePenalty
     * Disqualifies mathematically slain targets via the reservation table.
     * @param {Object} unit
     */
    evaluateTargetAcquisition(unit) {
        if (unit.targetEntity && !unit.targetEntity.isDead) {
            // Check if current target is already mathematically dead from in-flight shots
            if (this.reservationManager.isMathematicallySlain(unit.targetEntity)) {
                unit.targetEntity = null; // Drop target and search for next best!
            } else {
                return; // Maintain current engagement
            }
        }

        const scanLimit = unit.sight_range || 10.0;
        const enemies = this.app.entities.filter(e => e && !e.isDead && e.owner !== unit.owner && e.owner !== 2 &&
            Math.hypot(unit.wx - e.wx, unit.wy - e.wy) <= scanLimit);
        if (enemies.length === 0) return;

        let bestTarget = null;
        let maxScore = -Infinity;

        for (const target of enemies) {
            // 1. Overkill Prevention: Disqualify if effective HP <= 0
            if (this.reservationManager.isMathematicallySlain(target)) {
                continue;
            }

            // 2. Threat Category Weight
            let wThreat = 1.0;
            const name = target.name || '';
            if (name.includes('이순신') || name.includes('가토') || name.includes('권율') || target.level > 1) {
                wThreat = 4.0; // Hero
            } else if (target.mp !== undefined && target.mp > 0) {
                wThreat = 3.5; // Spellcaster / Healer
            } else if (name.includes('화차') || name.includes('불랑기') || name.includes('전차')) {
                wThreat = 3.0; // Siege
            } else if (target.attack_range >= 4.0) {
                wThreat = 2.2; // Ranged DPS
            } else if (name.includes('기병') || name.includes('닌자')) {
                wThreat = 1.8; // Fast Melee
            } else if (target.isWorker) {
                wThreat = 0.5; // Worker
            } else if (target.isBuilding) {
                wThreat = 0.3; // Building
            }

            // 3. HP Vulnerability Multiplier: 1.0 + 2.5 * (1 - EffHP/MaxHP)^2
            const effHp = this.reservationManager.getEffectiveHp(target);
            const hpRatio = effHp / target.max_hp;
            const vulnerability = 1.0 + 2.5 * Math.pow(1.0 - hpRatio, 2);

            // 4. Armor Damage Efficiency
            const rawDmg = unit.attack_power || 20;
            const def = target.defense || 0;
            const effDmg = Math.max(1, rawDmg - def);
            const damageEfficiency = effDmg / rawDmg;

            // 5. Distance Penalty
            const dist = Math.hypot(unit.wx - target.wx, unit.wy - target.wy);
            const sweetSpot = Math.max(0.5, (unit.attack_range || 1.2) - 0.5);
            const distPenalty = 1.0 + 0.18 * Math.max(0, dist - sweetSpot);

            const score = (wThreat * vulnerability * damageEfficiency) / distPenalty;
            if (score > maxScore) {
                maxScore = score;
                bestTarget = target;
            }
        }

        if (bestTarget) {
            unit.targetEntity = bestTarget;
        }
    }

    /**
     * Intercepts projectile firing to register damage in the reservation table.
     * @param {Object} attacker
     * @param {Object} target
     * @param {number} damage
     * @param {number} travelDurationSec
     */
    onProjectileSpawned(attacker, target, damage, travelDurationSec) {
        if (!target) return;
        this.reservationManager.addReservation(attacker.id, target.id, damage, travelDurationSec, this.gameTimeSec);
    }
}
