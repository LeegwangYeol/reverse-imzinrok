/**
 * Isometric Projection Mathematics for Imjinrok 2+: Dawn
 *
 * Implements 64x48 diamond tile projection math, 16px discrete elevation offsets,
 * raycast-based screen-to-grid mouse picking across elevations 5 down to 0,
 * frustum culling bounding box calculation, and depth key generation for sorting.
 */

export const TILE_WIDTH = 64;
export const TILE_HEIGHT = 48;
export const HALF_WIDTH = 32;
export const HALF_HEIGHT = 24;
export const ELEVATION_HEIGHT = 16;

/**
 * Joymax 8-direction to 5-stored-direction + DirectDraw horizontal flip (DDLT_MIRRORLEFTRIGHT) mapping.
 * Joymax .spr sprites store 5 directions facing the left half-plane (0:SW, 1:W, 2:NW, 3:N, 4:S).
 * Right half-plane directions (NE, E, SE) are rendered by horizontally mirroring NW, W, SW with flipX = true.
 */
export const DIR8_TO_JOYMAX5 = [
    { dir5: 4, flipX: false }, // 0: S
    { dir5: 0, flipX: false }, // 1: SW
    { dir5: 1, flipX: false }, // 2: W
    { dir5: 2, flipX: false }, // 3: NW
    { dir5: 3, flipX: false }, // 4: N
    { dir5: 2, flipX: true  }, // 5: NE (mirror of NW)
    { dir5: 1, flipX: true  }, // 6: E  (mirror of W)
    { dir5: 0, flipX: true  }  // 7: SE (mirror of SW)
];

export class IsometricMath {
    /**
     * Converts integer grid coordinates (gx, gy) and elevation level to screen pixel coordinates.
     *
     * @param {number} gx - Integer tile grid X
     * @param {number} gy - Integer tile grid Y
     * @param {number} [elevation=0] - Discrete elevation level (0..5)
     * @param {Object} [camera={ x: 0, y: 0 }] - Camera offset object with x and y properties
     * @returns {{ x: number, y: number }} Screen coordinates in pixels
     */
    static gridToScreen(gx, gy, elevation = 0, camera = { x: 0, y: 0 }) {
        const camX = camera ? (camera.x || 0) : 0;
        const camY = camera ? (camera.y || 0) : 0;
        const sx = (gx - gy) * HALF_WIDTH + camX;
        const sy = (gx + gy) * HALF_HEIGHT + camY - (elevation * ELEVATION_HEIGHT);
        return { x: sx, y: sy };
    }

    /**
     * Converts continuous world coordinates (wx, wy) and elevation level to screen pixel coordinates.
     *
     * @param {number} wx - Continuous world X (grid units, e.g. 10.5)
     * @param {number} wy - Continuous world Y (grid units, e.g. 12.3)
     * @param {number} [elevation=0] - Discrete or interpolated elevation
     * @param {Object} [camera={ x: 0, y: 0 }] - Camera offset object with x and y properties
     * @returns {{ x: number, y: number }} Screen coordinates in pixels
     */
    static worldToScreen(wx, wy, elevation = 0, camera = { x: 0, y: 0 }) {
        const camX = camera ? (camera.x || 0) : 0;
        const camY = camera ? (camera.y || 0) : 0;
        const sx = (wx - wy) * HALF_WIDTH + camX;
        const sy = (wx + wy) * HALF_HEIGHT + camY - (elevation * ELEVATION_HEIGHT);
        return { x: sx, y: sy };
    }

    /**
     * Performs elevation-aware mouse picking from screen pixels back to the grid coordinate.
     * Raycasts candidate tile positions from highest elevation (5) down to ground (0).
     *
     * @param {number} screenX - Mouse or screen point X
     * @param {number} screenY - Mouse or screen point Y
     * @param {Object} camera - Camera offset object with x and y
     * @param {Uint8Array|Array<number>|null} elevationGrid - 1D array of elevation values indexed by (gy * mapWidth + gx)
     * @param {number} [mapWidth=180] - Width of the map in tiles
     * @param {number} [mapHeight=180] - Height of the map in tiles
     * @returns {{ gx: number, gy: number, elevation: number, valid: boolean }} Picked tile result
     */
    static screenToGrid(screenX, screenY, camera = { x: 0, y: 0 }, elevationGrid = null, mapWidth = 180, mapHeight = 180) {
        const camX = camera ? (camera.x || 0) : 0;
        const camY = camera ? (camera.y || 0) : 0;

        // Raycast from elevation 5 down to 0
        if (elevationGrid && elevationGrid.length >= mapWidth * mapHeight) {
            for (let elev = 5; elev >= 0; elev--) {
                const adjY = screenY + (elev * ELEVATION_HEIGHT);
                const xNorm = (screenX - camX) / HALF_WIDTH;
                const yNorm = (adjY - camY) / HALF_HEIGHT;
                const gx = Math.floor((xNorm + yNorm) / 2);
                const gy = Math.floor((yNorm - xNorm) / 2);

                if (gx >= 0 && gx < mapWidth && gy >= 0 && gy < mapHeight) {
                    const idx = gy * mapWidth + gx;
                    if (elevationGrid[idx] === elev) {
                        return { gx, gy, elevation: elev, valid: true };
                    }
                }
            }
        }

        // Fallback to ground elevation 0
        const xNorm = (screenX - camX) / HALF_WIDTH;
        const yNorm = (screenY - camY) / HALF_HEIGHT;
        const rawGx = Math.floor((xNorm + yNorm) / 2);
        const rawGy = Math.floor((yNorm - xNorm) / 2);

        const isValid = (rawGx >= 0 && rawGx < mapWidth && rawGy >= 0 && rawGy < mapHeight);
        const gx = Math.max(0, Math.min(mapWidth - 1, rawGx));
        const gy = Math.max(0, Math.min(mapHeight - 1, rawGy));
        const elev = (elevationGrid && elevationGrid.length >= mapWidth * mapHeight)
            ? (elevationGrid[gy * mapWidth + gx] || 0)
            : 0;

        return { gx, gy, elevation: elev, valid: isValid };
    }

