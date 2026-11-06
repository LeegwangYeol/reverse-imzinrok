/**
 * Isometric Multi-Layer Canvas Renderer for Imjinrok 2+: Dawn
 *
 * Implements high-performance 60FPS Canvas 2D multi-layer rendering pipeline:
 * - Dynamic frustum culling limiting rendering to visible bounds
 * - Strict DepthKey sorting: (gx + gy) * 10000 + LayerPriority * 100 + sub_y
 * - Multi-layer drawing: Ground tiles, resources, buildings, units, projectiles with parabolic arc
 * - Selection circles, drag-box selection rectangle, directional frame offsets and unit scaling
 * - Health and Mana bars with Alt key toggle for all on-screen units (per syw2x.dll enhancement)
 */

import { IsometricMath, DIR8_TO_JOYMAX5 } from './isometric.js';
import { UnitState, CUSTOM_JOSEON_ANIM_SPECS } from '../simulation/entities.js';

export { CUSTOM_JOSEON_ANIM_SPECS };

export class IsometricRenderer {
    /**
     * @param {HTMLCanvasElement} canvas - Target HTML5 canvas element
     * @param {Object} [assetManager=null] - Asset manager providing sprites, tiles, and sounds
     */
    constructor(canvas, assetManager = null) {
        this.canvas = canvas;
        this.ctx = canvas ? canvas.getContext('2d', { alpha: false }) : null;
        this.assetManager = assetManager;

        // Health & Mana bar toggle (Alt key per syw2x.dll)
        this.showAllHealthBars = false;

        // Active drag selection box: { active: boolean, startX: number, startY: number, currentX: number, currentY: number }
        this.selectionBox = null;

        // Hovered tile indicator: { gx: number, gy: number, valid: boolean } | null
        this.hoverTile = null;

        // Active RTS Pending Command Reticle: { action, name, color, ... } and mouse position
        this.pendingCommand = null;
        this.currentMousePos = null;

        // Performance & FPS tracking
        this.fps = 60;
        this.frameCount = 0;
        this.lastFpsTimestamp = performance.now ? performance.now() : Date.now();
        this.renderQueueLength = 0;

        // Layer priorities matching WEB_ENGINE_BLUEPRINT
        this.LAYER_PRIORITY = {
            TILE: 0,
            DECAL: 1,
            RESOURCE: 2,
            BUILDING: 3,
            UNIT: 4,
            AIR_UNIT: 8,
            PROJECTILE: 9
        };

        this.initKeyboardListeners();
    }

