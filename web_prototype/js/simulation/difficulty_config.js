/**
 * Difficulty Configuration & Quantitative Parameter Calibration
 *
 * Imjinrok 2+: Dawn (임진록 2+: 여명) RTS Engine
 *
 * Defines strictly calibrated quantitative parameters across 4 difficulty tiers
 * (Easy, Normal, Hard, Brutal) as reverse-engineered from dawn.exe and specified
 * in 04_DIFFICULTY_CONTROL_AND_BINARY_HOOK_SPECIFICATION.md and
 * 05_AI_COMPREHENSIVE_OVERHAUL_MASTER_ARCHITECTURE.md.
 */

// Tactical Feature Bitmask Flags
export const TACTICAL_FLAGS = Object.freeze({
    NONE: 0,
    TACTICAL_KITING_BASIC: 0x001,          // Step back when enemy closes in
    TACTICAL_KITING_STUTTER_STEP: 0x002,   // Sync kiting with weapon cooldown timer
    TACTICAL_RETREAT_ENABLED: 0x004,       // Retreat when HP < threshold
    TACTICAL_HEALER_TRIAGE: 0x008,         // Route to healer / triage hub
    TACTICAL_AOE_REACTIVE: 0x010,          // Disperse after taking AoE splash
    TACTICAL_AOE_PREDICTIVE: 0x020,        // Evade projectile while in flight
    TACTICAL_PINCER_FLANKING: 0x040,       // Multi-directional Hammer & Anvil assault
    TACTICAL_FEINT_DIVERSION: 0x080,       // Dispatch feint squads
    TACTICAL_WORKER_HARASS: 0x100,         // Target enemy resource gatherers
    TACTICAL_OMNISCIENT_RADAR: 0x200,      // Global strategic vision (bypassing FoW)
    TACTICAL_FOCUS_FIRE_PRIORITY: 0x400,   // Focus low-HP, heroes, and siege targets
    TACTICAL_CONCAVE_FORMATION: 0x800      // Half-moon concave firing arcs
});

