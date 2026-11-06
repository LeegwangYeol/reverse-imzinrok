/**
 * 180x180 Map Grid Simulation State
 *
 * Implements high-performance typed arrays for terrain layers, elevation, walkability,
 * resource nodes, building placement, and unit occupancy matching the 1,132,876-byte
 * Imjinrok 2+ .map binary specification.
 */

export class GameGrid {
    /**
     * @param {number} [width=180] - Map width in tiles
     * @param {number} [height=180] - Map height in tiles
     */
    constructor(width = 180, height = 180) {
        this.width = width;
        this.height = height;
        this.size = width * height;

        // Terrain graphic layers
        this.tileLayer1 = new Uint16Array(this.size); // Lower terrain tile index (.ytl)
        this.tileLayer2 = new Uint16Array(this.size); // Middle terrain tile index (.ypr / decal)
        this.tileLayer3 = new Uint16Array(this.size); // Main terrain block ID

        // Physical properties matching .map byte grids
        this.terrainType = new Uint8Array(this.size); // 1=water, 2=ground
        this.walkability = new Uint8Array(this.size); // 0=passable, 1..32=obstacle/cliff/deep water
        this.elevation = new Uint8Array(this.size);   // Discrete elevation 0..5
        this.waterDepth = new Uint8Array(this.size);  // Water depth / shoreline transition

        // Static structures
        this.buildingIds = new Uint16Array(this.size);
        this.buildingOwners = new Uint8Array(this.size); // 0..7 player ID

        // Harvestable resources: 1=potato, 2=bamboo, 3=tree, 100=rice
        this.resourceTypes = new Uint8Array(this.size);
        this.resourceAmounts = new Uint16Array(this.size);

        // Dynamic unit occupancy (-1 = empty, >= 0 = entity ID)
        this.unitOccupancy = new Int32Array(this.size).fill(-1);

        // Initialize default ground
        this.clearToDefault();
    }

    /**
     * Resets the entire grid to flat, walkable ground.
     */
    clearToDefault() {
        this.tileLayer1.fill(1);
        this.tileLayer2.fill(0);
        this.tileLayer3.fill(0);
        this.terrainType.fill(2); // Ground
        this.walkability.fill(0); // Passable
        this.elevation.fill(0);
        this.waterDepth.fill(0);
        this.buildingIds.fill(0);
        this.buildingOwners.fill(0);
        this.resourceTypes.fill(0);
        this.resourceAmounts.fill(0);
        this.unitOccupancy.fill(-1);
    }

    /**
     * Computes linear array index from 2D coordinates.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @returns {number} 1D array index
     */
    getIndex(gx, gy) {
        return gy * this.width + gx;
    }

    /**
     * Checks if coordinates fall within the grid boundaries.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @returns {boolean} True if within map bounds
     */
    isValid(gx, gy) {
        return gx >= 0 && gx < this.width && gy >= 0 && gy < this.height;
    }