    /**
     * Initializes global keyboard listeners for Alt key health/mana bar display (syw2x.dll hook).
     */
    initKeyboardListeners() {
        if (typeof window === 'undefined') return;

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Alt' || e.code === 'AltLeft' || e.code === 'AltRight') {
                this.showAllHealthBars = true;
            }
        });

        window.addEventListener('keyup', (e) => {
            if (e.key === 'Alt' || e.code === 'AltLeft' || e.code === 'AltRight') {
                this.showAllHealthBars = false;
            }
        });
    }

    /**
     * Programmatically toggles or sets the visibility of health/mana bars for all units.
     *
     * @param {boolean} [forceState] - If provided, sets explicitly to this boolean state
     * @returns {boolean} New state of showAllHealthBars
     */
    toggleAllHealthBars(forceState) {
        this.showAllHealthBars = (forceState !== undefined) ? !!forceState : !this.showAllHealthBars;
        return this.showAllHealthBars;
    }

    /**
     * Sets or updates the active drag-selection box coordinates.
     *
     * @param {number} startX - Mouse start X in screen pixels
     * @param {number} startY - Mouse start Y in screen pixels
     * @param {number} currentX - Mouse current X in screen pixels
     * @param {number} currentY - Mouse current Y in screen pixels
     */
    setSelectionBox(startX, startY, currentX, currentY) {
        this.selectionBox = { active: true, startX, startY, currentX, currentY };
    }

    /**
     * Clears the active drag-selection box.
     */
    clearSelectionBox() {
        this.selectionBox = null;
    }

    /**
     * Sets the hovered tile for grid highlight rendering.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {boolean} [valid=true] - Whether tile is within bounds
     */
    setHoverTile(gx, gy, valid = true) {
        this.hoverTile = { gx, gy, valid };
    }

    /**
     * Sets or clears the active RTS pending command reticle state.
     *
     * @param {Object|null} pendingCommand - Command descriptor or null to clear
     * @param {{ x: number, y: number }|null} [mousePos=null] - Screen mouse coordinates
     */
    setPendingCommand(pendingCommand, mousePos = null) {
        this.pendingCommand = pendingCommand;
        if (mousePos) {
            this.currentMousePos = mousePos;
        }
    }

    /**
     * Updates current mouse position for canvas reticle rendering.
     *
     * @param {number} x - Mouse screen X
     * @param {number} y - Mouse screen Y
     */
    setMousePosition(x, y) {
        this.currentMousePos = { x, y };
    }

    /**
     * Primary 60FPS multi-layer rendering pipeline.
     *
     * @param {Object} grid - GameGrid instance containing 180x180 layers
     * @param {Array<Object>} [entities=[]] - Active Unit and Building entities
     * @param {Array<Object>} [projectiles=[]] - Active Projectile entities
     * @param {Object} [camera={ x: 0, y: 0, viewportWidth: 1024, viewportHeight: 768 }] - Camera controller
     * @param {Object|null} [pendingCommand=null] - Active RTS pending command descriptor { action, name, color, ... }
     * @param {{ x: number, y: number }|null} [mousePos=null] - Screen mouse coordinates
     */
    render(grid, entities = [], projectiles = [], camera = { x: 0, y: 0, viewportWidth: 1024, viewportHeight: 768 }, pendingCommand = null, mousePos = null) {
        if (!this.ctx && this.canvas) {
            this.ctx = this.canvas.getContext('2d', { alpha: false });
        }
        const ctx = this.ctx;
        if (!ctx) return;

        const viewportWidth = this.canvas ? this.canvas.width : (camera.viewportWidth || 1024);
        const viewportHeight = this.canvas ? this.canvas.height : (camera.viewportHeight || 768);
        const mapWidth = grid ? (grid.width || 180) : 180;
        const mapHeight = grid ? (grid.height || 180) : 180;

        // 1. Fill viewport with authentic stone-grey terrain base + world-locked 1:1 rock texture
        ctx.fillStyle = '#6c6658';
        ctx.fillRect(0, 0, viewportWidth, viewportHeight);
        if (this.assetManager && this.assetManager.stoneGroundCanvas) {
            const sg = this.assetManager.stoneGroundCanvas;
            const sw = sg.width;
            const sh = sg.height;
            const offX = ((Math.floor(camera.x) % sw) + sw) % sw;
            const offY = ((Math.floor(camera.y) % sh) + sh) % sh;
            for (let y = -offY; y < viewportHeight; y += sh) {
                for (let x = -offX; x < viewportWidth; x += sw) {
                    ctx.drawImage(sg, x, y);
                }
            }
        }

        // 2. Frustum Culling: Calculate visible tile bounds
        const bounds = IsometricMath.getVisibleTileBounds(camera, viewportWidth, viewportHeight, mapWidth, mapHeight);

        // 3. Build Depth-Sorted Render Queue
        const renderQueue = [];

        // Collect visible terrain tiles and resources
        if (grid) {
            for (let gy = bounds.minGy; gy <= bounds.maxGy; gy++) {
                for (let gx = bounds.minGx; gx <= bounds.maxGx; gx++) {
                    const idx = gy * mapWidth + gx;
                    const tileId1 = grid.tileLayer1 ? grid.tileLayer1[idx] : 0;
                    const tileId2 = grid.tileLayer2 ? grid.tileLayer2[idx] : 0;
                    const elev = grid.elevation ? grid.elevation[idx] : 0;
                    const walkability = grid.walkability ? grid.walkability[idx] : 0;
                    const terrainType = grid.terrainType ? grid.terrainType[idx] : 2;

                    // Layer 0: Ground Tile
                    renderQueue.push({
                        depthKey: IsometricMath.getDepthKey(gx, gy, this.LAYER_PRIORITY.TILE, 0),
                        type: 'tile',
                        gx,
                        gy,
                        elev,
                        tileId1,
                        tileId2,
                        terrainType,
                        walkability
                    });

                    // Layer 2: Harvestable Resource Nodes (Crops, Rice, Bamboo, Trees)
                    if (grid.resourceTypes) {
                        const resType = grid.resourceTypes[idx];
                        if (resType > 0) {
                            const resAmount = grid.resourceAmounts ? grid.resourceAmounts[idx] : 100;
                            renderQueue.push({
                                depthKey: IsometricMath.getDepthKey(gx, gy, this.LAYER_PRIORITY.RESOURCE, 0),
                                type: 'resource',
                                gx,
                                gy,
                                elev,
                                resType,
                                resAmount
                            });
                        }
                    }
                }
            }
        }

        // Collect visible Entities (Units, Heroes, Buildings)
        const entityMargin = 2;
        const now = performance.now ? performance.now() : Date.now();
        for (const ent of entities) {
            if (!ent) continue;

            const isCorpse = Boolean(ent.state === 'CORPSE_DECAY' || ent.state === UnitState.CORPSE_DECAY);
            const isDead = Boolean(ent.isDead);
            const isDieState = (ent.state === 'DIE' || ent.state === 'die');
            const isDying = (isDieState || ent._isDyingAnim || (isDead && !ent.deathAnimDone)) && !isCorpse;

            // Air unit (0x74 조선왕벌, isAirUnit): Instant vanish upon death! Zero corpse decay, zero decal, zero footprint
            const isAir = Boolean(
                ent.isAirUnit ||
                ent.unitType === 'air' ||
                ent.kindId === 0x74 ||
                (ent.archetype && (ent.archetype.isAirUnit || ent.archetype.is_air || ent.archetype.kind_id === 0x74)) ||
                (ent.spriteName && (ent.spriteName.toLowerCase().includes('bat') || ent.spriteName.toLowerCase().includes('hornet')))
            );
            if (isAir && isDead) {
                continue;
            }

            // If unit is dead and finished its death animation (and not a decaying corpse), cull it from rendering
            if (isDead && !isDying && !isCorpse) {
                continue;
            }

            // If unit just died or is in DIE state (fallback for units without internal simulation death timer), update timer
            if (isDying && !ent.animSpec && ent.deathTimer === undefined) {
                if (ent._deathTimer === undefined) {
                    ent._deathTimer = 0.8; // 800ms death animation duration
                    ent._deathFrame = 0;
                    ent._deathLastTime = now;
                    ent._isDyingAnim = true;
                } else {
                    const dt = Math.max(0, Math.min(0.2, (now - (ent._deathLastTime || now)) / 1000));
                    ent._deathLastTime = now;
                    ent._deathTimer = Math.max(0, ent._deathTimer - dt);
                    // 8-frame death animation (frames 0..7)
                    ent._deathFrame = Math.min(7, Math.max(0, Math.floor((1 - (ent._deathTimer / 0.8)) * 8)));
                    if (ent._deathTimer <= 0) {
                        ent.deathAnimDone = true;
                        ent._isDyingAnim = false;
                        continue; // Culled after full death animation has played
                    }
                }
            }

            const egx = Math.floor(ent.wx !== undefined ? ent.wx : ent.gx);
            const egy = Math.floor(ent.wy !== undefined ? ent.wy : ent.gy);

            // Bounds check with safety margin
            if (egx >= bounds.minGx - entityMargin && egx <= bounds.maxGx + entityMargin &&
                egy >= bounds.minGy - entityMargin && egy <= bounds.maxGy + entityMargin) {

                // Calculate sub-tile Y for smooth depth-passing: range [0..99]
                const wx = ent.wx !== undefined ? ent.wx : (ent.gx + 0.5);
                const wy = ent.wy !== undefined ? ent.wy : (ent.gy + 0.5);
                const subX = wx - Math.floor(wx);
                const subY = wy - Math.floor(wy);
                const subYFactor = Math.max(0, Math.min(99, Math.floor((subX + subY) * 50)));

                const priority = isAir ? this.LAYER_PRIORITY.AIR_UNIT :
                                (ent.isBuilding ? this.LAYER_PRIORITY.BUILDING : this.LAYER_PRIORITY.UNIT);

                renderQueue.push({
                    depthKey: IsometricMath.getDepthKey(egx, egy, priority, subYFactor),
                    type: ent.isBuilding ? 'building' : 'unit',
                    entity: ent,
                    gx: egx,
                    gy: egy
                });
            }
        }

        // Collect Projectiles (Arrows, Cannonballs, Bullets, Spells)
        for (const proj of projectiles) {
            if (!proj || proj.isArrived) continue;

            const pos = proj.getCurrentPos ? proj.getCurrentPos() : {
                wx: proj.wx || 0,
                wy: proj.wy || 0,
                arcZ: proj.arcZ || 0
            };

            const pgx = Math.floor(pos.wx);
            const pgy = Math.floor(pos.wy);

            renderQueue.push({
                depthKey: IsometricMath.getDepthKey(pgx, pgy, this.LAYER_PRIORITY.PROJECTILE, 0),
                type: 'projectile',
                proj,
                pos
            });
        }

        // 4. Depth Sorting: Strictly sort by integer DepthKey
        renderQueue.sort((a, b) => a.depthKey - b.depthKey);
        this.renderQueueLength = renderQueue.length;

        // 5. Draw All Sorted Render Items
        for (let i = 0; i < renderQueue.length; i++) {
            const item = renderQueue[i];
            switch (item.type) {
                case 'tile':
                    this.drawTile(ctx, item, camera);
                    break;
                case 'resource':
                    this.drawResource(ctx, item, camera);
                    break;
                case 'building':
                    this.drawBuilding(ctx, item.entity, camera, grid);
                    break;
                case 'unit':
                    this.drawUnit(ctx, item.entity, camera, grid);
                    break;
                case 'projectile':
                    this.drawProjectile(ctx, item, camera);
                    break;
            }
        }

        // 6. Draw Screen-Space Overlays (Hover tile, Drag selection box, Pending Command Reticle)
        this.drawHoverTile(ctx, camera, grid);
        this.drawSelectionBox(ctx);

        const activeCmd = pendingCommand || this.pendingCommand;
        const activeMouse = mousePos || this.currentMousePos;
        if (activeCmd && activeMouse) {
            this.drawPendingCommandReticle(ctx, activeCmd, activeMouse, entities, grid, camera);
        }

        this.updateFps();
    }

    /**
     * Draws a single ground tile at (gx, gy) with discrete elevation and optional layer 2 overlay.
     */
    drawTile(ctx, item, camera) {
        const pos = IsometricMath.gridToScreen(item.gx, item.gy, item.elev, camera);

        // 1. Always draw 3D elevation drop sides if tile has elevation > 0
        if (item.elev > 0) {
            const dropH = item.elev * 16;
            ctx.fillStyle = '#2a1e12'; // Shadowed cliff face
            ctx.beginPath();
            ctx.moveTo(pos.x - 32, pos.y + 24);
            ctx.lineTo(pos.x, pos.y + 48);
            ctx.lineTo(pos.x, pos.y + 48 + dropH);
            ctx.lineTo(pos.x - 32, pos.y + 24 + dropH);
            ctx.closePath();
            ctx.fill();

            ctx.fillStyle = '#3a2b1a'; // Lit cliff face
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y + 48);
            ctx.lineTo(pos.x + 32, pos.y + 24);
            ctx.lineTo(pos.x + 32, pos.y + 24 + dropH);
            ctx.lineTo(pos.x, pos.y + 48 + dropH);
            ctx.closePath();
            ctx.fill();
        }

        // 2. Try to draw authentic diamond-clipped tile from assetManager (for non-water tiles)
        let tileDrawn = false;
        if (this.assetManager && item.terrainType !== 1 && item.walkability <= 1) {
            const tileKey = item.tileId1 || ((item.gx * 5 + item.gy * 11) % 18 + 1);
            if (this.assetManager.stoneGroundCanvas && tileKey <= 18 && item.elev === 0) {
                // Continuous world-locked 1:1 stone ground already covers flat stone tiles seamlessly
                tileDrawn = true;
            } else {
                const tileImg = this.assetManager.getTileImage ? this.assetManager.getTileImage(tileKey) :
                               (this.assetManager.getTile ? this.assetManager.getTile(tileKey) : null);
                if (tileImg) {
                    ctx.drawImage(tileImg, pos.x - 33, pos.y - 1, 66, 50);
                    tileDrawn = true;
                }
            }
        }

        // 3. Fallback procedural diamond tile rendering (or water / cliff tiles)
        // Seamless 1px texture bleed overlap, ZERO artificial wireframe grid strokes!
        if (!tileDrawn) {
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y - 1);
            ctx.lineTo(pos.x + 33, pos.y + 24);
            ctx.lineTo(pos.x, pos.y + 49);
            ctx.lineTo(pos.x - 33, pos.y + 24);
            ctx.closePath();

            if (item.terrainType === 1) {
                ctx.fillStyle = ((item.gx + item.gy) % 2 === 0) ? '#1b4972' : '#184268';
            } else if (item.walkability > 1) {
                ctx.fillStyle = ((item.gx + item.gy) % 2 === 0) ? '#4a3d2c' : '#433727';
            } else if (item.elev > 0) {
                ctx.fillStyle = '#4f663c';
            } else {
                ctx.fillStyle = ((item.gx + item.gy) % 2 === 0) ? '#395228' : '#354c24';
            }

            ctx.fill();
        }
    }

    /**
     * Draws a resource node (crop, bamboo, tree, rice).
     */
    drawResource(ctx, item, camera) {
        const pos = IsometricMath.gridToScreen(item.gx, item.gy, item.elev, camera);

        // Try assetManager sprite (sliced frame or single image)
        if (this.assetManager) {
            const resSprite = this.assetManager.getResourceSprite ?
                this.assetManager.getResourceSprite(item.resType, item.gx, item.gy) : null;
            if (resSprite && resSprite.image) {
                if (resSprite.sw && resSprite.sh) {
                    if (item.resType === 4) {
                        // Dense golden rice paddy: 2 sheaves per tile like yt_maxres1.jpg
                        ctx.drawImage(
                            resSprite.image,
                            resSprite.sx || 0,
                            resSprite.sy || 0,
                            resSprite.sw,
                            resSprite.sh,
                            pos.x - (resSprite.ox || 32) - 10,
                            pos.y + 24 - (resSprite.oy || 24) - 6,
                            resSprite.sw,
                            resSprite.sh
                        );
                        ctx.drawImage(
                            resSprite.image,
                            resSprite.sx || 0,
                            resSprite.sy || 0,
                            resSprite.sw,
                            resSprite.sh,
                            pos.x - (resSprite.ox || 32) + 12,
                            pos.y + 24 - (resSprite.oy || 24) + 6,
                            resSprite.sw,
                            resSprite.sh
                        );
                    } else {
                        ctx.drawImage(
                            resSprite.image,
                            resSprite.sx || 0,
                            resSprite.sy || 0,
                            resSprite.sw,
                            resSprite.sh,
                            pos.x - (resSprite.ox || 32),
                            pos.y + 24 - (resSprite.oy || 24),
                            resSprite.sw,
                            resSprite.sh
                        );
                    }
                } else {
                    ctx.drawImage(resSprite.image, pos.x - 16, pos.y - 16);
                }
                return;
            }
        }

        // Procedural resource representation
        const centerX = pos.x;
        const centerY = pos.y + 24;

        ctx.save();
        switch (item.resType) {
            case 3: // Forest Tree
                // Tree shadow
                ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
                ctx.beginPath();
                ctx.ellipse(centerX, centerY + 2, 16, 8, 0, 0, Math.PI * 2);
                ctx.fill();

                // Trunk
                ctx.fillStyle = '#4b3319';
                ctx.fillRect(centerX - 3, centerY - 20, 6, 20);

                // Foliage canopy
                ctx.fillStyle = '#1e5922';
                ctx.beginPath();
                ctx.arc(centerX, centerY - 26, 16, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#2e7a33';
                ctx.beginPath();
                ctx.arc(centerX - 3, centerY - 30, 11, 0, Math.PI * 2);
                ctx.fill();
                break;

            case 2: // Bamboo grove
                ctx.fillStyle = '#2e7d32';
                for (let b = -6; b <= 6; b += 6) {
                    ctx.fillRect(centerX + b - 1, centerY - 24, 3, 24);
                }
                ctx.fillStyle = '#66bb6a';
                ctx.beginPath();
                ctx.arc(centerX, centerY - 24, 7, 0, Math.PI * 2);
                ctx.fill();
                break;

            case 100: // Ripe Rice Field
                ctx.fillStyle = '#bfa134';
                ctx.beginPath();
                ctx.ellipse(centerX, centerY - 4, 18, 10, 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#f9e068';
                ctx.fillRect(centerX - 2, centerY - 14, 4, 12);
                break;

            case 1: // Potato / Crop
            default:
                ctx.fillStyle = '#5c4033';
                ctx.beginPath();
                ctx.ellipse(centerX, centerY - 2, 14, 8, 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#7cb342';
                ctx.beginPath();
                ctx.arc(centerX, centerY - 8, 5, 0, Math.PI * 2);
                ctx.fill();
                break;
        }
        ctx.restore();
    }

    /**
     * Draws a unit or hero entity with selection ring, directional frame offsets, scale, and health/mana bars.
     */
    drawUnit(ctx, unit, camera, grid) {
        const elev = (grid && grid.elevation) ?
            (grid.elevation[Math.floor(unit.wy !== undefined ? unit.wy : unit.gy) * (grid.width || 180) + Math.floor(unit.wx !== undefined ? unit.wx : unit.gx)] || 0) : 0;

        const wx = unit.wx !== undefined ? unit.wx : (unit.gx + 0.5);
        const wy = unit.wy !== undefined ? unit.wy : (unit.gy + 0.5);
        const pos = IsometricMath.worldToScreen(wx, wy, elev, camera);
        const scale = unit.scale || 1.0;

        const isCorpse = Boolean(unit.state === 'CORPSE_DECAY' || (typeof UnitState !== 'undefined' && unit.state === UnitState.CORPSE_DECAY));
        const isDying = Boolean(unit.isDying || unit.state === 'DIE' || unit.state === 'die' || unit._isDyingAnim);
        const isDyingOrDead = Boolean(unit.isDead || isDying || isCorpse);

        const isAir = Boolean(
            unit.isAirUnit ||
            unit.unitType === 'air' ||
            unit.kindId === 0x74 ||
            (unit.archetype && (unit.archetype.isAirUnit || unit.archetype.is_air || unit.archetype.kind_id === 0x74)) ||
            (unit.spriteName && (unit.spriteName.toLowerCase().includes('bat') || unit.spriteName.toLowerCase().includes('hornet')))
        );
        const flightAltitude = isAir ? (unit.flightAltitude || 36) : 0;

        // 1. Subtle dark ground shadow for living units (suppressed for dead, dying, and corpse decay)
        // Selection circle: render green selection circle strictly for living selected units!
        ctx.save();
        if (!isDyingOrDead) {
            if (isAir) {
                // Air unit: ground shadow rendered on terrain below, diffused and attenuated
                ctx.fillStyle = 'rgba(0, 0, 0, 0.22)';
                ctx.beginPath();
                ctx.ellipse(pos.x, pos.y + 24, 10 * scale, 5 * scale, 0, 0, Math.PI * 2);
                ctx.fill();
            } else {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
                ctx.beginPath();
                ctx.ellipse(pos.x, pos.y + 24, 12 * scale, 6 * scale, 0, 0, Math.PI * 2);
                ctx.fill();
            }

            if (unit.selected) {
                ctx.strokeStyle = (unit.owner === 0) ? '#2ecc40' : ((unit.owner === 1) ? '#ff4444' : '#3498db');
                ctx.lineWidth = 1.8;
                ctx.beginPath();
                ctx.ellipse(pos.x, pos.y + 24, 16 * scale, 8 * scale, 0, 0, Math.PI * 2);
                ctx.stroke();
            }
        }
        ctx.restore();

        // 2. Unit Sprite with Joymax 5-direction + East horizontal flip (DDLT_MIRRORLEFTRIGHT)
        let spriteDrawn = false;
        if (this.assetManager) {
            const sprite = this.assetManager.getUnitSprite ? this.assetManager.getUnitSprite(unit.spriteName) :
                          (this.assetManager.getSprite ? this.assetManager.getSprite(unit.spriteName) : null);

            if (sprite && sprite.image) {
                const dir = unit.direction || 0;
                const frameIndex = isCorpse ? 0 : (isDying ? (unit.animFrame !== undefined ? unit.animFrame : (unit._deathFrame !== undefined ? unit._deathFrame : 0)) : (unit.animFrame || 0));
                const state = isCorpse ? 'CORPSE_DECAY' : (isDying ? 'DIE' : (unit.state || 'IDLE'));

                const frame = this.resolveUnitFrame(sprite, unit, dir, frameIndex, state);

                if (frame) {
                    ctx.save();
                    if (isCorpse) {
                        // Dissolve corpseAlpha linearly from 1.0 to 0.0 over the last 1.0s of decay
                        const alpha = (unit.corpseAlpha !== undefined) ? unit.corpseAlpha : 1.0;
                        ctx.globalAlpha = Math.max(0, Math.min(1.0, alpha));
                    } else if (isDying && unit._deathTimer !== undefined && unit._deathTimer < 0.2) {
                        ctx.globalAlpha = Math.max(0.15, unit._deathTimer / 0.2);
                    } else if (unit.isIllusion) {
                        ctx.globalAlpha = 0.70;
                    }

                    // Apply flight altitude elevation to air units (sprite flies above ground shadow)
                    ctx.translate(pos.x, pos.y + 24 - flightAltitude);
                    ctx.scale(frame.flipX ? -scale : scale, scale);
                    ctx.drawImage(
                        sprite.image,
                        frame.x || 0,
                        frame.y || 0,
                        frame.w || frame.width || 64,
                        frame.h || frame.height || 64,
                        -(frame.hotspotX || (frame.w ? frame.w / 2 : 32)),
                        -(frame.hotspotY || (frame.h ? frame.h * 0.78 : 48)),
                        frame.w || 64,
                        frame.h || 64
                    );
                    ctx.restore();
                    spriteDrawn = true;
                }
            }
        }

        // Procedural fallback token
        if (!spriteDrawn) {
            ctx.save();
            if (isCorpse) {
                const alpha = (unit.corpseAlpha !== undefined) ? unit.corpseAlpha : 1.0;
                ctx.globalAlpha = Math.max(0, Math.min(1.0, alpha));
            } else if (isDying && unit._deathTimer !== undefined && unit._deathTimer < 0.2) {
                ctx.globalAlpha = Math.max(0.15, unit._deathTimer / 0.2);
            } else if (unit.isIllusion) {
                ctx.globalAlpha = 0.70;
            }
            if (!isDyingOrDead) {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
                ctx.beginPath();
                ctx.ellipse(pos.x, pos.y + 24, 14 * scale, 7 * scale, 0, 0, Math.PI * 2);
                ctx.fill();
            }

            const factionColor = (unit.owner === 0) ? '#1e88e5' : ((unit.owner === 1) ? '#e53935' : '#8e24aa');
            ctx.fillStyle = factionColor;
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y + 12 - flightAltitude, 13 * scale, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            const dir = unit.direction || 0;
            const angle = (dir * Math.PI) / 4;
            ctx.strokeStyle = '#ffe600';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y + 12 - flightAltitude);
            ctx.lineTo(pos.x + Math.sin(angle) * 15 * scale, pos.y + 12 - flightAltitude + Math.cos(angle) * 11 * scale);
            ctx.stroke();

            ctx.fillStyle = '#ffffff';
            ctx.font = `bold ${Math.round(10 * scale)}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const label = unit.name ? unit.name.substring(0, 2) : 'U';
            ctx.fillText(label, pos.x, pos.y + 12 - flightAltitude);
            ctx.restore();
        }

        // Status Effect Overlays (Frozen ice block, Paralyzed golden ropes, Slowed frost)
        if (!isDyingOrDead && unit.statusEffects) {
            const centerX = pos.x;
            const centerY = pos.y + 12 - flightAltitude;

            // 1. Frozen: translucent crystalline ice cuboid
            if (unit.statusEffects.frozen > 0) {
                ctx.save();
                ctx.fillStyle = 'rgba(120, 210, 255, 0.40)';
                ctx.strokeStyle = '#a5f3fc';
                ctx.lineWidth = 1.5;
                const iw = 26 * scale;
                const ih = 34 * scale;
                const ix = centerX - iw / 2;
                const iy = centerY - ih / 2;
                ctx.fillRect(ix, iy, iw, ih);
                ctx.strokeRect(ix, iy, iw, ih);
                // Frost facets
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                ctx.beginPath();
                ctx.moveTo(ix, iy);
                ctx.lineTo(ix + iw, iy + ih);
                ctx.moveTo(ix + iw, iy);
                ctx.lineTo(ix, iy + ih);
                ctx.stroke();
                ctx.restore();
            }

            // 2. Paralyzed: golden binding rings & electrical sparks
            if (unit.statusEffects.paralyzed > 0) {
                ctx.save();
                ctx.strokeStyle = '#ffd700';
                ctx.lineWidth = 1.8;
                ctx.beginPath();
                ctx.ellipse(centerX, centerY + 8 * scale, 14 * scale, 6 * scale, 0, 0, Math.PI * 2);
                ctx.stroke();
                ctx.beginPath();
                ctx.ellipse(centerX, centerY - 2 * scale, 12 * scale, 5 * scale, 0, 0, Math.PI * 2);
                ctx.stroke();
                // Sparks / energy runes
                ctx.fillStyle = '#ffeb3b';
                ctx.beginPath();
                ctx.arc(centerX - 9 * scale, centerY + 2 * scale, 2, 0, Math.PI * 2);
                ctx.arc(centerX + 9 * scale, centerY - 6 * scale, 2, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            }

            // 3. Slowed: blue frost mist at unit feet
            if (unit.statusEffects.slowed > 0) {
                ctx.save();
                ctx.fillStyle = 'rgba(56, 189, 248, 0.35)';
                ctx.beginPath();
                ctx.ellipse(centerX, pos.y + 22 - flightAltitude, 12 * scale, 6 * scale, 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            }
        }

        // 3. Health & Mana Bars: Display strictly when living unit is selected, damaged, Hero, OR Alt key toggled on
        // Never render health bars for dead, dying, or decaying corpses!
        if (!isDyingOrDead) {
            const isHero = Boolean(unit.isHero || (unit.spriteName && unit.spriteName.includes('general')) || (unit.archetype && unit.archetype.is_hero));
            const isDamaged = unit.hp !== undefined && unit.max_hp && unit.hp < unit.max_hp;
            if (unit.selected || isHero || isDamaged || this.showAllHealthBars) {
                this.drawHealthAndManaBar(ctx, unit, pos.x, pos.y - 16 * scale - flightAltitude, scale);
            }
        }
    }

    /**
     * Resolves authentic Joymax 5-direction + flipX sprite frame for any unit archetype.
     * Prevents death/dying frames during idle/walk and maps all action blocks according to analysis.md.
     *
     * @param {Object} sprite - Sprite sheet container
     * @param {Object} unit - Unit simulation entity
     * @param {number} dir - Direction index 0..7 (0:S, 1:SW, 2:W, 3:NW, 4:N, 5:NE, 6:E, 7:SE)
     * @param {number} animFrame - Animation frame index
     * @param {string} state - Entity state string ('IDLE', 'WALK', 'ATTACK', 'DIE', etc.)
     * @returns {Object|null} Frame descriptor { x, y, w, h, hotspotX, hotspotY, flipX }
     */
    resolveUnitFrame(sprite, unit, dir, animFrame, state) {
        if (!sprite) return null;

        const isCorpse = Boolean(state === 'CORPSE_DECAY' || (typeof UnitState !== 'undefined' && state === UnitState.CORPSE_DECAY) || (unit && (unit.state === 'CORPSE_DECAY' || (typeof UnitState !== 'undefined' && unit.state === UnitState.CORPSE_DECAY))));
        const isDyingOrDead = Boolean(state === 'DIE' || state === 'die' || (unit && (unit.state === 'DIE' || unit._isDyingAnim || (unit.isDead && !unit.deathAnimDone && !isCorpse))));
        const effectiveState = isCorpse ? 'CORPSE_DECAY' : (isDyingOrDead ? 'DIE' : (state || (unit ? unit.state : 'IDLE')));

        const d8 = ((Math.floor(dir || 0) % 8) + 8) % 8;
        const { dir5, flipX } = IsometricMath.directionToJoymax ? IsometricMath.directionToJoymax(d8) : DIR8_TO_JOYMAX5[d8];
        const f8 = (animFrame !== undefined ? animFrame : (unit ? (unit._deathFrame !== undefined ? unit._deathFrame : (unit.animFrame || 0)) : 0)) % 8;
        const isAtk = (effectiveState === 'ATTACK' || effectiveState === 'ATTACK_WINDUP' || effectiveState === 'ATTACK_COOLDOWN');
        const isWalk = (effectiveState === 'WALK');
        const isDie = (effectiveState === 'DIE');

        const frameW = sprite.width || 64;
        const frameH = sprite.height || 64;
        const cols = sprite.cols || (sprite.image ? Math.floor(sprite.image.width / frameW) : 8) || 1;
        const frameCount = sprite.frameCount || (sprite.frames ? sprite.frames.length : (sprite.framesPerDir ? sprite.framesPerDir * 5 : 24));

        const getByIndex = (idx, mirrorX = flipX) => {
            const safeIdx = Math.max(0, Math.min(frameCount - 1, Math.floor(idx || 0)));
            if (sprite.frames && sprite.frames[safeIdx]) {
                const f = sprite.frames[safeIdx];
                return {
                    x: f.x !== undefined ? f.x : (f.u !== undefined ? f.u : (safeIdx % cols) * frameW),
                    y: f.y !== undefined ? f.y : (f.v !== undefined ? f.v : Math.floor(safeIdx / cols) * frameH),
                    w: f.w || f.width || frameW,
                    h: f.h || f.height || frameH,
                    hotspotX: f.hotspotX !== undefined ? f.hotspotX : (f.hotspot_x !== undefined ? f.hotspot_x : frameW / 2),
                    hotspotY: f.hotspotY !== undefined ? f.hotspotY : (f.hotspot_y !== undefined ? f.hotspot_y : frameH * 0.78),
                    flipX: mirrorX
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
                hotspotY: frameH * 0.78,
                flipX: mirrorX
            };
        };

        const sprKey = (unit && unit.spriteName ? unit.spriteName : (sprite.name || '')).toLowerCase();
        const sprClean = sprKey.replace('char/', '').replace('.spr', '');
        const unitKind = unit ? (unit.kindId || (unit.archetype && unit.archetype.kind_id)) : null;
        const unitName = (unit && unit.name ? unit.name : '').toLowerCase();

        // 0. CUSTOM 10 JOSEON UNITS (0x70~0x79) ANIMATION SPEC DISPATCH
        const customSpec = (unitKind && CUSTOM_JOSEON_ANIM_SPECS[unitKind]) ||
                           CUSTOM_JOSEON_ANIM_SPECS[sprClean] ||
                           CUSTOM_JOSEON_ANIM_SPECS[sprKey] ||
                           CUSTOM_JOSEON_ANIM_SPECS[unitName] ||
                           (unit && unit.animSpec ? unit.animSpec : null);

        if (customSpec) {
            // 5th Action: CORPSE_DECAY: static resting corpse frame (die_start + die_frames - 1)
            if (isCorpse) {
                if (customSpec.die && customSpec.die.corpse !== null && customSpec.die.corpse !== undefined) {
                    return getByIndex(customSpec.die.corpse, flipX);
                }
                // Air unit has null corpse (vanishes instantly)
                return null;
            }

            // 4th Action: DIE: sequential dying animation
            if (isDie) {
                const totalDie = (customSpec.die && customSpec.die.total) ? customSpec.die.total : 8;
                const dieStart = (customSpec.die && customSpec.die.start !== undefined) ? customSpec.die.start : 0;
                const fIdx = Math.max(0, Math.min(totalDie - 1, Math.floor(animFrame || 0)));
                return getByIndex(dieStart + fIdx, flipX);
            }

            // 3rd Action: ATTACK: 5-directional combat animation
            if (isAtk) {
                const fDir = (customSpec.atk && customSpec.atk.fDir) ? customSpec.atk.fDir : 8;
                const atkStart = (customSpec.atk && customSpec.atk.start !== undefined) ? customSpec.atk.start : 0;
                const fIdx = Math.floor(animFrame || 0) % fDir;
                return getByIndex(atkStart + dir5 * fDir + fIdx, flipX);
            }

            // 1st Action: WALK: 5-directional walking loop
            if (isWalk) {
                const fDir = (customSpec.move && customSpec.move.fDir) ? customSpec.move.fDir : 8;
                const moveStart = (customSpec.move && customSpec.move.start !== undefined) ? customSpec.move.start : 0;
                const fIdx = Math.floor(animFrame || 0) % fDir;
                return getByIndex(moveStart + dir5 * fDir + fIdx, flipX);
            }

            // 2nd Action: IDLE: 5-directional breathing / flight hover loop
            const fDir = (customSpec.idle && customSpec.idle.fDir) ? customSpec.idle.fDir : 8;
            const idleStart = (customSpec.idle && customSpec.idle.start !== undefined) ? customSpec.idle.start : 0;
            const fIdx = Math.floor(animFrame || 0) % fDir;
            return getByIndex(idleStart + dir5 * fDir + fIdx, flipX);
        }

        // 1. FARMERS: farmerk, farmerj, farmerc (288 frames = 36 blocks of 8 frames)
        if (frameCount === 288 || sprKey.includes('farmer') || sprKey.includes('worker')) {
            if (isDie) return getByIndex(40 + (f8 % 8), flipX); // Block 5: 40..47 non-directional collapse
            if (isAtk) {
                // Hammer building/repairing: Blocks 26..30: 208..247
                if (unit && unit.constructingTarget) {
                    return getByIndex(208 + dir5 * 8 + f8, flipX);
                }
                // Wood chopping (axe): Blocks 16..20: 128..167
                const isWood = unit && unit.harvestTarget && (unit.harvestTarget.rType === 2 || unit.harvestTarget.rType === 3);
                if (isWood) {
                    return getByIndex(128 + dir5 * 8 + f8, flipX);
                }
                // Combat sickle attack: Blocks 31..35: 248..287
                if (unit && unit.targetEntity && !unit.autoHarvest) {
                    return getByIndex(248 + dir5 * 8 + f8, flipX);
                }
                // Default crop harvest (sickle): Blocks 11..15: 88..127
                return getByIndex(88 + dir5 * 8 + f8, flipX);
            }
            if (isWalk) {
                // Sack walk: Blocks 6..10: 48..87
                // Empty walk: Blocks 0..4: 0..39
                const hasSack = Boolean(unit && unit.carryingAmount > 0);
                const base = hasSack ? 48 : 0;
                return getByIndex(base + dir5 * 8 + f8, flipX);
            }
            // Standing Idle: Blocks 21..25: 168..207 (4 breathing frames per dir)
            return getByIndex(168 + dir5 * 8 + (f8 % 4), flipX);
        }

        // 2. SPEARMEN / SAMURAI: swordk, swordj (192 frames = 24 blocks of 8 frames)
        if (frameCount === 192 || sprKey.includes('swordk') || sprKey.includes('swordj') || sprKey.includes('spearman') || sprKey.includes('samurai')) {
            if (isDie) return getByIndex(88 + dir5 * 8 + f8, flipX); // True death: Blocks 11..15 (88..127)
            if (isAtk) return getByIndex(40 + dir5 * 8 + f8, flipX); // True attack: Blocks 5..9 (40..79)
            if (isWalk) return getByIndex(0 + dir5 * 8 + f8, flipX);  // True walk: Blocks 0..4 (0..39)
            return getByIndex(128 + dir5 * 8 + (f8 % 4), flipX);     // True idle: Blocks 16..20 (128..167)
        }

        // 3. ARCHERS: archerk (176 frames = 22 blocks of 8 frames)
        if (frameCount === 176 || sprKey.includes('archerk') || sprKey.includes('archer')) {
            if (isDie) return getByIndex(40 + dir5 * 8 + f8, flipX);  // True death: Blocks 5..9 (40..79)
            if (isAtk) return getByIndex(120 + dir5 * 8 + f8, flipX); // Bow draw & fire: Blocks 15..19 (120..159)
            if (isWalk) return getByIndex(80 + dir5 * 8 + f8, flipX);  // Walk: Blocks 10..14 (80..119)
            return getByIndex(0 + dir5 * 8 + (f8 % 4), flipX);        // Idle: Blocks 0..4 (0..39)
        }

        // 4. MING SPEARMAN: swordc1 (90 frames = 5 dirs * 18 frames)
        if (frameCount === 90 || sprKey.includes('swordc1')) {
            const baseDir = dir5 * 18;
            if (isDie) return getByIndex(baseDir + 8 + (f8 % 8), flipX);
            if (isAtk) return getByIndex(baseDir + 8 + (f8 % 8), flipX);
            if (isWalk) return getByIndex(baseDir + (f8 % 8), flipX);
            return getByIndex(baseDir + 16 + (f8 % 2), flipX);
        }

        // 5. ASHIGARU GUNNER: gunj1 (80 frames = 5 dirs * 16 frames)
        if ((frameCount === 80 && sprKey.includes('gunj1')) || sprKey.includes('ashigaru')) {
            const baseDir = dir5 * 16;
            if (isDie) return getByIndex(baseDir + 8 + (f8 % 8), flipX);
            if (isAtk) return getByIndex(baseDir + 8 + (f8 % 8), flipX);
            if (isWalk) return getByIndex(baseDir + (f8 % 8), flipX);
            return getByIndex(baseDir + (f8 % 2), flipX);
        }

        // 6. GENERAL GWAK: generalk31 (80 frames = 40 walk + 40 attack)
        if (frameCount === 80 || sprKey.includes('generalk31') || sprKey.includes('gwak')) {
            if (isDie) return getByIndex(40 + dir5 * 8 + f8, flipX);
            if (isAtk) return getByIndex(40 + dir5 * 8 + f8, flipX);
            if (isWalk) return getByIndex(0 + dir5 * 8 + f8, flipX);
            return getByIndex(0 + dir5 * 8 + (f8 % 2), flipX);
        }

        // 7. HORSE ARCHER: horsearcherk (140 frames = 5 dirs * 28 frames)
        if (frameCount === 140 || sprKey.includes('horsearcher')) {
            const baseDir = dir5 * 28;
            if (isDie) return getByIndex(baseDir + 8 + (f8 % 8), flipX);
            if (isAtk) return getByIndex(baseDir + 8 + (f8 % 8), flipX);
            if (isWalk) return getByIndex(baseDir + (f8 % 8), flipX);
            return getByIndex(baseDir + 24 + (f8 % 4), flipX);
        }

        // 8. GENERAL YI SUN-SIN: generalk12 (56 frames = 5 dirs * 10 frames)
        if (frameCount === 56 || sprKey.includes('generalk12') || sprKey.includes('leesunshin')) {
            const baseDir = dir5 * 10;
            if (isDie) return getByIndex(baseDir + 2 + (f8 % 8), flipX);
            if (isAtk) return getByIndex(baseDir + 2 + (f8 % 8), flipX);
            return getByIndex(baseDir + (isWalk ? (f8 % 2) : 0), flipX);
        }

        // Fallback for siege/ships or other units:
        const stride = Math.max(1, Math.min(8, Math.floor(frameCount / 5)));
        return getByIndex(dir5 * stride + (isWalk || isAtk ? (f8 % stride) : 0), flipX);
    }

    /**
     * Draws authentic segmented Imjinrok 2+ health and mana bars (plus Hero/Veteran Lv badge) above an entity.
     * Cluttered 'Lv 1' badges are strictly suppressed: rendered only for heroes or veterans with level >= 2.
     */
    drawHealthAndManaBar(ctx, unit, cx, topY, scale) {
        const isBld = Boolean(unit.isBuilding);
        const barW = Math.round((isBld ? 76 : 36) * scale);
        const barH = isBld ? 5 : 4;
        const barX = Math.round(cx - barW / 2);
        const barY = Math.round(topY);

        ctx.save();

        // Level Badge rule: Suppress cluttered 'Lv 1' badges!
        // Render level badge strictly when !isBld && !unit.isWorker && (isHero || (unit.level && unit.level >= 2))
        const isHero = Boolean(unit.isHero || (unit.spriteName && unit.spriteName.includes('general')) || (unit.archetype && unit.archetype.is_hero));
        const showLv = !isBld && !unit.isWorker && (isHero || (unit.level && unit.level >= 2));
        if (showLv) {
            const heroLv = unit.level || 1;
            ctx.font = 'bold 11px monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = '#000000';
            ctx.fillText(`Lv ${heroLv}`, cx + 1, barY - 4);
            ctx.fillStyle = isHero ? '#ffd700' : '#ffffff';
            ctx.fillText(`Lv ${heroLv}`, cx, barY - 5);
        }

        // Outer black border
        ctx.fillStyle = '#000000';
        ctx.fillRect(barX - 1, barY - 1, barW + 2, barH + 2);

        // Health fill
        const maxHp = unit.max_hp || 100;
        const curHp = Math.max(0, Math.min(maxHp, unit.hp !== undefined ? unit.hp : maxHp));
        const hpRatio = curHp / maxHp;
        const fillW = Math.round(barW * hpRatio);

        ctx.fillStyle = hpRatio > 0.5 ? '#2ecc40' : (hpRatio > 0.25 ? '#f1c40f' : '#e74c3c');
        ctx.fillRect(barX, barY, fillW, barH);

        // Authentic vertical segment ticks inside health bar
        ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
        const step = isBld ? 5 : 4;
        for (let sx = barX + step; sx < barX + barW; sx += step) {
            ctx.fillRect(sx, barY, 1, barH);
        }

        // Mana bar (if unit has mana capacity)
        if (unit.max_mp && unit.max_mp > 0) {
            const curMp = Math.max(0, Math.min(unit.max_mp, unit.mp !== undefined ? unit.mp : unit.max_mp));
            const mpRatio = curMp / unit.max_mp;
            const mpBarY = barY + barH + 1;

            ctx.fillStyle = '#000000';
            ctx.fillRect(barX - 1, mpBarY - 1, barW + 2, 3);
            ctx.fillStyle = '#3498db';
            ctx.fillRect(barX, mpBarY, Math.round(barW * mpRatio), 2);
        }
        ctx.restore();
    }

    /**
     * Resolves a building sprite frame for construction scaffolding (0..6), completed intact (7), or waving banners (10..16).
     */
    resolveBuildingFrame(sprite, sprKey, frameIdx, isConstructing = false) {
        if (!sprite) return null;
        const frameW = sprite.width || 120;
        const frameH = sprite.height || 120;
        const cols = sprite.cols || (sprite.image ? Math.floor(sprite.image.width / frameW) : 1) || 1;
        const frameCount = sprite.frameCount || (sprite.frames ? sprite.frames.length : 24);
        const safeIdx = Math.max(0, Math.min(frameCount - 1, frameIdx));

        if (sprite.frames && sprite.frames[safeIdx]) {
            const f = sprite.frames[safeIdx];
            return {
                x: f.x !== undefined ? f.x : (f.u !== undefined ? f.u : (safeIdx % cols) * frameW),
                y: f.y !== undefined ? f.y : (f.v !== undefined ? f.v : Math.floor(safeIdx / cols) * frameH),
                w: f.w || f.width || frameW,
                h: f.h || f.height || frameH,
                hotspotX: f.hotspotX !== undefined ? f.hotspotX : frameW / 2,
                hotspotY: f.hotspotY !== undefined ? f.hotspotY : frameH * 0.72,
                flipX: false
            };
        }

        return {
            x: (safeIdx % cols) * frameW,
            y: Math.floor(safeIdx / cols) * frameH,
            w: frameW,
            h: frameH,
            hotspotX: frameW / 2,
            hotspotY: frameH * 0.72,
            flipX: false
        };
    }

    /**
     * Draws a building structure with authentic scaffolding stages (0..6), Frame 7 completed intact sprite,
     * waving banners (frames 10..16 for Chosun Barracks), orange corner selection brackets, and segmented health bar.
     */
    drawBuilding(ctx, bld, camera, grid) {
        const elev = (grid && grid.elevation) ? (grid.elevation[bld.gy * (grid.width || 180) + bld.gx] || 0) : 0;
        const pos = IsometricMath.gridToScreen(bld.gx, bld.gy, elev, camera);

        ctx.save();
        const factionColor = (bld.owner === 0) ? '#1565c0' : ((bld.owner === 1) ? '#c62828' : '#6a1b9a');
        const bW = (bld.footprintWidth || 2) * 34;
        const bH = (bld.footprintHeight || 2) * 22;
        const bDepth = 36;

        let spriteDrawn = false;
        const sprKey = (bld.spriteName || bld.sprite_name || '').toLowerCase();

        // Draw organic dark-brown building foundation dirt decal
        ctx.save();
        ctx.fillStyle = 'rgba(62, 46, 22, 0.72)';
        ctx.beginPath();
        ctx.ellipse(pos.x, pos.y + 12, bW * 0.74, bH * 0.68, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(42, 30, 12, 0.55)';
        ctx.beginPath();
        ctx.ellipse(pos.x - 8, pos.y + 16, bW * 0.58, bH * 0.52, 0.2, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        if (this.assetManager && sprKey) {
            const sprite = this.assetManager.getUnitSprite ? this.assetManager.getUnitSprite(sprKey) : null;
            if (sprite && sprite.image) {
                // Construction Stages: Scaffolding stages 0..6 based on Math.floor(progress * 7), Frame 7 for 100% intact building
                const isConst = Boolean(bld.isConstructing && (bld.constructionProgress === undefined || bld.constructionProgress < 1.0));
                const constStage = isConst ? Math.max(0, Math.min(6, Math.floor((bld.constructionProgress || 0) * 7))) : 7;
                const bestBldFrame = (sprKey.includes('barrackj') ? 18 : 7);
                const targetFrame = isConst ? constStage : bestBldFrame;

                let frame = sprite.getFrame ? sprite.getFrame(0, targetFrame, isConst ? 'constructing' : 'building') : null;
                if (!frame) {
                    frame = this.resolveBuildingFrame(sprite, sprKey, targetFrame, isConst);
                }

                if (frame) {
                    const fw = frame.w || 120;
                    const fh = frame.h || 120;
                    const drawX = pos.x - (frame.hotspotX || fw / 2);
                    const drawY = pos.y + 32 - (frame.hotspotY || fh * 0.72);
                    ctx.drawImage(
                        sprite.image,
                        frame.x || 0,
                        frame.y || 0,
                        fw,
                        fh,
                        drawX,
                        drawY,
                        fw,
                        fh
                    );

                    // Animated waving banners (frames 10..16) for Chosun Barracks
                    if (!isConst && (sprKey.includes('barrackk') || sprite.getBannerFrame)) {
                        const nowMs = performance.now ? performance.now() : Date.now();
                        const bannerTick = Math.floor(nowMs / 140);
                        let bFrame = sprite.getBannerFrame ? sprite.getBannerFrame(bannerTick) : null;
                        if (!bFrame) {
                            const bannerIdx = 10 + (bannerTick % 7);
                            bFrame = this.resolveBuildingFrame(sprite, sprKey, bannerIdx, false);
                        }
                        if (bFrame) {
                            ctx.drawImage(
                                sprite.image,
                                bFrame.x || 0,
                                bFrame.y || 0,
                                bFrame.w || fw,
                                bFrame.h || fh,
                                drawX,
                                drawY,
                                fw,
                                fh
                            );
                        }
                    }

                    if (isConst) {
                        ctx.font = 'bold 11px "Malgun Gothic", sans-serif';
                        ctx.textAlign = 'center';
                        const pctText = `🔨 건설중 ${Math.floor((bld.constructionProgress || 0) * 100)}%`;
                        ctx.fillStyle = '#000000';
                        ctx.fillText(pctText, pos.x + 1, pos.y - 25);
                        ctx.fillStyle = '#ffd700';
                        ctx.fillText(pctText, pos.x, pos.y - 26);
                    }
                    spriteDrawn = true;
                }
            }
        }

        if (!spriteDrawn) {
            ctx.fillStyle = '#263238';
            ctx.strokeStyle = factionColor;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.rect(pos.x - bW / 2, pos.y - bDepth, bW, bH + bDepth);
            ctx.fill();
            ctx.stroke();
        }

        // Authentic Imjinrok 2+ Selected Building Brackets & Rally Point Marker
        if (bld.selected) {
            const bxLeft = pos.x - bW * 0.72;
            const bxRight = pos.x + bW * 0.72;
            const byTop = pos.y - bDepth * 0.55;
            const byBot = pos.y + 38;
            const cLen = 7;

            ctx.strokeStyle = '#e69528';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(bxLeft, byBot - cLen); ctx.lineTo(bxLeft, byBot); ctx.lineTo(bxLeft + cLen, byBot);
            ctx.moveTo(bxRight - cLen, byBot); ctx.lineTo(bxRight, byBot); ctx.lineTo(bxRight, byBot - cLen);
            ctx.moveTo(bxLeft, byTop + cLen); ctx.lineTo(bxLeft, byTop); ctx.lineTo(bxLeft + cLen, byTop);
            ctx.moveTo(bxRight - cLen, byTop); ctx.lineTo(bxRight, byTop); ctx.lineTo(bxRight, byTop + cLen);
            ctx.stroke();

            if (bld.rallyPoint) {
                const rPos = IsometricMath.worldToScreen(bld.rallyPoint.gx + 0.5, bld.rallyPoint.gy + 0.5, 0, camera);
                const rx = rPos.x;
                const ry = rPos.y + 20;
                ctx.save();
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = 'rgba(46, 204, 64, 0.65)';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(pos.x, byBot);
                ctx.lineTo(rx, ry);
                ctx.stroke();
                ctx.restore();

                ctx.strokeStyle = '#2ecc40';
                ctx.lineWidth = 2.0;
                ctx.beginPath();
                ctx.moveTo(rx, ry - 6);
                ctx.lineTo(rx + 10, ry);
                ctx.lineTo(rx, ry + 6);
                ctx.lineTo(rx - 10, ry);
                ctx.closePath();
                ctx.stroke();
            }
        }

        // Building segmented health bar if selected, damaged, constructing, or Alt active
        const isDamaged = (bld.hp !== undefined && bld.max_hp && bld.hp < bld.max_hp) || bld.isConstructing;
        if (bld.selected || isDamaged || this.showAllHealthBars) {
            this.drawHealthAndManaBar(ctx, bld, pos.x, pos.y - bDepth - 12, 1.15);
        }
        ctx.restore();
    }

    /**
     * Renders authentic RTS tactical command cursor reticles on canvas:
     * - Tactical crosshairs with central notch and label at mouse position
     * - Projected isometric ground targeting ellipse / AoE circle at hovered tile
     * - Animated target lock brackets on hoverable targets (hostile red, friendly green)
     * - Dashed rally lines connecting selected buildings to target position
     *
     * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
     * @param {Object} pendingCommand - Active pending command descriptor { action, name, color, range, aoeRadius, ... }
     * @param {{ x: number, y: number }} mousePos - Screen mouse coordinates
     * @param {Array<Object>} [entities=[]] - Active entities list
     * @param {Object} [grid=null] - GameGrid instance
     * @param {Object} [camera={ x: 0, y: 0 }] - Camera controller
     */
    drawPendingCommandReticle(ctx, pendingCommand, mousePos, entities = [], grid = null, camera = { x: 0, y: 0 }) {
        if (!ctx || !pendingCommand || !mousePos) return;

        const mx = mousePos.x;
        const my = mousePos.y;
        const action = pendingCommand.action || '';
        const isAttack = (action === 'attack' || action === 'attack_ground' || action === 'all_charge');
        const isMove = (action === 'move');
        const isPatrol = (action === 'patrol');
        const isRally = (action === 'set_rally');
        const isSkill = action.startsWith('skill_');

        // Color coding: Attack/Skill = Red/Orange, Move = Green, Patrol/Rally = Gold/Blue
        const primaryColor = pendingCommand.color ||
            (isAttack ? '#ff3b30' : (isSkill ? '#ff9500' : (isRally ? '#34c759' : (isPatrol ? '#5856d6' : '#2ecc40'))));

        ctx.save();

        // 1. Unproject mouse to isometric ground tile
        const elevGrid = (grid && grid.elevation) ? grid.elevation : null;
        const mapW = grid ? (grid.width || 180) : 180;
        const mapH = grid ? (grid.height || 180) : 180;
        const picked = IsometricMath.screenToGrid(mx, my, camera, elevGrid, mapW, mapH);

        // 2. Projected Ground Targeting Ellipse / AoE Circle at hovered tile
        if (picked && picked.valid) {
            const gPos = IsometricMath.gridToScreen(picked.gx, picked.gy, picked.elevation, camera);
            const cx = gPos.x;
            const cy = gPos.y + 24;

            ctx.save();
            const now = performance.now ? performance.now() : Date.now();
            const pulse = 1 + 0.08 * Math.sin(now / 150);

            if (action === 'skill_firestorm') {
                // Wide AoE ground reticle for Firestorm
                ctx.strokeStyle = '#ff4500';
                ctx.fillStyle = 'rgba(255, 69, 0, 0.18)';
                ctx.lineWidth = 2.0;
                ctx.beginPath();
                ctx.ellipse(cx, cy, 64 * pulse, 32 * pulse, 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();

                // Inner dashed rotating ring
                ctx.setLineDash([6, 6]);
                ctx.strokeStyle = '#ffd700';
                ctx.beginPath();
                ctx.ellipse(cx, cy, 40, 20, 0, 0, Math.PI * 2);
                ctx.stroke();
            } else if (action === 'skill_shockwave') {
                // Directional Shockwave circle
                ctx.strokeStyle = '#00e5ff';
                ctx.fillStyle = 'rgba(0, 229, 255, 0.15)';
                ctx.lineWidth = 2.0;
                ctx.beginPath();
                ctx.ellipse(cx, cy, 48 * pulse, 24 * pulse, 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();
            } else {
                // Standard tile targeting diamond/ellipse
                ctx.strokeStyle = primaryColor;
                ctx.fillStyle = isAttack ? 'rgba(255, 59, 48, 0.14)' : 'rgba(46, 204, 64, 0.14)';
                ctx.lineWidth = 1.8;
                ctx.beginPath();
                ctx.ellipse(cx, cy, 28 * pulse, 14 * pulse, 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();

                // Diamond orientation outline
                ctx.strokeStyle = primaryColor;
                ctx.lineWidth = 1.2;
                ctx.beginPath();
                ctx.moveTo(gPos.x, gPos.y);
                ctx.lineTo(gPos.x + 32, gPos.y + 24);
                ctx.lineTo(gPos.x, gPos.y + 48);
                ctx.lineTo(gPos.x - 32, gPos.y + 24);
                ctx.closePath();
                ctx.stroke();
            }
            ctx.restore();
        }

        // 3. Hover Target Lock Brackets: Detect if hovering over a living unit or building
        let hoveredTarget = null;
        let bestDist = 28; // Hit distance threshold in screen pixels
        for (const ent of entities) {
            if (!ent || ent.isDead) continue;
            const elev = (grid && grid.elevation) ? (grid.elevation[Math.floor(ent.wy !== undefined ? ent.wy : ent.gy) * mapW + Math.floor(ent.wx !== undefined ? ent.wx : ent.gx)] || 0) : 0;
            const wx = ent.wx !== undefined ? ent.wx : (ent.gx + 0.5);
            const wy = ent.wy !== undefined ? ent.wy : (ent.gy + 0.5);
            const sp = IsometricMath.worldToScreen(wx, wy, elev, camera);
            const d = Math.hypot(mx - sp.x, my - (sp.y + 16));
            if (d < bestDist) {
                bestDist = d;
                hoveredTarget = { entity: ent, screenPos: sp };
            }
        }

        if (hoveredTarget) {
            const ent = hoveredTarget.entity;
            const sp = hoveredTarget.screenPos;
            const isHostile = (ent.owner === 1);
            const lockColor = isHostile ? '#ff2a2a' : '#2ecc40';
            const size = ent.isBuilding ? 36 : 22;
            const lx1 = sp.x - size;
            const lx2 = sp.x + size;
            const ly1 = sp.y + 16 - size;
            const ly2 = sp.y + 16 + size;
            const bLen = Math.round(size * 0.45);

            ctx.save();
            ctx.strokeStyle = lockColor;
            ctx.lineWidth = 2.2;
            ctx.beginPath();
            // Top-left bracket [
            ctx.moveTo(lx1, ly1 + bLen); ctx.lineTo(lx1, ly1); ctx.lineTo(lx1 + bLen, ly1);
            // Top-right bracket ]
            ctx.moveTo(lx2 - bLen, ly1); ctx.lineTo(lx2, ly1); ctx.lineTo(lx2, ly1 + bLen);
            // Bottom-left bracket [
            ctx.moveTo(lx1, ly2 - bLen); ctx.lineTo(lx1, ly2); ctx.lineTo(lx1 + bLen, ly2);
            // Bottom-right bracket ]
            ctx.moveTo(lx2 - bLen, ly2); ctx.lineTo(lx2, ly2); ctx.lineTo(lx2, ly2 - bLen);
            ctx.stroke();

            // Target Name tooltip badge
            ctx.font = 'bold 11px monospace';
            ctx.textAlign = 'center';
            const targetName = ent.name || (ent.archetype ? ent.archetype.korean_name : '대상');
            ctx.fillStyle = '#000000';
            ctx.fillText(targetName, sp.x + 1, ly1 - 7);
            ctx.fillStyle = lockColor;
            ctx.fillText(targetName, sp.x, ly1 - 8);
            ctx.restore();
        }

        // 4. Dashed Rally Line (if setting rally point from selected building)
        if (isRally || action === 'set_rally') {
            const selectedBld = entities.find(e => e && e.selected && e.isBuilding);
            if (selectedBld) {
                const bElev = (grid && grid.elevation) ? (grid.elevation[selectedBld.gy * mapW + selectedBld.gx] || 0) : 0;
                const bPos = IsometricMath.gridToScreen(selectedBld.gx, selectedBld.gy, bElev, camera);
                const startX = bPos.x;
                const startY = bPos.y + 24;

                ctx.save();
                ctx.setLineDash([5, 5]);
                ctx.strokeStyle = '#2ecc40';
                ctx.lineWidth = 1.8;
                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.lineTo(mx, my);
                ctx.stroke();

                // Terminal Diamond at cursor
                ctx.setLineDash([]);
                ctx.fillStyle = '#2ecc40';
                ctx.beginPath();
                ctx.moveTo(mx, my - 6);
                ctx.lineTo(mx + 6, my);
                ctx.lineTo(mx, my + 6);
                ctx.lineTo(mx - 6, my);
                ctx.closePath();
                ctx.fill();
                ctx.restore();
            }
        }

        // 5. Tactical Crosshair at Mouse Screen Coordinates
        ctx.save();
        ctx.strokeStyle = primaryColor;
        ctx.lineWidth = 1.6;
        const armLen = 10;
        const gap = 4;

        // Top arm
        ctx.beginPath();
        ctx.moveTo(mx, my - gap - armLen);
        ctx.lineTo(mx, my - gap);
        // Bottom arm
        ctx.moveTo(mx, my + gap);
        ctx.lineTo(mx, my + gap + armLen);
        // Left arm
        ctx.moveTo(mx - gap - armLen, my);
        ctx.lineTo(mx - gap, my);
        // Right arm
        ctx.moveTo(mx + gap, my);
        ctx.lineTo(mx + gap + armLen, my);
        ctx.stroke();

        // Central crosshair dot
        ctx.fillStyle = primaryColor;
        ctx.beginPath();
        ctx.arc(mx, my, 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Label next to crosshair
        if (pendingCommand.name) {
            ctx.font = 'bold 11px "Malgun Gothic", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillStyle = '#000000';
            ctx.fillText(pendingCommand.name, mx + 13, my - 5);
            ctx.fillStyle = primaryColor;
            ctx.fillText(pendingCommand.name, mx + 12, my - 6);
        }

        ctx.restore();
        ctx.restore();
    }

    /**
     * Draws an in-flight projectile with 3D parabolic elevation arc.
     */
    drawProjectile(ctx, item, camera) {
        const pos = item.pos;
        const screenPos = IsometricMath.worldToScreen(pos.wx, pos.wy, 0, camera);
        // Apply vertical parabolic elevation arc (in pixels)
        const arcOffset = pos.arcZ || 0;
        const px = screenPos.x;
        const py = screenPos.y - arcOffset;

        ctx.save();
        const type = item.proj ? item.proj.type : 'arrow';

        if (type === 'cannon') {
            // Cannonball: Dark shaded sphere with smoke trail
            ctx.fillStyle = '#1c1c1c';
            ctx.beginPath();
            ctx.arc(px, py, 4.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#ff9800';
            ctx.lineWidth = 1;
            ctx.stroke();
        } else if (type === 'fireball') {
            // Flame cart / Fireball (0x79 불가살이): Bright flame sphere with glowing core
            ctx.fillStyle = '#ff3d00';
            ctx.beginPath();
            ctx.arc(px, py, 5.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#ffea00';
            ctx.beginPath();
            ctx.arc(px, py, 2.8, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#ff9100';
            ctx.lineWidth = 1.2;
            ctx.stroke();
        } else if (type === 'magic_bind') {
            // Talisman / Paralysis Orb (0x70 유생 포박술): Glowing golden talisman energy orb
            ctx.fillStyle = '#ffd700';
            ctx.beginPath();
            ctx.arc(px, py, 4.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.2;
            ctx.stroke();
            // Golden outer ring
            ctx.strokeStyle = 'rgba(255, 215, 0, 0.65)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(px, py, 7.0, 0, Math.PI * 2);
            ctx.stroke();
        } else if (type === 'frost_freeze') {
            // Frost freeze orb (0x76 털가면 얼리기): Cyan crystalline frost projectile
            ctx.fillStyle = '#00e5ff';
            ctx.beginPath();
            ctx.arc(px, py, 4.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#e0f7fa';
            ctx.beginPath();
            ctx.arc(px, py, 2.2, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.0;
            ctx.stroke();
        } else if (type === 'ice_splash') {
            // Ice splash cluster (0x77 설녀 얼음 스플래쉬): Crystalline ice shard core
            ctx.fillStyle = '#38bdf8';
            ctx.beginPath();
            ctx.arc(px, py, 5.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(px, py, 2.8, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#0284c7';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        } else if (type === 'bullet') {
            // Musket bullet: Bright spark streak
            ctx.fillStyle = '#fff59d';
            ctx.beginPath();
            ctx.arc(px, py, 2.5, 0, Math.PI * 2);
            ctx.fill();
        } else {
            // Arrow (standard): Directional projectile
            ctx.fillStyle = '#d7ccc8';
            ctx.strokeStyle = '#4e342e';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(px - 4, py - 4);
            ctx.lineTo(px + 4, py + 4);
            ctx.stroke();

            // Arrow tip
            ctx.fillStyle = '#9e9e9e';
            ctx.beginPath();
            ctx.arc(px + 4, py + 4, 2, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    }

    /**
     * Draws the drag-selection box rectangle on the screen.
     */
    drawSelectionBox(ctx) {
        if (!this.selectionBox || !this.selectionBox.active) return;

        const { startX, startY, currentX, currentY } = this.selectionBox;
        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const w = Math.abs(currentX - startX);
        const h = Math.abs(currentY - startY);

        if (w < 2 && h < 2) return;

        ctx.save();
        ctx.fillStyle = 'rgba(0, 255, 68, 0.12)';
        ctx.strokeStyle = '#00ff44';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 2]);

        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
        ctx.restore();
    }

    /**
     * Highlights the tile currently under the mouse cursor.
     */
    drawHoverTile(ctx, camera, grid) {
        if (!this.showTileHover || !this.hoverTile || !this.hoverTile.valid) return;

        const { gx, gy } = this.hoverTile;
        const elev = (grid && grid.elevation) ? (grid.elevation[gy * grid.width + gx] || 0) : 0;
        const pos = IsometricMath.gridToScreen(gx, gy, elev, camera);

        ctx.save();
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y);
        ctx.lineTo(pos.x + 32, pos.y + 24);
        ctx.lineTo(pos.x, pos.y + 48);
        ctx.lineTo(pos.x - 32, pos.y + 24);
        ctx.closePath();
        ctx.stroke();
        ctx.restore();
    }

    /**
     * Updates running FPS calculation.
     */
    updateFps() {
        this.frameCount++;
        const now = performance.now ? performance.now() : Date.now();
        const delta = now - this.lastFpsTimestamp;
        if (delta >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / delta);
            this.frameCount = 0;
            this.lastFpsTimestamp = now;
        }
    }
}
