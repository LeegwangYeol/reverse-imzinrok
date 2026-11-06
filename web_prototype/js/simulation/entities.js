/**
 * Entity Simulation Classes for Imjinrok 2+: Dawn
 *
 * Implements Unit, Building, and Projectile classes with full state machines (IDLE, WALK, ATTACK, DIE),
 * 8-directional orientation calculation, dynamic move_speed physics calculation,
 * and combat attribute management.
 */

import { PathFinder } from './pathfinding.js';
import { CombatSystem } from './combat.js';

export const UnitState = {
    IDLE: 'IDLE',
    WALK: 'WALK',
    ATTACK_WINDUP: 'ATTACK_WINDUP',
    ATTACK_COOLDOWN: 'ATTACK_COOLDOWN',
    ATTACK: 'ATTACK',
    DIE: 'DIE',
    CORPSE_DECAY: 'CORPSE_DECAY'
};

/**
 * Exact 5-Action animation boundary specifications for the 10 custom Joseon units (0x70~0x79).
 */
export const CUSTOM_JOSEON_ANIM_SPECS = {
    0x70: {
        id: 'chosun_yusaeng',
        alias_id: 'keon_1hs',
        name: '조선 유생',
        atk: { start: 0, fDir: 8, dirs: 5, total: 40, instant: 4 },
        die: { start: 60, total: 12, corpse: 71 },
        idle: { start: 72, fDir: 12, dirs: 5, total: 60 },
        move: { start: 132, fDir: 8, dirs: 5, total: 40 }
    },
    0x71: {
        id: 'chosun_geomsul_nangin',
        alias_id: 'SwordPirate_online',
        name: '검술 낭인',
        atk: { start: 0, fDir: 8, dirs: 5, total: 40, instant: 4 },
        idle: { start: 40, fDir: 8, dirs: 5, total: 40 },
        move: { start: 80, fDir: 8, dirs: 5, total: 40 },
        die: { start: 120, total: 9, corpse: 128 }
    },
    0x72: {
        id: 'chosun_jochong_nangin',
        alias_id: 'GunPirate_online',
        name: '조총 낭인',
        atk: { start: 0, fDir: 8, dirs: 5, total: 40, instant: 4 },
        idle: { start: 40, fDir: 8, dirs: 5, total: 40 },
        move: { start: 80, fDir: 8, dirs: 5, total: 40 },
        die: { start: 120, total: 9, corpse: 128 }
    },
    0x73: {
        id: 'chosun_gumiho',
        alias_id: 'fox',
        name: '구미호',
        atk: { start: 0, fDir: 8, dirs: 5, total: 40, instant: 4 },
        idle: { start: 40, fDir: 8, dirs: 5, total: 40 },
        move: { start: 80, fDir: 8, dirs: 5, total: 40 },
        die: { start: 120, total: 17, corpse: 136 }
    },
    0x74: {
        id: 'chosun_wangbeol',
        alias_id: 'bat_online',
        name: '조선왕벌',
        isAirUnit: true,
        idle: { start: 0, fDir: 8, dirs: 5, total: 40 },
        move: { start: 0, fDir: 8, dirs: 5, total: 40 },
        atk: { start: 72, fDir: 8, dirs: 5, total: 40, instant: 4 },
        die: { start: 144, total: 11, corpse: null } // 0 corpse decay, instant vanish
    },
    0x75: {
        id: 'chosun_horangi',
        alias_id: 'Tiger',
        name: '조선 호랑이',
        atk: { start: 0, fDir: 8, dirs: 5, total: 40, instant: 4 },
        idle: { start: 40, fDir: 8, dirs: 5, total: 40 },
        move: { start: 80, fDir: 8, dirs: 5, total: 40 },
        die: { start: 120, total: 10, corpse: 129 }
    },
    0x76: {
        id: 'chosun_teolgamyeon',
        alias_id: 'furheaddemon_online',
        name: '털가면',
        idle: { start: 0, fDir: 8, dirs: 5, total: 40 },
        atk: { start: 40, fDir: 8, dirs: 5, total: 40, instant: 4 },
        move: { start: 80, fDir: 8, dirs: 5, total: 40 },
        die: { start: 120, total: 10, corpse: 129 }
    },
    0x77: {
        id: 'chosun_seolnyeo',
        alias_id: 'snowwoman_online',
        name: '설녀',
        atk: { start: 0, fDir: 13, dirs: 5, total: 65, instant: 6 },
        die: { start: 65, total: 19, corpse: 83 },
        idle: { start: 84, fDir: 10, dirs: 5, total: 50 },
        move: { start: 134, fDir: 10, dirs: 5, total: 50 }
    },
    0x78: {
        id: 'chosun_dokkaebi',
        alias_id: 'oni_online',
        name: '조선 도깨비',
        atk: { start: 0, fDir: 12, dirs: 5, total: 60, instant: 6 },
        idle: { start: 60, fDir: 8, dirs: 5, total: 40 },
        move: { start: 100, fDir: 8, dirs: 5, total: 40 },
        die: { start: 140, total: 11, corpse: 150 }
    },
    0x79: {
        id: 'chosun_bulgasari',
        alias_id: 'starfish',
        name: '불가살이',
        idle: { start: 0, fDir: 8, dirs: 5, total: 40 },
        move: { start: 40, fDir: 8, dirs: 5, total: 40 },
        atk: { start: 80, fDir: 16, dirs: 5, total: 80, instant: 8 },
        die: { start: 160, total: 20, corpse: 179 }
    }
};

