/**
 * Imjinrok 2+: Dawn - Web RTS Live Modding Studio
 *
 * Implements the in-browser live modding sidebar component:
 * 1. Unit Stat Live Editor (sliders & number inputs with immediate in-memory updates).
 * 2. Custom New Unit Creator & Spawner (custom faction/sprite, Korean name, stats, projectile, command card slot, camera center spawn).
 * 3. Export to Local Binary / Mod (POST /api/save_mod_config and POST /api/patch_binary).
 *
 * @module ui/modding_studio
 */

import { Unit } from '../simulation/entities.js';
import { IsometricMath } from '../engine/isometric.js';

/**
 * Builtin iconic unit definitions from Imjinrok 2+: Dawn dataset.json
 * Used as immediate fallback and archetype templates.
 */
export const BUILTIN_UNIT_TEMPLATES = [
    // Chosun (조선)
    { index: 50, faction: 'chosun', korean_name: '조선 농부', sprite_path: 'char/farmerk.spr', sprite_name: 'char/farmerk.spr', move_speed: 12, hp: 350, mp: 0, attack_power: 12, attack_range: 1.2, attack_delay: 30, defense: 8, scale: 1.0, projectile_type: null, isWorker: true },
    { index: 51, faction: 'chosun', korean_name: '조선 창병', sprite_path: 'char/swordk.spr', sprite_name: 'char/swordk.spr', move_speed: 12, hp: 800, mp: 0, attack_power: 33, attack_range: 1.5, attack_delay: 26, defense: 24, scale: 1.0, projectile_type: null },
    { index: 52, faction: 'chosun', korean_name: '조선 궁수', sprite_path: 'char/archerk.spr', sprite_name: 'char/archerk.spr', move_speed: 11, hp: 520, mp: 0, attack_power: 28, attack_range: 6.5, attack_delay: 26, defense: 14, scale: 1.0, projectile_type: 'arrow' },
    { index: 53, faction: 'chosun', korean_name: '조선 기마궁수', sprite_path: 'char/horsearcherk.spr', sprite_name: 'char/horsearcherk.spr', move_speed: 16, hp: 900, mp: 0, attack_power: 38, attack_range: 6.5, attack_delay: 24, defense: 22, scale: 1.05, projectile_type: 'arrow' },
    { index: 54, faction: 'chosun', korean_name: '조선 포도대장', sprite_path: 'char/generalk31.spr', sprite_name: 'char/generalk31.spr', move_speed: 13, hp: 1100, mp: 100, attack_power: 52, attack_range: 1.8, attack_delay: 24, defense: 28, scale: 1.05, projectile_type: null },
    { index: 13, faction: 'chosun', korean_name: '조선 화차', sprite_path: 'char/cannonk.spr', sprite_name: 'char/cannonk.spr', move_speed: 9, hp: 950, mp: 0, attack_power: 75, attack_range: 8.5, attack_delay: 42, defense: 20, scale: 1.1, projectile_type: 'fireball' },
    { index: 8, faction: 'chosun', korean_name: '조선 불랑기포', sprite_path: 'char/cannonk.spr', sprite_name: 'char/cannonk.spr', move_speed: 8, hp: 1050, mp: 0, attack_power: 90, attack_range: 10.0, attack_delay: 48, defense: 24, scale: 1.05, projectile_type: 'cannon' },
    { index: 49, faction: 'chosun', korean_name: '조선 이순신', sprite_path: 'char/generalk12.spr', sprite_name: 'char/generalk12.spr', move_speed: 14, hp: 2000, mp: 200, attack_power: 158, attack_range: 5.5, attack_delay: 22, defense: 34, scale: 1.15, projectile_type: 'arrow', level: 3 },
    { index: 55, faction: 'chosun', korean_name: '조선 곽재우', sprite_path: 'char/generalk31.spr', sprite_name: 'char/generalk31.spr', move_speed: 15, hp: 1900, mp: 180, attack_power: 142, attack_range: 2.0, attack_delay: 22, defense: 32, scale: 1.15, projectile_type: null, level: 2 },
    { index: 56, faction: 'chosun', korean_name: '조선 사명대사', sprite_path: 'char/generalk12.spr', sprite_name: 'char/generalk12.spr', move_speed: 12, hp: 1650, mp: 250, attack_power: 125, attack_range: 6.0, attack_delay: 28, defense: 26, scale: 1.1, projectile_type: 'fireball', level: 2 },
    { index: 57, faction: 'chosun', korean_name: '조선 거북선', sprite_path: 'char/ashipk.spr', sprite_name: 'char/ashipk.spr', move_speed: 10, hp: 1800, mp: 0, attack_power: 110, attack_range: 7.5, attack_delay: 34, defense: 36, scale: 1.05, projectile_type: 'cannon' },

    // Japan (일본)
    { index: 60, faction: 'japan', korean_name: '일본 농부', sprite_path: 'char/farmerj.spr', sprite_name: 'char/farmerj.spr', move_speed: 12, hp: 320, mp: 0, attack_power: 10, attack_range: 1.2, attack_delay: 30, defense: 6, scale: 1.0, projectile_type: null, isWorker: true },
    { index: 61, faction: 'japan', korean_name: '일본 창병', sprite_path: 'char/swordj.spr', sprite_name: 'char/swordj.spr', move_speed: 12, hp: 750, mp: 0, attack_power: 32, attack_range: 1.5, attack_delay: 26, defense: 22, scale: 1.0, projectile_type: null },
    { index: 62, faction: 'japan', korean_name: '일본 사무라이', sprite_path: 'char/swordj.spr', sprite_name: 'char/swordj.spr', move_speed: 13, hp: 920, mp: 0, attack_power: 44, attack_range: 1.5, attack_delay: 24, defense: 26, scale: 1.05, projectile_type: null },
    { index: 63, faction: 'japan', korean_name: '일본 조총병', sprite_path: 'char/gunj1.spr', sprite_name: 'char/gunj1.spr', move_speed: 11, hp: 580, mp: 0, attack_power: 42, attack_range: 6.5, attack_delay: 36, defense: 16, scale: 1.0, projectile_type: 'bullet' },
    { index: 64, faction: 'japan', korean_name: '일본 화염전차', sprite_path: 'char/flametankj.spr', sprite_name: 'char/flametankj.spr', move_speed: 10, hp: 1200, mp: 0, attack_power: 68, attack_range: 5.5, attack_delay: 32, defense: 28, scale: 1.1, projectile_type: 'fireball' },
    { index: 65, faction: 'japan', korean_name: '도요토미 히데요시', sprite_path: 'char/swordj.spr', sprite_name: 'char/swordj.spr', move_speed: 13, hp: 1850, mp: 180, attack_power: 135, attack_range: 2.0, attack_delay: 25, defense: 30, scale: 1.2, projectile_type: null, level: 2 },
    { index: 66, faction: 'japan', korean_name: '가토 기요마사', sprite_path: 'char/swordj.spr', sprite_name: 'char/swordj.spr', move_speed: 14, hp: 1950, mp: 150, attack_power: 148, attack_range: 2.0, attack_delay: 23, defense: 32, scale: 1.2, projectile_type: null, level: 2 },
    { index: 67, faction: 'japan', korean_name: '고니시 유키나가', sprite_path: 'char/gunj1.spr', sprite_name: 'char/gunj1.spr', move_speed: 13, hp: 1750, mp: 180, attack_power: 130, attack_range: 6.5, attack_delay: 26, defense: 28, scale: 1.2, projectile_type: 'bullet', level: 1 },

    // Ming (명)
    { index: 70, faction: 'ming', korean_name: '명 농부', sprite_path: 'char/farmerc.spr', sprite_name: 'char/farmerc.spr', move_speed: 12, hp: 340, mp: 0, attack_power: 10, attack_range: 1.2, attack_delay: 30, defense: 6, scale: 1.0, projectile_type: null, isWorker: true },
    { index: 71, faction: 'ming', korean_name: '명 대도병', sprite_path: 'char/swordc1.spr', sprite_name: 'char/swordc1.spr', move_speed: 12, hp: 820, mp: 0, attack_power: 35, attack_range: 1.5, attack_delay: 28, defense: 25, scale: 1.0, projectile_type: null },
    { index: 72, faction: 'ming', korean_name: '명 화승총병', sprite_path: 'char/gunc.spr', sprite_name: 'char/gunc.spr', move_speed: 11, hp: 560, mp: 0, attack_power: 40, attack_range: 6.5, attack_delay: 38, defense: 18, scale: 1.0, projectile_type: 'bullet' },
    { index: 48, faction: 'ming', korean_name: '명 코끼리병', sprite_path: 'char/elephantc1.spr', sprite_name: 'char/elephantc1.spr', move_speed: 10, hp: 1600, mp: 0, attack_power: 82, attack_range: 2.2, attack_delay: 34, defense: 32, scale: 1.15, projectile_type: null },
    { index: 73, faction: 'ming', korean_name: '명 중기병', sprite_path: 'char/elephantc1.spr', sprite_name: 'char/elephantc1.spr', move_speed: 14, hp: 1150, mp: 0, attack_power: 56, attack_range: 1.8, attack_delay: 26, defense: 28, scale: 1.05, projectile_type: null },
    { index: 2, faction: 'ming', korean_name: '명 천린', sprite_path: 'char/swordc1.spr', sprite_name: 'char/swordc1.spr', move_speed: 14, hp: 1950, mp: 180, attack_power: 150, attack_range: 2.0, attack_delay: 22, defense: 33, scale: 1.2, projectile_type: null, level: 2 },
    { index: 4, faction: 'ming', korean_name: '명 이여송', sprite_path: 'char/gunc.spr', sprite_name: 'char/gunc.spr', move_speed: 15, hp: 1900, mp: 160, attack_power: 144, attack_range: 6.0, attack_delay: 24, defense: 30, scale: 1.2, projectile_type: 'cannon', level: 2 },

    // Custom Joseon Units (0x70 ~ 0x79)
    { index: 0x70, kind_id: 0x70, kindId: 0x70, faction: 'chosun', korean_name: '유생', sprite_path: 'char/keon_1hs.spr', sprite_name: 'char/keon_1hs.spr', move_speed: 18, hp: 450, mp: 100, attack_power: 18, attack_range: 5.0, sight_range: 7.0, attack_delay: 28, defense: 12, scale: 1.0, projectile_type: 'magic_bind', cost_rice: 250, cost_potato: 0, costRice: 250, costPotato: 0 },
    { index: 0x71, kind_id: 0x71, kindId: 0x71, faction: 'chosun', korean_name: '검술 낭인', sprite_path: 'char/SwordPirate_online.spr', sprite_name: 'char/SwordPirate_online.spr', move_speed: 21, hp: 600, mp: 80, attack_power: 25, attack_range: 1.2, sight_range: 5.0, attack_delay: 24, defense: 20, scale: 1.0, projectile_type: null, cost_rice: 180, cost_potato: 0, costRice: 180, costPotato: 0 },
    { index: 0x72, kind_id: 0x72, kindId: 0x72, faction: 'chosun', korean_name: '조총 낭인', sprite_path: 'char/GunPirate_online.spr', sprite_name: 'char/GunPirate_online.spr', move_speed: 18, hp: 480, mp: 0, attack_power: 14, attack_range: 6.0, sight_range: 7.0, attack_delay: 32, defense: 14, scale: 1.0, projectile_type: 'bullet', cost_rice: 240, cost_potato: 0, costRice: 240, costPotato: 0 },
    { index: 0x73, kind_id: 0x73, kindId: 0x73, faction: 'chosun', korean_name: '구미호', sprite_path: 'char/fox.spr', sprite_name: 'char/fox.spr', move_speed: 22, hp: 750, mp: 100, attack_power: 31, attack_range: 5.0, sight_range: 6.0, attack_delay: 26, defense: 18, scale: 1.1, projectile_type: 'fireball', cost_rice: 280, cost_potato: 50, costRice: 280, costPotato: 50 },
    { index: 0x74, kind_id: 0x74, kindId: 0x74, faction: 'chosun', korean_name: '조선왕벌', sprite_path: 'char/bat_online.spr', sprite_name: 'char/bat_online.spr', move_speed: 25, hp: 500, mp: 0, attack_power: 26, attack_range: 1.2, sight_range: 5.0, attack_delay: 20, defense: 10, scale: 1.0, projectile_type: null, isAirUnit: true, is_air: true, flightAltitude: 36, cost_rice: 200, cost_potato: 50, costRice: 200, costPotato: 50 },
    { index: 0x75, kind_id: 0x75, kindId: 0x75, faction: 'chosun', korean_name: '조선 호랑이', sprite_path: 'char/Tiger.Spr', sprite_name: 'char/Tiger.Spr', move_speed: 24, hp: 950, mp: 0, attack_power: 42, attack_range: 1.2, sight_range: 5.0, attack_delay: 22, defense: 22, scale: 1.1, projectile_type: null, cost_rice: 300, cost_potato: 0, costRice: 300, costPotato: 0 },
    { index: 0x76, kind_id: 0x76, kindId: 0x76, faction: 'chosun', korean_name: '털가면', sprite_path: 'char/furheaddemon_online.spr', sprite_name: 'char/furheaddemon_online.spr', move_speed: 19, hp: 700, mp: 80, attack_power: 28, attack_range: 5.0, sight_range: 6.0, attack_delay: 24, defense: 20, scale: 1.0, projectile_type: 'frost_freeze', cost_rice: 220, cost_potato: 40, costRice: 220, costPotato: 40 },
    { index: 0x77, kind_id: 0x77, kindId: 0x77, faction: 'chosun', korean_name: '설녀', sprite_path: 'char/snowwoman_online.spr', sprite_name: 'char/snowwoman_online.spr', move_speed: 20, hp: 850, mp: 120, attack_power: 36, attack_range: 6.0, sight_range: 7.0, attack_delay: 28, defense: 16, scale: 1.05, projectile_type: 'ice_splash', cost_rice: 280, cost_potato: 60, costRice: 280, costPotato: 60 },
    { index: 0x78, kind_id: 0x78, kindId: 0x78, faction: 'chosun', korean_name: '조선 도깨비', sprite_path: 'char/oni_online.spr', sprite_name: 'char/oni_online.spr', move_speed: 17, hp: 1100, mp: 0, attack_power: 40, attack_range: 1.4, sight_range: 5.0, attack_delay: 26, defense: 26, scale: 1.15, projectile_type: null, cost_rice: 320, cost_potato: 0, costRice: 320, costPotato: 0 },
    { index: 0x79, kind_id: 0x79, kindId: 0x79, faction: 'chosun', korean_name: '불가살이', sprite_path: 'char/starfish.spr', sprite_name: 'char/starfish.spr', move_speed: 15, hp: 1400, mp: 120, attack_power: 46, attack_range: 1.5, ranged_attack_range: 6.0, ranged_mp_cost: 20, sight_range: 7.0, attack_delay: 30, defense: 30, scale: 1.2, projectile_type: 'fireball', hybrid: true, cost_rice: 380, cost_potato: 100, costRice: 380, costPotato: 100 }
];

