/**
 * Minimap 2D Radar HUD for Imjinrok 2+: Dawn
 *
 * Implements interactive 200x200 2D radar HUD:
 * - Real-time rendering of terrain colors, water, cliffs, and elevation
 * - Harvestable resource dots (crops, rice, bamboo, trees)
 * - Faction-colored unit dots (Blue/Cyan for Player, Red for Enemy)
 * - Dynamic isometric camera viewport wireframe overlay
 * - Instant camera centering on left-click and continuous drag-panning
 * - Right-click on minimap to issue move and attack orders to selected units
 */

import { IsometricMath } from '../engine/isometric.js';

export class MinimapHUD {
    /**
     * @param {HTMLCanvasElement} canvas - Target 200x200 canvas element
     * @param {Object} [grid=null] - GameGrid instance
     * @param {Object} [camera=null] - Camera controller instance
     * @param {Function} [onMoveOrder=null] - Callback invoked on right-click with (gx, gy)
     */
    constructor(canvas, grid = null, camera = null, onMoveOrder = null) {
        this.canvas = canvas;
        this.ctx = canvas ? canvas.getContext('2d') : null;
        this.grid = grid;
        this.camera = camera;
        this.onMoveOrder = onMoveOrder;

        this.size = 200;
        this.mapWidth = grid ? (grid.width || 180) : 180;
        this.mapHeight = grid ? (grid.height || 180) : 180;
        this.scaleX = this.size / this.mapWidth;
        this.scaleY = this.size / this.mapHeight;

        this.isDragging = false;

        // Ensure canvas dimensions match radar size
        if (this.canvas) {
            this.canvas.width = this.size;
            this.canvas.height = this.size;
        }

        this.initEvents();
    }

    /**
     * Updates the grid reference and recalculates scaling ratios.
     *
     * @param {Object} grid - GameGrid instance
     */
    setGrid(grid) {
        this.grid = grid;
        if (grid) {
            this.mapWidth = grid.width || 180;
            this.mapHeight = grid.height || 180;
            this.scaleX = this.size / this.mapWidth;
            this.scaleY = this.size / this.mapHeight;
        }
    }

    /**
     * Updates the camera controller reference.
     *
     * @param {Object} camera - Camera instance
     */
    setCamera(camera) {
        this.camera = camera;
    }

    /**
     * Sets the callback for right-click orders.
     *
     * @param {Function} onMoveOrder - Callback (gx, gy) => void
     */
    setOnMoveOrder(onMoveOrder) {
        this.onMoveOrder = onMoveOrder;
    }

    /**
     * Converts mouse event coordinates relative to minimap canvas into grid coordinates (gx, gy).
     *
     * @param {MouseEvent} e - Mouse event
     * @returns {{ gx: number, gy: number }} Grid coordinates clamped to map dimensions
     */
    getGridCoordsFromEvent(e) {
        if (!this.canvas) return { gx: 0, gy: 0 };
        const rect = this.canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;

        const gx = Math.max(0, Math.min(this.mapWidth - 1, Math.floor(mx / this.scaleX)));
        const gy = Math.max(0, Math.min(this.mapHeight - 1, Math.floor(my / this.scaleY)));
        return { gx, gy };
    }