// String key aliases for CUSTOM_JOSEON_ANIM_SPECS
const _aliasMap = {
    'keon_1hs.spr': 0x70, 'keon_1hs': 0x70, 'chosun_yusaeng': 0x70, '유생': 0x70, '조선 유생': 0x70,
    'swordpirate_online.spr': 0x71, 'swordpirate_online': 0x71, 'chosun_geomsul_nangin': 0x71, '검술 낭인': 0x71,
    'gunpirate_online.spr': 0x72, 'gunpirate_online': 0x72, 'chosun_jochong_nangin': 0x72, '조총 낭인': 0x72,
    'fox.spr': 0x73, 'fox': 0x73, 'chosun_gumiho': 0x73, '구미호': 0x73,
    'bat_online.spr': 0x74, 'bat_online': 0x74, 'chosun_wangbeol': 0x74, '조선왕벌': 0x74, '왕벌': 0x74,
    'tiger.spr': 0x75, 'tiger': 0x75, 'chosun_horangi': 0x75, '조선 호랑이': 0x75, '호랑이': 0x75,
    'furheaddemon_online.spr': 0x76, 'furheaddemon_online': 0x76, 'chosun_teolgamyeon': 0x76, '털가면': 0x76,
    'snowwoman_online.spr': 0x77, 'snowwoman_online': 0x77, 'chosun_seolnyeo': 0x77, '설녀': 0x77,
    'oni_online.spr': 0x78, 'oni_online': 0x78, 'chosun_dokkaebi': 0x78, '조선 도깨비': 0x78, '도깨비': 0x78,
    'starfish.spr': 0x79, 'starfish': 0x79, 'chosun_bulgasari': 0x79, '불가살이': 0x79
};
for (const [k, v] of Object.entries(_aliasMap)) {
    CUSTOM_JOSEON_ANIM_SPECS[k] = CUSTOM_JOSEON_ANIM_SPECS[v];
}

/**
 * 8-Directional compass directions:
 * 0: South (S)
 * 1: South-West (SW)
 * 2: West (W)
 * 3: North-West (NW)
 * 4: North (N)
 * 5: North-East (NE)
 * 6: East (E)
 * 7: South-East (SE)
 */
export const Direction = {
    S: 0,
    SW: 1,
    W: 2,
    NW: 3,
    N: 4,
    NE: 5,
    E: 6,
    SE: 7
};

export class Unit {
    /**
     * @param {number} id - Unique entity ID
     * @param {Object} archetype - Unit stat archetype definition (from dataset.json)
     * @param {number} gx - Initial tile X
     * @param {number} gy - Initial tile Y
     * @param {number} [owner=0] - Faction/Player ID (0=Player, 1=Enemy, etc.)
     */
    constructor(id, archetype = {}, gx = 0, gy = 0, owner = 0) {
        this.id = id;
        this.archetype = archetype;
        this.owner = owner;
        this.name = archetype.korean_name || archetype.name || `Unit_${id}`;
        this.kindId = archetype.kind_id || archetype.kindId || (archetype.index !== undefined ? archetype.index : 0);
        this.spriteName = archetype.sprite_name || archetype.sprite || archetype.sprite_path || 'char/swordk.spr';
        this.unitType = archetype.unit_type || archetype.category || 'infantry'; // infantry, archer, cavalry, ship, siege, air

        // Air unit flag: 0x74 조선왕벌 (bat_online.spr) is strictly an air unit
        this.isAirUnit = Boolean(
            archetype.isAirUnit ||
            archetype.is_air ||
            this.unitType === 'air' ||
            this.kindId === 0x74 ||
            (this.spriteName && (this.spriteName.toLowerCase().includes('bat') || this.spriteName.toLowerCase().includes('hornet')))
        );
        this.flightAltitude = this.isAirUnit ? (archetype.flightAltitude || 36) : 0;

        // Action Animation Specifications
        this.animSpec = archetype.anim_spec || archetype.animSpec || Unit.getAnimSpec(this.kindId, this.spriteName, this.name);

        // Discrete tile grid coordinates
        this.gx = gx;
        this.gy = gy;

        // Continuous world grid coordinates (centered in tile)
        this.wx = gx + 0.5;
        this.wy = gy + 0.5;

        // Modifiable stats (directly bound to Live Modding Studio)
        this.move_speed = (archetype.move_speed !== undefined) ? archetype.move_speed : 12;
        this.max_hp = (archetype.hp !== undefined) ? archetype.hp : 100;
        this.hp = this.max_hp;
        this.max_mp = (archetype.mp !== undefined) ? archetype.mp : 0;
        this.mp = this.max_mp;
        this.attack_power = (archetype.attack_power !== undefined) ? archetype.attack_power : 10;
        this.attack_range = (archetype.attack_range !== undefined) ? archetype.attack_range : 1.5;
        this.attack_delay = (archetype.attack_delay !== undefined) ? archetype.attack_delay : 30; // ticks
        this.defense = (archetype.defense !== undefined) ? archetype.defense : 0;
        this.sight_range = (archetype.sight_range !== undefined) ? archetype.sight_range : 8;
        this.projectile_type = archetype.projectile_type || (this.attack_range > 2.5 ? 'arrow' : null);
        this.scale = 1.0;

        // State Machine
        this.state = UnitState.IDLE;
        this.direction = Direction.S;
        this.waypoints = [];
        this.targetEntity = null;
        this.targetGridPos = null;

        // Timers & Combat Cooldowns
        this.attackTimer = 0;       // Seconds remaining until next attack can begin
        this.windupTimer = 0;       // Seconds remaining in attack windup animation
        this.windupDuration = 0.25; // Attack animation windup before strike/projectile spawn

        // Animation state
        this.animFrame = 0;
        this.animTimer = 0;
        this.frameRate = 10; // Frames per second

        // UI & Selection
        this.selected = false;
        this.isDead = false;
        this.isDying = false;
        this.deathTimer = 0;
        this.deathAnimDone = false;
        const initialDieFrames = (this.animSpec && this.animSpec.die && this.animSpec.die.total) ? this.animSpec.die.total : 8;
        this.deathDuration = initialDieFrames / this.frameRate;
        this.holdPosition = false;

        // Corpse Decay Properties: ground units rest for 4.0s, dissolving over last 1.0s; air units 0.0s
        this.corpseDuration = this.isAirUnit ? 0.0 : (archetype.corpseDuration !== undefined ? archetype.corpseDuration : 4.0);
        this.corpseFadeDuration = 1.0;
        this.corpseTimer = 0;
        this.corpseAlpha = 1.0;

        // Status Effects & Abilities (Paralysis, Freeze, Slow)
        this.statusEffects = {
            paralyzed: 0, // duration in seconds (blocks movement, attacks, skills)
            frozen: 0,    // duration in seconds (freezes animation, movement, attacks)
            slowed: 0     // duration in seconds (reduces move_speed by 50%)
        };
        if (archetype.statusEffects) {
            this.statusEffects.paralyzed = archetype.statusEffects.paralyzed || 0;
            this.statusEffects.frozen = archetype.statusEffects.frozen || 0;
            this.statusEffects.slowed = archetype.statusEffects.slowed || 0;
        }
        this.isIllusion = Boolean(archetype.isIllusion);
        this.illusionDuration = archetype.isIllusion ? (archetype.illusionDuration || 25.0) : 0;
        this.hybrid = Boolean(archetype.hybrid || (this.kindId === 0x79));
        this.ranged_attack_range = (archetype.ranged_attack_range !== undefined) ? archetype.ranged_attack_range : (this.kindId === 0x79 ? 6.0 : 0);
        this.ranged_mp_cost = (archetype.ranged_mp_cost !== undefined) ? archetype.ranged_mp_cost : (this.kindId === 0x79 ? 20 : 0);

        // Telemetry
        this.totalDistanceMoved = 0;
    }