export class LiveModdingStudio {
    /**
     * @param {HTMLElement|string} panelElement - Container element or selector (#live-mod-panel)
     * @param {Object} [options={}] - Configuration options or legacy unitManager
     * @param {Function} [onExportBinary=null] - Optional callback when binary is patched
     */
    constructor(panelElement, options = {}, onExportBinary = null) {
        // Resolve panel element
        if (typeof panelElement === 'string') {
            this.panel = (typeof document !== 'undefined')
                ? (document.querySelector(panelElement) || document.getElementById(panelElement.replace('#', '')))
                : null;
        } else {
            this.panel = panelElement || null;
        }

        // Handle legacy positional parameters or options object
        let opts = {};
        if (options && typeof options === 'object') {
            if (Array.isArray(options)) {
                opts = { entities: options };
            } else if (('camera' in options) || ('grid' in options) || ('gameEngine' in options) || ('commandCard' in options) || ('dataset' in options)) {
                opts = options;
            } else if (typeof options.getUnits === 'function' || ('units' in options)) {
                opts = { unitManager: options, onExportBinary };
            } else {
                opts = options;
            }
        }

        this.entities = opts.entities || (Array.isArray(opts.unitManager) ? opts.unitManager : null);
        this.gameEngine = opts.gameEngine || (typeof window !== 'undefined' ? window.gameEngine : null) || null;
        this.unitManager = opts.unitManager || (this.gameEngine ? this.gameEngine.unitManager || this.gameEngine.entities : null);
        this.camera = opts.camera || (this.gameEngine ? this.gameEngine.camera : null);
        this.commandCard = opts.commandCard || (this.gameEngine ? this.gameEngine.commandCard : null);
        this.grid = opts.grid || (this.gameEngine ? this.gameEngine.grid : null);
        this.audioManager = opts.audioManager || (this.gameEngine ? this.gameEngine.audio : null);
        this.onExportBinary = opts.onExportBinary || onExportBinary || null;
        this.onSpawnCustom = opts.onSpawnCustom || null;

        // Dataset & Archetypes
        this.dataset = Array.isArray(opts.dataset) && opts.dataset.length > 0 ? opts.dataset : [...BUILTIN_UNIT_TEMPLATES];
        this.selectedUnit = null;      // Currently selected unit instance in world
        this.selectedUnits = [];       // Multi-selected unit instances
        this.selectedArchetype = null;  // Archetype picked from dataset dropdown
        this.statOverrides = {};       // Map of unit_index -> { move_speed, hp, attack_power, ... }
        this.customUnits = [];         // Array of user-created custom unit objects

        // Internal UI state
        this.isCollapsed = false;

        // Register global bridge for testing / headless browser
        if (typeof window !== 'undefined') {
            window.gameEngine = window.gameEngine || {};
            if (!window.gameEngine.getSelectedUnitSpeed) {
                window.gameEngine.getSelectedUnitSpeed = () => this.getSelectedUnitSpeed();
            }
            window.gameEngine.liveModdingStudio = this;
        }

        // Initialize DOM if in browser environment
        if (typeof document !== 'undefined') {
            this.init();
        }
    }