    /**
     * Binds mouse interaction events for left-click jump, drag panning, and right-click orders.
     */
    initEvents() {
        if (!this.canvas) return;

        // Left-click & Right-click handling
        this.canvas.addEventListener('mousedown', (e) => {
            const { gx, gy } = this.getGridCoordsFromEvent(e);

            if (e.button === 0) {
                // Left click: Instant camera center & start drag
                this.isDragging = true;
                this.panCameraTo(gx, gy);
            } else if (e.button === 2) {
                // Right click: Issue Move / Attack order to selected units
                e.preventDefault();
                if (this.onMoveOrder) {
                    this.onMoveOrder(gx, gy);
                }
            }
        });

        // Continuous drag-panning
        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isDragging && (e.buttons === 1 || e.which === 1)) {
                const { gx, gy } = this.getGridCoordsFromEvent(e);
                this.panCameraTo(gx, gy);
            }
        });

        // Mouse release / exit
        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
        });

        // Prevent default browser context menu on right-click
        this.canvas.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });
    }

    /**
     * Centers the camera on the specified grid coordinates.
     *
     * @param {number} gx - Target grid X
     * @param {number} gy - Target grid Y
     */
    panCameraTo(gx, gy) {
        if (this.camera && typeof this.camera.centerOnGrid === 'function') {
            this.camera.centerOnGrid(gx, gy, false);
        } else if (this.camera) {
            const sx = (gx - gy) * 32;
            const sy = (gx + gy) * 24;
            const vw = this.camera.viewportWidth || 1024;
            const vh = this.camera.viewportHeight || 768;
            this.camera.targetX = (vw / 2) - sx;
            this.camera.targetY = (vh / 2) - sy;
            this.camera.x = this.camera.targetX;
            this.camera.y = this.camera.targetY;
        }
    }

    /**
     * Renders the complete 2D radar view:
     * 1. Terrain & elevation color map
     * 2. Resource nodes
     * 3. Units and buildings
     * 4. Viewport wireframe frustum
     *
     * @param {Array<Object>} [entities=[]] - List of active entities to plot on radar
     */
    render(entities = []) {
        if (!this.ctx && this.canvas) {
            this.ctx = this.canvas.getContext('2d');
        }
        const ctx = this.ctx;
        if (!ctx) return;

        // 1. Clear radar canvas background
        ctx.fillStyle = '#141f11';
        ctx.fillRect(0, 0, this.size, this.size);

        // 2. Render Terrain Grid
        if (this.grid) {
            const step = 2; // Render in 2x2 blocks for optimal performance
            for (let gy = 0; gy < this.mapHeight; gy += step) {
                for (let gx = 0; gx < this.mapWidth; gx += step) {
                    const idx = gy * this.mapWidth + gx;
                    const walkability = this.grid.walkability ? this.grid.walkability[idx] : 0;
                    const terrainType = this.grid.terrainType ? this.grid.terrainType[idx] : 2;
                    const elevation = this.grid.elevation ? this.grid.elevation[idx] : 0;

                    let color = '#23331b'; // Default passable green

                    if (terrainType === 1) {
                        color = '#1a3a5f'; // Deep water blue
                    } else if (walkability > 0) {
                        color = '#3e3223'; // Rocky cliff / obstacle brown
                    } else if (elevation > 0) {
                        color = '#384d28'; // Elevated ground
                    }

                    ctx.fillStyle = color;
                    ctx.fillRect(gx * this.scaleX, gy * this.scaleY, step * this.scaleX + 0.5, step * this.scaleY + 0.5);
                }
            }

            // 3. Render Resource Nodes
            if (this.grid.resourceTypes) {
                for (let gy = 0; gy < this.mapHeight; gy += 2) {
                    for (let gx = 0; gx < this.mapWidth; gx += 2) {
                        const idx = gy * this.mapWidth + gx;
                        const resType = this.grid.resourceTypes[idx];
                        if (resType > 0) {
                            // Gold for crops/rice, forest green for trees/bamboo
                            ctx.fillStyle = (resType === 100 || resType === 1) ? '#f1c40f' : '#1b5e20';
                            ctx.fillRect(gx * this.scaleX, gy * this.scaleY, 2, 2);
                        }
                    }
                }
            }
        }

        // 4. Render Units and Buildings
        for (let i = 0; i < entities.length; i++) {
            const ent = entities[i];
            if (!ent || ent.isDead) continue;

            const egx = (ent.wx !== undefined ? ent.wx : ent.gx) * this.scaleX;
            const egy = (ent.wy !== undefined ? ent.wy : ent.gy) * this.scaleY;

            // Faction color: Player = Cyan (#00e5ff), Enemy = Red (#ff3333), Neutral = Purple (#ab47bc)
            const color = (ent.owner === 0) ? '#00e5ff' : ((ent.owner === 1) ? '#ff3333' : '#ab47bc');
            ctx.fillStyle = color;

            if (ent.isBuilding) {
                // Buildings rendered as larger 4x4 squares
                ctx.fillRect(egx - 2, egy - 2, 4, 4);
            } else {
                // Units rendered as 3x3 dots
                ctx.fillRect(egx - 1, egy - 1, 3, 3);
            }

            // Highlight selected units with a white outline
            if (ent.selected) {
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1;
                ctx.strokeRect(egx - 2.5, egy - 2.5, 5, 5);
            }
        }

        // 5. Render Camera Viewport Wireframe Overlay
        this.renderViewportWireframe(ctx);

        // 6. Draw Minimap Outer Bezel
        ctx.strokeStyle = '#43543d';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(0, 0, this.size, this.size);
    }

    /**
     * Computes the 4 corners of the camera viewport on the isometric grid
     * and draws the corresponding quadrilateral wireframe on the radar.
     */
    renderViewportWireframe(ctx) {
        if (!this.camera) return;

        const vw = this.camera.viewportWidth || 1024;
        const vh = this.camera.viewportHeight || 768;
        const elevGrid = this.grid ? this.grid.elevation : null;

        // Map the 4 screen corners back to grid space
        const p0 = IsometricMath.screenToGrid(0, 0, this.camera, elevGrid, this.mapWidth, this.mapHeight);
        const p1 = IsometricMath.screenToGrid(vw, 0, this.camera, elevGrid, this.mapWidth, this.mapHeight);
        const p2 = IsometricMath.screenToGrid(vw, vh, this.camera, elevGrid, this.mapWidth, this.mapHeight);
        const p3 = IsometricMath.screenToGrid(0, vh, this.camera, elevGrid, this.mapWidth, this.mapHeight);

        const x0 = p0.gx * this.scaleX;
        const y0 = p0.gy * this.scaleY;
        const x1 = p1.gx * this.scaleX;
        const y1 = p1.gy * this.scaleY;
        const x2 = p2.gx * this.scaleX;
        const y2 = p2.gy * this.scaleY;
        const x3 = p3.gx * this.scaleX;
        const y3 = p3.gy * this.scaleY;

        ctx.save();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.2;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.08)';

        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.lineTo(x3, y3);
        ctx.closePath();

        ctx.fill();
        ctx.stroke();
        ctx.restore();
    }
}