    /**
     * Loads grid data from a parsed map object (supporting both snake_case and camelCase keys).
     *
     * @param {Object} mapData - Parsed .map JSON data
     */
    loadFromMapData(mapData) {
        if (!mapData) return;

        const w = mapData.width || this.width;
        const h = mapData.height || this.height;

        if (w !== this.width || h !== this.height) {
            this.width = w;
            this.height = h;
            this.size = w * h;
            this.tileLayer1 = new Uint16Array(this.size);
            this.tileLayer2 = new Uint16Array(this.size);
            this.tileLayer3 = new Uint16Array(this.size);
            this.terrainType = new Uint8Array(this.size);
            this.walkability = new Uint8Array(this.size);
            this.elevation = new Uint8Array(this.size);
            this.waterDepth = new Uint8Array(this.size);
            this.buildingIds = new Uint16Array(this.size);
            this.buildingOwners = new Uint8Array(this.size);
            this.resourceTypes = new Uint8Array(this.size);
            this.resourceAmounts = new Uint16Array(this.size);
            this.unitOccupancy = new Int32Array(this.size).fill(-1);
        }

        const layers = mapData.layers || {};

        const assignLayer = (target, ...sources) => {
            for (const src of sources) {
                if (src && (Array.isArray(src) || src.buffer)) {
                    target.set(src.subarray ? src.subarray(0, this.size) : src.slice(0, this.size));
                    return;
                }
            }
        };

        assignLayer(this.tileLayer1, mapData.tile_layer_1, mapData.tileLayer1, mapData.tile1, layers.tile_layer_1, layers.tileLayer1, layers.tile1);
        assignLayer(this.tileLayer2, mapData.tile_layer_2, mapData.tileLayer2, mapData.tile2, layers.tile_layer_2, layers.tileLayer2, layers.tile2);
        assignLayer(this.tileLayer3, mapData.tile_layer_3, mapData.tileLayer3, mapData.tile3, layers.tile_layer_3, layers.tileLayer3, layers.tile3);
        assignLayer(this.terrainType, mapData.terrain_type, mapData.terrainType, layers.terrain_type, layers.terrainType);
        assignLayer(this.walkability, mapData.walkability, layers.walkability);
        assignLayer(this.elevation, mapData.elevation, layers.elevation);
        assignLayer(this.waterDepth, mapData.water_depth, mapData.waterDepth, layers.water_depth, layers.waterDepth);
        assignLayer(this.buildingIds, mapData.building_id, mapData.buildingIds, layers.building_id, layers.buildingIds);
        assignLayer(this.buildingOwners, mapData.building_owner, mapData.buildingOwners, layers.building_owner, layers.buildingOwners);
        assignLayer(this.resourceTypes, mapData.resource_type, mapData.resourceTypes, layers.resource_type, layers.resourceTypes);
        assignLayer(this.resourceAmounts, mapData.resource_amount, mapData.resourceAmounts, layers.resource_amount, layers.resourceAmounts);

        // In parsed .map files (OFFSET_BYTE_GRID_2), the 'elevation' byte grid is actually the
        // tile variation sub-index (0..5, 16..38), not discrete 3D cliff height steps.
        const isParsedMapFile = Boolean(mapData.slug || mapData.theme_name || mapData.num_players);
        if (isParsedMapFile) {
            for (let i = 0; i < this.size; i++) {
                const subVar = this.elevation[i];
                if (this.tileLayer1[i] <= 1) {
                    this.tileLayer1[i] = (subVar % 28) + 1;
                }
                // In parsed maps, preserve discrete elevation 0..5 while filtering variation sub-indices (> 5)
                this.elevation[i] = subVar <= 5 ? subVar : 0;
                // Walkability 16 in .map denotes farm/crop soil (passable)
                if (this.walkability[i] === 16) {
                    this.walkability[i] = 0;
                }
                if (this.terrainType[i] === 1 && this.walkability[i] === 0) {
                    this.walkability[i] = 1;
                }
            }
        }

        // Ingest resources list from mapData.resources if resourceTypes layer was not populated
        if (Array.isArray(mapData.resources)) {
            let hasResources = false;
            for (let i = 0; i < this.size; i++) {
                if (this.resourceTypes[i] > 0) {
                    hasResources = true;
                    break;
                }
            }
            if (!hasResources) {
                for (const r of mapData.resources) {
                    if (r && r.x !== undefined && r.y !== undefined) {
                        const rIdx = r.y * this.width + r.x;
                        if (rIdx >= 0 && rIdx < this.size) {
                            this.resourceTypes[rIdx] = r.type_id || 1;
                            this.resourceAmounts[rIdx] = r.amount || 0;
                        }
                    }
                }
            }
        }
    }

    /**
     * Determines if a ground tile is passable by units.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {boolean} [ignoreUnits=true] - If false, tiles occupied by other units count as unwalkable
     * @returns {boolean} True if walkable
     */
    isWalkable(gx, gy, ignoreUnits = true) {
        if (gx < 0 || gx >= this.width || gy < 0 || gy >= this.height) {
            return false;
        }
        const idx = gy * this.width + gx;

        // Impassable terrain / obstacle flag
        if (this.walkability[idx] !== 0) return false;

        // Blocked by building
        if (this.buildingIds[idx] !== 0) return false;

        // Blocked by tree / resource
        if (this.resourceTypes[idx] !== 0) return false;

        // Unit collision check if requested
        if (!ignoreUnits && this.unitOccupancy[idx] >= 0) return false;

        return true;
    }

    /**
     * Sets tile sprite index on layer 1 (base terrain) or layer 2 (middle/decal).
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {number} tileId - Tile sprite index
     * @param {number} [layer=1] - Layer (1 or 2)
     */
    setTile(gx, gy, tileId, layer = 1) {
        if (!this.isValid(gx, gy)) return;
        const idx = this.getIndex(gx, gy);
        if (layer === 1) {
            this.tileLayer1[idx] = tileId;
        } else if (layer === 2) {
            this.tileLayer2[idx] = tileId;
        } else if (layer === 3) {
            this.tileLayer3[idx] = tileId;
        }
    }

    /**
     * Gets tile sprite index at given coordinate.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {number} [layer=1] - Layer (1, 2, or 3)
     * @returns {number} Tile sprite ID
     */
    getTile(gx, gy, layer = 1) {
        if (!this.isValid(gx, gy)) return 0;
        const idx = this.getIndex(gx, gy);
        if (layer === 1) return this.tileLayer1[idx];
        if (layer === 2) return this.tileLayer2[idx];
        return this.tileLayer3[idx];
    }