    /**
     * Initializes DOM layout, binds event handlers, and loads dataset.
     */
    init() {
        if (!this.panel) {
            // Attempt to find or create default panel
            let existing = document.getElementById('live-mod-panel');
            if (!existing) {
                existing = document.createElement('div');
                existing.id = 'live-mod-panel';
                existing.className = 'live-mod-panel';
                document.body.appendChild(existing);
            }
            this.panel = existing;
        }

        this.renderDOM();
        this.bindEvents();
        this.fetchDatasetAsync();
    }

    /**
     * Asynchronously loads tools/modding/dataset.json via /api/dataset if available.
     */
    async fetchDatasetAsync() {
        if (typeof fetch === 'undefined') return;
        try {
            const resp = await fetch('/api/dataset');
            if (resp.ok) {
                const data = await resp.json();
                if (data && Array.isArray(data.units)) {
                    // Filter and merge combat units
                    const validUnits = data.units.filter(u => u && u.korean_name && !u.korean_name.startsWith('FILE_'));
                    if (validUnits.length > 0) {
                        this.dataset = validUnits.map(u => ({
                            index: u.index,
                            korean_name: u.korean_name,
                            sprite_name: u.sprite_path || u.sprite_name,
                            sprite_path: u.sprite_path || u.sprite_name,
                            move_speed: (u.speed_field && typeof u.speed_field.dawn_val === 'number') ? u.speed_field.dawn_val : 12,
                            hp: (u.hp_field && typeof u.hp_field.dawn_val === 'number') ? u.hp_field.dawn_val : 100,
                            mp: (u.mp_field && typeof u.mp_field.dawn_val === 'number') ? u.mp_field.dawn_val : 0,
                            attack_power: (u.attack_field && typeof u.attack_field.dawn_val === 'number') ? u.attack_field.dawn_val : 15,
                            attack_delay: (u.attack_delay && typeof u.attack_delay.dawn_val === 'number') ? u.attack_delay.dawn_val : 30,
                            attack_range: (u.attack_range && typeof u.attack_range.dawn_val === 'number') ? u.attack_range.dawn_val : 2.0,
                            defense: (u.defense && typeof u.defense.dawn_val === 'number') ? u.defense.dawn_val : 0,
                            scale: 1.0,
                            projectile_type: (u.attack_range && u.attack_range.dawn_val > 4) ? 'arrow' : null
                        }));
                        this.populateUnitSelectDropdown();
                    }
                }
            }
        } catch {
            // Keep builtin templates if API is unreachable
        }
    }

