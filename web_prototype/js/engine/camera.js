/**
 * Camera Controller for Isometric RTS Engine
 *
 * Handles smooth keyboard panning (WASD, Arrow keys), viewport edge panning,
 * zoom scaling, map boundary clamping, and grid centering.
 */

export class Camera {
    /**
     * @param {number} [viewportWidth=1024] - Initial viewport width in pixels
     * @param {number} [viewportHeight=768] - Initial viewport height in pixels
     * @param {number} [mapWidth=180] - Width of the map in tiles
     * @param {number} [mapHeight=180] - Height of the map in tiles
     */
    constructor(viewportWidth = 1024, viewportHeight = 768, mapWidth = 180, mapHeight = 180) {
        this.viewportWidth = viewportWidth;
        this.viewportHeight = viewportHeight;
        this.mapWidth = mapWidth;
        this.mapHeight = mapHeight;

        // Current rendered camera position (screen offset)
        this.x = 0;
        this.y = 0;

        // Target camera position for smooth interpolation
        this.targetX = 0;
        this.targetY = 0;

        // Zoom parameters
        this.zoom = 1.0;
        this.minZoom = 0.5;
        this.maxZoom = 2.0;
        this.targetZoom = 1.0;

        // Pan configuration
        this.panSpeed = 800; // Pixels per second at 1.0 zoom
        this.edgeThreshold = 24; // Distance from window edge for edge scrolling
        this.enableEdgePan = true;
        this.smoothing = 14; // Lerp smoothing factor

        // Bounds padding in pixels
        this.boundsMargin = 250;

        // Center on the middle of the map by default
        this.centerOnGrid(Math.floor(mapWidth / 2), Math.floor(mapHeight / 2), true);
    }

    /**
     * Centers the camera on a specific integer or floating-point grid position.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {boolean} [snap=false] - If true, immediately teleports without smooth lerp
     */
    centerOnGrid(gx, gy, snap = false) {
        const sx = (gx - gy) * 32;
        const sy = (gx + gy) * 24;

        this.targetX = (this.viewportWidth / 2) - sx;
        this.targetY = (this.viewportHeight / 2) - sy;

        this.clampBounds();

        if (snap) {
            this.x = this.targetX;
            this.y = this.targetY;
        }
    }

    /**
     * Sets the target zoom factor, clamped to [minZoom, maxZoom].
     *
     * @param {number} zoomLevel - Target zoom multiplier
     * @param {boolean} [snap=false] - Whether to snap immediately
     */
    setZoom(zoomLevel, snap = false) {
        this.targetZoom = Math.max(this.minZoom, Math.min(this.maxZoom, zoomLevel));
        if (snap) {
            this.zoom = this.targetZoom;
        }
    }

    /**
     * Adjusts zoom relative to current zoom by a delta.
     *
     * @param {number} delta - Zoom increment (e.g. +0.1 or -0.1)
     */
    zoomBy(delta) {
        this.setZoom(this.targetZoom + delta);
    }

    /**
     * Updates viewport dimensions on canvas or window resize.
     *
     * @param {number} width - New viewport width
     * @param {number} height - New viewport height
     */
    resize(width, height) {
        this.viewportWidth = width;
        this.viewportHeight = height;
        this.clampBounds();
    }

    /**
     * Clamps camera target coordinates so it cannot scroll indefinitely off into the void.
     */
    clampBounds() {
        // In diamond isometric projection:
        // Top corner (0, 0) -> sx = 0, sy = 0
        // Right corner (W, 0) -> sx = W * 32, sy = W * 24
        // Bottom corner (W, H) -> sx = (W - H) * 32, sy = (W + H) * 24
        // Left corner (0, H) -> sx = -H * 32, sy = H * 24
        const maxSx = this.mapWidth * 32;
        const minSx = -this.mapHeight * 32;
        const maxSy = (this.mapWidth + this.mapHeight) * 24;
        const minSy = 0;

        // The camera target (targetX, targetY) shifts the world:
        // Screen pixel = World pixel + targetX
        // Allow camera to pan such that center stays within the map bounding diamond plus margins
        const minTargetX = (this.viewportWidth / 2) - maxSx - this.boundsMargin;
        const maxTargetX = (this.viewportWidth / 2) - minSx + this.boundsMargin;
        const minTargetY = (this.viewportHeight / 2) - maxSy - this.boundsMargin;
        const maxTargetY = (this.viewportHeight / 2) - minSy + this.boundsMargin;

        this.targetX = Math.max(minTargetX, Math.min(maxTargetX, this.targetX));
        this.targetY = Math.max(minTargetY, Math.min(maxTargetY, this.targetY));
    }

    /**
     * Main update routine called each animation frame.
     *
     * @param {number} deltaSec - Frame elapsed time in seconds
     * @param {Object<string, boolean>} [keysDown={}] - Map of active key codes
     * @param {{ x: number, y: number }|null} [mousePos=null] - Mouse screen coordinates
     */
    update(deltaSec, keysDown = {}, mousePos = null) {
        let dx = 0;
        let dy = 0;

        // Keyboard panning (Arrow keys or WASD)
        if (keysDown['ArrowLeft'] || keysDown['KeyA']) dx += 1;
        if (keysDown['ArrowRight'] || keysDown['KeyD']) dx -= 1;
        if (keysDown['ArrowUp'] || keysDown['KeyW']) dy += 1;
        if (keysDown['ArrowDown'] || keysDown['KeyS']) dy -= 1;

        // Viewport edge panning
        if (this.enableEdgePan && mousePos) {
            if (mousePos.x >= 0 && mousePos.x <= this.edgeThreshold) {
                dx += 1;
            } else if (mousePos.x >= this.viewportWidth - this.edgeThreshold && mousePos.x <= this.viewportWidth) {
                dx -= 1;
            }

            if (mousePos.y >= 0 && mousePos.y <= this.edgeThreshold) {
                dy += 1;
            } else if (mousePos.y >= this.viewportHeight - this.edgeThreshold && mousePos.y <= this.viewportHeight) {
                dy -= 1;
            }
        }

        // Apply movement vector with normalization
        const len = Math.hypot(dx, dy);
        if (len > 0) {
            const speed = (this.panSpeed / this.zoom) * deltaSec;
            this.targetX += (dx / len) * speed;
            this.targetY += (dy / len) * speed;
            this.clampBounds();
        }

        // Smooth camera position interpolation
        const lerpFactor = Math.min(1.0, this.smoothing * deltaSec);
        this.x += (this.targetX - this.x) * lerpFactor;
        this.y += (this.targetY - this.y) * lerpFactor;

        // Smooth zoom interpolation
        if (Math.abs(this.targetZoom - this.zoom) > 0.001) {
            this.zoom += (this.targetZoom - this.zoom) * lerpFactor;
        } else {
            this.zoom = this.targetZoom;
        }
    }
}