    /**
     * Applies a status effect (paralyzed, frozen, slowed) with specified duration.
     *
     * @param {string} type - 'paralyzed', 'frozen', or 'slowed'
     * @param {number} duration - Effect duration in seconds
     * @param {Object} [sourceUnit=null] - Attacker unit
     */
    applyStatusEffect(type, duration, sourceUnit = null) {
        if (this.isDead) return;
        if (!this.statusEffects) {
            this.statusEffects = { paralyzed: 0, frozen: 0, slowed: 0 };
        }
        if (this.statusEffects[type] !== undefined) {
            this.statusEffects[type] = Math.max(this.statusEffects[type] || 0, duration);
        }
    }

    /**
     * Resolves the animation spec for custom Joseon units.
     */
    static getAnimSpec(kindId, spriteName = '', name = '') {
        if (kindId && CUSTOM_JOSEON_ANIM_SPECS[kindId]) {
            return CUSTOM_JOSEON_ANIM_SPECS[kindId];
        }
        const sprClean = (spriteName || '').replace('char/', '').toLowerCase();
        if (sprClean && CUSTOM_JOSEON_ANIM_SPECS[sprClean]) {
            return CUSTOM_JOSEON_ANIM_SPECS[sprClean];
        }
        const sprBase = sprClean.replace('.spr', '');
        if (sprBase && CUSTOM_JOSEON_ANIM_SPECS[sprBase]) {
            return CUSTOM_JOSEON_ANIM_SPECS[sprBase];
        }
        if (name && CUSTOM_JOSEON_ANIM_SPECS[name]) {
            return CUSTOM_JOSEON_ANIM_SPECS[name];
        }
        return null;
    }

    /**
     * Issues a move command to a destination tile.
     *
     * @param {number} targetGx - Target tile X
     * @param {number} targetGy - Target tile Y
     * @param {Object} grid - GameGrid instance
     * @param {boolean} [smooth=true] - Whether to smooth path
     */
    moveTo(targetGx, targetGy, grid, smooth = true) {
        if (this.isDead) return;
        this.targetEntity = null;
        this.targetGridPos = { gx: targetGx, gy: targetGy };

        // Air units fly straight without ground collision/pathfinding constraints
        if (this.isAirUnit) {
            this.waypoints = [{ gx: targetGx, gy: targetGy }];
            this.state = UnitState.WALK;
            return;
        }

        const currentGx = Math.floor(this.wx);
        const currentGy = Math.floor(this.wy);

        const path = PathFinder.findPath(grid, currentGx, currentGy, targetGx, targetGy, { smooth });
        if (path && path.length > 0) {
            this.waypoints = path;
            this.state = UnitState.WALK;
        } else {
            this.waypoints = [];
            this.state = UnitState.IDLE;
        }
    }

    /**
     * Issues an attack command targeting another entity.
     *
     * @param {Unit|Building} target - Enemy entity
     */
    attackOrder(target) {
        if (this.isDead || !target || target.isDead) return;
        this.targetEntity = target;
        this.targetGridPos = null;
    }