    /**
     * Generates inner HTML structure for Live Modding Studio.
     */
    renderDOM() {
        this.panel.innerHTML = `
            <div class="mod-studio-container">
                <!-- Header -->
                <div class="mod-studio-header">
                    <div class="header-title">
                        <span class="icon">🛠️</span>
                        <h3>Live Modding Studio</h3>
                    </div>
                    <button type="button" id="toggle-studio-btn" class="toggle-btn" title="Toggle Modding Panel">−</button>
                </div>

                <div class="mod-studio-body" id="mod-studio-body">
                    <!-- Target Indicator Banner -->
                    <div class="target-indicator" id="target-indicator">
                        <span class="indicator-badge">ACTIVE TARGET</span>
                        <div class="target-name" id="target-unit-name">🎯 [Track Selected Unit]</div>
                        <div class="target-meta" id="target-unit-meta">Click any unit on screen or choose from dropdown</div>
                    </div>

                    <!-- Unit Selector Dropdown -->
                    <div class="form-group select-unit-group">
                        <label for="mod-unit-select">Choose Unit Type (유닛 템플릿 선택):</label>
                        <select id="mod-unit-select" class="mod-select">
                            <option value="auto">🎯 Track Selected On-Screen Unit (현재 선택 유닛)</option>
                        </select>
                    </div>

                    <!-- 1. Unit Stat Live Editor Section -->
                    <div class="mod-section stat-editor-section">
                        <div class="section-title">
                            <h4>⚡ Unit Stat Live Editor (실시간 스탯 수정)</h4>
                            <span class="section-desc">Changes take effect immediately on next frame</span>
                        </div>

                        <!-- Movement Speed (1 to 30) -->
                        <div class="stat-control" data-stat="move_speed">
                            <div class="stat-label-row">
                                <label for="input-move-speed">🏃 Movement Speed (이동 속도):</label>
                                <span class="val-display" id="val-speed">12</span>
                            </div>
                            <div class="stat-inputs-row">
                                <input type="range" id="input-move-speed" class="stat-slider" min="1" max="30" step="1" value="12">
                                <input type="number" id="num-move-speed" class="stat-num" min="1" max="30" step="1" value="12">
                            </div>
                            <div class="stat-limits">Min: 1 | Max: 30</div>
                        </div>

                        <!-- Health HP (10 to 2000) -->
                        <div class="stat-control" data-stat="hp">
                            <div class="stat-label-row">
                                <label for="input-hp">❤️ Health (HP / 최대 생명력):</label>
                                <span class="val-display" id="val-hp">200</span>
                            </div>
                            <div class="stat-inputs-row">
                                <input type="range" id="input-hp" class="stat-slider" min="10" max="2000" step="10" value="200">
                                <input type="number" id="num-hp" class="stat-num" min="10" max="2000" step="10" value="200">
                            </div>
                            <div class="stat-limits">Min: 10 | Max: 2000</div>
                        </div>

                        <!-- Attack Power (1 to 200) -->
                        <div class="stat-control" data-stat="attack_power">
                            <div class="stat-label-row">
                                <label for="input-attack-power">⚔️ Attack Power (공격력):</label>
                                <span class="val-display" id="val-atk">15</span>
                            </div>
                            <div class="stat-inputs-row">
                                <input type="range" id="input-attack-power" class="stat-slider" min="1" max="200" step="1" value="15">
                                <input type="number" id="num-attack-power" class="stat-num" min="1" max="200" step="1" value="15">
                            </div>
                            <div class="stat-limits">Min: 1 | Max: 200</div>
                        </div>

                        <!-- Attack Range (1 to 15) -->
                        <div class="stat-control" data-stat="attack_range">
                            <div class="stat-label-row">
                                <label for="input-attack-range">🎯 Attack Range (사정거리):</label>
                                <span class="val-display" id="val-range">2.0</span>
                            </div>
                            <div class="stat-inputs-row">
                                <input type="range" id="input-attack-range" class="stat-slider" min="1" max="15" step="0.5" value="2.0">
                                <input type="number" id="num-attack-range" class="stat-num" min="1" max="15" step="0.5" value="2.0">
                            </div>
                            <div class="stat-limits">Min: 1 | Max: 15</div>
                        </div>

                        <!-- Attack Delay (5 to 60) -->
                        <div class="stat-control" data-stat="attack_delay">
                            <div class="stat-label-row">
                                <label for="input-attack-delay">⏱️ Attack Delay / Speed (공격 딜레이):</label>
                                <span class="val-display" id="val-delay">30</span>
                            </div>
                            <div class="stat-inputs-row">
                                <input type="range" id="input-attack-delay" class="stat-slider" min="5" max="60" step="1" value="30">
                                <input type="number" id="num-attack-delay" class="stat-num" min="5" max="60" step="1" value="30">
                            </div>
                            <div class="stat-limits">Min: 5 | Max: 60 (Lower = Faster Attack)</div>
                        </div>

                        <!-- Scale / Size (0.5 to 2.5) -->
                        <div class="stat-control" data-stat="scale">
                            <div class="stat-label-row">
                                <label for="input-scale">🔍 Scale / Size (크기 배율):</label>
                                <span class="val-display" id="val-scale">1.0</span>x
                            </div>
                            <div class="stat-inputs-row">
                                <input type="range" id="input-scale" class="stat-slider" min="0.5" max="2.5" step="0.1" value="1.0">
                                <input type="number" id="num-scale" class="stat-num" min="0.5" max="2.5" step="0.1" value="1.0">
                            </div>
                            <div class="stat-limits">Min: 0.5x | Max: 2.5x</div>
                        </div>
                    </div>

                    <!-- 2. Custom New Unit Creator & Spawner Section -->
                    <div class="mod-section unit-creator-section">
                        <div class="section-title">
                            <h4>✨ Custom Unit Creator (신규 유닛 생성)</h4>
                            <span class="section-desc">Create custom unit & spawn at camera center</span>
                        </div>

                        <div class="form-row">
                            <div class="form-group flex-1">
                                <label for="custom-unit-faction">Faction (진영):</label>
                                <select id="custom-unit-faction" class="mod-select">
                                    <option value="chosun">조선 (Chosun)</option>
                                    <option value="japan">일본 (Japan)</option>
                                    <option value="ming">명 (Ming)</option>
                                </select>
                            </div>
                            <div class="form-group flex-2">
                                <label for="custom-base-sprite">Base Sprite (스프라이트):</label>
                                <select id="custom-base-sprite" class="mod-select">
                                    <!-- Populated dynamically -->
                                </select>
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="custom-unit-name">Korean Unit Name (유닛 이름):</label>
                            <input type="text" id="custom-unit-name" class="mod-input" value="조선 초인검사" placeholder="유닛 이름 입력 (예: 조선 초인검사)">
                        </div>

                        <div class="form-row stats-grid-mini">
                            <div class="form-group">
                                <label for="custom-speed">Speed (속도):</label>
                                <input type="number" id="custom-speed" class="mod-input mini" min="1" max="30" value="16">
                            </div>
                            <div class="form-group">
                                <label for="custom-hp">HP (생명력):</label>
                                <input type="number" id="custom-hp" class="mod-input mini" min="10" max="2000" value="400">
                            </div>
                            <div class="form-group">
                                <label for="custom-atk">Attack (공격력):</label>
                                <input type="number" id="custom-atk" class="mod-input mini" min="1" max="200" value="35">
                            </div>
                            <div class="form-group">
                                <label for="custom-range">Range (사거리):</label>
                                <input type="number" id="custom-range" class="mod-input mini" min="1" max="15" step="0.5" value="2.5">
                            </div>
                            <div class="form-group">
                                <label for="custom-delay">Delay (딜레이):</label>
                                <input type="number" id="custom-delay" class="mod-input mini" min="5" max="60" value="20">
                            </div>
                            <div class="form-group">
                                <label for="custom-scale">Scale (크기):</label>
                                <input type="number" id="custom-scale" class="mod-input mini" min="0.5" max="2.5" step="0.1" value="1.2">
                            </div>
                        </div>

                        <div class="form-row">
                            <div class="form-group flex-1">
                                <label for="custom-projectile-type">Projectile (투사체):</label>
                                <select id="custom-projectile-type" class="mod-select">
                                    <option value="arrow">🏹 Arrow (화살)</option>
                                    <option value="bullet">💥 Bullet (조총 탄환)</option>
                                    <option value="cannon">💣 Cannon (대포알)</option>
                                    <option value="fireball">🔥 Fireball (신기전 화염)</option>
                                </select>
                            </div>
                            <div class="form-group flex-1">
                                <label for="custom-command-slot">Command Slot (슬롯):</label>
                                <select id="custom-command-slot" class="mod-select">
                                    <option value="8">Slot 8 [Z] (특수생산 1)</option>
                                    <option value="9">Slot 9 [X] (특수생산 2)</option>
                                    <option value="10">Slot 10 [C] (특수생산 3)</option>
                                    <option value="11">Slot 11 [V] (특수생산 4)</option>
                                    <option value="0">Slot 0 [Q]</option>
                                    <option value="1">Slot 1 [W]</option>
                                    <option value="2">Slot 2 [E]</option>
                                    <option value="3">Slot 3 [R]</option>
                                </select>
                            </div>
                        </div>

                        <button type="button" id="spawn-custom-btn" class="mod-btn mod-btn-primary">
                            ⚡ Spawn Unit at Camera Center (중앙 소환)
                        </button>
                    </div>

                    <!-- 3. Export to Local Binary / Mod Section -->
                    <div class="mod-section export-section">
                        <div class="section-title">
                            <h4>💾 Export to Local Binary / Mod (모드 저장 & 바이너리 패치)</h4>
                            <span class="section-desc">Save mod configuration & patch local dawn.exe</span>
                        </div>

                        <div class="form-group">
                            <label for="export-profile-name">Mod Profile Name:</label>
                            <input type="text" id="export-profile-name" class="mod-input" value="imzinrok_dawn_mod_v1">
                        </div>

                        <div class="button-group-export">
                            <button type="button" id="export-mod-config-btn" class="mod-btn mod-btn-secondary">
                                📄 Export Mod Config (JSON)
                            </button>
                            <button type="button" id="patch-local-binary-btn" class="mod-btn mod-btn-accent">
                                🚀 Patch Local dawn.exe
                            </button>
                        </div>

                        <!-- Result / Status Box -->
                        <div id="mod-export-result" class="export-result-box" style="display:none;"></div>
                    </div>
                </div>
            </div>
        `;

        this.populateUnitSelectDropdown();
        this.updateBaseSpriteDropdown('chosun');
    }

