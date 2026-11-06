/**
 * Imjinrok 2+: Dawn (임진록 2+: 여명) - Web RTS Prototype Application Bootstrap
 *
 * Assembles and initializes:
 * - Camera, Audio, GameGrid, Simulation Entities, Combat System, IsometricRenderer
 * - Minimap 2D Radar HUD, 4x3 Command Card HUD, Live Modding Studio, Map Editor Mode
 * - Complete input event handling: Left-click/drag selection box, Right-click move/attack orders,
 *   animated move markers (movemark.spr), Alt key all health bars toggle (syw2x.dll),
 *   WASD/arrows panning, and QWER/ASDF/ZXCV command card hotkeys.
 * - 60FPS requestAnimationFrame loop with clamped delta time.
 * - Global window.gameEngine bridge for automated testing and headless browser integration.
 */

import { IsometricMath } from './engine/isometric.js';
import { Camera } from './engine/camera.js';
import { SoundEngine } from './engine/audio.js';
import { GameGrid } from './simulation/grid.js';
import { PathFinder } from './simulation/pathfinding.js';
import { Unit, Building, Projectile, UnitState } from './simulation/entities.js';
import { CombatSystem } from './simulation/combat.js';
import { IsometricRenderer } from './engine/renderer.js';
import { MinimapHUD } from './ui/minimap.js';
import { CommandCardHUD } from './ui/command_card.js';
import { LiveModdingStudio, BUILTIN_UNIT_TEMPLATES } from './ui/modding_studio.js';
import { MapEditor } from './ui/map_editor.js';
import { DIFFICULTY_TIERS, getDifficultyConfig } from './simulation/difficulty_config.js';
import { StrategicMacroAI } from './simulation/strategic_macro_ai.js';
import { TacticalMicroManager } from './simulation/tactical_micro.js';

export { BUILTIN_UNIT_TEMPLATES } from './ui/modding_studio.js';
export { DIFFICULTY_TIERS, getDifficultyConfig, StrategicMacroAI, TacticalMicroManager };
export const DIFFICULTY_CONFIG = DIFFICULTY_TIERS;

/* --------------------------------------------------------------------------
   Asset Manager Class
   -------------------------------------------------------------------------- */
class WebAssetManager {
    constructor() {
        this.manifest = null;
        this.images = new Map();
        this.metadata = new Map();
        this.tiles = new Map();
        this.unitSprites = new Map();
        this.isLoaded = false;
    }

    async init() {
        try {
            const resp = await fetch('assets/manifest.json');
            if (resp.ok) {
                this.manifest = await resp.json();
                await this.preloadAll();
            }
        } catch (err) {
            console.warn('[AssetManager] Manifest fetch fallback:', err);
        }
        this.isLoaded = true;
    }

    async preloadAll() {
        if (!this.manifest) return;
        const promises = [];

        // Preload unit sprites
        if (this.manifest.units) {
            for (const [key, info] of Object.entries(this.manifest.units)) {
                if (info.atlas) promises.push(this.loadImage(`assets/${info.atlas}`, `unit_${key}`));
                if (info.meta) promises.push(this.loadJSON(`assets/${info.meta}`, `unit_meta_${key}`));
            }
        }

        // Preload tiles (support both manifest.tiles and manifest.tilesets.normal.tiles)
        if (this.manifest.tiles) {
            for (const [key, info] of Object.entries(this.manifest.tiles)) {
                if (info.atlas) promises.push(this.loadImage(`assets/${info.atlas}`, `tile_${key}`));
                if (info.meta) promises.push(this.loadJSON(`assets/${info.meta}`, `tile_meta_${key}`));
            }
        }
        if (this.manifest.tilesets) {
            for (const ts of Object.values(this.manifest.tilesets)) {
                if (ts && Array.isArray(ts.tiles)) {
                    for (const info of ts.tiles) {
                        const key = info.name;
                        if (info.atlas) promises.push(this.loadImage(`assets/${info.atlas}`, `tile_${key}`));
                        if (info.meta) promises.push(this.loadJSON(`assets/${info.meta}`, `tile_meta_${key}`));
                    }
                }
            }
        }

        // Preload resources
        if (this.manifest.resources) {
            for (const [key, info] of Object.entries(this.manifest.resources)) {
                if (info.atlas) promises.push(this.loadImage(`assets/${info.atlas}`, `res_${key}`));
                if (info.meta) promises.push(this.loadJSON(`assets/${info.meta}`, `res_meta_${key}`));
            }
        }

        // Preload UI
        if (this.manifest.ui) {
            for (const [key, info] of Object.entries(this.manifest.ui)) {
                if (info.atlas) promises.push(this.loadImage(`assets/${info.atlas}`, `ui_${key}`));
                else if (info.image) promises.push(this.loadImage(`assets/${info.image}`, `ui_${key}`));
                if (info.meta) promises.push(this.loadJSON(`assets/${info.meta}`, `ui_meta_${key}`));
            }
        }

        // Preload Custom Unit Button Icons (buttons_manifest.json)
        try {
            const btnResp = await fetch('assets/ui/buttons/buttons_manifest.json');
            if (btnResp.ok) {
                const btnData = await btnResp.json();
                if (btnData && Array.isArray(btnData.units)) {
                    for (const u of btnData.units) {
                        if (u.icon_url) {
                            promises.push(this.loadImage(u.icon_url, `btn_${u.kind_hex ? u.kind_hex.toLowerCase() : u.id}`));
                        }
                    }
                }
            }
        } catch (_) {
            // Non-critical fallback
        }

        await Promise.allSettled(promises);
        this.sliceTiles();
        this.assembleUnitSprites();
    }

    async loadImage(url, key) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                this.images.set(key, img);
                resolve(img);
            };
            img.onerror = () => resolve(null);
            img.src = url;
        });
    }

    async loadJSON(url, key) {
        try {
            const resp = await fetch(url);
            if (resp.ok) {
                const data = await resp.json();
                this.metadata.set(key, data);
                return data;
            }
        } catch (_) {}
        return null;
    }

    sliceTiles() {
        // Build 100% seamless 1:1 pixel-art stone ground sheet + tile cache
        const grssAtlas = this.images.get('tile_grss1');
        const diffAtlas = this.images.get('tile_diff1');
        const diff2Atlas = this.images.get('tile_diff2');
        const diff13Atlas = this.images.get('tile_diff13');
        const newblkAtlas = this.images.get('tile_newblk0');
        const newblk1Atlas = this.images.get('tile_newblk1');
        let idCounter = 1;

        // 1. Build 512x256 seamless 1:1 staggered isometric diamond tessellation of normal_newblk0_atlas.png
        //    (Exact Joymax DirectDraw 64x32 diamond tessellation: zero transparent pixels, zero grid lines, 1:1 crisp rock art!)
        const sgCanvas = document.createElement('canvas');
        sgCanvas.width = 512;
        sgCanvas.height = 256;
        const sgCtx = sgCanvas.getContext('2d');
        sgCtx.imageSmoothingEnabled = false;
        sgCtx.fillStyle = '#4d4435';
        sgCtx.fillRect(0, 0, 512, 256);

        if (newblkAtlas) {
            for (let r = -1; r < 17; r++) {
                for (let c = -1; c < 9; c++) {
                    const variant = (((c * 3 + r * 5) % 8) + 8) % 8;
                    const dx = c * 64 + ((r & 1) ? 32 : 0);
                    const dy = r * 16;
                    sgCtx.drawImage(newblkAtlas, variant * 64, 0, 64, 32, dx, dy, 64, 32);
                }
            }
            // Apply authentic Imjinrok 2+ gamma/brightness lift to match yt_maxres1.jpg stone tone
            sgCtx.globalCompositeOperation = 'screen';
            sgCtx.fillStyle = 'rgba(120, 118, 110, 0.36)';
            sgCtx.fillRect(0, 0, 512, 256);
            sgCtx.globalCompositeOperation = 'source-over';
        }
        this.stoneGroundCanvas = sgCanvas;

        const createSeamlessTile = (atlas, col, row, baseFill, srcYOffset = 8, srcH = 16, tintRgba = null) => {
            const offscreen = document.createElement('canvas');
            offscreen.width = 64;
            offscreen.height = 48;
            const ctx = offscreen.getContext('2d');
            ctx.imageSmoothingEnabled = false;

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(32, 0);
            ctx.lineTo(64, 24);
            ctx.lineTo(32, 48);
            ctx.lineTo(0, 24);
            ctx.closePath();
            ctx.clip();

            ctx.fillStyle = baseFill;
            ctx.fill();
            if (atlas) {
                ctx.drawImage(atlas, col * 64 + 16, row * 48 + srcYOffset, 32, srcH, 0, 0, 64, 48);
            }
            if (tintRgba) {
                ctx.fillStyle = tintRgba;
                ctx.fillRect(0, 0, 64, 48);
            }
            ctx.restore();
            return offscreen;
        };

        // IDs 1..18: Authentic seamless stone-grey battlefield earth
        for (let i = 0; i < 18; i++) {
            const c = i % 8;
            this.tiles.set(
                idCounter++,
                createSeamlessTile(diff13Atlas || diff2Atlas || newblkAtlas, c, 0, '#6a665a', 12, 20)
            );
        }

        // IDs 19..22: Lush dark-green forest floor
        for (let i = 0; i < 4; i++) {
            const c = i % 6;
            this.tiles.set(idCounter++, createSeamlessTile(grssAtlas, c, 1, '#2b4c1b', 8, 16));
        }

        // IDs 23..30: Furrowed brown field soil (밭 이랑, matches yt_maxres3.jpg)
        for (let i = 0; i < 8; i++) {
            const c = i % 7;
            this.tiles.set(idCounter++, createSeamlessTile(diff2Atlas || diffAtlas, c, 1, '#584428', 12, 24));
        }

        // IDs 31..40: Authentic Jagged Grey Rock Crags from normal_newblk1_atlas.png (matches top-left & right of yt_maxres1.jpg!)
        const cragCols = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10];
        for (let i = 0; i < 10; i++) {
            const offscreen = document.createElement('canvas');
            offscreen.width = 64;
            offscreen.height = 48;
            const ctx = offscreen.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            if (newblk1Atlas) {
                ctx.drawImage(newblk1Atlas, cragCols[i] * 64, 0, 64, 32, 0, 0, 64, 48);
            }
            this.tiles.set(idCounter++, offscreen);
        }
    }

    assembleUnitSprites() {
        if (!this.manifest || !this.manifest.units) return;

        // Frame 7 is the 100% intact completed building in Imjinrok 2+ .spr files (Frame 8 is half-destroyed!)
        const BUILDING_BEST_FRAME = {
            'hqk_plus.spr': 7,
            'hqk.spr': 7,
            'barrackk.spr': 7,
            'millk_plus.spr': 7,
            'stablek.spr': 7,
            'storagek.spr': 7,
            'jhq.spr': 7,
            'barrackj.spr': 18,
            'hqc.spr': 7,
            'barrackc.spr': 7
        };

        // Joymax 8-direction to 5-stored-direction + DirectDraw horizontal flip (DDLT_MIRRORLEFTRIGHT)
        // Engine Direction: 0:S, 1:SW, 2:W, 3:NW, 4:N, 5:NE, 6:E, 7:SE
        // Stored .spr 5-Dir: 0:SW, 1:W, 2:NW, 3:N, 4:S
        const DIR8_TO_JOYMAX5 = [
            { dir5: 4, flipX: false }, // 0: S
            { dir5: 0, flipX: false }, // 1: SW
            { dir5: 1, flipX: false }, // 2: W
            { dir5: 2, flipX: false }, // 3: NW
            { dir5: 3, flipX: false }, // 4: N
            { dir5: 2, flipX: true  }, // 5: NE (mirror of NW)
            { dir5: 1, flipX: true  }, // 6: E  (mirror of W)
            { dir5: 0, flipX: true  }  // 7: SE (mirror of SW)
        ];

        for (const [key, info] of Object.entries(this.manifest.units)) {
            const img = this.images.get(`unit_${key}`);
            const meta = this.metadata.get(`unit_meta_${key}`);
            if (!img) continue;

            const frameW = info.frame_width || (meta && meta.width) || 64;
            const frameH = info.frame_height || (meta && meta.height) || 64;
            const cols = (meta && meta.cols) || Math.floor(img.width / frameW) || 1;
            const directions = info.directions || 8;
            const frameCount = info.frame_count || (meta && meta.frame_count) || 24;
            const framesPerDir = Math.max(1, Math.floor(frameCount / directions));
            const isBld = info.category === 'building';
            const sprFile = (info.sprite_file || '').toLowerCase();
            const bestBldFrame = (BUILDING_BEST_FRAME[sprFile] !== undefined)
                ? BUILDING_BEST_FRAME[sprFile]
                : Math.min(7, frameCount - 1);

            const getFrameByIndex = (index, flipX = false) => {
                const safeIdx = Math.max(0, Math.min(frameCount - 1, index || 0));
                if (meta && meta.frames && meta.frames[safeIdx]) {
                    const m = meta.frames[safeIdx];
                    const w = m.w || m.width || frameW;
                    const h = m.h || m.height || frameH;
                    return {
                        x: m.u !== undefined ? m.u : (m.x || 0),
                        y: m.v !== undefined ? m.v : (m.y || 0),
                        w,
                        h,
                        hotspotX: w / 2,
                        hotspotY: isBld ? h * 0.72 : h * 0.78,
                        flipX
                    };
                }
                const col = safeIdx % cols;
                const row = Math.floor(safeIdx / cols);
                return {
                    x: col * frameW,
                    y: row * frameH,
                    w: frameW,
                    h: frameH,
                    hotspotX: frameW / 2,
                    hotspotY: isBld ? frameH * 0.72 : frameH * 0.78,
                    flipX
                };
            };

            const spriteObj = {
                image: img,
                width: frameW,
                height: frameH,
                directions,
                framesPerDir,
                isBuilding: isBld,
                getFrame: (dir, animFrame, state, unit = null) => {
                    if (state === 'constructing') {
                        return getFrameByIndex(Math.max(0, Math.min(6, animFrame || 0)), false);
                    }
                    if (isBld || state === 'building') {
                        return getFrameByIndex(bestBldFrame, false);
                    }

                    const d8 = ((dir || 0) % 8 + 8) % 8;
                    const { dir5, flipX } = DIR8_TO_JOYMAX5[d8];
                    const f8 = (animFrame || 0) % 8;
                    const isAtk = (state === 'ATTACK' || state === 'ATTACK_WINDUP' || state === 'ATTACK_COOLDOWN');
                    const isWalk = (state === 'WALK');
                    const isDie = (state === 'DIE');

                    // 1. Farmers (farmerk.spr, farmerj.spr, farmerc.spr — 288 frames)
                    if (frameCount === 288) {
                        if (isDie) return getFrameByIndex(40 + f8, flipX);
                        if (isAtk) {
                            const isWoodOrBuild = unit && (unit.constructingTarget || (unit.harvestTarget && unit.harvestTarget.rType !== 100 && unit.harvestTarget.rType !== 1));
                            const base = isWoodOrBuild ? 128 : 88; // 128: axe/hammer, 88: sickle harvest
                            return getFrameByIndex(base + dir5 * 8 + f8, flipX);
                        }
                        if (isWalk) {
                            const base = (unit && unit.carryingAmount > 0) ? 48 : 0; // 48: carrying grain/wood sack!
                            return getFrameByIndex(base + dir5 * 8 + f8, flipX);
                        }
                        return getFrameByIndex(168 + dir5 * 8 + (f8 % 4), flipX); // 168..207: standing idle
                    }

                    // 2. Spearmen / Samurai (swordk.spr, swordj.spr — 192 frames)
                    if (frameCount === 192) {
                        if (isDie) return getFrameByIndex(40 + f8, flipX);
                        if (isAtk) return getFrameByIndex(48 + dir5 * 8 + f8, flipX);
                        if (isWalk) return getFrameByIndex(0 + dir5 * 8 + f8, flipX);
                        return getFrameByIndex(128 + dir5 * 8 + (f8 % 4), flipX);
                    }

                    // 3. Chosun Archer (archerk.spr — 176 frames)
                    if (frameCount === 176) {
                        if (isDie) return getFrameByIndex(168 + f8, flipX);
                        if (isAtk) return getFrameByIndex(120 + dir5 * 8 + f8, flipX);
                        if (isWalk) return getFrameByIndex(80 + dir5 * 8 + f8, flipX);
                        return getFrameByIndex(0 + dir5 * 8 + (f8 % 4), flipX);
                    }

                    // 4. Horse Archer (horsearcherk.spr — 140 frames)
                    if (frameCount === 140) {
                        if (isAtk) return getFrameByIndex(48 + dir5 * 8 + f8, flipX);
                        if (isWalk) return getFrameByIndex(0 + dir5 * 8 + f8, flipX);
                        return getFrameByIndex(96 + dir5 * 8 + (f8 % 4), flipX);
                    }

                    // 5. General Gwak / Ashigaru Gunner (generalk31.spr, gunj1.spr — 80 frames)
                    if (frameCount === 80) {
                        if (isAtk) return getFrameByIndex(40 + dir5 * 8 + f8, flipX);
                        if (isWalk) return getFrameByIndex(0 + dir5 * 8 + f8, flipX);
                        return getFrameByIndex(0 + dir5 * 8 + (f8 % 2), flipX);
                    }

                    // 6. General Yi Sun-sin / Ming Elephant (generalk12.spr, elephantc1.spr — 56 frames)
                    if (frameCount === 56) {
                        if (isAtk) return getFrameByIndex(dir5 * 10 + 2 + f8, flipX);
                        return getFrameByIndex(dir5 * 10 + (isWalk ? (f8 % 2) : 0), flipX);
                    }

                    // Default fallback for siege/ships (cannonk, ashipk, flametankj, swordc1, gunc)
                    const stride = Math.max(1, Math.min(8, Math.floor(frameCount / 5)));
                    return getFrameByIndex(dir5 * stride + (isWalk || isAtk ? (f8 % stride) : 0), flipX);
                },
                // Waving red '訓' flags on Chosun Barracks (frames 10..16 in barrackk_atlas.png)
                getBannerFrame: (sprFile === 'barrackk.spr')
                    ? (tick) => getFrameByIndex(10 + ((tick || 0) % 7), false)
                    : null
            };

            this.unitSprites.set(key, spriteObj);
            if (info.sprite_file) {
                this.unitSprites.set(`char/${info.sprite_file}`, spriteObj);
                this.unitSprites.set(info.sprite_file, spriteObj);
            }
        }
    }

    getTileImage(tileId) {
        if (!this.tiles.size) return null;
        if (this.tiles.has(tileId)) return this.tiles.get(tileId);
        const wrapped = ((Math.max(1, tileId) - 1) % 18) + 1;
        return this.tiles.get(wrapped) || this.tiles.get(1) || null;
    }

    getUnitSprite(spriteName) {
        if (!spriteName) return null;
        const clean = spriteName.replace('char/', '').toLowerCase();
        const ALIASES = {
            'hqk.spr': 'hqk_plus.spr',
            'millk.spr': 'millk_plus.spr',
            'worker_k.spr': 'farmerk.spr',
            'worker_j.spr': 'farmerj.spr',
            'worker_m.spr': 'farmerc.spr',
            'general_leesunshin.spr': 'generalk12.spr',
            'leesunsin.spr': 'generalk12.spr',
            'general_gwak.spr': 'generalk31.spr',
            'general_samyeong.spr': 'generalk12.spr',
            'podo.spr': 'generalk31.spr',
            'gapsa.spr': 'swordk.spr',
            'cavalry_k.spr': 'horsearcherk.spr',
            'turtle.spr': 'ashipk.spr',
            'bulangki.spr': 'cannonk.spr',
            'hwacha.spr': 'cannonk.spr',
            'samurai.spr': 'swordj.spr',
            'sword_j.spr': 'swordj.spr',
            'ninja.spr': 'swordj.spr',
            'general_hideyoshi.spr': 'swordj.spr',
            'general_kato.spr': 'swordj.spr',
            'gunner_j.spr': 'gunj1.spr',
            'gunnerj.spr': 'gunj1.spr',
            'general_konishi.spr': 'gunj1.spr',
            'sword_m.spr': 'swordc1.spr',
            'generalc2.spr': 'swordc1.spr',
            'gunner_m.spr': 'gunc.spr',
            'archer_m.spr': 'gunc.spr',
            'generalc43.spr': 'gunc.spr',
            'cavalry_m.spr': 'elephantc1.spr',
            'cavalrym.spr': 'elephantc1.spr'
        };
        const mapped = ALIASES[clean] || clean;
        return this.unitSprites.get(spriteName) ||
               this.unitSprites.get(clean) ||
               this.unitSprites.get(mapped) ||
               this.unitSprites.get(`char/${mapped}`) ||
               this.unitSprites.get('chosun_spearman') || null;
    }

    getResourceSprite(type, gx = 0, gy = 0) {
        let key = 'crop0';
        // Mature/full-grown frame indices in each resource atlas
        let matureFrames = [5, 15, 25];
        if (type === 100) {
            key = 'crop1';
            matureFrames = [20, 21, 22, 26, 27, 28, 30];
        } else if (type === 3 || type === 2) {
            // Mix expansion tree_plus (oak, maple, pine, bamboo) with tree0 (7 leafy tree species)
            const usePlus = ((gx * 3 + gy * 7) % 3 === 0) && this.images.get('res_tree_plus');
            if (usePlus) {
                key = 'tree_plus';
                matureFrames = [0, 5, 10, 15, 20];
            } else {
                key = 'tree0';
                matureFrames = [0, 10, 20, 30, 40, 50, 60];
            }
        }

        const img = this.images.get(`res_${key}`);
        const meta = this.metadata.get(`res_meta_${key}`);
        if (!img) return null;

        const hash = Math.abs((gx * 7 + gy * 13)) % matureFrames.length;
        const frameIdx = matureFrames[hash];
        if (meta && meta.frames && meta.frames[frameIdx]) {
            const f = meta.frames[frameIdx];
            const sw = f.width || meta.width || 64;
            const sh = f.height || meta.height || 48;
            return {
                image: img,
                sx: f.u || 0,
                sy: f.v || 0,
                sw,
                sh,
                ox: Math.round(sw / 2),
                oy: (key === 'tree0' || key === 'tree_plus') ? Math.round(sh * 0.80) : Math.round(sh * 0.35)
            };
        }
        return null;
    }
}

/* --------------------------------------------------------------------------
   Game Engine Core Application Class
   -------------------------------------------------------------------------- */