    /**
     * Primary entity update tick called each simulation frame.
     *
     * @param {number} deltaSec - Frame delta in seconds
     * @param {Object} grid - GameGrid
     * @param {Array<Unit|Building>} [entityList=[]] - All active game entities
     * @param {Object} [audioManager=null] - Sound engine
     * @param {Array<Projectile>} [projectiles=[]] - Active projectile list
     */
    update(deltaSec, grid, entityList = [], audioManager = null, projectiles = []) {
        // 5th Action: Corpse Decay Lifecycle: unit rests on collapsed corpse frame for 4.0s, releasing tile occupancy, dissolving over last 1.0s
        if (this.state === UnitState.CORPSE_DECAY) {
            this.corpseTimer -= deltaSec;
            if (this.corpseTimer <= this.corpseFadeDuration) {
                this.corpseAlpha = Math.max(0, Math.min(1.0, this.corpseTimer / this.corpseFadeDuration));
            } else {
                this.corpseAlpha = 1.0;
            }
            if (this.corpseTimer <= 0) {
                this.corpseAlpha = 0.0;
                this.isDying = false;
                this.isDead = true;
                this.deathAnimDone = true;
            }
            return;
        }

        // 4th Action: Dying animation lifecycle: play death frames before corpse decay or removal
        if (this.isDying || this.state === UnitState.DIE) {
            // Air Unit (0x74 조선왕벌, isAirUnit): Instant vanish rule! ZERO ground corpse decay, ZERO decal, ZERO tile footprint!
            if (this.isAirUnit) {
                if (grid && grid.clearUnitOccupancy) {
                    grid.clearUnitOccupancy(this.gx, this.gy);
                }
                this.isDying = false;
                this.isDead = true;
                this.deathAnimDone = true;
                this.corpseAlpha = 0.0;
                return;
            }

            this.deathTimer += deltaSec;
            this.animTimer += deltaSec;
            const frameInterval = 1.0 / this.frameRate;
            if (this.animTimer >= frameInterval) {
                this.animTimer -= frameInterval;
                this.animFrame++;
            }

            const dieFrames = (this.animSpec && this.animSpec.die && this.animSpec.die.total) ? this.animSpec.die.total : 8;
            if (this.deathTimer >= this.deathDuration || this.animFrame >= dieFrames) {
                // Ground unit: transition to 5th Action CORPSE_DECAY
                this.state = UnitState.CORPSE_DECAY;
                this.corpseTimer = this.corpseDuration;
                this.corpseAlpha = 1.0;
                this.animFrame = dieFrames - 1; // Rest on final collapsed death frame
                // Release tile occupancy immediately so other units can walk over the corpse!
                if (grid && grid.clearUnitOccupancy) {
                    grid.clearUnitOccupancy(this.gx, this.gy);
                }
            }
            return;
        }

        if (this.isDead) return;

        // Illusion expiration lifecycle
        if (this.isIllusion && this.illusionDuration > 0) {
            this.illusionDuration -= deltaSec;
            if (this.illusionDuration <= 0 && !this.isDying) {
                this.isDying = true;
                this.state = UnitState.DIE;
                return;
            }
        }

        // Status effect timers
        if (this.statusEffects) {
            if (this.statusEffects.paralyzed > 0) {
                this.statusEffects.paralyzed = Math.max(0, this.statusEffects.paralyzed - deltaSec);
            }
            if (this.statusEffects.frozen > 0) {
                this.statusEffects.frozen = Math.max(0, this.statusEffects.frozen - deltaSec);
            }
            if (this.statusEffects.slowed > 0) {
                this.statusEffects.slowed = Math.max(0, this.statusEffects.slowed - deltaSec);
            }
        }

        // Clamp unit movement and attacks when paralyzed > 0 or frozen > 0
        if (this.statusEffects && (this.statusEffects.paralyzed > 0 || this.statusEffects.frozen > 0)) {
            if (this.state === UnitState.WALK) {
                this.waypoints = [];
                this.state = UnitState.IDLE;
            } else if (this.state === UnitState.ATTACK_WINDUP) {
                this.state = UnitState.IDLE;
            }
            this.gx = Math.floor(this.wx);
            this.gy = Math.floor(this.wy);
            return;
        }

        // Animation frame advancing for living actions (WALK, IDLE, ATTACK)
        this.animTimer += deltaSec;
        const frameInterval = 1.0 / this.frameRate;
        if (this.animTimer >= frameInterval) {
            this.animTimer -= frameInterval;
            let maxFrames = 8;
            if (this.animSpec) {
                if (this.state === UnitState.WALK && this.animSpec.move) {
                    maxFrames = this.animSpec.move.fDir || 8;
                } else if (this.state === UnitState.IDLE && this.animSpec.idle) {
                    maxFrames = this.animSpec.idle.fDir || 8;
                } else if ((this.state === UnitState.ATTACK || this.state === UnitState.ATTACK_WINDUP || this.state === UnitState.ATTACK_COOLDOWN) && this.animSpec.atk) {
                    maxFrames = this.animSpec.atk.fDir || 8;
                }
            }
            this.animFrame = (this.animFrame + 1) % maxFrames;
        }

        // Decrement attack cooldown timer
        if (this.attackTimer > 0) {
            this.attackTimer = Math.max(0, this.attackTimer - deltaSec);
        }

        // State Machine Dispatch
        switch (this.state) {
            case UnitState.IDLE:
                this.updateIdle(deltaSec, grid, entityList);
                break;
            case UnitState.WALK:
                this.updateWalk(deltaSec, grid);
                break;
            case UnitState.ATTACK_WINDUP:
                this.updateWindup(deltaSec, audioManager, projectiles, grid);
                break;
            case UnitState.ATTACK_COOLDOWN:
            case UnitState.ATTACK:
                this.updateCooldown(deltaSec, grid);
                break;
        }

        // Keep integer grid tile synchronized
        this.gx = Math.floor(this.wx);
        this.gy = Math.floor(this.wy);
    }

