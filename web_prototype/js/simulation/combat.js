/**
 * Combat Simulation System for Imjinrok 2+: Dawn
 *
 * Handles target acquisition, attack range checks, elevation advantage damage modifiers,
 * projectile tracking, and overall combat lifecycle management.
 */

import { Projectile, UnitState } from './entities.js';

export class CombatSystem {
    /**
     * Calculates net damage inflicted by attacker onto target entity.
     * Incorporates defense subtraction and high-ground elevation advantage.
     *
     * @param {Object} attacker - Attacking Unit
     * @param {Object} target - Target Unit or Building
     * @param {Object} [grid=null] - GameGrid instance for elevation checks
     * @returns {number} Net damage (minimum 1)
     */
    static calculateDamage(attacker, target, grid = null) {
        let baseDmg = attacker.attack_power || 10;

        // High ground elevation advantage: +15% damage bonus if attacker is at higher elevation
        if (grid && attacker.gx !== undefined && target.gx !== undefined) {
            const attackerElev = grid.getElevation(attacker.gx, attacker.gy);
            const targetElev = grid.getElevation(target.gx, target.gy);
            if (attackerElev > targetElev) {
                baseDmg = Math.round(baseDmg * 1.15);
            }
        }

        const defense = target.defense || 0;
        return Math.max(1, Math.round(baseDmg - defense));
    }

    /**
     * Checks if target is within attacker's attack range.
     *
     * @param {Object} attacker - Attacking entity
     * @param {Object} target - Target entity
     * @param {number} [extraMargin=0.2] - Tolerance threshold to prevent jitter
     * @returns {boolean} True if within range
     */
    static isInRange(attacker, target, extraMargin = 0.2) {
        if (!attacker || !target) return false;
        let effectiveRange = attacker.attack_range || 1.5;
        if (attacker.hybrid && attacker.kindId === 0x79) {
            if (attacker.mp >= (attacker.ranged_mp_cost || 20)) {
                effectiveRange = attacker.ranged_attack_range || 6.0;
            }
        }
        const dist = Math.hypot(target.wx - attacker.wx, target.wy - attacker.wy);
        const range = effectiveRange + extraMargin;
        return dist <= range;
    }

    /**
     * Scans entity list for the closest living enemy within sight range.
     *
     * @param {Object} unit - Inquiring unit
     * @param {Array<Object>} entityList - List of all active units and buildings
     * @param {number} [maxRange] - Maximum scan distance (defaults to unit.sight_range)
     * @returns {Object|null} Nearest hostile entity or null
     */
    static findNearestEnemy(unit, entityList, maxRange = null) {
        if (!unit || unit.isDead) return null;

        const scanLimit = maxRange !== null ? maxRange : (unit.sight_range || 8);
        let closestEnemy = null;
        let closestDist = Infinity;

        for (const ent of entityList) {
            if (ent === unit || ent.isDead) continue;
            // Hostility check: different owner (e.g. 0=player, 1=enemy)
            if (ent.owner !== unit.owner && ent.owner !== 2) { // 2 = neutral
                const dist = Math.hypot(ent.wx - unit.wx, ent.wy - unit.wy);
                if (dist <= scanLimit && dist < closestDist) {
                    closestDist = dist;
                    closestEnemy = ent;
                }
            }
        }
        return closestEnemy;
    }