export class GameApp {
    constructor() {
        // Canvas & Context
        this.canvas = document.getElementById('rts-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d', { alpha: false }) : null;

        // Core Components
        this.assetManager = new WebAssetManager();
        this.camera = new Camera(1280, 720, 100, 100);
        this.soundEngine = new SoundEngine();
        this.grid = new GameGrid(100, 100);
        this.entities = [];
        this.projectiles = [];
        this.nextEntityId = 1;
        this.nextProjId = 1;

        // Visual Effects: Animated Move Markers
        this.moveMarkers = []; // { wx, wy, elev, time, duration, type }

        // Subsystems & HUD
        this.renderer = null;
        this.minimap = null;
        this.commandCard = null;
        this.liveModding = null;
        this.mapEditor = null;

        // Input & Selection State
        this.keysDown = {};
        this.mousePos = { x: 640, y: 360 };
        this.isMouseDown = false;
        this.mouseDownPos = { x: 0, y: 0 };
        this.isDragSelecting = false;
        this.selectedUnits = [];

        // Game Loop Timing & Telemetry
        this.lastTime = performance.now();
        this.elapsedGameTime = 0;
        this.fpsHistory = [];
        this.currentFps = 60;
        this.lastFpsUpdate = 0;

        // In-game Resources (Player 0)
        this.resources = {
            rice: 2500,
            potato: 1800,
            wood: 950,
            money: 600,
            population: 14,
            maxPopulation: 50
        };

        // DOM elements
        this.dom = {
            resRice: document.getElementById('res-rice'),
            resPotato: document.getElementById('res-potato'),
            resWood: document.getElementById('res-wood'),
            resMoney: document.getElementById('res-money'),
            resPopulation: document.getElementById('res-population'),
            gameTimer: document.getElementById('game-timer'),
            fpsCounter: document.getElementById('fps-counter'),
            selectionName: document.getElementById('selection-name'),
            selectionFaction: document.getElementById('selection-faction'),
            selectionHpFill: document.getElementById('selection-hp-fill'),
            selectionHpText: document.getElementById('selection-hp-text'),
            selectionMpFill: document.getElementById('selection-mp-fill'),
            selectionMpText: document.getElementById('selection-mp-text'),
            statAttack: document.getElementById('stat-attack'),
            statDefense: document.getElementById('stat-defense'),
            statRange: document.getElementById('stat-range'),
            statSpeed: document.getElementById('stat-speed'),
            liveModPanel: document.getElementById('live-mod-panel'),
            mapEditorPanel: document.getElementById('map-editor-panel'),
            helpModal: document.getElementById('help-modal'),
            resRice: document.getElementById('res-rice'),
            resPotato: document.getElementById('res-potato'),
            resWood: document.getElementById('res-wood'),
            resSupply: document.getElementById('res-supply'),
            portraitSprite: document.getElementById('portrait-sprite'),
            hudProdRow: document.getElementById('hud-prod-row'),
            hudProdIcon: document.getElementById('hud-prod-icon'),
            hudProdPct: document.getElementById('hud-prod-pct'),
            hudProdLabel: document.getElementById('hud-prod-label'),
            hudProdBox: document.getElementById('hud-production-box'),
            targetBracketsBox: document.getElementById('target-brackets-box'),
            fKeyBar: document.getElementById('f-key-bar'),
            compassDial: document.getElementById('hud-compass-dial'),
            compassCanvas: document.getElementById('compass-canvas')
        };

        this.resources = {
            rice: 1154,
            potato: 2300,
            wood: 2300,
            supplyUsed: 98,
            supplyMax: 2500
        };
        this.floatingTexts = [];
        this.enemyWaveTimer = 0;
        this.barracksProdProgress = 0.43; // Starts at 43%

        // =====================================================================
        // Authentic Imjinrok 2+: Dawn Gameplay Systems (Text_kor.dat, ExpForLevelUp.dat, screenPt_plus.dat)
        // =====================================================================
        // 1. ExpForLevelUp.dat exact level thresholds (Lv1..Lv12)
        this.expTable = [0, 100, 140, 220, 340, 500, 700, 940, 1220, 1540, 1900, 2300, 2800];

        // 2. Authentic System Message Ticker & syw2x.dll F12 Real-Time Clock
        this.systemBanner = {
            text: '임진록 2+ 조선의 반격: 여명 — 전장 시뮬레이션 가동 중',
            color: '#f4efe1',
            timer: 8.0
        };
        this.showF12Clock = true;

        // 3. Wind & Weather System (Compass Dial at 197, 521 + Downwind Fire + Rain Crop Regrowth)
        this.windDirection = 2; // 0:북, 1:북동, 2:동, 3:남동, 4:남, 5:남서, 6:서, 7:북서
        this.windTimer = 0;
        this.weather = 'sunny'; // 'sunny' | 'rain' (기우제 비)
        this.rainTimer = 0;
        this.groundFires = [
            { wx: 25.5, wy: 25.2, phase: 0, life: 35.0, spreadTimer: 0 },
            { wx: 26.2, wy: 25.6, phase: 7, life: 35.0, spreadTimer: 1.5 },
            { wx: 26.9, wy: 26.0, phase: 14, life: 35.0, spreadTimer: 3.0 },
            { wx: 26.0, wy: 26.3, phase: 21, life: 35.0, spreadTimer: 2.2 }
        ];
        this.depletedCrops = new Map(); // key "gx,gy" -> { gx, gy, rType, regrowProgress }
        this.inspectedResource = null;  // { gx, gy, rType, name, amount, maxAmount }

        // 4. Farmer 2-Tier Construction & Placement Ghost (건물1 초급건물 / 건물2 고급건물)
        this.farmerMenuTier = 0; // 0: normal, 1: 초급건물(Z), 2: 고급건물(X)
        this.placingBuilding = null; // { korean_name, sprite_name, width, height, hp, defense, costWood, costRice }
        this.pendingCommand = null;  // RTS Target Cursor Mode: { action, name, color, radius }

        // 5. Researched Technologies, Control Groups (Ctrl+1..9) & F1..F11 Quick-Select Bar
        this.researchedTechs = new Set();
        this.controlGroups = new Map();
        this.lastGroupKey = null;
        this.lastGroupTapTime = 0;
        this.fKeyUnits = [];
        this.lastFKeyUpdate = 0;
        this.lastFKeySlot = null;
        this.lastFKeyTapTime = 0;

        // 6. Multi-Player Resource Tracking & Calibrated Difficulty AI Overhaul
        this.playerResources = {
            0: this.resources,
            1: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 20, supplyMax: 2000 },
            2: { rice: 1000, potato: 800, wood: 1000, supplyUsed: 20, supplyMax: 2000 }
        };
        this.getPlayerResources = (owner) => {
            if (!this.playerResources[owner]) {
                this.playerResources[owner] = { rice: 1000, potato: 800, wood: 1000, supplyUsed: 0, supplyMax: 2000 };
            }
            return this.playerResources[owner];
        };