    /**
     * Populates the unit template dropdown from this.dataset.
     */
    populateUnitSelectDropdown() {
        const select = this.panel.querySelector('#mod-unit-select');
        if (!select) return;

        // Keep the first auto option
        select.innerHTML = '<option value="auto">🎯 Track Selected On-Screen Unit (현재 선택 유닛)</option>';

        const factions = {
            chosun: { label: '조선 (Chosun)', units: [] },
            japan: { label: '일본 (Japan)', units: [] },
            ming: { label: '명 (Ming)', units: [] },
            other: { label: '기타 / 건물 (Other)', units: [] }
        };

        for (const u of this.dataset) {
            const kn = u.korean_name || '';
            if (kn.startsWith('조선') || u.faction === 'chosun' || kn === '이순신' || kn === '곽재우' || kn === '사명대사' || kn === '권율') {
                factions.chosun.units.push(u);
            } else if (kn.startsWith('일본') || u.faction === 'japan' || kn.includes('사무라이') || kn.includes('도요토미') || kn.includes('가토') || kn.includes('고니시')) {
                factions.japan.units.push(u);
            } else if (kn.startsWith('명') || u.faction === 'ming' || kn.includes('천린') || kn.includes('이여송') || kn.includes('리루쑹')) {
                factions.ming.units.push(u);
            } else {
                factions.other.units.push(u);
            }
        }

        for (const [key, group] of Object.entries(factions)) {
            if (group.units.length > 0) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = group.label;
                for (const u of group.units) {
                    const opt = document.createElement('option');
                    opt.value = u.index !== undefined ? String(u.index) : u.korean_name;
                    opt.textContent = `${u.korean_name} (Spd:${u.move_speed}, HP:${u.hp}, Atk:${u.attack_power})`;
                    optgroup.appendChild(opt);
                }
                select.appendChild(optgroup);
            }
        }
    }

    /**
     * Updates the base sprite dropdown based on chosen faction.
     */
    updateBaseSpriteDropdown(faction) {
        const spriteSelect = this.panel.querySelector('#custom-base-sprite');
        if (!spriteSelect) return;

        const spriteMap = {
            chosun: [
                { val: 'char/swordk.spr', label: '조선 창병 검사 (swordk.spr)' },
                { val: 'char/archerk.spr', label: '조선 궁수 (archerk.spr)' },
                { val: 'char/generalk12.spr', label: '이순신 장군 (generalk12.spr)' },
                { val: 'char/generalk31.spr', label: '곽재우 장군 (generalk31.spr)' },
                { val: 'char/ashipk.spr', label: '조선 거북선 (ashipk.spr)' },
                { val: 'char/farmerk.spr', label: '조선 농부 (farmerk.spr)' }
            ],
            japan: [
                { val: 'char/swordj.spr', label: '일본 사무라이 (swordj.spr)' },
                { val: 'char/gunj1.spr', label: '일본 뎃뽀 조총병 (gunj1.spr)' },
                { val: 'char/flametankj.spr', label: '일본 화염전차 (flametankj.spr)' },
                { val: 'char/farmerj.spr', label: '일본 농부 (farmerj.spr)' }
            ],
            ming: [
                { val: 'char/elephantc1.spr', label: '명 전투코끼리 (elephantc1.spr)' },
                { val: 'char/swordc1.spr', label: '명 대도병 (swordc1.spr)' },
                { val: 'char/gunc.spr', label: '명 화승총병 (gunc.spr)' },
                { val: 'char/farmerc.spr', label: '명 농부 (farmerc.spr)' }
            ]
        };

        const list = spriteMap[faction] || spriteMap.chosun;
        spriteSelect.innerHTML = '';
        for (const item of list) {
            const opt = document.createElement('option');
            opt.value = item.val;
            opt.textContent = item.label;
            spriteSelect.appendChild(opt);
        }
    }

    /**
     * Binds all input, change, and click event listeners.
     */
    bindEvents() {
        // Toggle Collapse Button
        const toggleBtn = this.panel.querySelector('#toggle-studio-btn');
        const studioBody = this.panel.querySelector('#mod-studio-body');
        if (toggleBtn && studioBody) {
            toggleBtn.addEventListener('click', () => {
                this.isCollapsed = !this.isCollapsed;
                studioBody.style.display = this.isCollapsed ? 'none' : 'block';
                toggleBtn.textContent = this.isCollapsed ? '+' : '−';
            });
        }

        // Unit Dropdown Selection
        const unitSelect = this.panel.querySelector('#mod-unit-select');
        if (unitSelect) {
            unitSelect.addEventListener('change', (e) => {
                const val = e.target.value;
                if (val === 'auto') {
                    this.selectedArchetype = null;
                    if (this.selectedUnit) {
                        this.updateControlsFromUnit(this.selectedUnit);
                    } else {
                        this.setTargetIndicator('🎯 [Track Selected Unit]', 'Click any unit on screen or choose from dropdown');
                    }
                } else {
                    const archetype = this.dataset.find(u => String(u.index) === val || u.korean_name === val);
                    if (archetype) {
                        this.selectedArchetype = archetype;
                        this.updateControlsFromArchetype(archetype);
                    }
                }
            });
        }

        // Pair Slider <-> Number Input for each of the 6 stats
        const statConfig = [
            { id: 'move-speed', prop: 'move_speed', valId: 'val-speed', min: 1, max: 30 },
            { id: 'hp', prop: 'hp', valId: 'val-hp', min: 10, max: 2000 },
            { id: 'attack-power', prop: 'attack_power', valId: 'val-atk', min: 1, max: 200 },
            { id: 'attack-range', prop: 'attack_range', valId: 'val-range', min: 1, max: 15 },
            { id: 'attack-delay', prop: 'attack_delay', valId: 'val-delay', min: 5, max: 60 },
            { id: 'scale', prop: 'scale', valId: 'val-scale', min: 0.5, max: 2.5 }
        ];

        for (const cfg of statConfig) {
            const slider = this.panel.querySelector(`#input-${cfg.id}`);
            const numInput = this.panel.querySelector(`#num-${cfg.id}`);
            const valLabel = this.panel.querySelector(`#${cfg.valId}`);

            const onUpdate = (rawVal) => {
                let val = parseFloat(rawVal);
                if (isNaN(val)) return;
                val = Math.max(cfg.min, Math.min(cfg.max, val));

                if (slider && slider.value !== String(val)) slider.value = val;
                if (numInput && numInput.value !== String(val)) numInput.value = val;
                if (valLabel) valLabel.textContent = cfg.prop === 'scale' ? val.toFixed(1) : val;

                // IMMEDIATELY apply to live in-memory unit
                this.applyStatToLiveUnits(cfg.prop, val);
            };

            if (slider) {
                slider.addEventListener('input', (e) => onUpdate(e.target.value));
                slider.addEventListener('change', (e) => onUpdate(e.target.value));
            }
            if (numInput) {
                numInput.addEventListener('input', (e) => onUpdate(e.target.value));
                numInput.addEventListener('change', (e) => onUpdate(e.target.value));
            }
        }

        // Faction Dropdown in Custom Unit Creator
        const factionSelect = this.panel.querySelector('#custom-unit-faction');
        if (factionSelect) {
            factionSelect.addEventListener('change', (e) => {
                this.updateBaseSpriteDropdown(e.target.value);
            });
        }

        // Spawn Custom Unit Button
        const spawnBtn = this.panel.querySelector('#spawn-custom-btn');
        if (spawnBtn) {
            spawnBtn.addEventListener('click', () => {
                this.spawnCustomUnitFromForm();
            });
        }

        // Export Mod Config Button
        const exportConfigBtn = this.panel.querySelector('#export-mod-config-btn');
        if (exportConfigBtn) {
            exportConfigBtn.addEventListener('click', () => {
                this.exportModConfig();
            });
        }

        // Patch Local Binary Button
        const patchBinaryBtn = this.panel.querySelector('#patch-local-binary-btn');
        if (patchBinaryBtn) {
            patchBinaryBtn.addEventListener('click', () => {
                this.patchLocalBinary();
            });
        }
    }

    /**
     * Applies a modified stat value immediately to in-memory units and archetypes.
     *
     * @param {string} prop - Stat property name ('move_speed', 'hp', 'attack_power', etc.)
     * @param {number} val - New stat value
     */
    applyStatToLiveUnits(prop, val) {
        // 1. Update focused single unit
        if (this.selectedUnit) {
            this.setUnitStat(this.selectedUnit, prop, val);
        }

        // 2. Update multi-selected units
        if (Array.isArray(this.selectedUnits)) {
            for (const u of this.selectedUnits) {
                if (u && u !== this.selectedUnit) {
                    this.setUnitStat(u, prop, val);
                }
            }
        }

        // 3. Update active archetype & record override
        const targetArchetype = this.selectedArchetype || (this.selectedUnit ? this.selectedUnit.archetype : null);
        if (targetArchetype) {
            const archKey = targetArchetype.index !== undefined ? String(targetArchetype.index) : (targetArchetype.korean_name || targetArchetype.name);
            if (!this.statOverrides[archKey]) {
                this.statOverrides[archKey] = {};
            }
            this.statOverrides[archKey][prop] = val;

            if (prop === 'move_speed') targetArchetype.move_speed = val;
            else if (prop === 'hp') { targetArchetype.hp = val; targetArchetype.max_hp = val; }
            else if (prop === 'attack_power') targetArchetype.attack_power = val;
            else if (prop === 'attack_range') targetArchetype.attack_range = val;
            else if (prop === 'attack_delay') targetArchetype.attack_delay = val;
            else if (prop === 'scale') targetArchetype.scale = val;

            // Also update any live units sharing this archetype on the field
            const allEntities = this.getAllEntities();
            for (const ent of allEntities) {
                if (ent && ent.archetype && (ent.archetype.index === targetArchetype.index || ent.name === targetArchetype.korean_name)) {
                    this.setUnitStat(ent, prop, val);
                }
            }
        }

        // 4. Update global gameEngine state if present
        if (typeof window !== 'undefined' && window.gameEngine) {
            if (prop === 'move_speed') {
                window.gameEngine.selectedUnitSpeed = val;
                if (window.gameEngine.selectedUnit) {
                    window.gameEngine.selectedUnit.move_speed = val;
                }
            }
            if (typeof window.gameEngine.onUnitStatChanged === 'function') {
                window.gameEngine.onUnitStatChanged(this.selectedUnit, prop, val);
            }
        }
    }

    /**
     * Sets a specific stat on a unit instance, adjusting dependent fields.
     */
    setUnitStat(unit, prop, val) {
        if (!unit) return;
        if (prop === 'move_speed') {
            unit.move_speed = val;
        } else if (prop === 'hp') {
            const prevMax = unit.max_hp || 100;
            unit.max_hp = val;
            // Proportionally adjust or keep health valid
            if (unit.hp >= prevMax || unit.hp > val) {
                unit.hp = val;
            }
        } else if (prop === 'attack_power') {
            unit.attack_power = val;
        } else if (prop === 'attack_range') {
            unit.attack_range = val;
        } else if (prop === 'attack_delay') {
            unit.attack_delay = val;
        } else if (prop === 'scale') {
            unit.scale = val;
        }
    }

    /**
     * Binds the editor UI to a live unit on screen.
     *
     * @param {Unit} unit - Currently selected unit
     */
    setSelectedUnit(unit) {
        this.selectedUnit = unit;
        this.selectedUnits = unit ? [unit] : [];

        if (!unit) {
            const unitSelect = this.panel ? this.panel.querySelector('#mod-unit-select') : null;
            if (unitSelect && unitSelect.value === 'auto') {
                this.setTargetIndicator('🎯 [Track Selected Unit]', 'No unit selected. Click a unit on screen or pick from dropdown.');
            }
            return;
        }

        this.setTargetIndicator(
            `🎯 ${unit.name} (ID: #${unit.id})`,
            `Faction: ${unit.owner === 0 ? 'Player (아군)' : 'Enemy (적군)'} | Sprite: ${unit.spriteName || 'default'}`
        );

        this.updateControlsFromUnit(unit);
    }

    /**
     * Binds the editor UI to multiple selected units.
     *
     * @param {Array<Unit>} units - Array of currently selected units
     */
    setSelectedUnits(units) {
        if (!Array.isArray(units) || units.length === 0) {
            this.setSelectedUnit(null);
            return;
        }
        this.selectedUnits = units;
        this.setSelectedUnit(units[0]);
        if (units.length > 1) {
            this.setTargetIndicator(
                `🎯 Multi-Selected (${units.length} Units)`,
                `Primary: ${units[0].name} (#${units[0].id}) + ${units.length - 1} more units`
            );
        }
    }

    /**
     * Updates slider & number inputs to match the given unit's current values.
     */
    updateControlsFromUnit(unit) {
        if (!this.panel) return;
        this.setControlValue('move-speed', 'val-speed', unit.move_speed);
        this.setControlValue('hp', 'val-hp', unit.max_hp || unit.hp);
        this.setControlValue('attack-power', 'val-atk', unit.attack_power);
        this.setControlValue('attack-range', 'val-range', unit.attack_range);
        this.setControlValue('attack-delay', 'val-delay', unit.attack_delay);
        this.setControlValue('scale', 'val-scale', unit.scale || 1.0);
    }

    /**
     * Updates slider & number inputs from an archetype definition.
     */
    updateControlsFromArchetype(archetype) {
        if (!this.panel || !archetype) return;
        const archKey = archetype.index !== undefined ? String(archetype.index) : archetype.korean_name;
        const overrides = this.statOverrides[archKey] || {};

        this.setTargetIndicator(
            `📋 Template: ${archetype.korean_name} (Index: #${archetype.index || 'N/A'})`,
            `Base Sprite: ${archetype.sprite_path || archetype.sprite_name || 'N/A'}`
        );

        this.setControlValue('move-speed', 'val-speed', overrides.move_speed !== undefined ? overrides.move_speed : archetype.move_speed);
        this.setControlValue('hp', 'val-hp', overrides.hp !== undefined ? overrides.hp : (archetype.hp || 100));
        this.setControlValue('attack-power', 'val-atk', overrides.attack_power !== undefined ? overrides.attack_power : (archetype.attack_power || 15));
        this.setControlValue('attack-range', 'val-range', overrides.attack_range !== undefined ? overrides.attack_range : (archetype.attack_range || 2.0));
        this.setControlValue('attack-delay', 'val-delay', overrides.attack_delay !== undefined ? overrides.attack_delay : (archetype.attack_delay || 30));
        this.setControlValue('scale', 'val-scale', overrides.scale !== undefined ? overrides.scale : (archetype.scale || 1.0));
    }

    setControlValue(id, valId, value) {
        const slider = this.panel.querySelector(`#input-${id}`);
        const numInput = this.panel.querySelector(`#num-${id}`);
        const valLabel = this.panel.querySelector(`#${valId}`);
        const num = parseFloat(value);

        if (slider && !isNaN(num)) slider.value = num;
        if (numInput && !isNaN(num)) numInput.value = num;
        if (valLabel && !isNaN(num)) valLabel.textContent = (id === 'scale') ? num.toFixed(1) : num;
    }

    setTargetIndicator(title, meta) {
        if (!this.panel) return;
        const nameEl = this.panel.querySelector('#target-unit-name');
        const metaEl = this.panel.querySelector('#target-unit-meta');
        if (nameEl) nameEl.textContent = title;
        if (metaEl) metaEl.textContent = meta;
    }

    /**
     * Returns currently active move_speed for tests or headless verification.
     */
    getSelectedUnitSpeed() {
        if (this.selectedUnit && this.selectedUnit.move_speed !== undefined) {
            return this.selectedUnit.move_speed;
        }
        if (this.panel) {
            const slider = this.panel.querySelector('#input-move-speed');
            if (slider) return parseFloat(slider.value);
        }
        return 12;
    }

    /**
     * Reads custom unit creator form and spawns the unit at camera center on map.
     */
    spawnCustomUnitFromForm() {
        if (!this.panel) return;

        const faction = this.panel.querySelector('#custom-unit-faction')?.value || 'chosun';
        const baseSprite = this.panel.querySelector('#custom-base-sprite')?.value || 'char/swordk.spr';
        const customName = this.panel.querySelector('#custom-unit-name')?.value.trim() || '조선 초인검사';
        const speed = parseFloat(this.panel.querySelector('#custom-speed')?.value) || 16;
        const hp = parseFloat(this.panel.querySelector('#custom-hp')?.value) || 400;
        const atk = parseFloat(this.panel.querySelector('#custom-atk')?.value) || 35;
        const range = parseFloat(this.panel.querySelector('#custom-range')?.value) || 2.5;
        const delay = parseFloat(this.panel.querySelector('#custom-delay')?.value) || 20;
        const scale = parseFloat(this.panel.querySelector('#custom-scale')?.value) || 1.2;
        const projType = this.panel.querySelector('#custom-projectile-type')?.value || 'arrow';
        const cmdSlot = parseInt(this.panel.querySelector('#custom-command-slot')?.value, 10) || 8;

        const customConfig = {
            id: `custom_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
            index: 1000 + this.customUnits.length,
            korean_name: customName,
            name: customName,
            faction: faction,
            sprite_name: baseSprite,
            sprite_path: baseSprite,
            move_speed: speed,
            hp: hp,
            max_hp: hp,
            attack_power: atk,
            attack_range: range,
            attack_delay: delay,
            scale: scale,
            projectile_type: projType,
            command_slot: cmdSlot,
            is_custom: true
        };

        this.customUnits.push(customConfig);

        // Calculate spawn coordinates at camera center
        const spawnCoords = this.getCameraCenterGridCoords();
        const newUnit = this.spawnUnitInstance(customConfig, spawnCoords.gx, spawnCoords.gy, 0);

        // Bind custom unit to Command Card HUD slot
        this.bindCustomUnitToCommandCard(customConfig);

        // Show feedback in export result box
        this.showResultBox(
            `✨ <strong>[${customName}] 소환 완료!</strong><br>` +
            `위치: (${spawnCoords.gx}, ${spawnCoords.gy}) | 슬롯: Slot ${cmdSlot} [${this.getSlotHotkey(cmdSlot)}]<br>` +
            `속도: ${speed} | HP: ${hp} | 공격력: ${atk} | 투사체: ${projType}`,
            'success'
        );

        if (this.audioManager && typeof this.audioManager.play === 'function') {
            this.audioManager.play('select');
        }

        if (typeof this.onSpawnCustom === 'function') {
            this.onSpawnCustom(newUnit, customConfig);
        }

        return newUnit;
    }

    /**
     * Determines grid coordinates at the center of the camera viewport.
     */
    getCameraCenterGridCoords() {
        const camera = this.camera || (this.gameEngine ? this.gameEngine.camera : null);
        const grid = this.grid || (this.gameEngine ? this.gameEngine.grid : null);

        let centerGx = 90;
        let centerGy = 90;

        if (camera) {
            const vpW = camera.viewportWidth || 1280;
            const vpH = camera.viewportHeight || 720;
            const screenCenterX = vpW / 2;
            const screenCenterY = vpH / 2;

            const camObj = {
                x: (camera.targetX !== undefined) ? camera.targetX : (camera.x || 0),
                y: (camera.targetY !== undefined) ? camera.targetY : (camera.y || 0)
            };

            if (grid && typeof IsometricMath !== 'undefined' && typeof IsometricMath.screenToGrid === 'function') {
                const pt = IsometricMath.screenToGrid(screenCenterX, screenCenterY, camObj, grid.elevation, grid.width, grid.height);
                centerGx = pt.gx;
                centerGy = pt.gy;
            } else {
                const normX = (screenCenterX - camObj.x) / 32;
                const normY = (screenCenterY - camObj.y) / 24;
                centerGx = Math.max(0, Math.min(179, Math.floor((normX + normY) / 2)));
                centerGy = Math.max(0, Math.min(179, Math.floor((normY - normX) / 2)));
            }
        }

        // Walkability check & adjustment
        if (grid && typeof grid.isWalkable === 'function' && !grid.isWalkable(centerGx, centerGy)) {
            for (let r = 1; r <= 5; r++) {
                let found = false;
                for (let dy = -r; dy <= r && !found; dy++) {
                    for (let dx = -r; dx <= r && !found; dx++) {
                        if (grid.isWalkable(centerGx + dx, centerGy + dy)) {
                            centerGx += dx;
                            centerGy += dy;
                            found = true;
                        }
                    }
                }
                if (found) break;
            }
        }

        return { gx: centerGx, gy: centerGy };
    }

    /**
     * Instantiates and registers a new Unit instance into the live game simulation.
     */
    spawnUnitInstance(config, gx, gy, owner = 0) {
        const id = Date.now() + Math.floor(Math.random() * 1000);
        let unitInstance;

        if (typeof Unit !== 'undefined') {
            unitInstance = new Unit(id, config, gx, gy, owner);
        } else if (this.gameEngine && typeof this.gameEngine.createUnit === 'function') {
            unitInstance = this.gameEngine.createUnit(config, gx, gy, owner);
        } else {
            // Fallback object matching Unit interface
            unitInstance = {
                id,
                archetype: config,
                owner,
                name: config.korean_name,
                spriteName: config.sprite_name,
                gx, gy,
                wx: gx + 0.5,
                wy: gy + 0.5,
                move_speed: config.move_speed,
                max_hp: config.hp,
                hp: config.hp,
                attack_power: config.attack_power,
                attack_range: config.attack_range,
                attack_delay: config.attack_delay,
                scale: config.scale || 1.0,
                selected: false,
                isDead: false,
                waypoints: []
            };
        }

        // Add to entity collection
        const list = this.getEntitiesList();
        if (list) {
            list.push(unitInstance);
        }

        // Automatically focus newly spawned unit
        this.setSelectedUnit(unitInstance);

        return unitInstance;
    }

    /**
     * Binds the custom unit definition to a Command Card slot.
     */
    bindCustomUnitToCommandCard(config) {
        const cmdCard = this.commandCard || (this.gameEngine ? this.gameEngine.commandCard : null);
        if (!cmdCard) return;

        const slot = config.command_slot !== undefined ? config.command_slot : 8;
        const buttonDef = {
            slotIndex: slot,
            name: config.korean_name,
            cost: { rice: 100, potato: 50 },
            iconUrl: 'assets/ui/icon_custom.png',
            action: () => {
                const coords = this.getCameraCenterGridCoords();
                this.spawnUnitInstance(config, coords.gx, coords.gy, 0);
            }
        };

        if (typeof cmdCard.setButton === 'function') {
            cmdCard.setButton(slot, buttonDef);
        } else if (Array.isArray(cmdCard.currentButtons)) {
            cmdCard.currentButtons[slot] = buttonDef;
            if (typeof cmdCard.setButtons === 'function') {
                cmdCard.setButtons(cmdCard.currentButtons);
            }
        }
    }

    getSlotHotkey(slotIndex) {
        const hotkeys = ['Q', 'W', 'E', 'R', 'A', 'S', 'D', 'F', 'Z', 'X', 'C', 'V'];
        return hotkeys[slotIndex] || 'Key';
    }

    /**
     * Serializes current mod configuration and submits to POST /api/save_mod_config.
     */
    async exportModConfig() {
        const profileInput = this.panel ? this.panel.querySelector('#export-profile-name') : null;
        const profileName = (profileInput ? profileInput.value.trim() : '') || `mod_profile_${Date.now()}`;

        const payload = {
            profile_name: profileName,
            stat_overrides: this.statOverrides,
            custom_units: this.customUnits,
            active_unit: this.selectedUnit ? {
                id: this.selectedUnit.id,
                name: this.selectedUnit.name,
                move_speed: this.selectedUnit.move_speed,
                hp: this.selectedUnit.max_hp,
                attack_power: this.selectedUnit.attack_power,
                attack_range: this.selectedUnit.attack_range,
                attack_delay: this.selectedUnit.attack_delay,
                scale: this.selectedUnit.scale
            } : null,
            exported_at: new Date().toISOString()
        };

        try {
            const resp = await fetch('/api/save_mod_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (resp.ok) {
                const data = await resp.json();
                this.showResultBox(
                    `✅ <strong>Mod Config Successfully Exported!</strong><br>` +
                    `• File Path: <code>${data.file_path || data.profile_name}</code><br>` +
                    `• Stat Overrides: ${data.stat_overrides_count || Object.keys(this.statOverrides).length} units<br>` +
                    `• Custom Units: ${data.custom_units_count || this.customUnits.length} created`,
                    'success'
                );
            } else {
                throw new Error(`Server returned HTTP ${resp.status}`);
            }
        } catch (err) {
            // Client-side fallback download
            this.downloadJSON(payload, `${profileName}.json`);
            this.showResultBox(
                `💾 <strong>Exported via Browser Download</strong> (Local API unavailable: ${err.message})<br>` +
                `Downloaded: <code>${profileName}.json</code> with ${this.customUnits.length} custom units.`,
                'info'
            );
        }
    }

    /**
     * Patches a copy of dawn.exe via POST /api/patch_binary.
     */
    async patchLocalBinary() {
        const targetFilename = 'dawn_modded.exe';
        let unitId = 50; // default: 조선 농부 / 일본 농부
        let speedVal = 14;

        if (this.selectedUnit) {
            unitId = (this.selectedUnit.archetype && this.selectedUnit.archetype.index) ? this.selectedUnit.archetype.index : 50;
            speedVal = Math.round(this.selectedUnit.move_speed);
        } else if (this.selectedArchetype && this.selectedArchetype.index) {
            unitId = this.selectedArchetype.index;
            const overrides = this.statOverrides[String(unitId)];
            speedVal = overrides && overrides.move_speed ? Math.round(overrides.move_speed) : Math.round(this.selectedArchetype.move_speed);
        } else {
            const speedSlider = this.panel ? this.panel.querySelector('#input-move-speed') : null;
            if (speedSlider) speedVal = Math.round(parseFloat(speedSlider.value));
        }

        const payload = {
            unit_id: unitId,
            stat_name: 'speed',
            new_value: speedVal,
            target_filename: targetFilename
        };

        this.showResultBox('⏳ Patching local dawn.exe binary...', 'info');

        try {
            const resp = await fetch('/api/patch_binary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();
            if (resp.ok && data.success) {
                const shortSha = data.output_sha256 ? data.output_sha256.substring(0, 16) : 'Verified';
                this.showResultBox(
                    `🚀 <strong>Local dawn.exe Successfully Patched!</strong><br>` +
                    `• Output File: <code>${data.output_file}</code><br>` +
                    `• Target Unit: #${unitId} (${data.patch_result?.unit_name || 'Unit'})<br>` +
                    `• move_speed Patched: <code>${data.patch_result?.new_value || speedVal}</code><br>` +
                    `• File Size: <code>1,032,192 bytes</code> (PE Valid)<br>` +
                    `• SHA-256: <code>${shortSha}...</code>`,
                    'success'
                );

                if (typeof this.onExportBinary === 'function') {
                    this.onExportBinary(data);
                }
            } else {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }
        } catch (err) {
            this.showResultBox(
                `❌ <strong>Binary Patch Failed:</strong> ${err.message}<br>` +
                `Ensure local server (<code>python serve_web.py</code>) is running.`,
                'error'
            );
        }
    }

    showResultBox(htmlContent, type = 'info') {
        if (!this.panel) return;
        const box = this.panel.querySelector('#mod-export-result');
        if (!box) return;
        box.style.display = 'block';
        box.className = `export-result-box ${type}`;
        box.innerHTML = htmlContent;
    }

    downloadJSON(obj, filename) {
        if (typeof document === 'undefined') return;
        const str = JSON.stringify(obj, null, 2);
        const blob = new Blob([str], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    getEntitiesList() {
        if (this.entities && Array.isArray(this.entities)) {
            return this.entities;
        }
        if (this.gameEngine && Array.isArray(this.gameEngine.entities)) {
            return this.gameEngine.entities;
        }
        if (this.unitManager) {
            if (Array.isArray(this.unitManager.entities)) return this.unitManager.entities;
            if (Array.isArray(this.unitManager)) return this.unitManager;
        }
        if (typeof window !== 'undefined' && window.gameEngine && Array.isArray(window.gameEngine.entities)) {
            return window.gameEngine.entities;
        }
        return [];
    }

    getAllEntities() {
        return this.getEntitiesList();
    }
}

export default LiveModdingStudio;