    /**
     * Calculates the bounding range of grid tiles visible within the camera viewport for frustum culling.
     * Takes into account screen corners and maximum elevation offsets.
     *
     * @param {Object} camera - Camera object
     * @param {number} viewportWidth - Viewport width in pixels
     * @param {number} viewportHeight - Viewport height in pixels
     * @param {number} [mapWidth=180] - Width of the map in tiles
     * @param {number} [mapHeight=180] - Height of the map in tiles
     * @returns {{ minGx: number, maxGx: number, minGy: number, maxGy: number }} Bounding tile box
     */
    static getVisibleTileBounds(camera, viewportWidth, viewportHeight, mapWidth = 180, mapHeight = 180) {
        const camX = camera ? (camera.x || 0) : 0;
        const camY = camera ? (camera.y || 0) : 0;

        // Screen boundary corners to test:
        // Include top-left, top-right, bottom-right, bottom-left, plus upper elevation margin
        const maxElevShift = 5 * ELEVATION_HEIGHT; // 80 pixels
        const margin = 4;
        const elevMargin = 6;

        // Screen Y can reach viewportHeight + maxElevShift to account for high plateaus rendered upwards into the view
        const testPoints = [
            { sx: 0, sy: -maxElevShift },
            { sx: viewportWidth, sy: -maxElevShift },
            { sx: viewportWidth, sy: viewportHeight + maxElevShift },
            { sx: 0, sy: viewportHeight + maxElevShift },
            { sx: viewportWidth / 2, sy: 0 },
            { sx: viewportWidth / 2, sy: viewportHeight }
        ];

        let minX = Infinity;
        let maxX = -Infinity;
        let minY = Infinity;
        let maxY = -Infinity;

        for (const pt of testPoints) {
            const xNorm = (pt.sx - camX) / HALF_WIDTH;
            const yNorm = (pt.sy - camY) / HALF_HEIGHT;
            const gx = Math.floor((xNorm + yNorm) / 2);
            const gy = Math.floor((yNorm - xNorm) / 2);

            if (gx < minX) minX = gx;
            if (gx > maxX) maxX = gx;
            if (gy < minY) minY = gy;
            if (gy > maxY) maxY = gy;
        }

        return {
            minGx: Math.max(0, minX - margin),
            maxGx: Math.min(mapWidth - 1, maxX + margin),
            minGy: Math.max(0, minY - elevMargin),
            maxGy: Math.min(mapHeight - 1, maxY + margin)
        };
    }

    /**
     * Calculates a unique 64-bit safe integer depth key for isometric multi-layer Z-ordering.
     * DepthKey = (gx + gy) * 10000 + (layerPriority * 100) + subY
     *
     * Layer priorities:
     * 0: Ground tile (.ytl)
     * 1: Decal / shoreline (.ypr)
     * 2: Resource nodes (crop, bamboo, tree, rice)
     * 3: Pre-placed buildings / structures
     * 4: Ground units / heroes
     * 8: Air units
     * 9: Projectiles / VFX / damage numbers
     *
     * @param {number} gx - Discrete grid X
     * @param {number} gy - Discrete grid Y
     * @param {number} [layerPriority=0] - Drawing layer priority (0..9)
     * @param {number} [subY=0] - Sub-tile Y offset (0..99) for smooth passing sorting
     * @returns {number} Integer depth key
     */
    static getDepthKey(gx, gy, layerPriority = 0, subY = 0) {
        const clampedSubY = Math.max(0, Math.min(99, Math.floor(subY)));
        const clampedPriority = Math.max(0, Math.min(99, Math.floor(layerPriority)));
        return (gx + gy) * 10000 + (clampedPriority * 100) + clampedSubY;
    }

    /**
     * Maps an 8-direction index (0:S..7:SE) to Joymax 5-direction index (0:SW, 1:W, 2:NW, 3:N, 4:S) and flipX mirror boolean.
     *
     * @param {number} dir8 - Engine direction 0..7
     * @returns {{ dir5: number, flipX: boolean }} Joymax 5-dir and mirror flag
     */
    static directionToJoymax(dir8) {
        const d8 = ((Math.floor(dir8 || 0) % 8) + 8) % 8;
        return DIR8_TO_JOYMAX5[d8];
    }
}