    /**
     * Updates walking along waypoints with dynamic move_speed physics.
     *
     * @param {number} deltaSec - Elapsed seconds
     * @param {Object} grid - GameGrid
     */
    updateWalk(deltaSec, grid) {
        // Hold Position (홀드 E): 0 displacement clamp
        if (this.holdPosition) {
            this.waypoints = [];
            this.state = UnitState.IDLE;
            return;
        }

        if (this.waypoints.length === 0) {
            this.state = UnitState.IDLE;
            return;
        }

        const currentSpeed = (this.statusEffects && this.statusEffects.slowed > 0)
            ? (this.move_speed * 0.5)
            : this.move_speed;
        let remainingStep = (currentSpeed / 4) * deltaSec;

        while (remainingStep > 0 && this.waypoints.length > 0) {
            const next = this.waypoints[0];
            const targetWx = next.gx + 0.5;
            const targetWy = next.gy + 0.5;

            const dx = targetWx - this.wx;
            const dy = targetWy - this.wy;
            const dist = Math.hypot(dx, dy);

            if (dist < 0.0001) {
                this.waypoints.shift();
                continue;
            }

            // Compute 8-direction orientation from isometric screen vector
            this.direction = Unit.calculateDirection(dx, dy);

            if (dist <= remainingStep) {
                this.wx = targetWx;
                this.wy = targetWy;
                this.totalDistanceMoved += dist;
                remainingStep -= dist;
                this.waypoints.shift();

                if (this.waypoints.length === 0) {
                    this.state = UnitState.IDLE;
                    break;
                }
            } else {
                const moveFraction = remainingStep / dist;
                this.wx += dx * moveFraction;
                this.wy += dy * moveFraction;
                this.totalDistanceMoved += remainingStep;
                remainingStep = 0;
            }
        }
    }

    /**
     * Updates idle behavior, including chasing targetEntity if assigned,
     * respecting holdPosition, attackMoveTarget, and patrolRoute.
     */
    updateIdle(deltaSec, grid, entityList) {
        if (this.targetEntity) {
            if (this.targetEntity.isDead) {
                this.targetEntity = null;
                return;
            }

            const dist = Math.hypot(this.targetEntity.wx - this.wx, this.targetEntity.wy - this.wy);
            let effectiveRange = this.attack_range || 1.5;
            if (this.hybrid && this.kindId === 0x79) {
                if (this.mp >= (this.ranged_mp_cost || 20)) {
                    effectiveRange = this.ranged_attack_range || 6.0;
                }
            }

            if (dist <= effectiveRange) {
                // In range: face target and initiate attack if cooldown ready
                this.direction = Unit.calculateDirection(this.targetEntity.wx - this.wx, this.targetEntity.wy - this.wy);
                if (this.attackTimer <= 0) {
                    this.state = UnitState.ATTACK_WINDUP;
                    this.windupTimer = this.windupDuration;
                }
            } else if (this.holdPosition) {
                // Hold Position (홀드 E): never chase targets outside attack range, clamp displacement to 0
                this.targetEntity = null;
                this.waypoints = [];
            } else {
                // Out of range: check enemy leash if marching on Attack-Move
                if (this.attackMoveTarget && dist > (this.sight_range || 8) * 1.5) {
                    this.targetEntity = null;
                    return;
                }
                // Out of range: calculate path to target
                const targetGx = Math.floor(this.targetEntity.wx);
                const targetGy = Math.floor(this.targetEntity.wy);
                const path = PathFinder.findPath(grid, Math.floor(this.wx), Math.floor(this.wy), targetGx, targetGy);
                if (path && path.length > 0) {
                    this.waypoints = path;
                    this.state = UnitState.WALK;
                }
            }
            return;
        }

        // Resume Attack-Move destination once combat clears
        if (this.attackMoveTarget && grid) {
            const distToDest = Math.hypot(this.wx - (this.attackMoveTarget.gx + 0.5), this.wy - (this.attackMoveTarget.gy + 0.5));
            if (distToDest > 1.4) {
                const dest = this.attackMoveTarget;
                const path = PathFinder.findPath(grid, Math.floor(this.wx), Math.floor(this.wy), dest.gx, dest.gy);
                if (path && path.length > 0) {
                    this.waypoints = path;
                    this.state = UnitState.WALK;
                } else {
                    this.attackMoveTarget = null;
                }
            } else {
                this.attackMoveTarget = null;
            }
        } else if (this.patrolRoute && grid) {
            const dest = this.patrolRoute.goingToEnd ? this.patrolRoute.to : this.patrolRoute.from;
            const distToDest = Math.hypot(this.wx - (dest.gx + 0.5), this.wy - (dest.gy + 0.5));
            if (distToDest <= 1.5) {
                this.patrolRoute.goingToEnd = !this.patrolRoute.goingToEnd;
            }
            const nextDest = this.patrolRoute.goingToEnd ? this.patrolRoute.to : this.patrolRoute.from;
            const path = PathFinder.findPath(grid, Math.floor(this.wx), Math.floor(this.wy), nextDest.gx, nextDest.gy);
            if (path && path.length > 0) {
                this.waypoints = path;
                this.state = UnitState.WALK;
            }
        }
    }

    /**
     * Handles attack windup timer before damage / projectile release.
     */
    updateWindup(deltaSec, audioManager, projectiles, grid = null) {
        if (!this.targetEntity || this.targetEntity.isDead) {
            this.targetEntity = null;
            this.state = UnitState.IDLE;
            return;
        }

        // Keep facing target
        this.direction = Unit.calculateDirection(this.targetEntity.wx - this.wx, this.targetEntity.wy - this.wy);

        this.windupTimer -= deltaSec;
        if (this.windupTimer <= 0) {
            // Execute attack!
            this.executeAttack(audioManager, projectiles, grid);
            // Enter cooldown
            const cooldownSec = (this.attack_delay || 30) / 30; // 30 ticks = 1.0 second
            this.attackTimer = Math.max(0.2, cooldownSec);
            this.state = UnitState.ATTACK_COOLDOWN;
        }
    }