// Quantitative Difficulty Tiers
export const DIFFICULTY_TIERS = Object.freeze({
    EASY: Object.freeze({
        id: 'easy',
        name: 'Easy',
        apm: 45,
        reactionDelayMs: 850,
        reactionDelayTicks: 20,            // ~833-850ms at 24 Hz
        reactionJitterTicks: 4,            // ±167ms
        decisionCadenceTicks: 32,          // 32-tick decision cadence (~1333ms)
        tacticalScanTicks: 16,             // 16-tick micro cadence (~667ms)
        gatherMultiplier: 0.80,            // -20% handicap
        cheat5050Enabled: false,           // 0% cheats across all tiers
        kitingEnabled: false,
        kitingStutterStep: false,
        retreatEnabled: false,
        retreatHpThreshold: 0.0,
        aoeDodgingEnabled: false,
        aoePredictive: false,
        flankingEnabled: false,
        flankingRatio: 0.0,
        burstCapacity: 3,
        perUnitCooldownTicks: 36,          // 1500ms command cooldown per unit
        allowExpansion: false,
        scoutIntervalTicks: 1440,          // 60 seconds
        concurrentScouts: 1,
        flags: TACTICAL_FLAGS.NONE
    }),

    NORMAL: Object.freeze({
        id: 'normal',
        name: 'Normal',
        apm: 110,
        reactionDelayMs: 417,
        reactionDelayTicks: 10,            // ~417ms at 24 Hz (100% human parity)
        reactionJitterTicks: 2,            // ±83ms
        decisionCadenceTicks: 16,          // 16-tick decision cadence (~667ms)
        tacticalScanTicks: 8,              // 8-tick micro cadence (~333ms)
        gatherMultiplier: 1.00,            // 1.0x fair gather rate (100% fair parity, 0% cheats)
        cheat5050Enabled: false,
        kitingEnabled: true,               // Basic kiting enabled
        kitingStutterStep: false,
        retreatEnabled: true,              // Retreat enabled
        retreatHpThreshold: 0.25,          // Retreat when HP < 25%
        aoeDodgingEnabled: true,           // Reactive AoE dodging
        aoePredictive: false,
        flankingEnabled: false,
        flankingRatio: 0.0,
        burstCapacity: 8,
        perUnitCooldownTicks: 18,          // 750ms command cooldown per unit
        allowExpansion: true,
        scoutIntervalTicks: 720,           // 30 seconds
        concurrentScouts: 1,
        flags: TACTICAL_FLAGS.TACTICAL_KITING_BASIC |
               TACTICAL_FLAGS.TACTICAL_RETREAT_ENABLED |
               TACTICAL_FLAGS.TACTICAL_HEALER_TRIAGE |
               TACTICAL_FLAGS.TACTICAL_AOE_REACTIVE
    }),

    HARD: Object.freeze({
        id: 'hard',
        name: 'Hard',
        apm: 240,
        reactionDelayMs: 167,
        reactionDelayTicks: 4,             // ~167ms at 24 Hz (competitive esports)
        reactionJitterTicks: 1,            // ±42ms
        decisionCadenceTicks: 8,           // 8-tick decision cadence (~333ms)
        tacticalScanTicks: 4,              // 4-tick micro cadence (~167ms)
        gatherMultiplier: 1.15,            // +15% competitive multiplier
        cheat5050Enabled: false,
        kitingEnabled: true,
        kitingStutterStep: true,           // Advanced stutter-step kiting enabled
        retreatEnabled: true,              // Retreat enabled
        retreatHpThreshold: 0.35,          // Retreat to triage when HP < 35%
        aoeDodgingEnabled: true,           // Advanced AoE dodging enabled
        aoePredictive: true,               // In-flight predictive dodging
        flankingEnabled: true,
        flankingRatio: 0.30,               // 30% flank squad
        burstCapacity: 20,
        perUnitCooldownTicks: 6,           // 250ms command cooldown per unit
        allowExpansion: true,
        scoutIntervalTicks: 360,           // 15 seconds
        concurrentScouts: 2,
        flags: TACTICAL_FLAGS.TACTICAL_KITING_BASIC |
               TACTICAL_FLAGS.TACTICAL_KITING_STUTTER_STEP |
               TACTICAL_FLAGS.TACTICAL_RETREAT_ENABLED |
               TACTICAL_FLAGS.TACTICAL_HEALER_TRIAGE |
               TACTICAL_FLAGS.TACTICAL_AOE_PREDICTIVE |
               TACTICAL_FLAGS.TACTICAL_PINCER_FLANKING |
               TACTICAL_FLAGS.TACTICAL_WORKER_HARASS |
               TACTICAL_FLAGS.TACTICAL_FOCUS_FIRE_PRIORITY
    }),

    BRUTAL: Object.freeze({
        id: 'brutal',
        name: 'Brutal',
        apm: 420,
        reactionDelayMs: 42,
        reactionDelayTicks: 1,             // ~42ms at 24 Hz (superhuman/frame-perfect)
        reactionJitterTicks: 0,            // Deterministic, 0 jitter
        decisionCadenceTicks: 4,           // 4-tick decision cadence (~167ms)
        tacticalScanTicks: 2,              // 2-tick micro cadence (~83ms)
        gatherMultiplier: 1.30,            // +30% nightmare multiplier
        cheat5050Enabled: false,
        kitingEnabled: true,
        kitingStutterStep: true,
        eliteKiting: true,                 // Elite stutter-stepping & concave
        retreatEnabled: true,              // Elite retreat & rank rotation
        retreatHpThreshold: 0.40,          // Rank cycle when HP < 40%
        aoeDodgingEnabled: true,           // Elite AoE evasion enabled
        aoePredictive: true,
        flankingEnabled: true,             // Elite flanking & pincer enabled
        flankingRatio: 0.40,               // 40% flanking echelons
        burstCapacity: 40,
        perUnitCooldownTicks: 2,           // 83ms command cooldown per unit
        allowExpansion: true,
        scoutIntervalTicks: 120,           // 5 seconds
        concurrentScouts: 3,
        flags: TACTICAL_FLAGS.TACTICAL_KITING_BASIC |
               TACTICAL_FLAGS.TACTICAL_KITING_STUTTER_STEP |
               TACTICAL_FLAGS.TACTICAL_RETREAT_ENABLED |
               TACTICAL_FLAGS.TACTICAL_HEALER_TRIAGE |
               TACTICAL_FLAGS.TACTICAL_AOE_PREDICTIVE |
               TACTICAL_FLAGS.TACTICAL_PINCER_FLANKING |
               TACTICAL_FLAGS.TACTICAL_FEINT_DIVERSION |
               TACTICAL_FLAGS.TACTICAL_WORKER_HARASS |
               TACTICAL_FLAGS.TACTICAL_OMNISCIENT_RADAR |
               TACTICAL_FLAGS.TACTICAL_FOCUS_FIRE_PRIORITY |
               TACTICAL_FLAGS.TACTICAL_CONCAVE_FORMATION
    })
});