    /**
     * Updates combat state for an individual unit.
     *
     * @param {Object} unit - Unit instance
     * @param {number} deltaSec - Elapsed seconds
     * @param {Array<Object>} entityList - All entities
     * @param {Array<Projectile>} projectiles - Active projectile list
     * @param {Object} [audioManager=null]
     * @param {Object} [grid=null]
     */
    static updateUnitCombat(unit, deltaSec, entityList, projectiles, audioManager = null, grid = null) {
        if (!unit || unit.isDead) return;

        // Workers busy harvesting or constructing do not auto-aggro enemies
        if (unit.isWorker && (unit.autoHarvest || unit.constructingTarget) && !unit.targetEntity) {
            return;
        }

        // If unit is idle (or walking in Attack-Move / Patrol mode) without an explicit target, auto-acquire nearby enemy
        const isAttackMoving = Boolean(unit.attackMoveTarget || unit.patrolRoute);
        if (!unit.targetEntity && (unit.state === UnitState.IDLE || (isAttackMoving && unit.state === UnitState.WALK))) {
            const scanLimit = unit.holdPosition ? (unit.attack_range || 1.5) + 0.2 : null;
            const enemy = this.findNearestEnemy(unit, entityList, scanLimit);
            if (enemy) {
                unit.targetEntity = enemy;
                if (isAttackMoving && unit.state === UnitState.WALK) {
                    unit.waypoints = [];
                    unit.state = UnitState.IDLE;
                }
            }
        }

        // If unit has an active target
        if (unit.targetEntity) {
            if (unit.targetEntity.isDead) {
                unit.targetEntity = null;
                if (unit.state === UnitState.ATTACK_WINDUP || unit.state === UnitState.ATTACK) {
                    unit.state = UnitState.IDLE;
                }
                return;
            }

            // Check if within attack range
            if (this.isInRange(unit, unit.targetEntity)) {
                // If walking, stop and engage
                if (unit.state === UnitState.WALK) {
                    unit.waypoints = [];
                    unit.state = UnitState.IDLE;
                }

                // If ready to attack
                if (unit.state === UnitState.IDLE && unit.attackTimer <= 0) {
                    unit.state = UnitState.ATTACK_WINDUP;
                    unit.windupTimer = unit.windupDuration || 0.25;
                }
            }
        }
    }