    /**
     * Executes the attack: creates projectile or applies direct melee strike.
     * Incorporates high-ground elevation advantage via CombatSystem.calculateDamage().
     */
    executeAttack(audioManager, projectiles, grid = null) {
        let target = this.targetEntity;
        let actualAudioManager = audioManager;
        let actualProjectiles = projectiles;
        let actualGrid = grid;

        // Support alternate signature: executeAttack(target, grid, audioManager)
        if (audioManager && (typeof audioManager.takeDamage === 'function' || (audioManager.id !== undefined && audioManager.hp !== undefined))) {
            target = audioManager;
            actualGrid = projectiles;
            actualAudioManager = grid;
            actualProjectiles = null;
        }

        if (!target || target.isDead) return;

        let damage = this.attack_power;
        let alreadyMitigated = false;
        if (actualGrid) {
            damage = CombatSystem.calculateDamage(this, target, actualGrid);
            alreadyMitigated = true;
        }

        // Hybrid Attack Evaluation (e.g. 0x79 불가살이)
        let isRanged = Boolean(this.projectile_type && actualProjectiles);
        let usedProjectileType = this.projectile_type;
        const distToTarget = Math.hypot(target.wx - this.wx, target.wy - this.wy);

        if (this.hybrid && this.kindId === 0x79) {
            const mpCost = this.ranged_mp_cost || 20;
            if (distToTarget > 1.5 && this.mp >= mpCost && actualProjectiles) {
                this.consumeMana(mpCost);
                isRanged = true;
                usedProjectileType = 'fireball';
            } else {
                // Engage in melee smash when close (<= 1.5) or MP is depleted
                isRanged = false;
            }
        }

        // Configure projectile / attack status payloads
        const options = { sourceUnit: this };
        if (this.kindId === 0x70 || usedProjectileType === 'magic_bind') {
            options.statusEffect = { type: 'paralyzed', duration: 3.5 };
        } else if (this.kindId === 0x76 || usedProjectileType === 'frost_freeze') {
            options.statusEffect = { type: 'frozen', duration: 3.0 };
        } else if (this.kindId === 0x77 || usedProjectileType === 'ice_splash') {
            options.statusEffect = { type: 'slowed', duration: 4.0 };
            options.splashRadius = 2.0;
            options.splashFactor = 0.6;
        }

        if (isRanged && actualProjectiles) {
            // Ranged attack: spawn projectile
            const projId = Date.now() + Math.random();
            const projSpeed = usedProjectileType === 'bullet' ? 24 : 12;
            const proj = new Projectile(
                projId,
                usedProjectileType,
                this.wx,
                this.wy,
                target,
                projSpeed,
                damage,
                options
            );
            actualProjectiles.push(proj);

            if (actualAudioManager) {
                let soundName = 'arrow';
                if (usedProjectileType === 'cannon') soundName = 'cannon';
                else if (usedProjectileType === 'fireball') soundName = 'fire1';
                else if (usedProjectileType === 'bullet') soundName = 'gun1';
                else if (usedProjectileType === 'frost_freeze' || usedProjectileType === 'ice_splash') soundName = 'freeze';
                else if (usedProjectileType === 'magic_bind') soundName = 'magic';
                actualAudioManager.play(soundName, this.wx, this.wy);
            }
        } else {
            // Melee attack: apply damage directly
            target.takeDamage(damage, actualAudioManager, alreadyMitigated);
            if (options.statusEffect && typeof target.applyStatusEffect === 'function') {
                target.applyStatusEffect(options.statusEffect.type, options.statusEffect.duration, this);
            }
            if (actualAudioManager) {
                const meleeSound = (this.kindId === 0x78 || this.kindId === 0x79) ? 'cannon' : 'attack';
                actualAudioManager.play(meleeSound, this.wx, this.wy);
            }
        }
    }

    /**
     * Updates attack cooldown state.
     */
    updateCooldown(deltaSec, grid) {
        if (this.attackTimer <= 0) {
            this.state = UnitState.IDLE;
        }
    }

    /**
     * Applies damage to the unit considering its defense value.
     *
     * @param {number} damage - Incoming damage
     * @param {Object} [audioManager=null] - Audio manager for sound effects
     * @param {boolean} [alreadyMitigated=false] - True if defense/elevation was already applied
     * @returns {number} Actual net damage taken
     */
    takeDamage(damage, audioManager = null, alreadyMitigated = false) {
        if (this.isDead) return 0;

        const netDamage = alreadyMitigated ? Math.max(1, Math.round(damage)) : Math.max(1, Math.round(damage - this.defense));
        this.hp = Math.max(0, this.hp - netDamage);

        if (this.hp <= 0) {
            this.hp = 0;
            this.waypoints = [];
            this.targetEntity = null;
            if (audioManager) {
                audioManager.play('die', this.wx, this.wy);
            }

            // Air Unit (0x74 조선왕벌, isAirUnit): ENFORCE zero-corpse instant vanish rule!
            // When HP <= 0, hornet must vanish instantly with ZERO ground corpse decay, ZERO decal, and ZERO ground tile footprint.
            if (this.isAirUnit) {
                this.isDead = true;
                this.isDying = false;
                this.state = UnitState.DIE;
                this.deathAnimDone = true;
                this.corpseAlpha = 0.0;
                return netDamage;
            }

            // Ground units enter death animation followed by 4.0s CORPSE_DECAY
            this.isDead = true;
            this.isDying = true;
            this.deathTimer = 0;
            this.animFrame = 0;
            this.animTimer = 0;
            this.state = UnitState.DIE;
            const dieFrames = (this.animSpec && this.animSpec.die && this.animSpec.die.total) ? this.animSpec.die.total : 8;
            this.deathDuration = dieFrames / this.frameRate;
        }
        return netDamage;
    }

    /**
     * Restores health points up to max_hp.
     *
     * @param {number} amount - HP to restore
     */
    heal(amount) {
        if (this.isDead) return;
        this.hp = Math.min(this.max_hp, this.hp + amount);
    }