/**
 * Returns the difficulty tier configuration object.
 * @param {string|Object} tierInput - Tier key ('easy'|'normal'|'hard'|'brutal') or tier object
 * @returns {Object} Tier configuration
 */
export function getDifficultyConfig(tierInput) {
    if (!tierInput) return DIFFICULTY_TIERS.NORMAL;
    if (typeof tierInput === 'object' && tierInput.apm) return tierInput;
    const key = String(tierInput).toUpperCase();
    return DIFFICULTY_TIERS[key] || DIFFICULTY_TIERS.NORMAL;
}

/**
 * Samples a human-calibrated reaction delay in seconds.
 * @param {Object|string} tier - Difficulty tier
 * @param {Function} [randomFn=Math.random] - Optional PRNG
 * @returns {number} Delay in seconds
 */
export function sampleReactionDelaySec(tier, randomFn = Math.random) {
    const cfg = getDifficultyConfig(tier);
    let ticks = cfg.reactionDelayTicks;
    if (cfg.reactionJitterTicks > 0) {
        const jitter = Math.floor(randomFn() * (cfg.reactionJitterTicks * 2 + 1)) - cfg.reactionJitterTicks;
        ticks = Math.max(1, ticks + jitter);
    }
    // Simulation runs at 24 ticks/sec
    return ticks / 24.0;
}

/**
 * Leaky Token Bucket APM Limiter
 * Restricts AI actions per minute according to human physical capabilities.
 */
export class ApmLimiter {
    /**
     * @param {Object|string} tier - Difficulty configuration
     */
    constructor(tier = DIFFICULTY_TIERS.NORMAL) {
        this.config = getDifficultyConfig(tier);
        this.currentTokens = this.config.burstCapacity;
        this.capacity = this.config.burstCapacity;
        this.refillRatePerSec = this.config.apm / 60.0; // Tokens per second
        this.lastTimeSec = 0;
        this.unitCommandTimestamps = new Map(); // unitId -> lastCommandTimeSec
    }

    /**
     * Reconfigures for a different difficulty tier.
     * @param {Object|string} tier
     */
    setDifficulty(tier) {
        this.config = getDifficultyConfig(tier);
        this.capacity = this.config.burstCapacity;
        this.refillRatePerSec = this.config.apm / 60.0;
        this.currentTokens = Math.min(this.currentTokens, this.capacity);
    }

    /**
     * Updates token replenishment.
     * @param {number} currentTimeSec
     */
    update(currentTimeSec) {
        if (this.lastTimeSec <= 0) {
            this.lastTimeSec = currentTimeSec;
            return;
        }
        const delta = Math.max(0, currentTimeSec - this.lastTimeSec);
        this.lastTimeSec = currentTimeSec;
        this.currentTokens = Math.min(this.capacity, this.currentTokens + delta * this.refillRatePerSec);
    }

    /**
     * Attempts to consume APM tokens for issuing an action to a specific unit.
     * Checks both the global APM token pool and the per-unit command cooldown.
     * @param {number|string} [unitId=null] - Unit identifier
     * @param {number} [currentTimeSec=0] - Current simulation time
     * @param {number} [tokens=1.0] - Action cost in tokens
     * @returns {boolean} True if command is permitted, false if rate-limited
     */
    tryConsume(unitId = null, currentTimeSec = 0, tokens = 1.0) {
        this.update(currentTimeSec);

        // Check per-unit cooldown
        if (unitId !== null) {
            const cooldownSec = this.config.perUnitCooldownTicks / 24.0;
            const lastCmd = this.unitCommandTimestamps.get(unitId);
            if (lastCmd !== undefined && (currentTimeSec - lastCmd) < cooldownSec) {
                return false; // Suppress unnatural command-spam jitter
            }
        }

        // Check global APM token bucket
        if (this.currentTokens >= tokens) {
            this.currentTokens -= tokens;
            if (unitId !== null) {
                this.unitCommandTimestamps.set(unitId, currentTimeSec);
            }
            return true;
        }

        return false;
    }

    /**
     * Cleans up dead units from the cooldown cache.
     * @param {Set<number|string>} aliveUnitIds
     */
    pruneDeadUnits(aliveUnitIds) {
        for (const id of this.unitCommandTimestamps.keys()) {
            if (!aliveUnitIds.has(id)) {
                this.unitCommandTimestamps.delete(id);
            }
        }
    }

    reset() {
        this.currentTokens = this.capacity;
        this.lastTimeSec = 0;
        this.unitCommandTimestamps.clear();
    }
}