    /**
     * Sets elevation level, clamped between 0 and 5.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {number} elev - Elevation (0..5)
     */
    setElevation(gx, gy, elev) {
        if (!this.isValid(gx, gy)) return;
        const idx = this.getIndex(gx, gy);
        this.elevation[idx] = Math.max(0, Math.min(5, Math.floor(elev)));
    }

    /**
     * Gets elevation level at tile.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @returns {number} Elevation level (0..5)
     */
    getElevation(gx, gy) {
        if (!this.isValid(gx, gy)) return 0;
        return this.elevation[this.getIndex(gx, gy)];
    }

    /**
     * Sets walkability flag.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {number|boolean} walkable - 0/true for passable, 1/false for impassable
     */
    setWalkability(gx, gy, walkable) {
        if (!this.isValid(gx, gy)) return;
        const idx = this.getIndex(gx, gy);
        this.walkability[idx] = (typeof walkable === 'boolean') ? (walkable ? 0 : 1) : walkable;
    }

    /**
     * Places a harvestable resource node.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {number} type - Resource type (1=potato, 2=bamboo, 3=tree, 100=rice)
     * @param {number} [amount=100] - Initial harvestable amount
     */
    setResource(gx, gy, type, amount = 100) {
        if (!this.isValid(gx, gy)) return;
        const idx = this.getIndex(gx, gy);
        this.resourceTypes[idx] = type;
        this.resourceAmounts[idx] = amount;
    }

    /**
     * Clears any resource on the tile.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     */
    clearResource(gx, gy) {
        if (!this.isValid(gx, gy)) return;
        const idx = this.getIndex(gx, gy);
        this.resourceTypes[idx] = 0;
        this.resourceAmounts[idx] = 0;
    }

    /**
     * Places a building on the grid occupying a rectangle footprint.
     *
     * @param {number} gx - Origin grid tile X
     * @param {number} gy - Origin grid tile Y
     * @param {number} buildingId - Building archetype ID
     * @param {number} [owner=0] - Player owner ID
     * @param {number} [footprintW=2] - Width in tiles
     * @param {number} [footprintH=2] - Height in tiles
     */
    setBuilding(gx, gy, buildingId, owner = 0, footprintW = 2, footprintH = 2) {
        for (let dy = 0; dy < footprintH; dy++) {
            for (let dx = 0; dx < footprintW; dx++) {
                const targetX = gx + dx;
                const targetY = gy + dy;
                if (this.isValid(targetX, targetY)) {
                    const idx = this.getIndex(targetX, targetY);
                    this.buildingIds[idx] = buildingId;
                    this.buildingOwners[idx] = owner;
                }
            }
        }
    }

    /**
     * Clears a building footprint.
     *
     * @param {number} gx - Origin grid tile X
     * @param {number} gy - Origin grid tile Y
     * @param {number} [footprintW=2] - Width in tiles
     * @param {number} [footprintH=2] - Height in tiles
     */
    clearBuilding(gx, gy, footprintW = 2, footprintH = 2) {
        for (let dy = 0; dy < footprintH; dy++) {
            for (let dx = 0; dx < footprintW; dx++) {
                const targetX = gx + dx;
                const targetY = gy + dy;
                if (this.isValid(targetX, targetY)) {
                    const idx = this.getIndex(targetX, targetY);
                    this.buildingIds[idx] = 0;
                    this.buildingOwners[idx] = 0;
                }
            }
        }
    }

    /**
     * Sets unit occupancy for a single tile.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     * @param {number} unitId - Entity ID
     */
    setUnitOccupancy(gx, gy, unitId) {
        if (!this.isValid(gx, gy)) return;
        this.unitOccupancy[this.getIndex(gx, gy)] = unitId;
    }

    /**
     * Clears unit occupancy for a single tile.
     *
     * @param {number} gx - Grid tile X
     * @param {number} gy - Grid tile Y
     */
    clearUnitOccupancy(gx, gy) {
        if (!this.isValid(gx, gy)) return;
        this.unitOccupancy[this.getIndex(gx, gy)] = -1;
    }

    /**
     * Serializes all grid layers to a JSON-compatible object for saving/exporting.
     *
     * @returns {Object} Structured map layer data
     */
    exportToJSON() {
        return {
            width: this.width,
            height: this.height,
            tile_layer_1: Array.from(this.tileLayer1),
            tile_layer_2: Array.from(this.tileLayer2),
            tile_layer_3: Array.from(this.tileLayer3),
            terrain_type: Array.from(this.terrainType),
            walkability: Array.from(this.walkability),
            elevation: Array.from(this.elevation),
            water_depth: Array.from(this.waterDepth),
            building_id: Array.from(this.buildingIds),
            building_owner: Array.from(this.buildingOwners),
            resource_type: Array.from(this.resourceTypes),
            resource_amount: Array.from(this.resourceAmounts)
        };
    }
}