    /**
     * Restores mana points up to max_mp.
     *
     * @param {number} amount - MP to restore
     */
    restoreMana(amount) {
        if (this.isDead) return;
        this.mp = Math.min(this.max_mp, this.mp + amount);
    }

    /**
     * Consumes mana for special skills or spells.
     *
     * @param {number} amount - MP cost
     * @returns {boolean} True if mana was successfully consumed
     */
    consumeMana(amount) {
        if (this.mp >= amount) {
            this.mp -= amount;
            return true;
        }
        return false;
    }

    /**
     * Calculates 8-direction orientation (0=S..7=SE) from continuous grid displacement (dx, dy).
     *
     * @param {number} dx - World delta X
     * @param {number} dy - World delta Y
     * @returns {number} Direction index (0..7)
     */
    static calculateDirection(dx, dy) {
        if (Math.abs(dx) < 0.0001 && Math.abs(dy) < 0.0001) {
            return Direction.S;
        }

        // Convert world delta (dx, dy) to screen projection vector (sx, sy)
        const sx = (dx - dy) * 32;
        const sy = (dx + dy) * 24;

        // Angle in radians (-PI to +PI)
        const angle = Math.atan2(sy, sx);

        // Normalize so South (angle = PI/2) maps to 0
        const normalized = (angle - (Math.PI / 2) + (2 * Math.PI)) % (2 * Math.PI);
        const dir = Math.round(normalized / (Math.PI / 4)) % 8;

        return dir;
    }
}

export class Building {
    /**
     * @param {number} id - Unique building ID
     * @param {Object} archetype - Building archetype data
     * @param {number} gx - Origin tile X
     * @param {number} gy - Origin tile Y
     * @param {number} [owner=0] - Player owner ID
     */
    constructor(id, archetype = {}, gx = 0, gy = 0, owner = 0) {
        this.id = id;
        this.archetype = archetype;
        this.owner = owner;
        this.name = archetype.korean_name || archetype.name || `Building_${id}`;
        this.spriteName = archetype.sprite_name || archetype.sprite || 'char/base_chosun.spr';

        this.gx = gx;
        this.gy = gy;
        this.width = archetype.width || 3;
        this.height = archetype.height || 3;

        // Centered world coordinates
        this.wx = gx + (this.width / 2);
        this.wy = gy + (this.height / 2);

        this.max_hp = archetype.hp || 1500;
        this.hp = this.max_hp;
        this.defense = archetype.defense || 5;
        this.isDead = false;
        this.selected = false;

        // Production Queue
        this.productionQueue = [];
        this.currentProductionTime = 0;
        this.totalProductionTime = 0;
        this.rallyPoint = { gx: gx + this.width, gy: gy + this.height };
    }

    /**
     * Adds a unit to the production queue.
     *
     * @param {Object} unitArchetype - Archetype definition of unit to produce
     * @param {number} [buildTime=5.0] - Production time in seconds
     */
    queueUnit(unitArchetype, buildTime = 5.0) {
        if (this.isDead) return false;
        if (this.productionQueue.length >= 5) return false; // Queue full

        this.productionQueue.push({
            archetype: unitArchetype,
            buildTime: buildTime
        });

        if (this.productionQueue.length === 1) {
            this.currentProductionTime = 0;
            this.totalProductionTime = buildTime;
        }
        return true;
    }

    /**
     * Cancels an item in the production queue by index.
     *
     * @param {number} index - Queue index to cancel
     */
    cancelProduction(index) {
        if (index < 0 || index >= this.productionQueue.length) return;
        this.productionQueue.splice(index, 1);
        if (index === 0 && this.productionQueue.length > 0) {
            this.currentProductionTime = 0;
            this.totalProductionTime = this.productionQueue[0].buildTime;
        }
    }

    /**
     * Updates production progress.
     *
     * @param {number} deltaSec - Frame elapsed time in seconds
     * @returns {Object|null} Completed unit archetype ready to spawn, or null
     */
    update(deltaSec) {
        if (this.isDead || this.productionQueue.length === 0) return null;

        this.currentProductionTime += deltaSec;
        if (this.currentProductionTime >= this.totalProductionTime) {
            const completed = this.productionQueue.shift();
            if (this.productionQueue.length > 0) {
                this.currentProductionTime = 0;
                this.totalProductionTime = this.productionQueue[0].buildTime;
            }
            return completed.archetype;
        }
        return null;
    }

    /**
     * Applies damage to the building.
     *
     * @param {number} damage - Incoming damage
     * @param {Object} [audioManager=null]
     * @param {boolean} [alreadyMitigated=false]
     * @returns {number} Net damage taken
     */
    takeDamage(damage, audioManager = null, alreadyMitigated = false) {
        if (this.isDead) return 0;
        const netDamage = alreadyMitigated ? Math.max(1, Math.round(damage)) : Math.max(1, Math.round(damage - this.defense));
        this.hp = Math.max(0, this.hp - netDamage);

        if (this.hp <= 0) {
            this.hp = 0;
            this.isDead = true;
            this.productionQueue = [];
            if (audioManager) {
                audioManager.play('explosion', this.wx, this.wy);
            }
        }
        return netDamage;
    }
}