    /**
     * Spawns a projectile directed at a target.
     *
     * @param {Object} attacker - Firing unit
     * @param {Object} target - Target unit or building
     * @param {Array<Projectile>} projectiles - Active projectile list
     * @param {Object} [audioManager=null]
     * @returns {Projectile} Newly spawned projectile
     */
    static spawnProjectile(attacker, target, projectiles, audioManager = null) {
        let type = attacker.projectile_type || (attacker.attack_range > 2.5 ? 'arrow' : 'bullet');
        const projId = `${attacker.id}_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
        const speed = (type === 'cannon') ? 8 : (type === 'bullet' ? 24 : (type === 'arrow' ? 12 : 14));
        const damage = attacker.attack_power || 10;

        const options = { sourceUnit: attacker };
        if (attacker.kindId === 0x70 || type === 'magic_bind') {
            options.statusEffect = { type: 'paralyzed', duration: 3.5 };
        } else if (attacker.kindId === 0x76 || type === 'frost_freeze') {
            options.statusEffect = { type: 'frozen', duration: 3.0 };
        } else if (attacker.kindId === 0x77 || type === 'ice_splash') {
            options.statusEffect = { type: 'slowed', duration: 4.0 };
            options.splashRadius = 2.0;
            options.splashFactor = 0.6;
        }

        const proj = new Projectile(
            projId,
            type,
            attacker.wx,
            attacker.wy,
            target,
            speed,
            damage,
            options
        );
        projectiles.push(proj);

        if (audioManager) {
            let soundKey = (type === 'cannon') ? 'cannon' : 'arrow';
            if (type === 'bullet') soundKey = 'gun1';
            else if (type === 'fireball') soundKey = 'fire1';
            else if (type === 'frost_freeze' || type === 'ice_splash') soundKey = 'freeze';
            else if (type === 'magic_bind') soundKey = 'magic';
            audioManager.play(soundKey, attacker.wx, attacker.wy);
        }
        return proj;
    }

    /**
     * Updates all active projectiles and removes those that have arrived.
     * Passes entityList to proj.update() for AoE splash damage computation.
     *
     * @param {Array<Projectile>} projectiles - Active projectile list
     * @param {number} deltaSec - Elapsed seconds
     * @param {Object} [audioManager=null]
     * @param {Array<Object>} [entityList=null]
     */
    static updateProjectiles(projectiles, deltaSec, audioManager = null, entityList = null) {
        for (let i = projectiles.length - 1; i >= 0; i--) {
            const proj = projectiles[i];
            proj.update(deltaSec, audioManager, entityList);
            if (proj.isArrived) {
                projectiles.splice(i, 1);
            }
        }
    }

    /**
     * Top-level simulation step for combat across all entities and projectiles.
     *
     * @param {Array<Object>} entities - All units and buildings
     * @param {Array<Projectile>} projectiles - Active projectile list
     * @param {number} deltaSec - Elapsed seconds
     * @param {Object} [audioManager=null]
     * @param {Object} [grid=null]
     */
    static update(entities, projectiles, deltaSec, audioManager = null, grid = null) {
        for (const ent of entities) {
            if (ent.update && !ent.isDead) {
                this.updateUnitCombat(ent, deltaSec, entities, projectiles, audioManager, grid);
            }
        }
        this.updateProjectiles(projectiles, deltaSec, audioManager, entities);
    }

    // =========================================================================
    // Custom Joseon Units (0x70 ~ 0x79) Skills & Combat Abilities
    // =========================================================================

    /**
     * 0x70 유생: 포박술 (Paralysis Spell)
     * Fires talisman binding projectile or directly applies 3.5s paralysis to target.
     */
    static castPobaksul(caster, target, projectiles = null, audioManager = null) {
        if (!caster || !target || target.isDead) return false;
        if (projectiles) {
            const projId = `pobak_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            const proj = new Projectile(
                projId,
                'magic_bind',
                caster.wx,
                caster.wy,
                target,
                14,
                caster.attack_power || 18,
                {
                    sourceUnit: caster,
                    statusEffect: { type: 'paralyzed', duration: 3.5 }
                }
            );
            projectiles.push(proj);
        } else {
            if (typeof target.takeDamage === 'function') {
                target.takeDamage(caster.attack_power || 18, audioManager);
            }
            if (typeof target.applyStatusEffect === 'function') {
                target.applyStatusEffect('paralyzed', 3.5, caster);
            }
        }
        if (audioManager) {
            audioManager.play('magic', caster.wx, caster.wy);
        }
        return true;
    }

    /**
     * 0x71 검술 낭인: 폭뢰격 (Explosion Wave Skill)
     * Consumes 60 MP and inflicts 150 AoE fire damage within 3x3 tiles.
     */
    static castPokroegyeok(caster, targetGx, targetGy, entities = [], groundFires = null, audioManager = null) {
        if (!caster || caster.isDead) return false;
        const mpCost = 60;
        if (caster.consumeMana && !caster.consumeMana(mpCost)) {
            return false;
        }

        const centerWx = targetGx + 0.5;
        const centerWy = targetGy + 0.5;

        for (const ent of entities) {
            if (!ent || ent.isDead || ent === caster || ent.owner === caster.owner) continue;
            const dist = Math.hypot(ent.wx - centerWx, ent.wy - centerWy);
            if (dist <= 2.2) {
                if (typeof ent.takeDamage === 'function') {
                    ent.takeDamage(150, audioManager);
                }
            }
        }

        if (Array.isArray(groundFires)) {
            groundFires.push(
                { wx: centerWx, wy: centerWy, phase: 0, life: 25.0, spreadTimer: 0 },
                { wx: centerWx + 0.6, wy: centerWy + 0.4, phase: 8, life: 25.0, spreadTimer: 1.0 },
                { wx: centerWx - 0.5, wy: centerWy + 0.6, phase: 16, life: 25.0, spreadTimer: 2.0 }
            );
        }

        if (audioManager) {
            audioManager.play('fire1', centerWx, centerWy);
        }
        return true;
    }

    /**
     * 0x73 구미호: 분신술 (Illusion Duplication Skill)
     * Consumes 50 MP and spawns an illusion clone lasting 25 seconds.
     */
    static castBunshinsul(caster, entities = [], spawnCallback = null) {
        if (!caster || caster.isDead) return null;
        const mpCost = 50;
        if (caster.consumeMana && !caster.consumeMana(mpCost)) {
            return null;
        }

        const spawnGx = Math.round(caster.wx) + 1;
        const spawnGy = Math.round(caster.wy) + 1;

        if (typeof spawnCallback === 'function') {
            return spawnCallback({
                archetype: {
                    ...(caster.archetype || {}),
                    isIllusion: true,
                    illusionDuration: 25.0,
                    hp: 300,
                    max_hp: 300
                },
                gx: spawnGx,
                gy: spawnGy,
                faction: caster.owner || 0
            });
        }

        // Direct instantiation fallback
        const clone = Object.assign(Object.create(Object.getPrototypeOf(caster)), caster);
        clone.id = Date.now() + Math.random();
        clone.isIllusion = true;
        clone.illusionDuration = 25.0;
        clone.hp = 300;
        clone.max_hp = 300;
        clone.name = `${caster.name || '구미호'} (분신)`;
        clone.gx = spawnGx;
        clone.gy = spawnGy;
        clone.wx = spawnGx + 0.5;
        clone.wy = spawnGy + 0.5;
        if (Array.isArray(entities)) {
            entities.push(clone);
        }
        return clone;
    }

    /**
     * 0x76 털가면: 얼리기 (Freeze Attack)
     * Launches frost bomb inflicting 3.0s complete freezing immobilization.
     */
    static castFreeze(caster, target, projectiles = null, audioManager = null) {
        if (!caster || !target || target.isDead) return false;
        if (projectiles) {
            const projId = `freeze_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            const proj = new Projectile(
                projId,
                'frost_freeze',
                caster.wx,
                caster.wy,
                target,
                12,
                caster.attack_power || 28,
                {
                    sourceUnit: caster,
                    statusEffect: { type: 'frozen', duration: 3.0 }
                }
            );
            projectiles.push(proj);
        } else {
            if (typeof target.takeDamage === 'function') {
                target.takeDamage(caster.attack_power || 28, audioManager);
            }
            if (typeof target.applyStatusEffect === 'function') {
                target.applyStatusEffect('frozen', 3.0, caster);
            }
        }
        if (audioManager) {
            audioManager.play('freeze', caster.wx, caster.wy);
        }
        return true;
    }

    /**
     * 0x77 설녀: 얼음 스플래쉬 (Ice Splash AoE)
     * Fires ice projectile that inflicts damage, radius 2.0 AoE splash, and 4.0s slow.
     */
    static castIceSplash(caster, target, projectiles = null, audioManager = null) {
        if (!caster || !target || target.isDead) return false;
        if (projectiles) {
            const projId = `splash_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            const proj = new Projectile(
                projId,
                'ice_splash',
                caster.wx,
                caster.wy,
                target,
                12,
                caster.attack_power || 36,
                {
                    sourceUnit: caster,
                    statusEffect: { type: 'slowed', duration: 4.0 },
                    splashRadius: 2.0,
                    splashFactor: 0.6
                }
            );
            projectiles.push(proj);
        } else {
            if (typeof target.takeDamage === 'function') {
                target.takeDamage(caster.attack_power || 36, audioManager);
            }
            if (typeof target.applyStatusEffect === 'function') {
                target.applyStatusEffect('slowed', 4.0, caster);
            }
        }
        if (audioManager) {
            audioManager.play('freeze', caster.wx, caster.wy);
        }
        return true;
    }

    /**
     * 0x79 불가살이: 하이브리드 공격 (Hybrid Attack Dispatch)
     * When MP >= 20 and dist > 1.5: fires range 6.0 flame cart projectile (consumes 20 MP).
     * When MP < 20 or dist <= 1.5: executes heavy melee smash (0 MP cost).
     */
    static castBulgasariAttack(caster, target, projectiles = null, audioManager = null) {
        if (!caster || !target || target.isDead) return 'none';
        const dist = Math.hypot(target.wx - caster.wx, target.wy - caster.wy);
        const mpCost = caster.ranged_mp_cost || 20;

        if (dist > 1.5 && caster.mp >= mpCost && projectiles) {
            caster.consumeMana(mpCost);
            const projId = `flame_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            const proj = new Projectile(
                projId,
                'fireball',
                caster.wx,
                caster.wy,
                target,
                14,
                caster.attack_power || 46,
                { sourceUnit: caster }
            );
            projectiles.push(proj);
            if (audioManager) {
                audioManager.play('fire1', caster.wx, caster.wy);
            }
            return 'ranged';
        } else {
            // Melee smash
            if (typeof target.takeDamage === 'function') {
                target.takeDamage(caster.attack_power || 46, audioManager);
            }
            if (audioManager) {
                audioManager.play('cannon', caster.wx, caster.wy);
            }
            return 'melee';
        }
    }
}