        this.difficulty = DIFFICULTY_TIERS.NORMAL;
        this.difficultyConfig = getDifficultyConfig(this.difficulty);
        this.macroAI = new StrategicMacroAI(this, { owner: 1, faction: 'japan', difficulty: this.difficulty });
        this.tacticalMicro = new TacticalMicroManager(this, { owner: 1, difficulty: this.difficulty });
    }

    setDifficulty(tier) {
        this.difficulty = (typeof tier === 'string') ? (DIFFICULTY_TIERS[tier.toUpperCase()] || DIFFICULTY_TIERS.NORMAL) : (tier || DIFFICULTY_TIERS.NORMAL);
        this.difficultyConfig = getDifficultyConfig(this.difficulty);
        if (this.macroAI) this.macroAI.difficultyConfig = this.difficultyConfig;
        if (this.tacticalMicro) this.tacticalMicro.setDifficulty(this.difficulty);
    }

    setPendingCommand(action, name, color = '#32e650', radius = 0.8, slotIndex = -1) {
        this.pendingCommand = { action, name, color, radius, slotIndex };
        if (this.canvas) this.canvas.style.cursor = 'crosshair';
        if (this.commandCard && typeof this.commandCard.setActiveCommand === 'function') {
            this.commandCard.setActiveCommand(action, slotIndex);
        }
        this.announceSystemMessage(`🎯 [${name}] 목표 지점이나 대상을 전장에서 좌클릭하세요 (우클릭 / ESC: 취소)`, color);
    }

    clearPendingCommand() {
        this.pendingCommand = null;
        if (this.canvas) this.canvas.style.cursor = 'default';
        if (this.commandCard && typeof this.commandCard.clearActiveCommand === 'function') {
            this.commandCard.clearActiveCommand();
        }
    }

    markBuildingFootprint(b) {
        if (!b || !this.grid) return;
        const bw = Math.max(1, (b.width || 2) - 1);
        const bh = Math.max(1, (b.height || 2) - 1);
        for (let dy = 0; dy < bh; dy++) {
            for (let dx = 0; dx < bw; dx++) {
                const tx = Math.round(b.gx) + dx;
                const ty = Math.round(b.gy) + dy;
                if (tx >= 0 && tx < this.grid.width && ty >= 0 && ty < this.grid.height) {
                    this.grid.setWalkability(tx, ty, 1);
                }
            }
        }
    }

    announceSystemMessage(text, color = '#ffd700') {
        this.systemBanner = { text, color, timer: 6.5 };
    }

    async start() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());

        // 1. Initialize Asset Pipeline
        await this.assetManager.init();

        // 2. Initialize Subsystems
        this.renderer = new IsometricRenderer(this.canvas, this.assetManager);

        const minimapCanvas = document.getElementById('minimap-canvas');
        this.minimap = new MinimapHUD(minimapCanvas, this.grid, this.camera, (gx, gy) => {
            this.issueOrder(gx, gy, false);
        });

        const appSelf = this;

        // Authentic Imjinrok 2+ Command Card Presets (decoded from Text_kor.dat)
        CommandCardHUD.prototype.setDefaultUnitCommands = function() {
            const buttons = new Array(12).fill(null);
            buttons[0] = { id: 'move', action: 'move', name: '이동 (Move)', hotkey: 'Q', atlasPos: '-204px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '선택한 부대를 목표 지점으로 이동시킵니다. [Q / 우클릭]' };
            buttons[1] = { id: 'stop', action: 'stop', name: '정지 (Stop)', hotkey: 'W', atlasPos: '-238px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '현재 이동 및 공격 명령을 즉시 중지합니다. [W]' };
            buttons[2] = { id: 'hold', action: 'hold', name: '위치 사수 (Hold)', hotkey: 'E', atlasPos: '-272px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '현 위치를 고수하며 사거리 내 적을 요격합니다. [E]' };
            buttons[3] = { id: 'attack', action: 'attack_ground', name: '공격 진군 (Attack)', hotkey: 'R', atlasPos: '-136px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '가장 가까운 적군 진영을 향해 공격 진군합니다. [R]' };
            buttons[4] = { id: 'patrol', action: 'patrol', name: '순찰 (Patrol)', hotkey: 'A', atlasPos: '-306px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '본영과 전방 초소 사이를 왕복 순찰합니다. [A]' };
            buttons[5] = { id: 'skill_shockwave', action: 'skill_shockwave', name: '기공신포 (MP 40)', hotkey: 'S', atlasPos: '-0px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '장수의 기공신포/충격파로 전방 적군을 타격합니다. [S]' };
            buttons[6] = { id: 'skill_firestorm', action: 'skill_firestorm', name: '폭뢰격 화공 (MP 60)', hotkey: 'D', atlasPos: '-68px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '전방 적 진영에 폭뢰격과 화공 불길을 일으킵니다! [D]' };
            buttons[7] = { id: 'all_charge', action: 'all_charge', name: '전군 총공격 (Charge)', hotkey: 'F', atlasPos: '-170px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '아군 전체 전투 부대를 적 본영으로 총돌격시킵니다! [F]' };
            buttons[8] = { id: 'use_ginseng', action: 'use_ginseng', name: '인삼 복용 (+300 HP)', hotkey: 'Z', atlasPos: '-102px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '인삼을 복용하여 선택된 장수/부대의 체력을 즉시 300 회복합니다. [Z]' };
            buttons[9] = { id: 'cast_rain', action: 'cast_rain', name: '기우제 주문 (비 내리기)', hotkey: 'X', atlasPos: '-136px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '기우제를 지내 전장의 불길을 끄고 논밭의 벼를 빠르게 재생시킵니다! [X]' };
            buttons[10] = { id: 'summon_clones', action: 'summon_clones', name: '분신술 (MP 80)', hotkey: 'C', atlasPos: '-170px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '선택한 장수의 환영 분신을 소환하여 전투를 돕게 합니다. [C]' };
            buttons[11] = { id: 'produce_hwacha', action: 'produce_hwacha', name: '신기전 화차 지원', hotkey: 'V', atlasPos: '-238px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '군기시에서 다연장 신기전 화차를 배치합니다 (목재 120). [V]' };
            this.setButtons(buttons);
        };

        CommandCardHUD.prototype.setFarmerCommands = function(tier = 0) {
            const buttons = new Array(12).fill(null);
            if (tier === 1) {
                // 건물1 (초급건물) from Text_kor.dat
                buttons[0] = { id: 'place_hq', action: 'place_hq', name: '조선 본영 (쌀500 목500)', hotkey: 'Q', atlasPos: '-238px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '농부를 생산하고 장수를 등용하는 조선 본영을 건설합니다. [Q]' };
                buttons[1] = { id: 'place_mill', action: 'place_mill', name: '조선 방앗간 (목재 150)', hotkey: 'W', atlasPos: '-306px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '식량 비축량(인구 최대치 +500)을 늘리고 상인을 부르는 방앗간을 짓습니다. [W]' };
                buttons[2] = { id: 'place_barracks', action: 'place_barracks', name: '조선 훈련소 (목재 200)', hotkey: 'E', atlasPos: '-272px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '창병, 궁수, 갑사, 승병을 양성하는 조선 훈련소를 건설합니다. [E]' };
                buttons[3] = { id: 'place_stable', action: 'place_stable', name: '조선 목장 (목재 250)', hotkey: 'R', atlasPos: '-0px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '기마궁수와 신기전 화차를 생산하는 조선 목장(마구간)을 건설합니다. [R]' };
                buttons[4] = { id: 'place_tower', action: 'place_tower', name: '신기전망루 (목재 180)', hotkey: 'A', atlasPos: '-68px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '적의 침입을 자동으로 요격하는 방어용 신기전망루를 건설합니다. [A]' };
                buttons[11] = { id: 'farmer_menu_cancel', action: 'farmer_menu_cancel', name: '취소 (Cancel)', hotkey: 'V', atlasPos: '-306px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '농부 기본 명령 메뉴로 돌아갑니다. [V / ESC]' };
            } else if (tier === 2) {
                // 건물2 (고급건물) from Text_kor.dat
                buttons[0] = { id: 'place_armory', action: 'place_armory', name: '조선 훈련도감 (목재 300)', hotkey: 'Q', atlasPos: '-102px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '고급 마법 연구와 장수 무기(청홍검·폭마혈도)를 제작하는 훈련도감(군기시)을 짓습니다. [Q]' };
                buttons[1] = { id: 'place_smithy', action: 'place_smithy', name: '조선 제철장 (목재 260)', hotkey: 'W', atlasPos: '-136px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '전군 공격력/방어력 업그레이드를 수행하는 제철장을 건설합니다. [W]' };
                buttons[2] = { id: 'place_temple', action: 'place_temple', name: '조선 절 (목재 240)', hotkey: 'E', atlasPos: '-170px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '사명대사와 승병의 법력을 강화하는 사찰을 건설합니다. [E]' };
                buttons[11] = { id: 'farmer_menu_cancel', action: 'farmer_menu_cancel', name: '취소 (Cancel)', hotkey: 'V', atlasPos: '-306px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '농부 기본 명령 메뉴로 돌아갑니다. [V / ESC]' };
            } else {
                // 농부 기본 메뉴 (Text_kor.dat: 이동, 정지, 공격, 수확, 수리, 불끄기, 황소농부로.., 건물1, 건물2)
                buttons[0] = { id: 'move', action: 'move', name: '이동 (Move)', hotkey: 'Q', atlasPos: '-204px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '농부를 목표 지점으로 이동시킵니다. [Q]' };
                buttons[1] = { id: 'stop', action: 'stop', name: '정지 (Stop)', hotkey: 'W', atlasPos: '-238px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '현재 작업을 중지합니다. [W]' };
                buttons[2] = { id: 'attack', action: 'attack_ground', name: '공격 (Attack)', hotkey: 'E', atlasPos: '-136px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '적을 공격합니다. [E]' };
                buttons[3] = { id: 'harvest', action: 'harvest', name: '수확 (Harvest)', hotkey: 'R', atlasPos: '-68px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '주변 논밭의 쌀(벼)이나 숲의 목재를 자동 수확합니다. [R]' };
                buttons[4] = { id: 'repair_building', action: 'repair_building', name: '건물 수리 (Repair)', hotkey: 'A', atlasPos: '-204px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '손상된 아군 건물의 체력을 즉시 수리합니다. [A]' };
                buttons[5] = { id: 'extinguish_fire', action: 'extinguish_fire', name: '불끄기 (Extinguish)', hotkey: 'S', atlasPos: '-136px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '전장에 번진 화공 불길(groundfire)을 진압합니다! [S]' };
                buttons[6] = { id: 'upgrade_ox_farmer', action: 'upgrade_ox_farmer', name: '황소농부로.. (쌀 80)', hotkey: 'D', atlasPos: '-68px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '황소를 태워 채집량과 체력이 2배 높은 황소농부로 전환합니다. [D]' };
                buttons[8] = { id: 'farmer_tier1', action: 'farmer_tier1', name: '건물1 (초급건물)', hotkey: 'Z', atlasPos: '-272px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '초급건물(본영·방앗간·훈련소·목장·신기전망루) 건설 메뉴를 엽니다. [Z]' };
                buttons[9] = { id: 'farmer_tier2', action: 'farmer_tier2', name: '건물2 (고급건물)', hotkey: 'X', atlasPos: '-102px -136px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '고급건물(훈련도감·제철장·절) 건설 메뉴를 엽니다. [X]' };
            }
            this.setButtons(buttons);
        };

        CommandCardHUD.prototype.setBuildingProductionCommands = function(building) {
            const bName = (building && building.name) ? building.name : '조선 훈련소';
            const buttons = new Array(12).fill(null);

            const getUnitBtn = (id) => {
                if (typeof this.getCustomUnitButtonDef === 'function') {
                    const b = this.getCustomUnitButtonDef(id);
                    if (b) return b;
                }
                const fallback = {
                    yusaeng: { id: 'produce_unit_0x70', unitId: 'yusaeng', action: 'produce_custom_unit', kindId: 0x70, kindHex: '0x70', name: '유생 [Y]', hotkey: 'Y', slot: 9, costRice: 250, costPotato: 0, iconUrl: 'assets/ui/buttons/btn_unit_0x70.png', isCustomUnit: true },
                    bulgasari: { id: 'produce_unit_0x79', unitId: 'bulgasari', action: 'produce_custom_unit', kindId: 0x79, kindHex: '0x79', name: '불가살이 [U]', hotkey: 'U', slot: 10, costRice: 380, costPotato: 100, iconUrl: 'assets/ui/buttons/btn_unit_0x79.png', isCustomUnit: true },
                    gumiho: { id: 'produce_unit_0x73', unitId: 'gumiho', action: 'produce_custom_unit', kindId: 0x73, kindHex: '0x73', name: '구미호 [F]', hotkey: 'F', slot: 11, costRice: 280, costPotato: 50, iconUrl: 'assets/ui/buttons/btn_unit_0x73.png', isCustomUnit: true },
                    geomsul_nangin: { id: 'produce_unit_0x71', unitId: 'geomsul_nangin', action: 'produce_custom_unit', kindId: 0x71, kindHex: '0x71', name: '검술 낭인 [K]', hotkey: 'K', slot: 8, costRice: 180, costPotato: 0, iconUrl: 'assets/ui/buttons/btn_unit_0x71.png', isCustomUnit: true },
                    jochong_nangin: { id: 'produce_unit_0x72', unitId: 'jochong_nangin', action: 'produce_custom_unit', kindId: 0x72, kindHex: '0x72', name: '조총 낭인 [N]', hotkey: 'N', slot: 9, costRice: 240, costPotato: 0, iconUrl: 'assets/ui/buttons/btn_unit_0x72.png', isCustomUnit: true },
                    teolgamyeon: { id: 'produce_unit_0x76', unitId: 'teolgamyeon', action: 'produce_custom_unit', kindId: 0x76, kindHex: '0x76', name: '털가면 [M]', hotkey: 'M', slot: 10, costRice: 220, costPotato: 40, iconUrl: 'assets/ui/buttons/btn_unit_0x76.png', isCustomUnit: true },
                    wangbeol: { id: 'produce_unit_0x74', unitId: 'wangbeol', action: 'produce_custom_unit', kindId: 0x74, kindHex: '0x74', name: '조선왕벌 [B]', hotkey: 'B', slot: 7, isAir: true, isAirUnit: true, costRice: 200, costPotato: 50, iconUrl: 'assets/ui/buttons/btn_unit_0x74.png', isCustomUnit: true },
                    horangi: { id: 'produce_unit_0x75', unitId: 'horangi', action: 'produce_custom_unit', kindId: 0x75, kindHex: '0x75', name: '조선 호랑이 [T]', hotkey: 'T', slot: 8, costRice: 300, costPotato: 0, iconUrl: 'assets/ui/buttons/btn_unit_0x75.png', isCustomUnit: true },
                    seolnyeo: { id: 'produce_unit_0x77', unitId: 'seolnyeo', action: 'produce_custom_unit', kindId: 0x77, kindHex: '0x77', name: '설녀 [S]', hotkey: 'S', slot: 9, costRice: 280, costPotato: 60, iconUrl: 'assets/ui/buttons/btn_unit_0x77.png', isCustomUnit: true },
                    dokkaebi: { id: 'produce_unit_0x78', unitId: 'dokkaebi', action: 'produce_custom_unit', kindId: 0x78, kindHex: '0x78', name: '조선 도깨비 [D]', hotkey: 'D', slot: 10, costRice: 320, costPotato: 0, iconUrl: 'assets/ui/buttons/btn_unit_0x78.png', isCustomUnit: true }
                };
                return fallback[id] || null;
            };

            if (bName.includes('본영') || bName.includes('HQ') || bName.includes('hq')) {
                // 조선 본영: 농부 생산 + 장수 등용 (이순신, 곽재우, 권율, 사명대사, 허준, 김덕령) + Slot 9 (유생 [Y]), Slot 10 (불가살이 [U]), Slot 11 (구미호 [F])
                buttons[0] = { id: 'produce_farmer', action: 'produce_farmer', name: '조선 농부 (쌀 40)', hotkey: 'Q', atlasPos: '-68px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '자원을 채집하고 건물을 건설하는 조선 농부를 생산합니다. [Q]' };
                buttons[1] = { id: 'set_rally', action: 'set_rally', name: '집결지 설정 (Rally)', hotkey: 'W', atlasPos: '-204px -0px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '생산된 병력이 모일 집결지를 설정합니다 (우클릭 가능). [W]' };
                buttons[4] = { id: 'summon_hero', action: 'summon_hero', name: '이순신 등용 (쌀 150)', hotkey: 'A', atlasPos: '-0px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '충무공 이순신 장군을 본영에서 등용합니다 (기공신포 보유). [A]' };
                buttons[5] = { id: 'summon_kwak', action: 'summon_kwak', name: '곽재우 등용 (쌀 140)', hotkey: 'S', atlasPos: '-68px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '홍의장군 곽재우를 본영에서 등용합니다 (화공/불화살 특화). [S]' };
                buttons[6] = { id: 'summon_samyeong', action: 'summon_samyeong', name: '사명대사 등용 (쌀 140)', hotkey: 'D', atlasPos: '-102px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '사명대사를 등용합니다 (번개술·기우제 마법 특화). [D]' };
                buttons[7] = { id: 'summon_heojun', action: 'summon_heojun', name: '허준 등용 (쌀 120)', hotkey: 'F', atlasPos: '-136px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '명의 허준을 등용하여 아군 부대를 치료합니다. [F]' };
                buttons[8] = { id: 'tech_harvest', action: 'tech_harvest', name: '장수우선훈련 연구', hotkey: 'Z', atlasPos: '-204px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '장수의 경험치 획득량과 마법력 회복 속도를 높입니다 (목재 150). [Z]' };
                buttons[9] = getUnitBtn('yusaeng');
                buttons[10] = getUnitBtn('bulgasari');
                buttons[11] = getUnitBtn('gumiho');
            } else if (bName.includes('방앗간')) {
                // 조선 방앗간: 우경법, 자원 가치 향상, 상인 호출, 곡물팔기, 목재팔기 (Text_kor.dat!)
                buttons[0] = { id: 'tech_plow', action: 'tech_plow', name: '우경법 연구 (목재 100)', hotkey: 'Q', atlasPos: '-68px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '소를 이용한 깊은 갈이로 농부의 쌀 수확량을 +50% 증가시킵니다! [Q]' };
                buttons[1] = { id: 'tech_economy', action: 'tech_economy', name: '자원 가치 향상 (목 150)', hotkey: 'W', atlasPos: '-102px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '자원 비축 효율을 높여 모든 채집 수입을 +30% 향상시킵니다. [W]' };
                buttons[4] = { id: 'call_merchant', action: 'call_merchant', name: '개성 김씨 상인 호출', hotkey: 'A', atlasPos: '-170px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '개성 김씨 상인을 불러들여 희귀 아이템과 군자금을 교역합니다. [A]' };
                buttons[5] = { id: 'buy_ginseng', action: 'buy_ginseng', name: '인삼 구입 (쌀 100)', hotkey: 'S', atlasPos: '-102px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '장수/부대 체력을 즉시 300 회복시키는 고려 인삼을 구입합니다. [S]' };
                buttons[6] = { id: 'buy_rain_scroll', action: 'buy_rain_scroll', name: '기우제 주문서 (쌀 120)', hotkey: 'D', atlasPos: '-136px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '전장에 비를 내려 화공을 끄고 벼를 급속 재생시키는 기우제를 발동합니다! [D]' };
                buttons[8] = { id: 'sell_grain', action: 'sell_grain', name: '곡물팔기 (쌀500→목350)', hotkey: 'Z', atlasPos: '-238px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '비축된 쌀 500석을 시장에 팔아 목재 350을 즉시 확보합니다. [Z]' };
                buttons[9] = { id: 'sell_wood', action: 'sell_wood', name: '목재팔기 (목500→쌀350)', hotkey: 'X', atlasPos: '-272px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '비축된 목재 500을 시장에 팔아 쌀 350석을 즉시 확보합니다. [X]' };
            } else if (bName.includes('마구간') || bName.includes('목장') || bName.includes('stable')) {
                // 조선 마구간/목장 (Stables): Slot 7 (조선왕벌 [B]), Slot 8 (조선 호랑이 [T]), Slot 9 (설녀 [S]), Slot 10 (조선 도깨비 [D]). (Slot 11 empty).
                buttons[0] = { id: 'produce_cavalry', action: 'produce_cavalry', name: '기마궁수 (쌀80 목30)', hotkey: 'Q', atlasPos: '-170px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '기동력과 사거리를 겸비한 조선 기마궁수를 생산합니다. [Q]' };
                buttons[1] = { id: 'produce_hwacha', action: 'produce_hwacha', name: '조선 화차 (목재 120)', hotkey: 'W', atlasPos: '-238px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '다연장 신기전을 발사하여 적 진영을 불바다로 만드는 화차를 생산합니다. [W]' };
                buttons[2] = { id: 'produce_cannon', action: 'produce_cannon', name: '불랑기포 (목재 140)', hotkey: 'E', atlasPos: '-272px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '강력한 포격으로 적 건물과 밀집 부대를 타격하는 불랑기포를 생산합니다. [E]' };
                buttons[3] = { id: 'produce_elephant', action: 'produce_elephant', name: '명 코끼리병 (쌀 120)', hotkey: 'R', atlasPos: '-306px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '막강한 체력의 명나라 코끼리병 지원군을 호출합니다. [R]' };
                buttons[7] = getUnitBtn('wangbeol');
                buttons[8] = getUnitBtn('horangi');
                buttons[9] = getUnitBtn('seolnyeo');
                buttons[10] = getUnitBtn('dokkaebi');
                buttons[11] = null;
            } else if (bName.includes('군기시') || bName.includes('훈련도감')) {
                // 조선 군기시(훈련도감): 고급 마법 연구 & 장수 보물 무기 구매 (청홍검, 폭마혈도, 용기린갑옷)
                buttons[0] = { id: 'tech_shockwave', action: 'tech_shockwave', name: '기공신포 연구 (목 150)', hotkey: 'Q', atlasPos: '-0px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '이순신 장군의 기공신포 위력을 2배로 강화합니다. [Q]' };
                buttons[1] = { id: 'tech_clones', action: 'tech_clones', name: '분신술 연구 (목 180)', hotkey: 'W', atlasPos: '-170px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '장수가 전투 중 환영 분신을 소환하는 분신술을 해금합니다. [W]' };
                buttons[2] = { id: 'tech_heojun', action: 'tech_heojun', name: '동의보감 편찬 (목 160)', hotkey: 'E', atlasPos: '-136px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '모든 아군 부대가 비전투 시 체력을 자동 회복합니다! [E]' };
                buttons[4] = { id: 'buy_blood_blade', action: 'buy_blood_blade', name: '폭마혈도 구입 (쌀 200)', hotkey: 'A', atlasPos: '-68px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '아군 장수에게 폭마혈도를 장착시켜 공격력 +25 및 폭뢰격 마법을 부여합니다! [A]' };
                buttons[5] = { id: 'buy_kirin_armor', action: 'buy_kirin_armor', name: '용기린갑옷 (목재 200)', hotkey: 'S', atlasPos: '-102px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '아군 장수에게 용기린갑옷을 장착시켜 방어력 +20 및 최대 체력 +500을 부여합니다! [S]' };
            } else {
                // 조선 훈련소/병영 (Barracks): Slot 8 (검술 낭인 [K]), Slot 9 (조총 낭인 [N]), Slot 10 (털가면 [M]). (조선 조총병 0x49 omitted; Slot 11 empty).
                buttons[0] = { id: 'produce_spearman', action: 'produce_spearman', name: '조선 창병 (쌀 50)', hotkey: 'Q', atlasPos: '-102px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '근접 전투에 강한 조선군 주력 창병을 생산 대기열에 추가합니다. [Q]' };
                buttons[1] = { id: 'produce_archer', action: 'produce_archer', name: '조선 궁수 (쌀 60)', hotkey: 'W', atlasPos: '-136px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '원거리 화살 공격을 퍼붓는 조선 궁수를 생산 대기열에 추가합니다. [W]' };
                buttons[2] = { id: 'produce_cavalry', action: 'produce_cavalry', name: '기마궁수 (쌀 80)', hotkey: 'E', atlasPos: '-170px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '기동력과 사거리를 겸비한 조선 기마궁수를 생산합니다. [E]' };
                buttons[3] = { id: 'produce_farmer', action: 'produce_farmer', name: '조선 농부 (쌀 40)', hotkey: 'R', atlasPos: '-68px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '자원(쌀·감자·목재)을 채집하고 건물을 짓는 농부를 생산합니다. [R]' };
                buttons[4] = { id: 'summon_hero', action: 'summon_hero', name: '이순신 장군 (쌀 150)', hotkey: 'A', atlasPos: '-0px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '충무공 이순신 장군을 전장에 소환합니다. [A]' };
                buttons[5] = { id: 'summon_kwak', action: 'summon_kwak', name: '곽재우 장군 (쌀 140)', hotkey: 'S', atlasPos: '-68px -170px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '홍의장군 곽재우를 전장에 소환합니다. [S]' };
                buttons[6] = { id: 'produce_hwacha', action: 'produce_hwacha', name: '조선 화차 (목재 120)', hotkey: 'D', atlasPos: '-238px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '다연장 신기전을 발사하는 조선 화차를 생산합니다. [D]' };
                buttons[7] = { id: 'produce_elephant', action: 'produce_elephant', name: '코끼리병 (감자 120)', hotkey: 'F', atlasPos: '-306px -102px', iconUrl: 'assets/ui/button_plus_atlas.png', tooltip: '막강한 체력의 명나라 코끼리병 지원군을 호출합니다. [F]' };
                buttons[8] = getUnitBtn('geomsul_nangin');
                buttons[9] = getUnitBtn('jochong_nangin');
                buttons[10] = getUnitBtn('teolgamyeon');
                buttons[11] = null;
            }
            this.setButtons(buttons);
        };

        const cmdCardElem = document.getElementById('command-card');
        this.commandCard = new CommandCardHUD(cmdCardElem, (cmd) => this.handleCommandCardAction(cmd));

        this.liveModding = new LiveModdingStudio('#live-mod-panel', {
            gameEngine: this,
            camera: this.camera,
            commandCard: this.commandCard,
            grid: this.grid,
            audioManager: this.soundEngine,
            onExportBinary: (stats) => this.exportBinaryPatch(stats)
        });

        // Collapse Live Modding sidebar by default so the full 1280x720 battlefield is visible like yt_maxres1.jpg
        if (this.dom.liveModPanel) {
            this.dom.liveModPanel.classList.add('collapsed');
        }
        const btnModdingInit = document.getElementById('btn-toggle-modding');
        if (btnModdingInit) {
            btnModdingInit.classList.remove('active');
        }

        this.mapEditor = new MapEditor(this.grid, {
            canvas: this.canvas,
            camera: this.camera,
            entityManager: this.entities,
            onModeChange: (isEditor) => {
                if (this.renderer) {
                    this.renderer.showTileHover = Boolean(isEditor);
                }
                if (this.dom.mapEditorPanel) {
                    if (isEditor) this.dom.mapEditorPanel.classList.remove('hidden');
                    else this.dom.mapEditorPanel.classList.add('hidden');
                }
            }
        });

        // 3. Register Sounds
        this.registerAudioAssets();

        // 4. Load Map & Spawn Initial Entities
        await this.loadInitialMap();
        this.spawnInitialBattalion();
        this.updateResourceHUD();

        // 5. Setup Input Event Listeners
        this.setupInputHandlers();
        this.setupToolbarActions();

        // 6. Center Camera on Chosun Main Base & Rice Paddy (exact composition of yt_maxres1.jpg & yt_maxres3.jpg)
        this.camera.centerOnGrid(21, 19, true);

        // 7. Register Global Bridge for Automation Tests
        this.registerAutomationBridge();

        // 8. Start 60FPS Game Loop
        this.lastTime = performance.now();
        requestAnimationFrame((time) => this.gameLoop(time));
    }

    resizeCanvas() {
        if (!this.canvas) return;
        const rect = this.canvas.parentElement ? this.canvas.parentElement.getBoundingClientRect() : null;
        const w = rect ? Math.max(640, Math.floor(rect.width)) : window.innerWidth;
        const h = rect ? Math.max(480, Math.floor(rect.height)) : window.innerHeight;

        this.canvas.width = w;
        this.canvas.height = h;
        if (this.camera) this.camera.resize(w, h);
    }

    registerAudioAssets() {
        const soundList = [
            ['click', 'assets/audio/click.wav'],
            ['decidebuild', 'assets/audio/decidebuild.wav'],
            ['arrow1', 'assets/audio/arrow1.wav'],
            ['cannon1', 'assets/audio/cannon1.wav'],
            ['gun1', 'assets/audio/gun1.wav'],
            ['bigsword1', 'assets/audio/bigsword1.wav'],
            ['fire1', 'assets/audio/fire1.wav'],
            ['heal', 'assets/audio/heal.wav'],
            ['horsedie1', 'assets/audio/horsedie1.wav'],
            ['select_swordk0', 'assets/audio/select_swordk0.wav'],
            ['move_swordk0', 'assets/audio/move_swordk0.wav'],
            ['attack_swordk0', 'assets/audio/attack_swordk0.wav'],
            ['die_swordk0', 'assets/audio/die_swordk0.wav'],
            ['startgame', 'assets/audio/startgame.wav'],
            ['win', 'assets/audio/win.wav'],
            ['lose', 'assets/audio/lose.wav']
        ];
        for (const [name, url] of soundList) {
            this.soundEngine.registerSound(name, url);
        }
    }

    async loadInitialMap() {
        try {
            const resp = await fetch('assets/maps/taegeuk.json');
            if (resp.ok) {
                const mapData = await resp.json();
                this.grid.loadFromMapData(mapData);
                this.prepareBattlefieldResources();
                this.minimap.setGrid(this.grid);
                return;
            }
        } catch (_) {}

        this.grid.clearToDefault();
        this.prepareBattlefieldResources();
        this.minimap.setGrid(this.grid);
    }

    prepareBattlefieldResources() {
        // 1. Paint seamless stone-grey Imjinrok 2+ battlefield earth across the active play zone (0..70, 0..70)
        for (let gy = 0; gy <= 70; gy++) {
            for (let gx = 0; gx <= 70; gx++) {
                this.grid.setElevation(gx, gy, 0);
                this.grid.setWalkability(gx, gy, 0);
                // Stone-grey ground tile IDs 1..18 (seamless interior stone texture)
                this.grid.setTile(gx, gy, 1 + ((gx * 7 + gy * 13) % 18));
                const idx = gy * this.grid.width + gx;
                this.grid.resourceTypes[idx] = 0;
                this.grid.resourceAmounts[idx] = 0;
            }
        }

        // 2. Place Authentic Jagged Grey Rock Crags (normal_newblk1_atlas.png, tileIds 31..40) at Top-Left & Right Ridge (matches yt_maxres1.jpg!)
        const cragCoords = [
            // Top-left rock ridge (under resource counter in yt_maxres1.jpg)
            [11, 16], [12, 16], [13, 16], [11, 17], [12, 17], [13, 17], [12, 18],
            // Right rock cliff ridge (under '임진록 2+ 조선의 반격' watermark in yt_maxres1.jpg)
            [28, 17], [29, 17], [30, 17],
            [28, 18], [29, 18], [30, 18],
            [27, 19], [28, 19], [29, 19],
            [27, 20], [28, 20], [29, 20],
            [26, 21], [27, 21], [28, 21]
        ];
        cragCoords.forEach(([cx, cy], idx) => {
            this.grid.setTile(cx, cy, 31 + (idx % 10));
        });

        // 3. Place Dense Golden Rice Cluster on the East/Southeast of the 2 Chosun HQs (exact layout of yt_maxres1.jpg!)
        const riceCoords = [
            [23, 13], [24, 13], [25, 13],
            [23, 14], [24, 14], [25, 14], [26, 14],
            [24, 15], [25, 15], [26, 15], [27, 15],
            [24, 16], [25, 16], [26, 16], [27, 16], [28, 16],
            [24, 17], [25, 17], [26, 17], [27, 17],
            [23, 18], [24, 18], [25, 18], [26, 18], [27, 18],
            [22, 19], [23, 19], [24, 19], [25, 19], [26, 19],
            [21, 20], [22, 20], [23, 20], [24, 20], [25, 20], [26, 20],
            [20, 21], [21, 21], [22, 21], [23, 21], [24, 21], [25, 21],
            [19, 22], [20, 22], [21, 22], [22, 22], [23, 22], [24, 22],
            [19, 23], [20, 23], [21, 23], [22, 23], [23, 23]
        ];
        for (const [rx, ry] of riceCoords) {
            this.grid.setResource(rx, ry, 100, 150); // Golden Rice Sheaves (crop1.spr)
        }

        // 4. Place Dense Mixed Forest Clusters (Northeast & Southwest — exact positions of yt_maxres1.jpg!)
        const treeCoords = [
            // Northeast forest cluster (top-right of yt_maxres1.jpg)
            [24, 10], [25, 10], [26, 10], [27, 10], [28, 10],
            [24, 11], [25, 11], [26, 11], [27, 11], [28, 11], [29, 11],
            [25, 12], [26, 12], [27, 12], [28, 12], [29, 12], [30, 12],
            [26, 13], [27, 13], [28, 13], [29, 13], [30, 13],
            // Southwest forest cluster (bottom-left of yt_maxres1.jpg, right above octagonal portrait)
            [14, 21], [15, 21], [16, 21], [17, 21],
            [14, 22], [15, 22], [16, 22], [17, 22], [18, 22],
            [15, 23], [16, 23], [17, 23], [18, 23]
        ];
        for (const [tx, ty] of treeCoords) {
            this.grid.setResource(tx, ty, 3, 250);
        }
    }

    spawnInitialBattalion() {
        // =====================================================================
        // 1. Player 0 (Chosun) Main Base Buildings
        // =====================================================================
        const chosunBuildings = [
            { korean_name: '조선 본영', sprite_name: 'char/hqk_plus.spr', width: 3, height: 3, hp: 6000, defense: 30, gx: 18, gy: 17 },
            { korean_name: '조선 본영', sprite_name: 'char/hqk_plus.spr', width: 3, height: 3, hp: 6000, defense: 30, gx: 21, gy: 14 },
            { korean_name: '조선 훈련소', sprite_name: 'char/barrackk.spr', width: 2, height: 2, hp: 3600, defense: 33, gx: 15, gy: 19, isPrimaryBarracks: true },
            { korean_name: '조선 방앗간', sprite_name: 'char/millk_plus.spr', width: 2, height: 2, hp: 3200, defense: 20, gx: 12, gy: 5 },
            { korean_name: '조선 마구간', sprite_name: 'char/stablek.spr', width: 3, height: 2, hp: 3800, defense: 25, gx: 15, gy: 4 },
            { korean_name: '조선 군기시', sprite_name: 'char/storagek.spr', width: 3, height: 2, hp: 4200, defense: 26, gx: 18, gy: 3 }
        ];

        let primaryBarracks = null;
        for (const bDef of chosunBuildings) {
            const b = new Building(this.nextEntityId++, bDef, bDef.gx, bDef.gy, 0);
            b.isBuilding = true;
            b.rallyPoint = { gx: bDef.gx, gy: bDef.gy + 2 };
            b.move_speed = 12; // Proxy speed for headless modding test compatibility
            b.productionQueue = [];
            b.prodProgress = 0;
            if (bDef.isPrimaryBarracks) {
                b.isActiveProducer = true;
                b.rallyPoint = { gx: 15, gy: 21 };
                b.prodProgress = 0.43;
                b.productionQueue = [
                    { archetype: BUILTIN_UNIT_TEMPLATES[1], cost: { rice: 50 }, isWorker: false }
                ];
                primaryBarracks = b;
            }
            this.markBuildingFootprint(b);
            this.entities.push(b);
        }
        this.primaryBarracks = primaryBarracks;

        // 2. Chosun Farmers Harvesting the East Rice Field + Southern Frontline Battalion
        const chosunUnits = [
            { archetype: BUILTIN_UNIT_TEMPLATES[0], gx: 24, gy: 14, isWorker: true, harvestPref: 100 },
            { archetype: BUILTIN_UNIT_TEMPLATES[0], gx: 25, gy: 15, isWorker: true, harvestPref: 100 },
            { archetype: BUILTIN_UNIT_TEMPLATES[0], gx: 25, gy: 16, isWorker: true, harvestPref: 100 },
            { archetype: BUILTIN_UNIT_TEMPLATES[0], gx: 24, gy: 18, isWorker: true, harvestPref: 100 },
            { archetype: BUILTIN_UNIT_TEMPLATES[0], gx: 13, gy: 18, isWorker: true, harvestPref: 100 },
            // Southern Frontline Battalion & Heroes
            { archetype: BUILTIN_UNIT_TEMPLATES[1], gx: 23, gy: 25 },
            { archetype: BUILTIN_UNIT_TEMPLATES[1], gx: 24, gy: 25 },
            { archetype: BUILTIN_UNIT_TEMPLATES[1], gx: 25, gy: 26 },
            { archetype: BUILTIN_UNIT_TEMPLATES[1], gx: 24, gy: 26 },
            { archetype: BUILTIN_UNIT_TEMPLATES[3], gx: 22, gy: 25 },
            { archetype: BUILTIN_UNIT_TEMPLATES[3], gx: 23, gy: 26 },
            { archetype: BUILTIN_UNIT_TEMPLATES[2], gx: 22, gy: 24 },
            { archetype: BUILTIN_UNIT_TEMPLATES[2], gx: 23, gy: 24 },
            { archetype: BUILTIN_UNIT_TEMPLATES[5], gx: 21, gy: 25 },
            { archetype: BUILTIN_UNIT_TEMPLATES[7], gx: 24, gy: 24, isHero: true }, // 충무공 이순신
            { archetype: BUILTIN_UNIT_TEMPLATES[8], gx: 25, gy: 25, isHero: true }  // 홍의장군 곽재우
        ];

        for (const item of chosunUnits) {
            const unit = new Unit(this.nextEntityId++, item.archetype, item.gx, item.gy, 0);
            unit.isBuilding = false;
            unit.level = item.archetype.level || (item.isHero ? 3 : 1);
            unit.exp = this.expTable[Math.min(unit.level - 1, this.expTable.length - 1)] || 0;
            unit.isHero = Boolean(item.isHero || (unit.name && (unit.name.includes('이순신') || unit.name.includes('곽재우') || unit.name.includes('사명') || unit.name.includes('허준'))));
            unit.inventory = unit.isHero
                ? [
                    { id: 'sword', name: '청홍검 (공격+12)', icon: '⚔️', type: 'equip' },
                    { id: 'armor', name: '두정갑 (방어+8)', icon: '🛡️', type: 'equip' },
                    { id: 'ginseng', name: '고려 인삼 (+300 HP)', icon: '🌿', type: 'consumable', action: 'use_ginseng' },
                    { id: 'rain_scroll', name: '기우제 주문 (비)', icon: '🌧️', type: 'consumable', action: 'cast_rain' }
                ]
                : [
                    { id: 'ginseng', name: '주먹밥 (+150 HP)', icon: '🍙', type: 'consumable', action: 'use_ginseng' },
                    null, null, null
                ];
            if (item.isWorker) {
                unit.isWorker = true;
                unit.autoHarvest = true;
                unit.harvestPref = item.harvestPref || 100;
                unit.harvestTimer = Math.random() * 1.5;
                unit.carryingAmount = 0;
                unit.carryingType = 0;
            }
            this.entities.push(unit);
        }

        // Select Primary Chosun Barracks by default
        if (primaryBarracks) {
            this.selectSingleUnit(primaryBarracks);
        }

        // =====================================================================
        // 3. Player 1 (Japan) Outpost & Skirmish Vanguard in the Southeast
        // =====================================================================
        const hqJapan = new Building(this.nextEntityId++, {
            korean_name: '일본 본영',
            sprite_name: 'char/jhq.spr',
            width: 3, height: 3, hp: 6000, defense: 30
        }, 32, 28, 1);
        hqJapan.isBuilding = true;
        this.entities.push(hqJapan);

        const barracksJapan = new Building(this.nextEntityId++, {
            korean_name: '일본 훈련소',
            sprite_name: 'char/barrackj.spr',
            width: 2, height: 2, hp: 3600, defense: 24
        }, 36, 28, 1);
        barracksJapan.isBuilding = true;
        this.entities.push(barracksJapan);

        const japanUnits = [
            { archetype: BUILTIN_UNIT_TEMPLATES[13], gx: 26, gy: 25 },
            { archetype: BUILTIN_UNIT_TEMPLATES[13], gx: 27, gy: 26 },
            { archetype: BUILTIN_UNIT_TEMPLATES[14], gx: 28, gy: 25 },
            { archetype: BUILTIN_UNIT_TEMPLATES[14], gx: 31, gy: 27 },
            { archetype: BUILTIN_UNIT_TEMPLATES[15], gx: 32, gy: 26 },
            { archetype: BUILTIN_UNIT_TEMPLATES[17], gx: 27, gy: 25 }
        ];

        for (const item of japanUnits) {
            const unit = new Unit(this.nextEntityId++, item.archetype, item.gx, item.gy, 1);
            unit.isBuilding = false;
            unit.level = item.archetype.level || 1;
            unit.exp = 0;
            this.entities.push(unit);
        }

        // 4. Player 2 (Ming) Allied Detachment in the South
        const mingUnits = [
            { archetype: BUILTIN_UNIT_TEMPLATES[20], gx: 19, gy: 33 },
            { archetype: BUILTIN_UNIT_TEMPLATES[22], gx: 21, gy: 33 }
        ];
        for (const item of mingUnits) {
            const unit = new Unit(this.nextEntityId++, item.archetype, item.gx, item.gy, 2);
            unit.isBuilding = false;
            unit.level = 2;
            unit.exp = 100;
            this.entities.push(unit);
        }

        this.refreshFKeyBar();
    }

    updateResourceHUD() {
        const alivePlayerUnits = this.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === 0).length;
        const aliveMills = this.entities.filter(e => e && !e.isDead && e.isBuilding && e.owner === 0 && !e.isConstructing && e.name && e.name.includes('방앗간')).length;
        this.resources.supplyUsed = Math.max(98, alivePlayerUnits * 6);
        this.resources.supplyMax = 2000 + aliveMills * 500;

        if (this.dom.resRice) this.dom.resRice.textContent = Math.floor(this.resources.rice);
        if (this.dom.resPotato) this.dom.resPotato.textContent = Math.floor(this.resources.potato);
        if (this.dom.resWood) this.dom.resWood.textContent = Math.floor(this.resources.wood);
        if (this.dom.resSupply) this.dom.resSupply.textContent = `${this.resources.supplyUsed}/${this.resources.supplyMax}`;
    }

    addFloatingText(wx, wy, text, color = '#ffd700') {
        this.floatingTexts.push({
            wx,
            wy,
            text,
            color,
            time: 0,
            duration: 1.4
        });
    }

    /* ----------------------------------------------------------------------
       Input & Event Handlers
       ---------------------------------------------------------------------- */
    setupInputHandlers() {
        if (!this.canvas) return;

        // Context Menu Prevention on Canvas
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        // Mouse Down (Left/Right)
        this.canvas.addEventListener('mousedown', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            if (e.button === 0) {
                this.isMouseDown = true;
                this.mouseDownPos = { x: mx, y: my };
                this.isDragSelecting = false;
            } else if (e.button === 2) {
                e.preventDefault();
                // Right-click cancels pending RTS target command, building placement ghost, or Farmer sub-menu first
                if (this.pendingCommand) {
                    this.clearPendingCommand();
                    this.announceSystemMessage('명령 조준이 취소되었습니다.', '#cccccc');
                    return;
                }
                if (this.placingBuilding) {
                    this.placingBuilding = null;
                    this.announceSystemMessage('건물 건설 배치가 취소되었습니다.', '#cccccc');
                    return;
                }
                if (this.farmerMenuTier !== 0) {
                    this.farmerMenuTier = 0;
                    if (this.commandCard && this.commandCard.setFarmerCommands) {
                        this.commandCard.setFarmerCommands(0);
                    }
                    return;
                }
                const picked = IsometricMath.screenToGrid(mx, my, this.camera, this.grid.elevation, this.grid.width, this.grid.height);
                this.issueOrder(picked.gx, picked.gy, true, mx, my);
            }
        });

        // Mouse Move
        window.addEventListener('mousemove', (e) => {
            if (!this.canvas) return;
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            this.mousePos = { x: mx, y: my };

            if (this.renderer && mx >= 0 && mx <= this.canvas.width && my >= 0 && my <= this.canvas.height) {
                const picked = IsometricMath.screenToGrid(mx, my, this.camera, this.grid.elevation, this.grid.width, this.grid.height);
                this.renderer.setHoverTile(picked.gx, picked.gy, picked.valid);
                const coordsEl = document.getElementById('minimap-coords');
                if (coordsEl && picked.valid) {
                    coordsEl.textContent = `좌표: ${picked.gx}, ${picked.gy}`;
                }
            }

            if (this.isMouseDown && !this.placingBuilding && !this.pendingCommand) {
                const dist = Math.hypot(mx - this.mouseDownPos.x, my - this.mouseDownPos.y);
                if (dist > 6) {
                    this.isDragSelecting = true;
                    if (this.renderer) {
                        this.renderer.setSelectionBox(this.mouseDownPos.x, this.mouseDownPos.y, mx, my);
                    }
                }
            }
        });

        // Mouse Up
        window.addEventListener('mouseup', (e) => {
            if (e.button === 0 && this.isMouseDown) {
                this.isMouseDown = false;
                const rect = this.canvas.getBoundingClientRect();
                const mx = e.clientX - rect.left;
                const my = e.clientY - rect.top;

                if (this.isDragSelecting) {
                    this.finishDragSelection(this.mouseDownPos.x, this.mouseDownPos.y, mx, my, e.shiftKey);
                    if (this.renderer) this.renderer.clearSelectionBox();
                    this.isDragSelecting = false;
                } else if (mx >= 0 && mx <= this.canvas.width && my >= 0 && my <= this.canvas.height) {
                    this.handleClickSelection(mx, my, e.shiftKey);
                }
            }
        });

        // Double-Click Selection (Canvas): Select all visible units of matching archetype/sprite on screen
        this.canvas.addEventListener('dblclick', (e) => {
            if (e.button !== 0 || this.pendingCommand || this.placingBuilding) return;

            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            let clickedUnit = null;
            let bestDist = 42;
            for (let i = this.entities.length - 1; i >= 0; i--) {
                const ent = this.entities[i];
                if (!ent || ent.isDead) continue;
                const elev = this.grid.getElevation(Math.floor(ent.wx), Math.floor(ent.wy)) || 0;
                const sp = IsometricMath.worldToScreen(ent.wx, ent.wy, elev, this.camera);
                const hitYOffset = ent.isBuilding ? 8 : 16;
                const dist = Math.hypot(mx - sp.x, my - (sp.y + hitYOffset));
                if (dist < (ent.isBuilding ? 56 : 26) * (ent.scale || 1.0) && dist < bestDist) {
                    bestDist = dist;
                    clickedUnit = ent;
                }
            }

            if (!clickedUnit || clickedUnit.isBuilding || clickedUnit.owner !== 0) return;

            const targetName = clickedUnit.name;
            const targetSprite = clickedUnit.spriteName;
            const sameTypeUnits = [];

            for (const ent of this.entities) {
                if (!ent || ent.isDead || ent.isBuilding || ent.owner !== 0) continue;
                if (ent.name !== targetName && ent.spriteName !== targetSprite) continue;

                const elev = this.grid.getElevation(Math.floor(ent.wx), Math.floor(ent.wy)) || 0;
                const sp = IsometricMath.worldToScreen(ent.wx, ent.wy, elev, this.camera);
                if (sp.x >= -32 && sp.x <= this.canvas.width + 32 && sp.y >= -32 && sp.y <= this.canvas.height + 32) {
                    sameTypeUnits.push(ent);
                    if (sameTypeUnits.length >= 24) break;
                }
            }

            if (sameTypeUnits.length > 0) {
                if (!e.shiftKey) this.clearSelection();
                for (const u of sameTypeUnits) {
                    u.selected = true;
                    if (!this.selectedUnits.includes(u)) {
                        this.selectedUnits.push(u);
                    }
                }
                const first = this.selectedUnits[0];
                this.updateSelectionHUD(first);
                if (this.commandCard) {
                    if (first.isWorker && this.commandCard.setFarmerCommands) {
                        this.farmerMenuTier = 0;
                        this.commandCard.setFarmerCommands(0);
                    } else if (this.commandCard.setDefaultUnitCommands) {
                        this.commandCard.setDefaultUnitCommands();
                    }
                }
                if (this.liveModding) this.liveModding.setSelectedUnit(first);
                this.soundEngine.play('select_swordk0', first.wx, first.wy, this.camera);
                this.announceSystemMessage(`선택: [${targetName}] 전장 동종 부대 ${sameTypeUnits.length}기 일괄 선택`, '#55ff77');
            }
        });

        // Mouse Wheel Zoom
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            if (e.deltaY < 0) this.camera.zoomBy(0.1);
            else this.camera.zoomBy(-0.1);
        }, { passive: false });

        // Keyboard Navigation (WASD / Arrows / Hotkeys / Control Groups 1..9 / F1..F12)
        window.addEventListener('keydown', (e) => {
            if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) {
                return;
            }
            this.keysDown[e.code] = true;

            if (e.key === 'Alt' || e.code === 'AltLeft' || e.code === 'AltRight') {
                if (this.renderer) this.renderer.showAllHealthBars = true;
            }

            if (e.code === 'Escape') {
                if (this.pendingCommand) {
                    this.clearPendingCommand();
                    this.announceSystemMessage('명령 조준이 취소되었습니다.', '#cccccc');
                } else if (this.placingBuilding) {
                    this.placingBuilding = null;
                    this.announceSystemMessage('건물 건설 배치가 취소되었습니다.', '#cccccc');
                } else if (this.farmerMenuTier !== 0) {
                    this.farmerMenuTier = 0;
                    if (this.commandCard && this.commandCard.setFarmerCommands) {
                        this.commandCard.setFarmerCommands(0);
                    }
                }
            } else if (/^(Digit|Numpad)[1-9]$/.test(e.code)) {
                e.preventDefault();
                const grpNum = e.code.replace(/^(Digit|Numpad)/, '');
                if (e.ctrlKey || e.metaKey) {
                    const valid = this.selectedUnits.filter(u => u && !u.isDead);
                    if (valid.length > 0) {
                        this.controlGroups.set(grpNum, [...valid]);
                        this.announceSystemMessage(`🚩 부대 지정 [Ctrl+${grpNum}]: ${valid.length}기 편성 완료 (${grpNum}번 키로 호출)`, '#55ff77');
                    }
                } else if (e.shiftKey) {
                    const existing = (this.controlGroups.get(grpNum) || []).filter(u => u && !u.isDead);
                    const current = this.selectedUnits.filter(u => u && !u.isDead);
                    const union = [...existing];
                    for (const u of current) {
                        if (!union.includes(u) && union.length < 24) {
                            union.push(u);
                        }
                    }
                    if (union.length > 0) {
                        this.controlGroups.set(grpNum, union);
                        this.announceSystemMessage(`🚩 부대 추가 [Shift+${grpNum}]: ${union.length}기 편성 완료 (${grpNum}번 키로 호출)`, '#55ff77');
                    }
                } else {
                    const saved = (this.controlGroups.get(grpNum) || []).filter(u => u && !u.isDead);
                    if (saved.length > 0) {
                        this.clearSelection();
                        for (const u of saved) {
                            u.selected = true;
                            this.selectedUnits.push(u);
                        }
                        const leader = saved[0];
                        this.updateSelectionHUD(leader);
                        if (this.commandCard) {
                            if (leader.isBuilding && this.commandCard.setBuildingProductionCommands) {
                                this.commandCard.setBuildingProductionCommands(leader);
                            } else if (leader.isWorker && this.commandCard.setFarmerCommands) {
                                this.commandCard.setFarmerCommands(0);
                            } else if (this.commandCard.setDefaultUnitCommands) {
                                this.commandCard.setDefaultUnitCommands();
                            }
                        }
                        const now = performance.now();
                        if (this.lastGroupKey === grpNum && (now - this.lastGroupTapTime) < 350) {
                            const centroidX = saved.reduce((sum, u) => sum + (u.wx !== undefined ? u.wx : u.gx), 0) / saved.length;
                            const centroidY = saved.reduce((sum, u) => sum + (u.wy !== undefined ? u.wy : u.gy), 0) / saved.length;
                            this.camera.centerOnGrid(centroidX, centroidY, false);
                        }
                        this.lastGroupKey = grpNum;
                        this.lastGroupTapTime = now;
                    }
                }
            } else if (e.code === 'KeyM') {
                this.toggleSound();
            } else if (e.code === 'KeyE' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.toggleMapEditor();
            } else if (e.code === 'KeyH') {
                e.preventDefault();
                this.toggleHelpModal();
            } else if (e.code === 'F12') {
                e.preventDefault();
                this.showF12Clock = !this.showF12Clock;
            } else if (/^F([1-9]|10|11)$/.test(e.code)) {
                e.preventDefault();
                const slotIdx = parseInt(e.code.replace('F', ''), 10) - 1;
                const targetUnit = this.fKeyUnits[slotIdx];
                if (targetUnit && !targetUnit.isDead) {
                    this.selectSingleUnit(targetUnit);
                    const now = performance.now();
                    if (this.lastFKeySlot === slotIdx && (now - this.lastFKeyTapTime) < 350) {
                        this.camera.centerOnGrid(targetUnit.wx, targetUnit.wy, false);
                    }
                    this.lastFKeySlot = slotIdx;
                    this.lastFKeyTapTime = now;
                }
            }
        });

        window.addEventListener('keyup', (e) => {
            this.keysDown[e.code] = false;
            if (e.key === 'Alt' || e.code === 'AltLeft' || e.code === 'AltRight') {
                if (this.renderer) this.renderer.showAllHealthBars = false;
            }
        });
    }

    setupToolbarActions() {
        const btnEditor = document.getElementById('btn-toggle-editor');
        if (btnEditor) btnEditor.addEventListener('click', () => this.toggleMapEditor());

        const btnAudio = document.getElementById('btn-toggle-audio');
        if (btnAudio) btnAudio.addEventListener('click', () => this.toggleSound());

        const btnModding = document.getElementById('btn-toggle-modding');
        if (btnModding) {
            btnModding.addEventListener('click', () => {
                if (this.dom.liveModPanel) {
                    this.dom.liveModPanel.classList.toggle('collapsed');
                    btnModding.classList.toggle('active');
                }
            });
        }

        const btnCloseMod = document.getElementById('btn-close-mod-panel');
        if (btnCloseMod) {
            btnCloseMod.addEventListener('click', () => {
                if (this.dom.liveModPanel) this.dom.liveModPanel.classList.add('collapsed');
                if (btnModding) btnModding.classList.remove('active');
            });
        }

        const btnHelp = document.getElementById('btn-help');
        if (btnHelp) btnHelp.addEventListener('click', () => this.toggleHelpModal(true));

        const hudSettingsBtn = document.getElementById('hud-settings-btn');
        if (hudSettingsBtn) hudSettingsBtn.addEventListener('click', () => this.toggleHelpModal());

        const portraitBox = document.getElementById('selection-portrait');
        if (portraitBox) {
            portraitBox.addEventListener('click', () => {
                const u = this.selectedUnits[0];
                if (u) this.camera.centerOnGrid(u.wx, u.wy, false);
            });
        }

        // Interactive Wind & Weather Compass Dial (Clock at 197, 521 in screenPt_plus.dat)
        if (this.dom.compassDial) {
            this.dom.compassDial.addEventListener('click', (e) => {
                if (e.shiftKey) {
                    this.triggerRainStorm();
                } else {
                    const dirNames = ['북풍 ↑', '북동풍 ↗', '동풍 →', '남동풍 ↘', '남풍 ↓', '남서풍 ↙', '서풍 ←', '북서풍 ↖'];
                    this.windDirection = (this.windDirection + 1) % 8;
                    this.announceSystemMessage(`풍향이 [${dirNames[this.windDirection]}]으로 바뀌었습니다. (화공 불길 이동 방향 변경)`, '#80d8ff');
                }
            });
            this.dom.compassDial.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.triggerRainStorm();
            });
        }

        const btnCloseHelp = document.getElementById('btn-close-help');
        if (btnCloseHelp) btnCloseHelp.addEventListener('click', () => this.toggleHelpModal(false));

        const btnConfirmHelp = document.getElementById('btn-modal-confirm');
        if (btnConfirmHelp) btnConfirmHelp.addEventListener('click', () => this.toggleHelpModal(false));

        // Speed Slider Direct Reactive Listener
        const speedSlider = document.getElementById('input-move-speed');
        if (speedSlider) {
            speedSlider.addEventListener('input', (e) => {
                const spd = parseFloat(e.target.value);
                const valLabel = document.getElementById('val-speed');
                if (valLabel) valLabel.textContent = spd;

                for (const u of this.selectedUnits) {
                    u.move_speed = spd;
                }
            });
        }
    }

    triggerRainStorm() {
        if (this.weather === 'rain') {
            this.weather = 'sunny';
            this.rainTimer = 0;
            this.announceSystemMessage('☀️ 비가 그치고 날씨가 맑아졌습니다.', '#ffd700');
        } else {
            this.weather = 'rain';
            this.rainTimer = 25.0;
            this.announceSystemMessage('🌧️ 기우제 주문 발동! 비가 내려 전장의 화공 불길이 꺼지고 논밭의 벼가 급속 재생됩니다!', '#66ccff');
            this.soundEngine.play('heal', 22, 20, this.camera);
        }
    }

    refreshFKeyBar() {
        if (!this.dom.fKeyBar) return;
        const slots = this.dom.fKeyBar.querySelectorAll('.f-slot');
        // Prioritize Player 0 Heroes first, then key combat units, then workers
        const playerUnits = this.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === 0);
        playerUnits.sort((a, b) => {
            if (Boolean(a.isHero) !== Boolean(b.isHero)) return a.isHero ? -1 : 1;
            if (Boolean(a.isWorker) !== Boolean(b.isWorker)) return a.isWorker ? 1 : -1;
            return (b.level || 1) - (a.level || 1);
        });

        this.fKeyUnits = playerUnits.slice(0, 11);
        slots.forEach((slotEl, idx) => {
            const u = this.fKeyUnits[idx];
            slotEl.onclick = null;
            slotEl.ondblclick = null;
            if (!u) {
                slotEl.classList.remove('active-hero');
                slotEl.innerHTML = `<span>F${idx + 1}</span>`;
                slotEl.title = `F${idx + 1} 빈 슬롯`;
                return;
            }
            const shortName = (u.name || '').replace('조선 ', '').replace('충무공 ', '').slice(0, 3);
            const hpPct = Math.max(0, Math.min(100, Math.round((u.hp / Math.max(1, u.max_hp)) * 100)));
            const isSelected = Boolean(u.selected);
            slotEl.classList.toggle('active-hero', isSelected);
            slotEl.title = `[F${idx + 1}] ${u.name} (Lv.${u.level || 1}) — 체력 ${Math.round(u.hp)}/${Math.round(u.max_hp)}`;
            slotEl.innerHTML = `<span>F${idx + 1} ${shortName}</span><div class="f-hp-mini" style="width:${hpPct}%;background:${hpPct > 50 ? '#32e632' : '#ff5555'}"></div>`;
            slotEl.onclick = () => {
                this.selectSingleUnit(u);
            };
            slotEl.ondblclick = () => {
                this.selectSingleUnit(u);
                this.camera.centerOnGrid(u.wx, u.wy, false);
            };
        });
    }

    toggleSound() {
        this.soundEngine.init();
        const nextMute = !this.soundEngine.isMuted;
        this.soundEngine.setMuted(nextMute);
        const btn = document.getElementById('btn-toggle-audio');
        if (btn) {
            btn.innerHTML = nextMute ? '<span class="btn-icon">🔇</span> 음소거' : '<span class="btn-icon">🔊</span> 사운드';
        }
    }

    toggleMapEditor() {
        if (this.mapEditor) {
            this.mapEditor.toggle();
            const btn = document.getElementById('btn-toggle-editor');
            if (btn) btn.classList.toggle('active', this.mapEditor.isEnabled);
        }
    }

    toggleHelpModal(open) {
        if (!this.dom.helpModal) return;
        if (open !== undefined) {
            if (open) this.dom.helpModal.classList.remove('hidden');
            else this.dom.helpModal.classList.add('hidden');
        } else {
            this.dom.helpModal.classList.toggle('hidden');
        }
    }

    /* ----------------------------------------------------------------------
       Selection, Building Placement Ghost & Resource Tile Inspection
       ---------------------------------------------------------------------- */
    handleClickSelection(screenX, screenY, isMultiSelect = false) {
        // 1. If Farmer Building Placement Mode is active, place scaffolding foundation at clicked grid!
        if (this.placingBuilding) {
            const picked = IsometricMath.screenToGrid(screenX, screenY, this.camera, this.grid.elevation, this.grid.width, this.grid.height);
            const bPlan = this.placingBuilding;
            const needWood = bPlan.costWood || 0;
            const needRice = bPlan.costRice || 0;

            if (this.resources.wood < needWood || this.resources.rice < needRice) {
                this.announceSystemMessage(`자원이 부족합니다! (쌀 ${needRice}, 목재 ${needWood} 필요)`, '#ff5555');
                return;
            }

            this.resources.wood -= needWood;
            this.resources.rice -= needRice;

            const bx = Math.max(4, Math.min(this.grid.width - 5, picked.gx));
            const by = Math.max(4, Math.min(this.grid.height - 5, picked.gy));
            const newBld = new Building(this.nextEntityId++, bPlan, bx, by, 0);
            newBld.isBuilding = true;
            newBld.isConstructing = true;
            newBld.constructionProgress = 0.08;
            newBld.hp = Math.max(100, Math.round(newBld.max_hp * 0.15));
            newBld.rallyPoint = { gx: bx, gy: by + 3 };
            newBld.productionQueue = [];
            newBld.prodProgress = 0;
            this.markBuildingFootprint(newBld);
            this.entities.push(newBld);

            // Send selected Farmer(s) or nearest Farmer to hammer & construct the building!
            let builders = this.selectedUnits.filter(u => !u.isBuilding && u.isWorker && u.owner === 0);
            if (builders.length === 0) {
                const anyWorker = this.entities.find(u => u && !u.isDead && !u.isBuilding && u.isWorker && u.owner === 0);
                if (anyWorker) builders = [anyWorker];
            }
            for (const w of builders) {
                w.autoHarvest = false;
                w.constructingTarget = newBld;
                w.moveTo(bx + 1, by + 1, this.grid);
            }

            this.placingBuilding = null;
            this.farmerMenuTier = 0;
            if (this.commandCard && this.commandCard.setFarmerCommands) {
                this.commandCard.setFarmerCommands(0);
            }
            this.soundEngine.play('decidebuild', bx, by, this.camera);
            this.announceSystemMessage(`🔨 [${bPlan.korean_name}] 기초 공사를 시작합니다! 농부가 건설을 진행합니다.`, '#ffd700');
            this.updateResourceHUD();
            return;
        }

        let pickedEntity = null;
        let bestDist = 42;

        // Hit-test entities from front to back
        for (let i = this.entities.length - 1; i >= 0; i--) {
            const ent = this.entities[i];
            if (!ent || ent.isDead) continue;

            const elev = this.grid.getElevation(Math.floor(ent.wx), Math.floor(ent.wy)) || 0;
            const sp = IsometricMath.worldToScreen(ent.wx, ent.wy, elev, this.camera);
            const hitYOffset = ent.isBuilding ? 8 : 16;
            const dist = Math.hypot(screenX - sp.x, screenY - (sp.y + hitYOffset));

            if (dist < (ent.isBuilding ? 56 : 26) * (ent.scale || 1.0) && dist < bestDist) {
                bestDist = dist;
                pickedEntity = ent;
            }
        }

        // 2. If RTS Target Cursor Mode (pendingCommand) is active, execute the targeted command at the clicked coordinate/unit!
        if (this.pendingCommand) {
            const cmdObj = this.pendingCommand;
            const picked = IsometricMath.screenToGrid(screenX, screenY, this.camera, this.grid.elevation, this.grid.width, this.grid.height);
            const tx = Math.max(1, Math.min(this.grid.width - 2, picked.gx));
            const ty = Math.max(1, Math.min(this.grid.height - 2, picked.gy));
            this.clearPendingCommand();
            this.executeTargetedCommand(cmdObj.action, tx, ty, pickedEntity);
            return;
        }

        if (pickedEntity) {
            this.inspectedResource = null;
            if (isMultiSelect) {
                pickedEntity.selected = !pickedEntity.selected;
                this.updateSelectedUnitsList();
            } else {
                this.selectSingleUnit(pickedEntity);
            }
            if (!pickedEntity.isBuilding && pickedEntity.owner === 0) {
                this.soundEngine.play('select_swordk0', pickedEntity.wx, pickedEntity.wy, this.camera);
            } else if (pickedEntity.isBuilding) {
                this.soundEngine.play('click', pickedEntity.wx, pickedEntity.wy, this.camera);
            }
        } else {
            // Check if the user clicked on a Resource Tile (쌀/벼, 토란/감자, 목재) like yt_maxres3.jpg!
            const picked = IsometricMath.screenToGrid(screenX, screenY, this.camera, this.grid.elevation, this.grid.width, this.grid.height);
            if (picked.valid) {
                const idx = picked.gy * this.grid.width + picked.gx;
                const rType = this.grid.resourceTypes[idx];
                const rAmt = this.grid.resourceAmounts[idx];
                if (rType > 0 && rAmt > 0) {
                    const rName = (rType === 100) ? '쌀 (황금 벼 논밭)' : ((rType === 1) ? '토란 · 감자밭' : '목재 (울창한 숲)');
                    const rMax = (rType === 100) ? 150 : 250;
                    this.inspectedResource = { gx: picked.gx, gy: picked.gy, rType, name: rName, amount: rAmt, maxAmount: rMax };
                    this.clearSelection();
                    this.renderInspectedResourceHUD();
                    return;
                }
            }
            if (!isMultiSelect) {
                this.inspectedResource = null;
                this.clearSelection();
            }
        }
    }

    renderInspectedResourceHUD() {
        const res = this.inspectedResource;
        if (!res) return;
        if (this.dom.selectionName) this.dom.selectionName.textContent = res.name;
        if (this.dom.selectionFaction) {
            this.dom.selectionFaction.textContent = `자연 자원 (${res.gx}, ${res.gy})`;
            this.dom.selectionFaction.style.color = '#2b5818';
        }
        if (this.dom.selectionHpText) this.dom.selectionHpText.textContent = `${res.amount}/${res.maxAmount}`;
        if (this.dom.selectionMpText && this.dom.selectionMpText.closest('.parchment-stat-line')) {
            this.dom.selectionMpText.closest('.parchment-stat-line').style.display = 'none';
        }
        if (this.dom.statAttack && this.dom.statAttack.closest('.parchment-stat-line')) {
            this.dom.statAttack.closest('.parchment-stat-line').style.display = 'none';
        }
        if (this.dom.statDefense) this.dom.statDefense.textContent = (this.weather === 'rain') ? '기우제 재생 3배' : '자연 재생 중';
        if (this.dom.hudProdLabel) this.dom.hudProdLabel.textContent = (res.rType === 100) ? '농부 우클릭: 쌀 수확' : '농부 우클릭: 벌목';
    }

    finishDragSelection(x1, y1, x2, y2, isShift = false) {
        const minX = Math.min(x1, x2);
        const maxX = Math.max(x1, x2);
        const minY = Math.min(y1, y2);
        const maxY = Math.max(y1, y2);

        this.inspectedResource = null;
        if (!isShift) {
            this.clearSelection();
        }

        const boxed = [];
        for (const ent of this.entities) {
            if (!ent || ent.isDead || ent.isBuilding || ent.owner !== 0) continue;

            const elev = this.grid.getElevation(Math.floor(ent.wx), Math.floor(ent.wy)) || 0;
            const sp = IsometricMath.worldToScreen(ent.wx, ent.wy, elev, this.camera);

            if (sp.x >= minX && sp.x <= maxX && sp.y + 16 >= minY && sp.y + 16 <= maxY) {
                boxed.push(ent);
            }
        }

        // RTS selection priority: prioritize military units over workers
        const military = boxed.filter(u => !u.isWorker);
        const candidates = (military.length > 0) ? military : boxed;

        for (const ent of candidates) {
            if (!this.selectedUnits.includes(ent)) {
                if (this.selectedUnits.length >= 24) break;
                ent.selected = true;
                this.selectedUnits.push(ent);
            }
        }

        if (this.selectedUnits.length > 0) {
            const first = this.selectedUnits[0];
            this.updateSelectionHUD(first);
            if (this.commandCard) {
                if (first.isWorker && this.commandCard.setFarmerCommands) {
                    this.farmerMenuTier = 0;
                    this.commandCard.setFarmerCommands(0);
                } else if (this.commandCard.setDefaultUnitCommands) {
                    this.commandCard.setDefaultUnitCommands();
                }
            }
            if (this.liveModding) this.liveModding.setSelectedUnit(first);
            this.soundEngine.play('select_swordk0', first.wx, first.wy, this.camera);
        }
    }

    selectSingleUnit(unit) {
        this.inspectedResource = null;
        this.clearSelection();
        unit.selected = true;
        this.selectedUnits = [unit];
        this.farmerMenuTier = 0;
        this.updateSelectionHUD(unit);

        if (this.commandCard) {
            if (unit.isBuilding && this.commandCard.setBuildingProductionCommands) {
                this.commandCard.setBuildingProductionCommands(unit);
            } else if (unit.isWorker && this.commandCard.setFarmerCommands) {
                this.commandCard.setFarmerCommands(0);
            } else if (this.commandCard.setDefaultUnitCommands) {
                this.commandCard.setDefaultUnitCommands();
            }
        }

        if (this.liveModding) this.liveModding.setSelectedUnit(unit);

        const slider = document.getElementById('input-move-speed');
        if (slider && unit.move_speed !== undefined) {
            slider.value = unit.move_speed;
            const valLabel = document.getElementById('val-speed');
            if (valLabel) valLabel.textContent = unit.move_speed;
        }
        this.refreshFKeyBar();
    }

    clearSelection() {
        for (const ent of this.entities) {
            ent.selected = false;
        }
        this.selectedUnits = [];
        this.resetSelectionHUD();
        if (this.liveModding) this.liveModding.setSelectedUnit(null);
    }

    updateSelectedUnitsList() {
        this.selectedUnits = this.entities.filter(e => e.selected && !e.isDead);
        if (this.selectedUnits.length > 0) {
            this.updateSelectionHUD(this.selectedUnits[0]);
            if (this.liveModding) this.liveModding.setSelectedUnit(this.selectedUnits[0]);
        } else {
            this.resetSelectionHUD();
            if (this.liveModding) this.liveModding.setSelectedUnit(null);
        }
    }

    getPortraitGridCoords(unit) {
        const name = (unit && unit.name) ? unit.name : '';
        if (name.includes('본영')) return [8, 4];
        if (name.includes('훈련소')) return [9, 4];
        if (name.includes('마구간')) return [10, 4];
        if (name.includes('군기시') || name.includes('방앗간')) return [11, 4];
        if (name.includes('농부')) return [0, 0];
        if (name.includes('창병')) return [1, 0];
        if (name.includes('궁수') && !name.includes('기마')) return [2, 0];
        if (name.includes('기마')) return [4, 0];
        if (name.includes('화차') || name.includes('불랑기')) return [6, 0];
        if (name.includes('이순신')) return [0, 1];
        if (name.includes('곽재우')) return [2, 1];
        if (name.includes('사무라이') || name.includes('창병')) return [1, 2];
        if (name.includes('조총')) return [2, 2];
        return [1, 0];
    }

    updateSelectionHUD(unit) {
        if (!unit) {
            if (this.inspectedResource) this.renderInspectedResourceHUD();
            return;
        }
        const countSuffix = this.selectedUnits.length > 1 ? ` 외 ${this.selectedUnits.length - 1}기` : '';
        const lvBadge = (!unit.isBuilding && unit.level) ? ` [Lv.${unit.level}]` : '';
        if (this.dom.selectionName) this.dom.selectionName.textContent = (unit.name || '조선 훈련소') + lvBadge + countSuffix;
        if (this.dom.selectionFaction) {
            if (unit.isBuilding && unit.isConstructing) {
                this.dom.selectionFaction.textContent = `🔨 건설 중 (${Math.floor((unit.constructionProgress || 0) * 100)}%)`;
                this.dom.selectionFaction.style.color = '#8b4500';
            } else if (!unit.isBuilding && unit.level) {
                const nextExp = this.expTable[Math.min(unit.level, this.expTable.length - 1)] || 9999;
                this.dom.selectionFaction.textContent = `경험치 ${Math.floor(unit.exp || 0)}/${nextExp}`;
                this.dom.selectionFaction.style.color = '#3a1f04';
            } else {
                this.dom.selectionFaction.textContent = (unit.owner === 0) ? '조선군 (본영)' : ((unit.owner === 1) ? '일본군 (적군)' : '명군 (원군)');
                this.dom.selectionFaction.style.color = (unit.owner === 0) ? '#3a1f04' : ((unit.owner === 1) ? '#8b1a1a' : '#1a5a2a');
            }
        }

        // Render miniature sprite of the selected building/unit inside the octagonal portrait window
        if (this.dom.portraitSprite && this.assetManager) {
            if (!this._portraitCache) this._portraitCache = new Map();
            const cacheKey = (unit.sprite_name || unit.name || 'default') + (unit.isConstructing ? '_con' : '');
            let dataUrl = this._portraitCache.get(cacheKey);
            if (!dataUrl) {
                const spr = this.assetManager.getUnitSprite(unit.sprite_name || (unit.archetype && unit.archetype.sprite_name) || 'char/barrackk.spr');
                if (spr && spr.image) {
                    const f = spr.getFrame(0, 0, unit.isBuilding ? 'building' : 'idle');
                    if (f && f.w > 0 && f.h > 0) {
                        const pc = document.createElement('canvas');
                        pc.width = 88;
                        pc.height = 72;
                        const pctx = pc.getContext('2d');
                        pctx.imageSmoothingEnabled = false;
                        pctx.fillStyle = '#231d15';
                        pctx.fillRect(0, 0, 88, 72);
                        const scale = Math.min(78 / f.w, 64 / f.h);
                        const dw = f.w * scale;
                        const dh = f.h * scale;
                        pctx.drawImage(spr.image, f.x, f.y, f.w, f.h, (88 - dw) / 2, (72 - dh) / 2, dw, dh);
                        dataUrl = pc.toDataURL();
                        this._portraitCache.set(cacheKey, dataUrl);
                    }
                }
            }
            if (dataUrl) {
                this.dom.portraitSprite.style.backgroundImage = `url("${dataUrl}")`;
                this.dom.portraitSprite.style.backgroundPosition = 'center';
                this.dom.portraitSprite.style.backgroundSize = 'cover';
            }
        }

        const hpRatio = Math.max(0, Math.min(1, unit.hp / Math.max(1, unit.max_hp)));
        if (this.dom.selectionHpFill) this.dom.selectionHpFill.style.width = `${Math.round(hpRatio * 100)}%`;
        if (this.dom.selectionHpText) this.dom.selectionHpText.textContent = `${Math.round(unit.hp)}/${Math.round(unit.max_hp)}`;

        const mpRatio = unit.max_mp > 0 ? Math.max(0, Math.min(1, unit.mp / unit.max_mp)) : 0;
        if (this.dom.selectionMpFill) this.dom.selectionMpFill.style.width = `${Math.round(mpRatio * 100)}%`;
        if (this.dom.selectionMpText) this.dom.selectionMpText.textContent = unit.max_mp > 0 ? `${Math.round(unit.mp)}/${Math.round(unit.max_mp)}` : '0/0';

        if (this.dom.selectionMpText && this.dom.selectionMpText.closest('.parchment-stat-line')) {
            this.dom.selectionMpText.closest('.parchment-stat-line').style.display = unit.isBuilding ? 'none' : 'flex';
        }
        if (this.dom.statAttack && this.dom.statAttack.closest('.parchment-stat-line')) {
            this.dom.statAttack.closest('.parchment-stat-line').style.display = unit.isBuilding ? 'none' : 'flex';
        }

        if (this.dom.statAttack) {
            const baseAtk = unit.attack_power !== undefined ? unit.attack_power : 33;
            this.dom.statAttack.textContent = `${baseAtk}/${baseAtk + 12}`;
        }
        if (this.dom.statDefense) {
            const baseDef = unit.defense !== undefined ? unit.defense : 33;
            this.dom.statDefense.textContent = unit.isBuilding ? `${baseDef}/${baseDef}` : `${baseDef}/${baseDef + 8}`;
        }
        if (this.dom.statRange) this.dom.statRange.textContent = unit.attack_range !== undefined ? unit.attack_range : '-';
        if (this.dom.statSpeed) this.dom.statSpeed.textContent = unit.move_speed !== undefined ? unit.move_speed : '-';

        // Render 5-Slot Building Production Queue OR 4-Slot Hero Item Inventory inside #target-brackets-box
        this.renderHanjiRightColumn(unit);
    }

    renderHanjiRightColumn(unit) {
        if (!this.dom.targetBracketsBox) return;

        if (unit.isBuilding) {
            const queue = unit.productionQueue || [];
            if (unit.isConstructing) {
                const pct = Math.floor((unit.constructionProgress || 0) * 100);
                if (this.dom.hudProdPct) this.dom.hudProdPct.textContent = `${pct}%`;
                if (this.dom.hudProdLabel) this.dom.hudProdLabel.textContent = '🔨 건물 축조 중';
                this.dom.targetBracketsBox.innerHTML = '<span>┏</span><span>┓</span><span>┗</span><span>┛</span>';
                return;
            }

            const activeItem = queue[0];
            const pct = activeItem
                ? Math.floor((unit.prodProgress || 0) * 100)
                : (unit === this.primaryBarracks ? Math.floor(this.barracksProdProgress * 100) : 0);
            if (this.dom.hudProdPct) this.dom.hudProdPct.textContent = activeItem || unit === this.primaryBarracks ? `${pct}%` : '대기';
            if (this.dom.hudProdLabel) {
                this.dom.hudProdLabel.textContent = activeItem
                    ? activeItem.archetype.korean_name
                    : (unit === this.primaryBarracks ? '조선 창병' : '생산 대기 중');
            }

            // Render clickable queue slots inside target-brackets-box (click to cancel & refund!)
            let html = '';
            const maxSlots = 4;
            for (let i = 0; i < maxSlots; i++) {
                const qItem = queue[i];
                if (qItem) {
                    const shortLabel = qItem.archetype.korean_name.replace('조선 ', '').slice(0, 2);
                    html += `<div class="hanji-slot-btn" data-qidx="${i}" title="클릭하여 [${qItem.archetype.korean_name}] 생산 취소 및 자원 환불">${shortLabel}<span class="slot-badge">${i === 0 ? `${pct}%` : `대기${i}`}</span></div>`;
                } else {
                    html += `<div class="hanji-slot-btn" style="opacity:0.35;pointer-events:none;">빈칸</div>`;
                }
            }
            this.dom.targetBracketsBox.innerHTML = html;
            this.dom.targetBracketsBox.querySelectorAll('.hanji-slot-btn[data-qidx]').forEach(btn => {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    const idx = parseInt(btn.getAttribute('data-qidx'), 10);
                    const removed = (unit.productionQueue || []).splice(idx, 1)[0];
                    if (removed && removed.cost) {
                        if (idx === 0) {
                            unit.prodProgress = 0;
                        }
                        this.resources.rice += (removed.cost.rice || 0);
                        this.resources.wood += (removed.cost.wood || 0);
                        this.resources.potato += (removed.cost.potato || 0);
                        this.announceSystemMessage(`[${removed.archetype.korean_name}] 생산이 취소되어 자원이 환불되었습니다.`, '#cccccc');
                        this.updateResourceHUD();
                        this.updateSelectionHUD(unit);
                    }
                };
            });
        } else {
            // Unit / Hero selected -> Show 4-Slot Equipment & Consumable Inventory (InventoryMenu from screenPt_plus.dat!)
            const inv = unit.inventory || [null, null, null, null];
            let html = '';
            for (let i = 0; i < 4; i++) {
                const item = inv[i];
                if (item) {
                    html += `<div class="hanji-slot-btn" data-invidx="${i}" title="${item.name} (클릭하여 사용/확인)">${item.icon}<span class="slot-badge">${item.name.slice(0, 3)}</span></div>`;
                } else {
                    html += `<div class="hanji-slot-btn" style="opacity:0.35;pointer-events:none;">장비</div>`;
                }
            }
            this.dom.targetBracketsBox.innerHTML = html;
            this.dom.targetBracketsBox.querySelectorAll('.hanji-slot-btn[data-invidx]').forEach(btn => {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    const idx = parseInt(btn.getAttribute('data-invidx'), 10);
                    const item = inv[idx];
                    if (item && item.action) {
                        this.handleCommandCardAction({ action: item.action });
                    } else if (item) {
                        this.announceSystemMessage(`장착 보물: [${item.name}] — 전투 능력치가 영구 상승합니다.`, '#ffd700');
                    }
                };
            });

            if (this.dom.hudProdPct) this.dom.hudProdPct.textContent = `Lv.${unit.level || 1}`;
            if (this.dom.hudProdLabel) this.dom.hudProdLabel.textContent = unit.isHero ? '장수 보물창' : '부대 군장';
        }
    }

    resetSelectionHUD() {
        if (this.inspectedResource) {
            this.renderInspectedResourceHUD();
            return;
        }
        if (this.dom.selectionName) this.dom.selectionName.textContent = '조선 훈련소';
        if (this.dom.selectionFaction) this.dom.selectionFaction.textContent = '조선군 (본영)';
        if (this.dom.selectionHpFill) this.dom.selectionHpFill.style.width = '100%';
        if (this.dom.selectionHpText) this.dom.selectionHpText.textContent = '3600/3600';
        if (this.dom.selectionMpFill) this.dom.selectionMpFill.style.width = '0%';
        if (this.dom.selectionMpText) this.dom.selectionMpText.textContent = '0/0';
        if (this.dom.statAttack) this.dom.statAttack.textContent = '-';
        if (this.dom.statDefense) this.dom.statDefense.textContent = '33/33';
        if (this.dom.statRange) this.dom.statRange.textContent = '-';
        if (this.dom.statSpeed) this.dom.statSpeed.textContent = '-';
    }

    /* ----------------------------------------------------------------------
       Orders & Tactical Action Execution
       ---------------------------------------------------------------------- */
    issueOrder(targetGx, targetGy, playSound = true, clickSx = null, clickSy = null) {
        if (this.selectedUnits.length === 0) return;

        // If a Building is selected, right-click updates its green diamond rally point!
        const selectedBuildings = this.selectedUnits.filter(u => u.isBuilding);
        if (selectedBuildings.length > 0) {
            for (const b of selectedBuildings) {
                b.rallyPoint = { gx: targetGx, gy: targetGy };
            }
            this.announceSystemMessage(`🚩 집결지가 (${targetGx}, ${targetGy}) 좌표로 설정되었습니다.`, '#55ff77');
        }

        // Check if right-clicking an unfinished/damaged friendly building with a worker -> Construct/Repair!
        let targetFriendlyBld = null;
        for (const ent of this.entities) {
            if (ent && !ent.isDead && ent.isBuilding && ent.owner === 0) {
                if (Math.abs(ent.wx - targetGx) < 2.5 && Math.abs(ent.wy - targetGy) < 2.5) {
                    if (ent.isConstructing || ent.hp < ent.max_hp) {
                        targetFriendlyBld = ent;
                        break;
                    }
                }
            }
        }

        const resIdx = targetGy * this.grid.width + targetGx;
        const clickedResType = (targetGx >= 0 && targetGx < this.grid.width && targetGy >= 0 && targetGy < this.grid.height)
            ? this.grid.resourceTypes[resIdx] : 0;

        let targetHostile = null;
        for (const ent of this.entities) {
            if (ent && !ent.isDead && ent.owner !== 0) {
                const hitRadius = ent.isBuilding ? 2.2 : 1.3;
                if (Math.abs(ent.wx - targetGx) < hitRadius && Math.abs(ent.wy - targetGy) < hitRadius) {
                    targetHostile = ent;
                    break;
                }
            }
        }

        const isAttack = Boolean(targetHostile);

        const elev = this.grid.getElevation(targetGx, targetGy) || 0;
        this.moveMarkers.push({
            gx: targetGx,
            gy: targetGy,
            wx: targetGx + 0.5,
            wy: targetGy + 0.5,
            elev: elev,
            time: 0,
            duration: 0.6,
            type: isAttack ? 'attack' : 'move'
        });

        if (playSound) {
            const voice = isAttack ? 'attack_swordk0' : 'move_swordk0';
            this.soundEngine.play(voice, targetGx, targetGy, this.camera);
        }

        const count = this.selectedUnits.length;
        this.selectedUnits.forEach((unit, idx) => {
            if (unit.isBuilding) return;

            unit.holdPosition = false;
            unit.attackMoveTarget = null;
            unit.patrolRoute = null;

            if (unit.isWorker && targetFriendlyBld && !isAttack) {
                unit.autoHarvest = false;
                unit.constructingTarget = targetFriendlyBld;
                unit.moveTo(Math.round(targetFriendlyBld.wx) + 1, Math.round(targetFriendlyBld.wy) + 1, this.grid);
                return;
            }

            if (unit.isWorker && clickedResType > 0 && !isAttack) {
                unit.constructingTarget = null;
                unit.autoHarvest = true;
                unit.harvestPref = clickedResType;
                unit.harvestTarget = { gx: targetGx, gy: targetGy, rType: clickedResType };
                unit.moveTo(targetGx, targetGy, this.grid);
                return;
            } else if (unit.isWorker) {
                unit.constructingTarget = null;
                unit.autoHarvest = false;
            }

            let destGx = targetGx;
            let destGy = targetGy;

            if (count > 1) {
                const cols = Math.ceil(Math.sqrt(count));
                const r = Math.floor(idx / cols) - Math.floor(cols / 2);
                const c = (idx % cols) - Math.floor(cols / 2);
                destGx = Math.max(0, Math.min(this.grid.width - 1, targetGx + c));
                destGy = Math.max(0, Math.min(this.grid.height - 1, targetGy + r));
            }

            if (isAttack) {
                unit.attackOrder(targetHostile);
            } else {
                unit.moveTo(destGx, destGy, this.grid);
            }
        });
    }

    /**
     * Executes an RTS command that waited for a Left-Click target coordinate/unit on the battlefield.
     */
    executeTargetedCommand(action, targetGx, targetGy, pickedEntity = null) {
        const elev = this.grid.getElevation(targetGx, targetGy) || 0;

        if (action === 'set_rally') {
            const selectedBuildings = this.selectedUnits.filter(u => u.isBuilding);
            for (const b of selectedBuildings) {
                b.rallyPoint = { gx: targetGx, gy: targetGy };
            }
            this.moveMarkers.push({ gx: targetGx, gy: targetGy, wx: targetGx + 0.5, wy: targetGy + 0.5, elev, time: 0, duration: 0.6, type: 'move' });
            this.announceSystemMessage(`🚩 집결지가 (${targetGx}, ${targetGy}) 좌표로 설정되었습니다.`, '#55ff77');
            return;
        }

        if (action === 'move') {
            this.moveMarkers.push({ gx: targetGx, gy: targetGy, wx: targetGx + 0.5, wy: targetGy + 0.5, elev, time: 0, duration: 0.6, type: 'move' });
            this.soundEngine.play('move_swordk0', targetGx, targetGy, this.camera);
            const count = this.selectedUnits.length;
            this.selectedUnits.forEach((unit, idx) => {
                if (unit.isBuilding) return;
                unit.holdPosition = false;
                unit.attackMoveTarget = null;
                unit.patrolRoute = null;
                unit.autoHarvest = false;
                unit.constructingTarget = null;
                const cols = Math.ceil(Math.sqrt(count));
                const r = count > 1 ? Math.floor(idx / cols) - Math.floor(cols / 2) : 0;
                const c = count > 1 ? (idx % cols) - Math.floor(cols / 2) : 0;
                unit.moveTo(
                    Math.max(0, Math.min(this.grid.width - 1, targetGx + c)),
                    Math.max(0, Math.min(this.grid.height - 1, targetGy + r)),
                    this.grid
                );
            });
            return;
        }

        if (action === 'attack_ground') {
            this.moveMarkers.push({ gx: targetGx, gy: targetGy, wx: targetGx + 0.5, wy: targetGy + 0.5, elev, time: 0, duration: 0.6, type: 'attack' });
            this.soundEngine.play('attack_swordk0', targetGx, targetGy, this.camera);
            const isDirectHostile = pickedEntity && !pickedEntity.isDead && pickedEntity.owner !== 0;
            const count = this.selectedUnits.length;
            this.selectedUnits.forEach((unit, idx) => {
                if (unit.isBuilding) return;
                unit.holdPosition = false;
                unit.patrolRoute = null;
                unit.autoHarvest = false;
                unit.constructingTarget = null;
                if (isDirectHostile) {
                    unit.attackMoveTarget = null;
                    unit.attackOrder(pickedEntity);
                } else {
                    const cols = Math.ceil(Math.sqrt(count));
                    const r = count > 1 ? Math.floor(idx / cols) - Math.floor(cols / 2) : 0;
                    const c = count > 1 ? (idx % cols) - Math.floor(cols / 2) : 0;
                    const dGx = Math.max(0, Math.min(this.grid.width - 1, targetGx + c));
                    const dGy = Math.max(0, Math.min(this.grid.height - 1, targetGy + r));
                    unit.attackMoveTarget = { gx: dGx, gy: dGy };
                    unit.moveTo(dGx, dGy, this.grid);
                }
            });
            this.announceSystemMessage(isDirectHostile ? `⚔️ [${pickedEntity.name}] 집중 공격!` : `⚔️ (${targetGx}, ${targetGy}) 지점으로 공격 진군(Attack-Move)!`, '#ff5555');
            return;
        }

        if (action === 'patrol') {
            this.moveMarkers.push({ gx: targetGx, gy: targetGy, wx: targetGx + 0.5, wy: targetGy + 0.5, elev, time: 0, duration: 0.6, type: 'move' });
            this.soundEngine.play('move_swordk0', targetGx, targetGy, this.camera);
            this.selectedUnits.forEach((unit) => {
                if (unit.isBuilding) return;
                unit.holdPosition = false;
                unit.attackMoveTarget = null;
                unit.autoHarvest = false;
                unit.constructingTarget = null;
                unit.patrolRoute = {
                    from: { gx: Math.floor(unit.wx), gy: Math.floor(unit.wy) },
                    to: { gx: targetGx, gy: targetGy },
                    goingToEnd: true
                };
                unit.moveTo(targetGx, targetGy, this.grid);
            });
            this.announceSystemMessage(`🔄 현 위치와 (${targetGx}, ${targetGy}) 사이를 왕복 순찰합니다.`, '#66ccff');
            return;
        }

        if (action === 'repair_building') {
            const bld = (pickedEntity && pickedEntity.isBuilding && pickedEntity.owner === 0)
                ? pickedEntity
                : this.entities.find(e => e && !e.isDead && e.isBuilding && e.owner === 0 &&
                    Math.hypot(e.wx - targetGx, e.wy - targetGy) <= 3.5 &&
                    (e.isConstructing || e.hp < e.max_hp));
            if (bld) {
                this.soundEngine.play('decidebuild', targetGx, targetGy, this.camera);
                this.selectedUnits.forEach(u => {
                    if (u.isWorker) {
                        u.autoHarvest = false;
                        u.constructingTarget = bld;
                        u.moveTo(Math.round(bld.wx) + 1, Math.round(bld.wy) + 1, this.grid);
                    }
                });
                this.announceSystemMessage(`🔨 농부가 [${bld.name}] 수리 및 축조를 시작합니다.`, '#55ff77');
            } else {
                this.announceSystemMessage('수리할 아군 건물을 좌클릭하세요.', '#cccccc');
            }
            return;
        }

        if (action === 'skill_shockwave') {
            const caster = this.selectedUnits.find(u => !u.isBuilding) || this.entities.find(e => e && !e.isDead && e.owner === 0 && e.isHero);
            if (caster) {
                for (const enemy of this.entities) {
                    if (enemy && !enemy.isDead && enemy.owner === 1 && Math.hypot(enemy.wx - targetGx, enemy.wy - targetGy) <= 5.5) {
                        enemy.hp = Math.max(0, enemy.hp - 220);
                        if (enemy.hp <= 0) {
                            enemy.isDead = true;
                            this.grantHeroExp(caster, 85);
                        }
                    }
                }
                this.projectiles.push(new Projectile(this.nextProjId++, 'cannon', caster.wx, caster.wy, { wx: targetGx + 0.5, wy: targetGy + 0.5 }, 12, 120, { sourceUnit: caster }));
                this.soundEngine.play('cannon1', targetGx, targetGy, this.camera);
                this.addFloatingText(targetGx, targetGy, '💥 기공신포 폭발!', '#ffd700');
                this.announceSystemMessage(`💥 [${caster.name}] 기공신포 발사! (${targetGx}, ${targetGy}) 일대 적군 타격!`, '#ffd700');
            }
            return;
        }

        if (action === 'skill_firestorm') {
            this.groundFires.push(
                { wx: targetGx, wy: targetGy, phase: 0, life: 30.0, spreadTimer: 0 },
                { wx: targetGx + 0.8, wy: targetGy + 0.5, phase: 9, life: 30.0, spreadTimer: 1.0 },
                { wx: targetGx - 0.6, wy: targetGy + 0.7, phase: 18, life: 30.0, spreadTimer: 2.0 }
            );
            this.soundEngine.play('fire1', targetGx, targetGy, this.camera);
            this.addFloatingText(targetGx, targetGy, '🔥 폭뢰격 화공!', '#ff5533');
            this.announceSystemMessage(`🔥 (${targetGx}, ${targetGy}) 지점에 [폭뢰격 화공] 발동! 바람 방향을 따라 불길이 번집니다!`, '#ff7744');
            return;
        }
    }

    handleCommandCardAction(cmd) {
        if (!cmd) return;
        const action = cmd.action || cmd.id || cmd.name;

        switch (action) {
            case 'move':
            case '이동':
                this.setPendingCommand('move', '이동 (Q)', '#32e650', 0.8);
                break;
            case 'stop':
            case '정지':
                this.clearPendingCommand();
                this.selectedUnits.forEach(u => {
                    if (u.isBuilding) return;
                    u.waypoints = [];
                    u.targetEntity = null;
                    u.holdPosition = false;
                    u.attackMoveTarget = null;
                    u.patrolRoute = null;
                    u.autoHarvest = false;
                    u.constructingTarget = null;
                    u.state = UnitState.IDLE;
                });
                this.announceSystemMessage('🛑 부대 정지 (Stop): 모든 이동·공격·수확 명령을 중지했습니다.', '#cccccc');
                break;
            case 'hold':
            case '홀드':
                this.clearPendingCommand();
                this.selectedUnits.forEach(u => {
                    if (u.isBuilding) return;
                    u.waypoints = [];
                    u.holdPosition = true;
                    u.attackMoveTarget = null;
                    u.patrolRoute = null;
                    u.autoHarvest = false;
                    u.state = UnitState.IDLE;
                });
                this.announceSystemMessage('🛡️ 위치 사수 (Hold): 현 위치를 고수하며 사거리 내 적만 요격합니다.', '#ffd700');
                break;
            case 'attack':
            case 'attack_ground':
                this.setPendingCommand('attack_ground', '공격 진군 (R)', '#ff4444', 1.2);
                break;
            case 'patrol':
                this.setPendingCommand('patrol', '순찰 (A)', '#66ccff', 1.0);
                break;
            case 'set_rally':
                this.setPendingCommand('set_rally', '집결지 설정 (W)', '#55ff77', 0.8);
                break;
            case 'harvest':
                this.selectedUnits.forEach(u => {
                    if (!u.isBuilding) {
                        u.isWorker = true;
                        u.autoHarvest = true;
                        u.constructingTarget = null;
                    }
                });
                this.addFloatingText(24, 16, '🌾 자동 수확 개시!', '#55ff77');
                this.announceSystemMessage('농부가 주변 논밭의 쌀(벼)과 숲의 목재를 자동 수확하여 가장 가까운 본영에 비축합니다.', '#55ff77');
                break;

            // =================================================================
            // Farmer 2-Tier Construction System (건물1 초급건물 / 건물2 고급건물)
            // =================================================================
            case 'farmer_tier1':
                this.farmerMenuTier = 1;
                if (this.commandCard && this.commandCard.setFarmerCommands) {
                    this.commandCard.setFarmerCommands(1);
                }
                this.announceSystemMessage('건물1 (초급건물): 건설할 건물을 선택한 뒤 전장 지면을 좌클릭하세요.', '#ffd700');
                break;
            case 'farmer_tier2':
                this.farmerMenuTier = 2;
                if (this.commandCard && this.commandCard.setFarmerCommands) {
                    this.commandCard.setFarmerCommands(2);
                }
                this.announceSystemMessage('건물2 (고급건물): 건설할 고급 건물을 선택한 뒤 전장 지면을 좌클릭하세요.', '#ffd700');
                break;
            case 'farmer_menu_cancel':
                this.farmerMenuTier = 0;
                this.placingBuilding = null;
                if (this.commandCard && this.commandCard.setFarmerCommands) {
                    this.commandCard.setFarmerCommands(0);
                }
                break;
            case 'place_hq':
                this.placingBuilding = { korean_name: '조선 본영', sprite_name: 'char/hqk_plus.spr', width: 3, height: 3, hp: 6000, defense: 30, costRice: 500, costWood: 500 };
                this.announceSystemMessage('🏰 [조선 본영] 건설 위치를 지면에서 좌클릭하세요 (우클릭: 취소).', '#55ff77');
                break;
            case 'place_mill':
                this.placingBuilding = { korean_name: '조선 방앗간', sprite_name: 'char/millk_plus.spr', width: 2, height: 2, hp: 3200, defense: 20, costRice: 0, costWood: 150 };
                this.announceSystemMessage('🌾 [조선 방앗간] 건설 위치를 지면에서 좌클릭하세요 (완공 시 인구 +500).', '#55ff77');
                break;
            case 'place_barracks':
            case 'build_barracks':
                this.placingBuilding = { korean_name: '조선 훈련소', sprite_name: 'char/barrackk.spr', width: 2, height: 2, hp: 3600, defense: 33, costRice: 0, costWood: 200 };
                this.announceSystemMessage('⚔️ [조선 훈련소] 건설 위치를 지면에서 좌클릭하세요 (목재 200).', '#55ff77');
                break;
            case 'place_stable':
                this.placingBuilding = { korean_name: '조선 마구간', sprite_name: 'char/stablek.spr', width: 3, height: 2, hp: 3800, defense: 25, costRice: 0, costWood: 250 };
                this.announceSystemMessage('🐎 [조선 목장(마구간)] 건설 위치를 지면에서 좌클릭하세요 (목재 250).', '#55ff77');
                break;
            case 'place_tower':
                this.placingBuilding = { korean_name: '조선 신기전망루', sprite_name: 'char/storagek.spr', width: 2, height: 2, hp: 2800, defense: 28, costRice: 0, costWood: 180 };
                this.announceSystemMessage('🏹 [조선 신기전망루] 건설 위치를 지면에서 좌클릭하세요 (목재 180).', '#55ff77');
                break;
            case 'place_armory':
                this.placingBuilding = { korean_name: '조선 군기시', sprite_name: 'char/storagek.spr', width: 3, height: 2, hp: 4200, defense: 26, costRice: 0, costWood: 300 };
                this.announceSystemMessage('🔥 [조선 훈련도감(군기시)] 건설 위치를 지면에서 좌클릭하세요 (목재 300).', '#55ff77');
                break;
            case 'place_smithy':
                this.placingBuilding = { korean_name: '조선 제철장', sprite_name: 'char/millk_plus.spr', width: 2, height: 2, hp: 3500, defense: 25, costRice: 0, costWood: 260 };
                this.announceSystemMessage('⚒️ [조선 제철장] 건설 위치를 지면에서 좌클릭하세요 (목재 260).', '#55ff77');
                break;
            case 'place_temple':
                this.placingBuilding = { korean_name: '조선 절', sprite_name: 'char/barrackk.spr', width: 2, height: 2, hp: 3400, defense: 24, costRice: 0, costWood: 240 };
                this.announceSystemMessage('☸️ [조선 절] 건설 위치를 지면에서 좌클릭하세요 (목재 240).', '#55ff77');
                break;

            // Farmer Utility Actions (수리, 불끄기, 황소농부로 전환)
            case 'repair_building':
                this.setPendingCommand('repair_building', '건물 수리 (A)', '#ffd700', 1.0, 4);
                break;
            case 'extinguish_fire': {
                this.groundFires = [];
                this.announceSystemMessage('💧 농부들이 전장의 화공 불길을 모두 진압했습니다!', '#66ccff');
                this.soundEngine.play('heal', 25, 25, this.camera);
                break;
            }
            case 'upgrade_ox_farmer': {
                if (this.resources.rice < 80) {
                    this.announceSystemMessage('쌀이 부족합니다 (황소농부 전환: 쌀 80 필요).', '#ff5555');
                    break;
                }
                this.resources.rice -= 80;
                this.selectedUnits.forEach(u => {
                    if (u.isWorker) {
                        u.name = '조선 황소농부';
                        u.max_hp = 450;
                        u.hp = 450;
                        u.harvestBonus = 2.0;
                    }
                });
                this.announceSystemMessage('🐂 황소농부로 전환되었습니다! (체력 450, 쌀·목재 수확량 2배)', '#ffd700');
                this.updateResourceHUD();
                break;
            }

            // =================================================================
            // Market Trading & Merchant System (방앗간 / 개성 김씨 상인)
            // =================================================================
            case 'sell_grain':
                if (this.resources.rice >= 500) {
                    this.resources.rice -= 500;
                    this.resources.wood += 350;
                    this.announceSystemMessage('⚖️ [곡물팔기] 쌀 500석을 팔아 목재 350을 확보했습니다!', '#ffd700');
                    this.soundEngine.play('click', 18, 17, this.camera);
                    this.updateResourceHUD();
                } else {
                    this.announceSystemMessage('곡물팔기에 필요한 쌀(500석)이 부족합니다!', '#ff5555');
                }
                break;
            case 'sell_wood':
                if (this.resources.wood >= 500) {
                    this.resources.wood -= 500;
                    this.resources.rice += 350;
                    this.announceSystemMessage('⚖️ [목재팔기] 목재 500을 팔아 쌀 350석을 확보했습니다!', '#ffd700');
                    this.soundEngine.play('click', 18, 17, this.camera);
                    this.updateResourceHUD();
                } else {
                    this.announceSystemMessage('목재팔기에 필요한 목재(500)가 부족합니다!', '#ff5555');
                }
                break;
            case 'call_merchant':
                this.resources.rice += 300;
                this.resources.wood += 200;
                this.announceSystemMessage('💰 개성 김씨 상인이 도착했습니다! 교역 보너스 (쌀 +300, 목재 +200) 획득!', '#ffd700');
                this.soundEngine.play('decidebuild', 18, 17, this.camera);
                this.updateResourceHUD();
                break;
            case 'buy_ginseng':
            case 'use_ginseng': {
                if (action === 'buy_ginseng') {
                    if (this.resources.rice < 100) {
                        this.announceSystemMessage('인삼 구입에 필요한 쌀(100석)이 부족합니다.', '#ff5555');
                        break;
                    }
                    this.resources.rice -= 100;
                }
                for (const ent of this.entities) {
                    if (ent && !ent.isDead && !ent.isBuilding && ent.owner === 0) {
                        ent.hp = Math.min(ent.max_hp, ent.hp + 300);
                    }
                }
                this.soundEngine.play('heal', 24, 24, this.camera);
                this.addFloatingText(24, 24, '🌿 고려 인삼 복용 (+300 HP)!', '#55ff77');
                this.announceSystemMessage('🌿 고려 인삼을 복용하여 아군 장수 및 부대의 체력이 +300 회복되었습니다!', '#55ff77');
                this.updateResourceHUD();
                break;
            }
            case 'buy_rain_scroll':
            case 'cast_rain':
                if (action === 'buy_rain_scroll') {
                    if (this.resources.rice < 120) {
                        this.announceSystemMessage('기우제 주문서 구입에 필요한 쌀(120석)이 부족합니다.', '#ff5555');
                        break;
                    }
                    this.resources.rice -= 120;
                    this.updateResourceHUD();
                }
                this.weather = 'snake_rain'; // Forces switch to 'rain'
                this.triggerRainStorm();
                break;
            case 'buy_blood_blade':
                if (this.resources.rice < 200) {
                    this.announceSystemMessage('폭마혈도 구입에 필요한 쌀(200석)이 부족합니다.', '#ff5555');
                    break;
                }
                this.resources.rice -= 200;
                this.entities.forEach(e => {
                    if (e && !e.isDead && e.owner === 0 && e.isHero) {
                        e.attack_power = (e.attack_power || 35) + 25;
                        if (e.inventory) e.inventory[0] = { id: 'blood_blade', name: '폭마혈도 (공격+25·폭뢰격)', icon: '🗡️', type: 'equip' };
                    }
                });
                this.announceSystemMessage('🗡️ 보물 [폭마혈도] 장착 완료! 아군 장수 공격력 +25 및 폭뢰격 마법 강화!', '#ffd700');
                this.updateResourceHUD();
                break;
            case 'buy_kirin_armor':
                if (this.resources.wood < 200) {
                    this.announceSystemMessage('용기린갑옷 구입에 필요한 목재(200)가 부족합니다.', '#ff5555');
                    break;
                }
                this.resources.wood -= 200;
                this.entities.forEach(e => {
                    if (e && !e.isDead && e.owner === 0 && e.isHero) {
                        e.defense = (e.defense || 20) + 20;
                        e.max_hp += 500;
                        e.hp += 500;
                        if (e.inventory) e.inventory[1] = { id: 'kirin_armor', name: '용기린갑옷 (방어+20·체력+500)', icon: '🛡️', type: 'equip' };
                    }
                });
                this.announceSystemMessage('🛡️ 보물 [용기린갑옷] 장착 완료! 아군 장수 방어력 +20 및 최대 체력 +500!', '#ffd700');
                this.updateResourceHUD();
                break;

            // =================================================================
            // Authentic Technology Researches (Text_kor.dat)
            // =================================================================
            case 'tech_plow':
            case 'tech_economy':
            case 'tech_fire_arrow':
            case 'tech_infantry_armor':
            case 'tech_hwacha':
            case 'tech_shockwave':
            case 'tech_clones':
            case 'tech_heojun':
            case 'tech_harvest': {
                if (this.researchedTechs.has(action)) {
                    this.announceSystemMessage('이미 완료된 연구입니다.', '#cccccc');
                    break;
                }
                if (this.resources.wood < 100) {
                    this.announceSystemMessage('연구에 필요한 목재(100)가 부족합니다.', '#ff5555');
                    break;
                }
                this.resources.wood -= 100;
                this.researchedTechs.add(action);
                if (action === 'tech_fire_arrow') {
                    this.entities.forEach(e => {
                        if (e && !e.isDead && e.owner === 0 && !e.isBuilding) e.attack_power = (e.attack_power || 18) + 8;
                    });
                    this.announceSystemMessage('🔥 연구가 완료되었습니다: [불화살 개발] — 궁수 공격력 +8 및 화공 점화!', '#ffd700');
                } else if (action === 'tech_infantry_armor') {
                    this.entities.forEach(e => {
                        if (e && !e.isDead && e.owner === 0 && !e.isBuilding) e.defense = (e.defense || 15) + 8;
                    });
                    this.announceSystemMessage('🛡️ 연구가 완료되었습니다: [포복술 연구] — 전군 방어력 +8 상승!', '#ffd700');
                } else {
                    this.announceSystemMessage(`📜 연구가 완료되었습니다: [${cmd.name || action}]!`, '#ffd700');
                }
                this.soundEngine.play('decidebuild', 18, 17, this.camera);
                this.updateResourceHUD();
                break;
            }

            // =================================================================
            // Hero Active MP Skills (기공신포, 폭뢰격, 분신술)
            // =================================================================
            case 'skill_shockwave': {
                this.setPendingCommand('skill_shockwave', '기공신포 (S)', '#ffd700', 2.5);
                break;
            }
            case 'skill_firestorm': {
                this.setPendingCommand('skill_firestorm', '폭뢰격 화공 (D)', '#ff5533', 2.2);
                break;
            }
            case 'summon_clones': {
                const hero = this.selectedUnits.find(u => !u.isBuilding) || this.entities.find(e => e && !e.isDead && e.owner === 0 && e.isHero);
                if (hero) {
                    const mpCost = 50;
                    if (hero.mp !== undefined && hero.max_mp > 0 && hero.mp < mpCost) {
                        this.announceSystemMessage('마력이 부족합니다! (필요 MP: 50)', '#ff5555');
                        break;
                    }
                    if (hero.consumeMana) {
                        hero.consumeMana(mpCost);
                    } else if (hero.mp !== undefined) {
                        hero.mp = Math.max(0, hero.mp - mpCost);
                    }
                    const clone = this.spawnUnit({
                        archetype: {
                            ...(hero.archetype || BUILTIN_UNIT_TEMPLATES[7]),
                            isIllusion: true,
                            illusionDuration: 25.0,
                            hp: 300,
                            max_hp: 300
                        },
                        faction: 0,
                        gx: Math.round(hero.wx) + 1,
                        gy: Math.round(hero.wy) + 1
                    });
                    if (clone) {
                        clone.isIllusion = true;
                        clone.illusionDuration = 25.0;
                        clone.name = `${hero.name} (분신)`;
                        this.addFloatingText(clone.wx, clone.wy, '✨ 분신술 소환!', '#66ccff');
                        this.announceSystemMessage(`✨ [${hero.name}] 분신술 발동! 환영 분신이 전장에 합류했습니다.`, '#66ccff');
                    }
                }
                break;
            }

            case 'all_charge': {
                const enemyTarget = this.entities.find(e => e && !e.isDead && e.owner === 1);
                for (const ent of this.entities) {
                    if (ent && !ent.isDead && !ent.isBuilding && ent.owner === 0 && !ent.isWorker) {
                        ent.holdPosition = false;
                        if (enemyTarget) {
                            ent.attackOrder(enemyTarget);
                        } else {
                            ent.attackMoveTarget = { gx: 32, gy: 28 };
                            ent.moveTo(32, 28, this.grid);
                        }
                    }
                }
                this.soundEngine.play('attack_swordk0', 25, 24, this.camera);
                this.addFloatingText(25, 23, '⚔️ 전군 돌격 명령!', '#ff5555');
                this.announceSystemMessage('⚔️ 전군 총공격 명령이 하달되었습니다!', '#ff5555');
                break;
            }
            case 'produce_farmer':
            case '농부':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[0], { rice: 40 }, true);
                break;
            case 'produce_spearman':
            case '창병':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[1], { rice: 50 }, false);
                break;
            case 'produce_archer':
            case '궁수':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[2], { rice: 60, wood: 20 }, false);
                break;
            case 'produce_cavalry':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[3], { rice: 80, wood: 30 }, false);
                break;
            case 'summon_hero':
            case '이순신': {
                const u = this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[7], { rice: 150 }, false, true);
                if (u) this.announceSystemMessage('⚓ 충무공 이순신 대령했습니다! (기공신포 사용 가능)', '#ffd700');
                break;
            }
            case 'summon_kwak':
            case 'summon_samyeong':
            case 'summon_heojun': {
                const u = this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[8], { rice: 140 }, false, true);
                if (u) {
                    if (action === 'summon_samyeong') u.name = '사명대사';
                    if (action === 'summon_heojun') u.name = '명의 허준';
                    this.announceSystemMessage(`⚔️ [${u.name}] 장군이 본영에서 등용되어 전장에 합류했습니다!`, '#ffd700');
                }
                break;
            }
            case 'produce_hwacha':
            case 'produce_cannon':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[5], { wood: 120 }, false);
                break;
            case 'build_turtle':
            case '거북선':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[10], { wood: 150 }, false);
                break;
            case 'produce_elephant':
                this.tryProduceUnit(BUILTIN_UNIT_TEMPLATES[22], { potato: 120 }, false);
                break;
            case 'produce_custom_unit':
            case 'produce_unit_0x70':
            case 'produce_unit_0x71':
            case 'produce_unit_0x72':
            case 'produce_unit_0x73':
            case 'produce_unit_0x74':
            case 'produce_unit_0x75':
            case 'produce_unit_0x76':
            case 'produce_unit_0x77':
            case 'produce_unit_0x78':
            case 'produce_unit_0x79': {
                const targetKindId = cmd.kindId || (cmd.id && cmd.id.startsWith('produce_unit_0x') ? parseInt(cmd.id.replace('produce_unit_', ''), 16) : null);
                const template = BUILTIN_UNIT_TEMPLATES.find(t =>
                    t.index === targetKindId ||
                    t.kind_id === targetKindId ||
                    t.kindId === targetKindId ||
                    (cmd.unitId && (t.sprite_name || t.sprite_path || '').toLowerCase().includes(cmd.unitId.toLowerCase())) ||
                    (t.korean_name && cmd.name && cmd.name.includes(t.korean_name))
                );
                if (template) {
                    const cost = {
                        rice: cmd.costRice !== undefined ? cmd.costRice : (template.cost_rice || template.costRice || 0),
                        potato: cmd.costPotato !== undefined ? cmd.costPotato : (template.cost_potato || template.costPotato || 0),
                        wood: cmd.costWood !== undefined ? cmd.costWood : 0
                    };
                    this.tryProduceUnit(template, cost, false);
                }
                break;
            }
            default:
                if (cmd && (cmd.isCustomUnit || (cmd.kindId >= 0x70 && cmd.kindId <= 0x79) || (cmd.id && cmd.id.startsWith('produce_unit_0x7')))) {
                    const targetKindId = cmd.kindId || (cmd.id && cmd.id.startsWith('produce_unit_0x') ? parseInt(cmd.id.replace('produce_unit_', ''), 16) : null);
                    const template = BUILTIN_UNIT_TEMPLATES.find(t =>
                        t.index === targetKindId ||
                        t.kind_id === targetKindId ||
                        t.kindId === targetKindId ||
                        (cmd.unitId && (t.sprite_name || t.sprite_path || '').toLowerCase().includes(cmd.unitId.toLowerCase())) ||
                        (t.korean_name && cmd.name && cmd.name.includes(t.korean_name))
                    );
                    if (template) {
                        const cost = {
                            rice: cmd.costRice !== undefined ? cmd.costRice : (template.cost_rice || template.costRice || 0),
                            potato: cmd.costPotato !== undefined ? cmd.costPotato : (template.cost_potato || template.costPotato || 0),
                            wood: cmd.costWood !== undefined ? cmd.costWood : 0
                        };
                        this.tryProduceUnit(template, cost, false);
                    }
                }
                break;
        }
    }

    grantHeroExp(unit, amount) {
        if (!unit || unit.isBuilding) return;
        unit.level = unit.level || 1;
        unit.exp = (unit.exp || 0) + amount;
        const nextThreshold = this.expTable[Math.min(unit.level, this.expTable.length - 1)] || 9999;
        if (unit.exp >= nextThreshold && unit.level < 12) {
            unit.level += 1;
            unit.max_hp = Math.round(unit.max_hp * 1.18);
            unit.hp = unit.max_hp;
            unit.attack_power = (unit.attack_power || 20) + 6;
            unit.defense = (unit.defense || 15) + 4;
            this.soundEngine.play('heal', unit.wx, unit.wy, this.camera);
            this.addFloatingText(unit.wx, unit.wy, `🎉 레벨 업! Lv.${unit.level}`, '#ffd700');
            this.announceSystemMessage(`🎉 [${unit.name}] 레벨이 올랐습니다! (Lv.${unit.level} 달성 — 체력·공격력·방어력 상승)`, '#ffd700');
            this.refreshFKeyBar();
        }
    }

    tryProduceUnit(archetype, cost = {}, isWorker = false, immediateHero = false) {
        const needRice = cost.rice || 0;
        const needPotato = cost.potato || 0;
        const needWood = cost.wood || 0;

        if (this.resources.rice < needRice || this.resources.potato < needPotato || this.resources.wood < needWood) {
            this.addFloatingText(20, 18, '⚠️ 자원이 부족합니다!', '#ff5555');
            this.announceSystemMessage('자원이 부족하여 생산할 수 없습니다.', '#ff5555');
            return null;
        }

        const spawner = this.selectedUnits.find(e => e.isBuilding && e.owner === 0) ||
                        this.primaryBarracks ||
                        this.entities.find(e => e.isBuilding && e.owner === 0) ||
                        { wx: 21, wy: 17 };

        // Authentic RTS Production Queue: enqueue in selected building and advance 0% -> 100% before spawning!
        if (spawner.isBuilding && !immediateHero) {
            if (!spawner.productionQueue) spawner.productionQueue = [];
            if (spawner.productionQueue.length >= 4) {
                this.announceSystemMessage('⚠️ 생산 대기열이 가득 찼습니다 (최대 4기 대기 가능).', '#ffcc33');
                return null;
            }
            this.resources.rice -= needRice;
            this.resources.potato -= needPotato;
            this.resources.wood -= needWood;
            spawner.productionQueue.push({ archetype, cost, isWorker });
            if (spawner.productionQueue.length === 1 && !spawner.prodProgress) {
                spawner.prodProgress = 0.02;
            }
            this.soundEngine.play('click', spawner.wx, spawner.wy, this.camera);
            this.announceSystemMessage(`⏳ [${archetype.korean_name}] 생산 대기열 추가 (${spawner.productionQueue.length}/4)`, '#ffd700');
            this.updateResourceHUD();
            if (this.selectedUnits[0] === spawner) {
                this.updateSelectionHUD(spawner);
            }
            return spawner;
        }

        this.resources.rice -= needRice;
        this.resources.potato -= needPotato;
        this.resources.wood -= needWood;

        const sx = Math.round(spawner.wx) + Math.floor(Math.random() * 3) - 1;
        const sy = Math.round(spawner.wy) + 2 + Math.floor(Math.random() * 2);

        const u = this.spawnUnit({ archetype, faction: 0, gx: sx, gy: sy });
        if (u) {
            u.level = archetype.level || (immediateHero ? 3 : 1);
            u.exp = this.expTable[Math.min(u.level - 1, this.expTable.length - 1)] || 0;
            u.isHero = Boolean(immediateHero);
            if (isWorker) {
                u.isWorker = true;
                u.autoHarvest = true;
                u.harvestPref = 100;
            } else if (spawner.rallyPoint) {
                u.moveTo(spawner.rallyPoint.gx, spawner.rallyPoint.gy, this.grid);
            }
            this.addFloatingText(u.wx, u.wy, `+ ${archetype.korean_name}`, '#4da6ff');
        }
        this.updateResourceHUD();
        this.refreshFKeyBar();
        if (this.selectedUnits[0] === spawner) {
            this.updateSelectionHUD(spawner);
        }
        return u;
    }

    spawnUnit(unitDef = {}) {
        const archetype = unitDef.archetype || BUILTIN_UNIT_TEMPLATES[1];
        const faction = (unitDef.faction !== undefined) ? unitDef.faction : 0;

        let sx = unitDef.gx;
        let sy = unitDef.gy;

        if (sx === undefined || sy === undefined) {
            const center = IsometricMath.screenToGrid(
                this.canvas.width / 2,
                this.canvas.height / 2,
                this.camera,
                this.grid.elevation,
                this.grid.width,
                this.grid.height
            );
            sx = center.gx;
            sy = center.gy;
        }

        // Find nearest walkable tile
        if (!this.grid.isWalkable(sx, sy)) {
            const near = PathFinder.findNearestWalkable(this.grid, sx, sy);
            if (near) { sx = near.gx; sy = near.gy; }
        }

        const newUnit = new Unit(this.nextEntityId++, archetype, sx, sy, faction);
        if (archetype.level) newUnit.level = archetype.level;
        if (unitDef.speed !== undefined) newUnit.move_speed = unitDef.speed;
        if (unitDef.hp !== undefined) { newUnit.max_hp = unitDef.hp; newUnit.hp = unitDef.hp; }
        if (unitDef.name) newUnit.name = unitDef.name;
        newUnit.isBuilding = false;

        this.entities.push(newUnit);
        this.soundEngine.play('decidebuild', sx, sy, this.camera);
        this.updateResourceHUD();
        return newUnit;
    }

    updateWorkerHarvest(worker, dt) {
        if (!worker || worker.isDead) return;

        // 1. If Farmer has an active building construction/repair order (scaffolding frames 0..6 -> 7)
        if (worker.constructingTarget) {
            const bld = worker.constructingTarget;
            if (bld.isDead || (!bld.isConstructing && bld.hp >= bld.max_hp)) {
                worker.constructingTarget = null;
                worker.autoHarvest = true;
                worker.state = UnitState.IDLE;
                return;
            }
            const distBld = Math.hypot(worker.wx - (bld.wx + 1.0), worker.wy - (bld.wy + 1.0));
            if (distBld <= 2.6) {
                worker.waypoints = [];
                worker.state = UnitState.ATTACK; // Hammering animation
                if (bld.isConstructing) {
                    bld.constructionProgress = Math.min(1.0, (bld.constructionProgress || 0.08) + dt * 0.14);
                    bld.hp = Math.min(bld.max_hp, Math.round(bld.max_hp * (0.15 + 0.85 * bld.constructionProgress)));
                    if (bld.constructionProgress >= 1.0) {
                        bld.isConstructing = false;
                        bld.constructionProgress = 1.0;
                        bld.hp = bld.max_hp;
                        worker.constructingTarget = null;
                        worker.autoHarvest = true;
                        worker.state = UnitState.IDLE;
                        this.soundEngine.play('decidebuild', bld.wx, bld.wy, this.camera);
                        this.addFloatingText(bld.wx, bld.wy, `🏰 ${bld.name} 완공!`, '#ffd700');
                        this.announceSystemMessage(`🏰 [${bld.name}] 건설이 완료되었습니다!`, '#55ff77');
                        this.updateResourceHUD();
                    }
                } else {
                    bld.hp = Math.min(bld.max_hp, bld.hp + dt * 180);
                }
            } else if (worker.state === UnitState.IDLE) {
                worker.moveTo(Math.round(bld.wx) + 1, Math.round(bld.wy) + 1, this.grid);
            }
            return;
        }

        if (!worker.autoHarvest) return;

        // 2. Drop off harvested grain/wood at the NEAREST completed HQ (본영) or Mill (방앗간)!
        let dropoff = null;
        let bestDropDist = 9999;
        for (const e of this.entities) {
            if (!e || e.isDead || !e.isBuilding || e.isConstructing || e.owner !== worker.owner) continue;
            if (e.name && (e.name.includes('본영') || e.name.includes('방앗간'))) {
                const d = Math.hypot(worker.wx - (e.wx + 1.0), worker.wy - (e.wy + 1.5));
                if (d < bestDropDist) {
                    bestDropDist = d;
                    dropoff = e;
                }
            }
        }
        if (!dropoff) dropoff = { wx: 21, wy: 14 };

        const dropGx = Math.round(dropoff.wx) + 2;
        const dropGy = Math.round(dropoff.wy) + 2;

        if (worker.carryingAmount > 0) {
            const distToHq = Math.hypot(worker.wx - (dropoff.wx + 1.5), worker.wy - (dropoff.wy + 1.5));
            if (distToHq <= 3.1) {
                let mult = worker.harvestBonus || 1.0;
                if (this.researchedTechs.has('tech_economy')) mult *= 1.3;
                if (worker.carryingType === 100 && this.researchedTechs.has('tech_plow')) mult *= 1.5;

                const gained = Math.round(worker.carryingAmount * mult);
                if (worker.carryingType === 100) {
                    this.resources.rice += gained;
                    this.addFloatingText(dropoff.wx + 1, dropoff.wy, `+${gained} 쌀`, '#ffd700');
                } else if (worker.carryingType === 1) {
                    this.resources.potato += gained;
                    this.addFloatingText(dropoff.wx + 1, dropoff.wy, `+${gained} 감자`, '#ffd700');
                } else {
                    this.resources.wood += gained;
                    this.addFloatingText(dropoff.wx + 1, dropoff.wy, `+${gained} 목재`, '#55ff77');
                }
                worker.carryingAmount = 0;
                worker.state = UnitState.IDLE;
                this.updateResourceHUD();
                if (worker.harvestTarget) {
                    worker.moveTo(worker.harvestTarget.gx, worker.harvestTarget.gy, this.grid);
                }
            } else if (worker.state === UnitState.IDLE) {
                worker.moveTo(dropGx, dropGy, this.grid);
            }
            return;
        }

        // 3. Find nearest preferred resource tile around base
        if (!worker.harvestTarget || this.grid.resourceAmounts[worker.harvestTarget.gy * this.grid.width + worker.harvestTarget.gx] <= 0) {
            let bestTile = null;
            let bestDist = 999;
            for (let gy = 10; gy <= 29; gy++) {
                for (let gx = 13; gx <= 33; gx++) {
                    const idx = gy * this.grid.width + gx;
                    const rType = this.grid.resourceTypes[idx];
                    const rAmt = this.grid.resourceAmounts[idx];
                    if (rType > 0 && rAmt > 0) {
                        const prefBonus = (rType === worker.harvestPref) ? 0 : 10;
                        const d = Math.hypot(worker.wx - gx, worker.wy - gy) + prefBonus;
                        if (d < bestDist) {
                            bestDist = d;
                            bestTile = { gx, gy, rType };
                        }
                    }
                }
            }
            worker.harvestTarget = bestTile;
        }

        if (!worker.harvestTarget) return;

        const distToRes = Math.hypot(worker.wx - (worker.harvestTarget.gx + 0.5), worker.wy - (worker.harvestTarget.gy + 0.5));
        if (distToRes <= 1.6) {
            worker.waypoints = [];
            worker.state = UnitState.ATTACK; // Work/harvest swing animation
            worker.harvestTimer = (worker.harvestTimer || 0) + dt;
            if (worker.harvestTimer >= 2.4) {
                worker.harvestTimer = 0;
                const { gx, gy, rType } = worker.harvestTarget;
                const idx = gy * this.grid.width + gx;
                const rem = this.grid.resourceAmounts[idx] || 0;
                const taken = Math.min(rem > 0 ? rem : 12, 12);
                if (rem > 0) {
                    this.grid.resourceAmounts[idx] = Math.max(0, rem - taken);
                    if (this.grid.resourceAmounts[idx] === 0 && (rType === 100 || rType === 1)) {
                        // Turn depleted crop tile into furrowed brown field soil (밭 이랑, tileIds 23..30) for regrowth!
                        this.grid.resourceTypes[idx] = 0;
                        this.grid.setTile(gx, gy, 23 + ((gx + gy) % 8));
                        this.depletedCrops.set(`${gx},${gy}`, { gx, gy, rType, regrowProgress: 0 });
                    }
                }
                worker.carryingAmount = taken;
                worker.carryingType = rType;
                worker.state = UnitState.IDLE;
                worker.moveTo(dropGx, dropGy, this.grid);
            }
        } else if (worker.state === UnitState.IDLE) {
            worker.moveTo(worker.harvestTarget.gx, worker.harvestTarget.gy, this.grid);
        }
    }

    updateWeatherAndFires(dt) {
        // 1. System Banner Countdown
        if (this.systemBanner && this.systemBanner.timer > 0) {
            this.systemBanner.timer = Math.max(0, this.systemBanner.timer - dt);
        }

        // 2. Wind rotation & Rain duration
        this.windTimer += dt;
        if (this.windTimer >= 45.0) {
            this.windTimer = 0;
            this.windDirection = (this.windDirection + 1) % 8;
        }
        if (this.weather === 'rain') {
            this.rainTimer -= dt;
            if (this.rainTimer <= 0) {
                this.weather = 'sunny';
                this.announceSystemMessage('☀️ 기우제 비가 그치고 전장이 맑아졌습니다.', '#ffd700');
            }
        }

        // 3. Downwind Ground Fire Propagation & Rain Extinguishing (groundfire.Spr)
        const windVectors = [
            [0, -1], [0.7, -0.7], [1, 0], [0.7, 0.7],
            [0, 1], [-0.7, 0.7], [-1, 0], [-0.7, -0.7]
        ];
        const [wdx, wdy] = windVectors[this.windDirection % 8];

        for (let i = this.groundFires.length - 1; i >= 0; i--) {
            const f = this.groundFires[i];
            f.life -= (this.weather === 'rain') ? dt * 6.0 : dt * 0.35;
            if (f.life <= 0) {
                this.groundFires.splice(i, 1);
                continue;
            }
            // Gently drift fire downwind when sunny
            if (this.weather === 'sunny') {
                f.wx += wdx * dt * 0.08;
                f.wy += wdy * dt * 0.08;
                f.spreadTimer = (f.spreadTimer || 0) + dt;
                if (f.spreadTimer >= 9.0 && this.groundFires.length < 10) {
                    f.spreadTimer = 0;
                    this.groundFires.push({
                        wx: f.wx + wdx * 0.9,
                        wy: f.wy + wdy * 0.9,
                        phase: Math.floor(Math.random() * 20),
                        life: 18.0,
                        spreadTimer: 0
                    });
                }
            }
            // Burn damage to units standing directly in the fire
            for (const ent of this.entities) {
                if (ent && !ent.isDead && !ent.isBuilding) {
                    if (Math.hypot(ent.wx - f.wx, ent.wy - f.wy) < 0.85) {
                        ent.hp = Math.max(10, ent.hp - dt * 8);
                    }
                }
            }
        }

        // 4. Regrow depleted rice/potato paddies (밭 이랑 -> 황금 벼, 3x faster in Rain!)
        const regrowSpeed = (this.weather === 'rain') ? dt * 0.18 : dt * 0.05;
        for (const [key, crop] of this.depletedCrops.entries()) {
            crop.regrowProgress += regrowSpeed;
            if (crop.regrowProgress >= 1.0) {
                this.grid.setResource(crop.gx, crop.gy, crop.rType, 150);
                this.depletedCrops.delete(key);
            }
        }

        // 5. Passive Donguibogam (동의보감) healing aura if researched
        if (this.researchedTechs.has('tech_heojun')) {
            for (const ent of this.entities) {
                if (ent && !ent.isDead && !ent.isBuilding && ent.owner === 0 && ent.hp < ent.max_hp) {
                    ent.hp = Math.min(ent.max_hp, ent.hp + dt * 6);
                }
            }
        }
    }

    updateEnemyAI(dt) {
        // 1. Update Player Building Production Queues (4-slot queue on Hanji scroll, ~3.5s per unit)
        for (const b of this.entities) {
            if (!b || b.isDead || !b.isBuilding || b.isConstructing || b.owner !== 0) continue;
            if (b.productionQueue && b.productionQueue.length > 0) {
                b.prodProgress = (b.prodProgress || 0) + dt * 0.28;
                if (b === this.primaryBarracks) {
                    this.barracksProdProgress = b.prodProgress;
                }
                if (b.prodProgress >= 1.0) {
                    b.prodProgress = 0;
                    const finished = b.productionQueue.shift();
                    if (finished) {
                        const spawnGx = Math.round(b.gx) + 1;
                        const spawnGy = Math.round(b.gy) + 2;
                        const u = this.spawnUnit({ archetype: finished.archetype, faction: 0, gx: spawnGx, gy: spawnGy });
                        if (u) {
                            u.level = finished.archetype.level || 1;
                            u.exp = 0;
                            if (finished.isWorker) {
                                u.isWorker = true;
                                u.autoHarvest = true;
                                u.harvestPref = 100;
                            } else if (b.rallyPoint) {
                                u.moveTo(Math.round(b.rallyPoint.gx), Math.round(b.rallyPoint.gy), this.grid);
                            }
                            this.addFloatingText(u.wx, u.wy, `+ ${finished.archetype.korean_name} 생산 완료!`, '#4da6ff');
                            this.announceSystemMessage(`⚔️ [${finished.archetype.korean_name}] 생산이 완료되어 집결지로 이동합니다!`, '#55ff77');
                            this.refreshFKeyBar();
                        }
                    }
                }
            } else if (b === this.primaryBarracks) {
                this.barracksProdProgress = 0;
            }
        }

        // 2. Grant gradual combat EXP to frontline Heroes & combat units (ExpForLevelUp.dat)
        for (const ent of this.entities) {
            if (ent && !ent.isDead && !ent.isBuilding && ent.owner === 0 && ent.state === UnitState.ATTACK && !ent.isWorker) {
                ent.combatExpAccum = (ent.combatExpAccum || 0) + dt * 12;
                if (ent.combatExpAccum >= 20) {
                    ent.combatExpAccum = 0;
                    this.grantHeroExp(ent, 20);
                }
            }
        }

        // 3. Strategic Macro AI & Tactical Micro AI Engine updates
        if (this.macroAI && typeof this.macroAI.update === 'function') {
            this.macroAI.update(dt);
        }
        if (this.tacticalMicro && typeof this.tacticalMicro.update === 'function') {
            this.tacticalMicro.update(dt);
        }

        // 4. Maintain enemy wave timer & periodic reinforcement (backward compatibility with test_09)
        this.enemyWaveTimer += dt;
        if (this.enemyWaveTimer < 25.0) return;
        this.enemyWaveTimer = 0;

        // Periodic skirmish reinforcement from Japan outpost
        const enemyCount = this.entities.filter(e => e && !e.isDead && !e.isBuilding && e.owner === 1).length;
        const japanHq = this.entities.find(e => e && !e.isDead && e.isBuilding && e.owner === 1);
        if (japanHq && enemyCount < 7) {
            const arch = (Math.random() < 0.5) ? BUILTIN_UNIT_TEMPLATES[13] : BUILTIN_UNIT_TEMPLATES[14];
            const raidUnit = new Unit(this.nextEntityId++, arch, Math.round(japanHq.wx) - 2, Math.round(japanHq.wy) + 1, 1);
            raidUnit.isBuilding = false;
            raidUnit.moveTo(27, 26, this.grid);
            this.entities.push(raidUnit);
        }
    }

    async exportBinaryPatch(statOverrides) {
        const statusBox = document.getElementById('mod-export-status');
        if (statusBox) statusBox.textContent = '바이너리 패치 요청 중... (POST /api/patch_binary)';

        try {
            const targetUnit = this.selectedUnits[0] || this.entities.find(e => !e.isBuilding);
            const payload = {
                unit_id: targetUnit ? (targetUnit.archetype.index || 51) : 51,
                stat_name: 'speed',
                new_value: targetUnit ? targetUnit.move_speed : 14,
                target_filename: 'dawn_modded.exe'
            };

            const resp = await fetch('/api/patch_binary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (resp.ok) {
                const res = await resp.json();
                if (statusBox) statusBox.innerHTML = `✅ 패치 성공: ${res.file_path || 'dawn_modded.exe'} (${res.file_size || 1032192}B)`;
            } else {
                if (statusBox) statusBox.textContent = `⚠️ 로컬 서버 응답 오류 (${resp.status})`;
            }
        } catch (err) {
            if (statusBox) statusBox.textContent = `ℹ️ 로컬 단독 실행 중: 모드 설정이 메모리에 보관되었습니다.`;
        }
    }

    /* ----------------------------------------------------------------------
       Main 60FPS Game Loop
       ---------------------------------------------------------------------- */
    gameLoop(timestamp) {
        const rawDt = (timestamp - this.lastTime) / 1000;
        const dt = Math.max(0.001, Math.min(0.1, rawDt));
        this.lastTime = timestamp;
        this.elapsedGameTime += dt;

        // 1. Update Camera Panning & Edge Scrolling
        if (this.camera) {
            this.camera.update(dt, this.keysDown, this.mousePos);
        }

        // 2. Update Weather, Wind-Driven Fires, Crop Regrowth, Entities & Combat
        if (!this.mapEditor || !this.mapEditor.isEnabled) {
            this.updateWeatherAndFires(dt);
            this.updateEnemyAI(dt);

            for (let i = this.entities.length - 1; i >= 0; i--) {
                const ent = this.entities[i];
                if (!ent) continue;

                if (ent.isDead) {
                    if (ent.isAirUnit || ent.kindId === 0x74) {
                        // Air unit Joseon Hornet (0x74) vanishes instantly upon death with zero corpse, zero decal, and zero ground footprint
                        if (this.grid) {
                            this.grid.clearUnitOccupancy(ent.gx, ent.gy);
                        }
                        this.entities.splice(i, 1);
                        continue;
                    }
                    if (ent.isDying) {
                        ent.update(dt, this.grid, this.entities, this.soundEngine, this.projectiles);
                        if (!ent.isDying) {
                            this.entities.splice(i, 1);
                        }
                    } else {
                        this.entities.splice(i, 1);
                    }
                    continue;
                }

                if (!ent.isBuilding) {
                    if (ent.isWorker) {
                        this.updateWorkerHarvest(ent, dt);
                    }
                    ent.update(dt, this.grid, this.entities, this.soundEngine, this.projectiles);
                    CombatSystem.updateUnitCombat(ent, dt, this.entities, this.projectiles, this.soundEngine, this.grid);
                } else if (ent.updateProduction) {
                    ent.updateProduction(dt, this.grid, this);
                }
            }

            // Update Projectiles (Ignite fire on Fire Arrow / Hwacha impact!)
            for (let i = this.projectiles.length - 1; i >= 0; i--) {
                const p = this.projectiles[i];
                p.update(dt, this.soundEngine, this.entities);
                if (p.isArrived) {
                    if ((this.researchedTechs.has('tech_fire_arrow') || p.type === 'cannon') && this.groundFires.length < 10 && Math.random() < 0.25) {
                        this.groundFires.push({ wx: p.targetX, wy: p.targetY, phase: 0, life: 14.0, spreadTimer: 0 });
                    }
                    this.projectiles.splice(i, 1);
                }
            }
        }

        // 3. Update Visual Move Markers & Floating Resource Popups
        for (let i = this.moveMarkers.length - 1; i >= 0; i--) {
            this.moveMarkers[i].time += dt;
            if (this.moveMarkers[i].time >= this.moveMarkers[i].duration) {
                this.moveMarkers.splice(i, 1);
            }
        }
        for (let i = this.floatingTexts.length - 1; i >= 0; i--) {
            this.floatingTexts[i].time += dt;
            if (this.floatingTexts[i].time >= this.floatingTexts[i].duration) {
                this.floatingTexts.splice(i, 1);
            }
        }

        // 4. Render 60FPS Isometric Scene + Fire/Rain/Placement Ghost + Authentic Top Overlay
        if (this.renderer) {
            const renderEntities = this.entities.map(e => {
                if (e && e.isDying) {
                    return new Proxy(e, {
                        get(target, prop) {
                            if (prop === 'isDead') return false;
                            return target[prop];
                        }
                    });
                }
                return e;
            });
            this.renderer.render(this.grid, renderEntities, this.projectiles, this.camera);
            this.drawBattlefieldFireEffects(this.renderer.ctx);
            this.drawPendingCommandReticle(this.renderer.ctx);
            this.drawMoveMarkers(this.renderer.ctx);
            this.drawFloatingTexts(this.renderer.ctx);
            this.drawAuthenticTopOverlay(this.renderer.ctx);
        }

        // 5. Update Minimap Radar & Compass Wind Dial
        if (this.minimap) {
            this.minimap.render(this.entities);
        }
        this.drawCompassDial();

        // 6. Update Selection HUD & F1..F11 Quick-Select Bar
        if (this.selectedUnits.length > 0) {
            this.updateSelectionHUD(this.selectedUnits[0]);
        }
        if (timestamp - this.lastFKeyUpdate > 600) {
            this.lastFKeyUpdate = timestamp;
            this.refreshFKeyBar();
        }

        // 7. Update Status Bar (Timer & FPS Counter)
        this.updateStatusBar(dt, timestamp);

        requestAnimationFrame((time) => this.gameLoop(time));
    }

    drawCompassDial() {
        const c = this.dom.compassCanvas;
        if (!c) return;
        const ctx = c.getContext('2d');
        if (!ctx) return;
        const w = c.width;
        const h = c.height;
        const cx = w / 2;
        const cy = h / 2;
        ctx.clearRect(0, 0, w, h);

        // Outer bronze ring
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, 28, 0, Math.PI * 2);
        ctx.fillStyle = (this.weather === 'rain') ? 'rgba(20, 48, 75, 0.72)' : 'rgba(32, 24, 14, 0.65)';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#c89e46';
        ctx.stroke();

        // Cardinal ticks
        ctx.font = 'bold 9px "Gulim", sans-serif';
        ctx.fillStyle = '#e5cfa0';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('북', cx, cy - 20);
        ctx.fillText('남', cx, cy + 20);
        ctx.fillText('동', cx + 20, cy);
        ctx.fillText('서', cx - 20, cy);

        // Rotating wind-vane spear needle
        const angle = (this.windDirection - 2) * (Math.PI / 4);
        ctx.translate(cx, cy);
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.moveTo(16, 0);
        ctx.lineTo(-8, -5);
        ctx.lineTo(-4, 0);
        ctx.lineTo(-8, 5);
        ctx.closePath();
        ctx.fillStyle = (this.weather === 'rain') ? '#66ccff' : '#ffcc33';
        ctx.fill();
        ctx.restore();
    }

    drawBattlefieldFireEffects(ctx) {
        if (!ctx || !this.assetManager || !this.camera) return;
        const fireImg = this.assetManager.images.get('ui_groundfire');
        const expImg = this.assetManager.images.get('ui_exp0');

        ctx.save();
        const z = this.camera.zoom || 1.0;
        const tick = Math.floor(performance.now() / 65);

        // 1. Dynamic Wind-Driven Battlefield Fires (groundfire.Spr)
        if (fireImg && this.groundFires.length > 0) {
            for (const spot of this.groundFires) {
                const pos = IsometricMath.worldToScreen(spot.wx, spot.wy, 0, this.camera);
                const frameIdx = (tick + (spot.phase || 0)) % 28;
                const col = frameIdx % 9;
                const row = Math.floor(frameIdx / 9);
                const fw = 96;
                const fh = 96;
                ctx.drawImage(
                    fireImg,
                    col * fw, row * fh, fw, fh,
                    pos.x - (fw * 0.45) * z,
                    pos.y - (fh * 0.65) * z,
                    fw * 0.9 * z,
                    fh * 0.9 * z
                );
            }
        }

        // 2. Cannon/Hwacha impact explosions on active projectiles nearing arrival
        if (expImg && Array.isArray(this.projectiles)) {
            for (const p of this.projectiles) {
                if (!p || p.progress < 0.72) continue;
                const targetWx = p.targetWx !== undefined ? p.targetWx : p.targetX;
                const targetWy = p.targetWy !== undefined ? p.targetWy : p.targetY;
                const pos = IsometricMath.worldToScreen(targetWx, targetWy, 0, this.camera);
                const expFrame = Math.min(19, Math.floor(((p.progress - 0.72) / 0.28) * 20));
                const col = expFrame % 6;
                const row = Math.floor(expFrame / 6);
                const ew = 110;
                const eh = 110;
                ctx.drawImage(
                    expImg,
                    col * ew, row * eh, ew, eh,
                    pos.x - (ew * 0.42) * z,
                    pos.y - (eh * 0.58) * z,
                    ew * 0.84 * z,
                    eh * 0.84 * z
                );
            }
        }

        // 3. Farmer Building Placement Isometric Footprint Ghost (건물1 / 건물2)
        if (this.placingBuilding && this.renderer && this.renderer.hoverTile && this.renderer.hoverTile.valid) {
            const gx = this.renderer.hoverTile.gx;
            const gy = this.renderer.hoverTile.gy;
            const bw = this.placingBuilding.width || 2;
            const bh = this.placingBuilding.height || 2;
            const canAfford = this.resources.wood >= (this.placingBuilding.costWood || 0) &&
                              this.resources.rice >= (this.placingBuilding.costRice || 0);

            for (let dy = 0; dy < bh; dy++) {
                for (let dx = 0; dx < bw; dx++) {
                    const p = IsometricMath.worldToScreen(gx + dx, gy + dy, 0, this.camera);
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p.x + 32 * z, p.y + 16 * z);
                    ctx.lineTo(p.x, p.y + 32 * z);
                    ctx.lineTo(p.x - 32 * z, p.y + 16 * z);
                    ctx.closePath();
                    ctx.fillStyle = canAfford ? 'rgba(50, 230, 80, 0.35)' : 'rgba(255, 60, 60, 0.40)';
                    ctx.fill();
                    ctx.strokeStyle = canAfford ? '#32e650' : '#ff3c3c';
                    ctx.lineWidth = 1.5;
                    ctx.stroke();
                }
            }

            // Draw translucent building sprite preview
            const spr = this.assetManager.getUnitSprite(this.placingBuilding.sprite_name);
            if (spr && spr.image) {
                const f = spr.getFrame(0, 0, 'building');
                const centerPos = IsometricMath.worldToScreen(gx + bw * 0.5, gy + bh * 0.5, 0, this.camera);
                ctx.globalAlpha = 0.65;
                ctx.drawImage(spr.image, f.x, f.y, f.w, f.h, centerPos.x - (f.w / 2) * z, centerPos.y - f.hotspotY * z, f.w * z, f.h * z);
                ctx.globalAlpha = 1.0;
            }
        }


        // 4. Rain Weather Overlay (기우제 비)
        if (this.weather === 'rain') {
            ctx.strokeStyle = 'rgba(140, 205, 255, 0.42)';
            ctx.lineWidth = 1.2;
            const cw = this.canvas.width;
            const ch = this.canvas.height;
            const offset = (performance.now() * 0.4) % 240;
            ctx.beginPath();
            for (let i = 0; i < 95; i++) {
                const rx = ((i * 97 + offset * 2) % cw);
                const ry = ((i * 53 + offset * 5) % ch);
                ctx.moveTo(rx, ry);
                ctx.lineTo(rx - 8, ry + 22);
            }
            ctx.stroke();
        }

        ctx.restore();
    }

    drawPendingCommandReticle(ctx) {
        if (!ctx || !this.pendingCommand) return;

        const cmd = this.pendingCommand;
        const mx = this.mousePos ? this.mousePos.x : 0;
        const my = this.mousePos ? this.mousePos.y : 0;
        const z = this.camera ? (this.camera.zoom || 1.0) : 1.0;

        ctx.save();

        // 1. Trajectory lines for Rally and Patrol
        if (cmd.action === 'set_rally') {
            const b = this.selectedUnits.find(u => u.isBuilding);
            if (b) {
                const bPos = IsometricMath.worldToScreen(b.wx, b.wy, 0, this.camera);
                ctx.strokeStyle = '#55ff77';
                ctx.lineWidth = 1.5;
                ctx.setLineDash([6, 4]);
                ctx.beginPath();
                ctx.moveTo(bPos.x, bPos.y);
                ctx.lineTo(mx, my);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        } else if (cmd.action === 'patrol' && this.selectedUnits.length > 0) {
            const leader = this.selectedUnits[0];
            const uPos = IsometricMath.worldToScreen(leader.wx, leader.wy, 0, this.camera);
            ctx.strokeStyle = '#66ccff';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(uPos.x, uPos.y);
            ctx.lineTo(mx, my);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // 2. Projected Ground AoE / Reticle at hover tile
        if (this.renderer && this.renderer.hoverTile && this.renderer.hoverTile.valid) {
            const gx = this.renderer.hoverTile.gx;
            const gy = this.renderer.hoverTile.gy;
            const p = IsometricMath.worldToScreen(gx + 0.5, gy + 0.5, 0, this.camera);

            const now = performance.now() / 1000;
            const pulse = 0.88 + 0.12 * Math.sin(now * 6);
            const rTiles = cmd.radius || 1.0;
            const rx = rTiles * 32 * z * pulse;
            const ry = rx * 0.5;

            ctx.strokeStyle = cmd.color || '#32e650';
            ctx.lineWidth = 2.0;
            if (cmd.color && cmd.color.startsWith('#')) {
                ctx.fillStyle = (cmd.action === 'attack_ground') ? 'rgba(255, 68, 68, 0.18)' :
                                (cmd.action === 'skill_shockwave') ? 'rgba(255, 215, 0, 0.22)' :
                                (cmd.action === 'skill_firestorm') ? 'rgba(255, 85, 51, 0.22)' : 'rgba(50, 230, 80, 0.15)';
            } else {
                ctx.fillStyle = 'rgba(50, 230, 80, 0.15)';
            }

            ctx.beginPath();
            ctx.ellipse(p.x, p.y + 16 * z, rx, ry, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            // Center crosshair on ground
            ctx.beginPath();
            ctx.moveTo(p.x - 10 * z, p.y + 16 * z);
            ctx.lineTo(p.x + 10 * z, p.y + 16 * z);
            ctx.moveTo(p.x, p.y + 6 * z);
            ctx.lineTo(p.x, p.y + 26 * z);
            ctx.stroke();
        }

        // 3. Mouse Reticle Corner Brackets [ ] and Command Badge
        if (mx > 0 && my > 0) {
            ctx.strokeStyle = cmd.color || '#32e650';
            ctx.lineWidth = 2.0;

            const s = 12;
            const gap = 4;
            ctx.beginPath();
            // Top-left
            ctx.moveTo(mx - s, my - gap); ctx.lineTo(mx - s, my - s); ctx.lineTo(mx - gap, my - s);
            // Top-right
            ctx.moveTo(mx + gap, my - s); ctx.lineTo(mx + s, my - s); ctx.lineTo(mx + s, my - gap);
            // Bottom-right
            ctx.moveTo(mx + s, my + gap); ctx.lineTo(mx + s, my + s); ctx.lineTo(mx + gap, my + s);
            // Bottom-left
            ctx.moveTo(mx - gap, my + s); ctx.lineTo(mx - s, my + s); ctx.lineTo(mx - s, my + gap);
            ctx.stroke();

            // Text Badge next to cursor
            ctx.font = 'bold 12px "Malgun Gothic", "Gulim", sans-serif';
            const text = `[${cmd.name}]`;
            const tw = ctx.measureText(text).width;
            ctx.fillStyle = 'rgba(15, 12, 8, 0.85)';
            ctx.fillRect(mx + 14, my - 10, tw + 10, 20);
            ctx.strokeStyle = cmd.color || '#32e650';
            ctx.lineWidth = 1;
            ctx.strokeRect(mx + 14, my - 10, tw + 10, 20);
            ctx.fillStyle = '#ffffff';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, mx + 19, my);
        }

        ctx.restore();
    }

    drawAuthenticTopOverlay(ctx) {
        if (!ctx) return;
        ctx.save();

        // 1. Top-Left Single-Line Horizontal Resource Bar (Grain | Wood | Supply from resource.Spr)
        const resImg = this.assetManager ? (this.assetManager.images.get('ui_resource') || this.assetManager.images.get('ui_resource_icons')) : null;
        const items = [
            { frame: 0, x: 18, text: `${Math.floor(this.resources.rice)}`, fallbackColor: '#e6b800' },
            { frame: 1, x: 122, text: `${Math.floor(this.resources.wood)}`, fallbackColor: '#a06028' },
            { frame: 2, x: 226, text: `${this.resources.supplyUsed}/${this.resources.supplyMax}`, fallbackColor: '#d4af37' }
        ];

        ctx.font = 'bold 15px "Gulim", "Malgun Gothic", monospace';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        const y = 20;
        items.forEach((item) => {
            if (resImg) {
                ctx.drawImage(resImg, item.frame * 20, 0, 20, 24, item.x, y - 12, 22, 24);
            } else {
                ctx.fillStyle = item.fallbackColor;
                ctx.fillRect(item.x, y - 7, 14, 14);
            }
            ctx.fillStyle = '#000000';
            ctx.fillText(item.text, item.x + 27, y + 1);
            ctx.fillText(item.text, item.x + 25, y + 1);
            ctx.fillStyle = '#f4efe1';
            ctx.fillText(item.text, item.x + 26, y);
        });

        // 2. Authentic Imjinrok 2+ System Notification Ticker & syw2x.dll F12 Clock + Wind/Weather Indicator
        // Positioned at x=340..740 so it never overlaps the top-right toolbar (#top-bar)
        const dirNames = ['북풍 ↑', '북동풍 ↗', '동풍 →', '남동풍 ↘', '남풍 ↓', '남서풍 ↙', '서풍 ←', '북서풍 ↖'];
        const weatherLabel = (this.weather === 'rain')
            ? `🌧️ 기우제 비 (${Math.ceil(this.rainTimer)}초)`
            : `☀️ 맑음 · ${dirNames[this.windDirection % 8]}`;

        if (this.showF12Clock) {
            const totalSec = Math.floor(this.elapsedGameTime);
            const hrs = String(Math.floor(totalSec / 3600)).padStart(2, '0');
            const min = String(Math.floor((totalSec % 3600) / 60)).padStart(2, '0');
            const sec = String(totalSec % 60).padStart(2, '0');
            const clockStr = `${hrs}:${min}:${sec}  [${weatherLabel}]`;

            ctx.font = 'bold 13px "Gulim", "Malgun Gothic", monospace';
            ctx.textAlign = 'left';
            ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
            ctx.fillText(clockStr, 341, 21);
            ctx.fillStyle = (this.weather === 'rain') ? '#80d8ff' : '#ffd700';
            ctx.fillText(clockStr, 340, 20);
        }

        if (this.systemBanner && this.systemBanner.timer > 0 && this.systemBanner.text) {
            const bx = 18;
            const by = 44;
            ctx.font = 'bold 13px "Malgun Gothic", "Gulim", sans-serif';
            ctx.textAlign = 'left';
            ctx.lineWidth = 3;
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)';
            ctx.strokeText(`📢 ${this.systemBanner.text}`, bx, by);
            ctx.fillStyle = this.systemBanner.color || '#ffd700';
            ctx.fillText(`📢 ${this.systemBanner.text}`, bx, by);
        }

        ctx.restore();
    }

    drawMoveMarkers(ctx) {
        if (!ctx || this.moveMarkers.length === 0) return;

        ctx.save();
        for (const m of this.moveMarkers) {
            const progress = m.time / m.duration;
            const pos = IsometricMath.worldToScreen(m.wx, m.wy, m.elev, this.camera);
            const radius = 10 + progress * 24;
            const alpha = Math.max(0, 1.0 - progress);

            ctx.strokeStyle = (m.type === 'attack') ? `rgba(255, 30, 30, ${alpha})` : `rgba(0, 255, 60, ${alpha})`;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.ellipse(pos.x, pos.y + 24, radius, radius * 0.5, 0, 0, Math.PI * 2);
            ctx.stroke();

            // Inner pulse dot
            ctx.fillStyle = ctx.strokeStyle;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y + 24, 3 * (1 - progress), 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    }

    drawFloatingTexts(ctx) {
        if (!ctx || this.floatingTexts.length === 0) return;
        ctx.save();
        ctx.font = 'bold 13px "Malgun Gothic", sans-serif';
        ctx.textAlign = 'center';
        for (const ft of this.floatingTexts) {
            const progress = ft.time / ft.duration;
            const alpha = Math.max(0, 1.0 - progress);
            const pos = IsometricMath.worldToScreen(ft.wx, ft.wy, 0, this.camera);
            const yOffset = -28 - progress * 28;
            ctx.fillStyle = `rgba(0, 0, 0, ${alpha * 0.8})`;
            ctx.fillText(ft.text, pos.x + 1, pos.y + yOffset + 1);
            ctx.fillStyle = ft.color;
            ctx.globalAlpha = alpha;
            ctx.fillText(ft.text, pos.x, pos.y + yOffset);
            ctx.globalAlpha = 1.0;
        }
        ctx.restore();
    }

    updateStatusBar(dt, timestamp) {
        // Game Timer
        if (this.dom.gameTimer) {
            const totalSec = Math.floor(this.elapsedGameTime);
            const min = String(Math.floor(totalSec / 60)).padStart(2, '0');
            const sec = String(totalSec % 60).padStart(2, '0');
            this.dom.gameTimer.textContent = `${min}:${sec}`;
        }

        // FPS Calculation
        this.fpsHistory.push(1 / dt);
        if (this.fpsHistory.length > 30) this.fpsHistory.shift();

        if (timestamp - this.lastFpsUpdate > 500) {
            this.lastFpsUpdate = timestamp;
            const avgFps = Math.round(this.fpsHistory.reduce((a, b) => a + b, 0) / this.fpsHistory.length);
            this.currentFps = avgFps;
            if (this.dom.fpsCounter) {
                this.dom.fpsCounter.textContent = `${avgFps} FPS`;
            }
        }
    }

    /* ----------------------------------------------------------------------
       Automated Test & Headless Browser Integration Bridge
       ---------------------------------------------------------------------- */
    registerAutomationBridge() {
        window.gameEngine = {
            app: this,
            grid: this.grid,
            camera: this.camera,
            renderer: this.renderer,
            audio: this.soundEngine,
            minimap: this.minimap,
            commandCard: this.commandCard,
            liveModdingStudio: this.liveModding,
            mapEditor: this.mapEditor,
            entities: this.entities,
            projectiles: this.projectiles,
            macroAI: this.macroAI,
            tacticalMicro: this.tacticalMicro,
            difficulty: this.difficulty,
            difficultyConfig: this.difficultyConfig,
            playerResources: this.playerResources,
            setDifficulty: (tier) => this.setDifficulty(tier),
            getPlayerResources: (player) => this.getPlayerResources(player),
            BUILTIN_UNIT_TEMPLATES: BUILTIN_UNIT_TEMPLATES,

            // Core Headless Test APIs
            getSelectedUnitSpeed: () => {
                const slider = document.getElementById('input-move-speed');
                if (this.selectedUnits.length > 0 && this.selectedUnits[0].move_speed !== undefined) {
                    return this.selectedUnits[0].move_speed;
                }
                return slider ? parseFloat(slider.value) : 12;
            },

            setSelectedUnitSpeed: (speed) => {
                const spd = parseFloat(speed);
                for (const u of this.selectedUnits) {
                    u.move_speed = spd;
                }
                const slider = document.getElementById('input-move-speed');
                if (slider) slider.value = spd;
                const valLabel = document.getElementById('val-speed');
                if (valLabel) valLabel.textContent = spd;
            },

            getEntities: () => this.entities,
            getGrid: () => this.grid,
            getCamera: () => this.camera,
            getRenderer: () => this.renderer,
            spawnUnit: (def) => this.spawnUnit(def),
            selectUnit: (unit) => this.selectSingleUnit(unit),
            isLoaded: true
        };
        if (typeof window !== 'undefined') {
            window.BUILTIN_UNIT_TEMPLATES = BUILTIN_UNIT_TEMPLATES;
        }
    }
}

/* --------------------------------------------------------------------------
   Auto-Bootstrap on DOMContentLoaded
   -------------------------------------------------------------------------- */
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        const app = new GameApp();
        app.start().catch((err) => {
            console.error('[Imjinrok 2+ Web RTS] Initialization error:', err);
        });
    });
}