export class Projectile {
    /**
     * @param {number|string} id - Unique projectile ID
     * @param {string} type - 'arrow', 'bullet', 'cannon', 'fireball', 'magic_bind', 'frost_freeze', 'ice_splash'
     * @param {number} startX - World grid X origin
     * @param {number} startY - World grid Y origin
     * @param {Unit|Building|Object} targetEntity - Target entity or coordinate object
     * @param {number} [speed=10] - Travel speed in tiles/sec
     * @param {number} [damage=10] - Damage delivered upon impact
     * @param {Object} [options={}] - Options payload: statusEffect, splashRadius, splashFactor, sourceUnit
     */
    constructor(id, type, startX, startY, targetEntity, speed = 10, damage = 10, options = {}) {
        // Defensive support for swapped/legacy signature: (id, startX, startY, targetX, targetY, damage, type, caster)
        if (typeof type === 'number' && typeof startX === 'number' && typeof startY === 'number') {
            const actualStartX = type;
            const actualStartY = startX;
            const actualTargetX = startY;
            const actualTargetY = targetEntity;
            const actualDamage = typeof speed === 'number' ? speed : 10;
            const actualType = typeof damage === 'string' ? damage : 'cannon';
            const actualSource = options;
            type = actualType;
            startX = actualStartX;
            startY = actualStartY;
            targetEntity = { wx: actualTargetX + 0.5, wy: actualTargetY + 0.5 };
            speed = 12;
            damage = actualDamage;
            options = { sourceUnit: actualSource };
        }

        this.id = id;
        this.type = type;
        this.startX = startX;
        this.startY = startY;
        this.targetEntity = targetEntity;
        this.targetWx = targetEntity ? (targetEntity.wx !== undefined ? targetEntity.wx : (targetEntity.gx !== undefined ? targetEntity.gx + 0.5 : startX)) : startX;
        this.targetWy = targetEntity ? (targetEntity.wy !== undefined ? targetEntity.wy : (targetEntity.gy !== undefined ? targetEntity.gy + 0.5 : startY)) : startY;
        this.speed = speed;
        this.damage = damage;
        this.progress = 0; // 0.0 to 1.0
        this.isArrived = false;

        this.options = options || {};
        this.statusEffect = this.options.statusEffect || null;
        this.splashRadius = this.options.splashRadius || 0;
        this.splashFactor = (this.options.splashFactor !== undefined) ? this.options.splashFactor : 0.6;
        this.sourceUnit = this.options.sourceUnit || null;

        const dist = Math.hypot(this.targetWx - this.startX, this.targetWy - this.startY);
        this.travelDuration = Math.max(0.05, dist / this.speed);
    }

    get targetX() {
        return this.targetWx;
    }

    get targetY() {
        return this.targetWy;
    }

    /**
     * Advances projectile position along its trajectory.
     *
     * @param {number} deltaSec - Frame elapsed time in seconds
     * @param {Object} [audioManager=null]
     * @param {Array<Object>} [entityList=null] - Battlefield entities for splash damage calculation
     */
    update(deltaSec, audioManager = null, entityList = null) {
        if (this.isArrived) return;

        // Track target entity position if target moves
        if (this.targetEntity && this.targetEntity.wx !== undefined) {
            this.targetWx = this.targetEntity.wx;
            this.targetWy = this.targetEntity.wy;
        }

        this.progress += deltaSec / this.travelDuration;

        if (this.progress >= 1.0) {
            this.progress = 1.0;
            this.isArrived = true;

            // Deliver primary target damage and status payload
            if (this.targetEntity && !this.targetEntity.isDead && typeof this.targetEntity.takeDamage === 'function') {
                this.targetEntity.takeDamage(this.damage, audioManager);
                if (this.statusEffect && typeof this.targetEntity.applyStatusEffect === 'function') {
                    this.targetEntity.applyStatusEffect(this.statusEffect.type, this.statusEffect.duration, this.sourceUnit);
                }
                if (audioManager) {
                    let hitSound = 'arrow_hit';
                    if (this.type === 'cannon' || this.type === 'fireball') hitSound = 'explosion';
                    else if (this.type === 'frost_freeze' || this.type === 'ice_splash') hitSound = 'freeze';
                    else if (this.type === 'magic_bind') hitSound = 'magic';
                    audioManager.play(hitSound, this.targetWx, this.targetWy);
                }
            }

            // Deliver AoE splash damage and status payload to surrounding entities (e.g. 0x77 설녀 radius 2.0)
            if (this.splashRadius > 0 && Array.isArray(entityList)) {
                const splashDmg = Math.max(1, Math.round(this.damage * this.splashFactor));
                const splashX = this.targetWx;
                const splashY = this.targetWy;
                for (const ent of entityList) {
                    if (!ent || ent.isDead || ent === this.targetEntity || typeof ent.takeDamage !== 'function') continue;

                    // Hit hostiles
                    const isEnemy = (this.targetEntity && this.targetEntity.owner !== undefined)
                        ? (ent.owner === this.targetEntity.owner)
                        : (this.sourceUnit && this.sourceUnit.owner !== undefined ? ent.owner !== this.sourceUnit.owner : true);

                    if (isEnemy) {
                        const d = Math.hypot(ent.wx - splashX, ent.wy - splashY);
                        if (d <= this.splashRadius) {
                            ent.takeDamage(splashDmg, null);
                            if (this.statusEffect && typeof ent.applyStatusEffect === 'function') {
                                ent.applyStatusEffect(this.statusEffect.type, Math.max(1.0, this.statusEffect.duration * 0.75), this.sourceUnit);
                            }
                        }
                    }
                }
            }
        }
    }

    /**
     * Returns current 3D position (wx, wy, arcZ) for isometric rendering.
     *
     * @returns {{ wx: number, wy: number, arcZ: number }}
     */
    getCurrentPos() {
        const curWx = this.startX + (this.targetWx - this.startX) * this.progress;
        const curWy = this.startY + (this.targetWy - this.startY) * this.progress;

        // Parabolic vertical arc for ballistic trajectories (arrows and cannonballs)
        const arcZ = (this.type === 'arrow' || this.type === 'cannon')
            ? Math.sin(this.progress * Math.PI) * 40
            : 0;

        return { wx: curWx, wy: curWy, arcZ };
    }
}
