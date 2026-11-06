/**
 * In-Browser Map Editor Mode for Imjinrok 2+: Dawn
 *
 * Provides live in-browser terrain painting, elevation sculpting with local
 * cliff walkability recalculation, resource node placement, unit/building placement,
 * map switching across authentic .map files, and JSON / bit-exact binary .map export.
 */

import { IsometricMath, HALF_WIDTH, HALF_HEIGHT, ELEVATION_HEIGHT, TILE_WIDTH, TILE_HEIGHT } from '../engine/isometric.js';

export const POPULAR_MAPS = [
    { id: '(2인,70X70)함성이그치지않는바다.map', name: '(2인, 70x70) 함성이 그치지 않는 바다', width: 70, height: 70, theme: 'bright', assetKey: 'sea_of_cries' },
    { id: '(2인,100x100)태극.map', name: '(2인, 100x100) 태극', width: 100, height: 100, theme: 'normal', assetKey: 'taegeuk' },
    { id: '(2인,100X100)수성.map', name: '(2인, 100x100) 수성', width: 100, height: 100, theme: 'normal', assetKey: 'suseong' },
    { id: '(4인,120X120)경주비빔밥.map', name: '(4인, 120x120) 경주비빔밥', width: 120, height: 120, theme: 'green', assetKey: 'gyeongju_bibimbap' },
    { id: '(4인,140x140)무극.map', name: '(4인, 140x140) 무극', width: 140, height: 140, theme: 'dark', assetKey: 'mugeuk' },
    { id: '(2인,180X180)바다위의성.map', name: '(2인, 180x180) 바다위의 성', width: 180, height: 180, theme: 'bright', assetKey: 'castle_on_the_sea' },
    { id: '(3인,180x180)삼파전.map', name: '(3인, 180x180) 삼파전', width: 180, height: 180, theme: 'normal', assetKey: 'three_way' },
    { id: '(4인,180X180)격돌공성전.map', name: '(4인, 180x180) 격돌공성전', width: 180, height: 180, theme: 'brown', assetKey: 'clash_siege' }
];

export const TILE_PALETTES = {
    grss: {
        name: 'Grass (평원)',
        tiles: [
            { id: 1, label: 'Grass 1' },
            { id: 2, label: 'Grass 2' },
            { id: 3, label: 'Grass 3' },
            { id: 4, label: 'Grass 4' },
            { id: 5, label: 'Grass Flower' },
            { id: 6, label: 'Grass Path' }
        ]
    },
    diff: {
        name: 'Dirt / Earth (황토/흙)',
        tiles: [
            { id: 10, label: 'Dirt Plain' },
            { id: 11, label: 'Dirt Mound' },
            { id: 12, label: 'Cliff Edge' },
            { id: 13, label: 'Rocky Soil' },
            { id: 14, label: 'Dry Earth' }
        ]
    },
    castle: {
        name: 'Castle / Stone (석벽/공성)',
        tiles: [
            { id: 20, label: 'Castle Stone 1' },
            { id: 21, label: 'Castle Stone 2' },
            { id: 22, label: 'Paved Road' },
            { id: 23, label: 'Stone Fortress' },
            { id: 24, label: 'Castle Tile' }
        ]
    },
    water: {
        name: 'Water (강/바다)',
        tiles: [
            { id: 30, label: 'Shallow Water' },
            { id: 31, label: 'Deep Water' },
            { id: 32, label: 'River Shore' }
        ]
    }
};

export const RESOURCE_TYPES = [
    { typeId: 1, name: 'Potato (감자밭)', defaultAmount: 70, category: 'food', icon: '🥔' },
    { typeId: 2, name: 'Bamboo (대나무)', defaultAmount: 25, category: 'wood', icon: '🎋' },
    { typeId: 3, name: 'Tree (나무/목재)', defaultAmount: 170, category: 'wood', icon: '🌲' },
    { typeId: 100, name: 'Rice (벼/논)', defaultAmount: 40, category: 'food', icon: '🌾' }
];

export const MAP_EDITOR_UNITS = [
    { id: 'farmer_k', name: '조선 농부', faction: 0, sprite: 'char/farmer.spr', speed: 8, hp: 80, cost: 50 },
    { id: 'sword_k', name: '조선 창병', faction: 0, sprite: 'char/swordk.spr', speed: 10, hp: 160, cost: 80 },
    { id: 'bow_k', name: '조선 궁수', faction: 0, sprite: 'char/bowmank.spr', speed: 9, hp: 120, cost: 100 },
    { id: 'turtle', name: '조선 거북선', faction: 0, sprite: 'char/turtle.spr', speed: 8, hp: 450, cost: 350 },
    { id: 'hwacha', name: '조선 화차', faction: 0, sprite: 'char/hwacha.spr', speed: 6, hp: 200, cost: 250 },
    { id: 'leesunsin', name: '이순신', faction: 0, sprite: 'char/leesunsin.spr', speed: 10, hp: 400, cost: 500 },
    { id: 'samurai_j', name: '일본 사무라이', faction: 1, sprite: 'char/samurai.spr', speed: 11, hp: 180, cost: 90 },
    { id: 'gunner_j', name: '일본 뎃뽀 아시가루', faction: 1, sprite: 'char/gunnerj.spr', speed: 8, hp: 110, cost: 110 },
    { id: 'seisho', name: '세이쇼오', faction: 1, sprite: 'char/seisho.spr', speed: 9, hp: 350, cost: 450 },
    { id: 'cavalry_m', name: '명 창기병', faction: 2, sprite: 'char/cavalrym.spr', speed: 14, hp: 220, cost: 180 },
    { id: 'chunlin', name: '천린', faction: 2, sprite: 'char/generalc2.spr', speed: 10, hp: 380, cost: 420 }
];

export const MAP_EDITOR_BUILDINGS = [
    { id: 1, name: '조선 본영', faction: 0, width: 3, height: 3, hp: 2000 },
    { id: 2, name: '조선 훈련소', faction: 0, width: 2, height: 2, hp: 1200 },
    { id: 3, name: '망루', faction: 0, width: 1, height: 1, hp: 600 },
    { id: 11, name: '일본 본영', faction: 1, width: 3, height: 3, hp: 2000 },
    { id: 12, name: '일본 훈련소', faction: 1, width: 2, height: 2, hp: 1200 },
    { id: 21, name: '중립 성문', faction: 2, width: 2, height: 2, hp: 1500 }
];

export class MapEditor {
    /**
     * @param {Object} grid - GameGrid instance
     * @param {Object|Function} [options={}] - Configuration options or onExportMap callback
     */
    constructor(grid, options = {}) {
        this.grid = grid;

        // Support passing onExportMap directly as second argument for backward compatibility
        const opts = (typeof options === 'function') ? { onExportMap: options } : options;

        this.container = opts.container || null;
        this.canvas = opts.canvas || null;
        this.camera = opts.camera || null;
        this.entityManager = opts.entityManager || opts.entities || null;
        this.onExportMap = opts.onExportMap || null;
        this.onModeChange = opts.onModeChange || null;
        this.onMapChange = opts.onMapChange || null;
        this.onPlaceUnit = opts.onPlaceUnit || null;
        this.apiBaseUrl = opts.apiBaseUrl || '';

        // Mode state
        this.isEnabled = false;
        this.activeTool = 'paint_tile'; // 'paint_tile', 'raise_elev', 'lower_elev', 'place_resource', 'place_unit', 'place_building', 'erase', 'player_start'

        // Brush settings
        this.brushSize = 1; // 1 (1x1), 2 (2x2), 3 (3x3)
        this.targetLayer = 1; // 1=tileLayer1, 2=tileLayer2
        this.selectedCategory = 'grss';
        this.selectedTileId = 1;

        // Elevation settings
        this.selectedElevation = 1;

        // Resource settings
        this.selectedResource = 1; // 1=potato, 2=bamboo, 3=tree, 100=rice
        this.resourceAmount = 70;

        // Unit / Building settings
        this.selectedFaction = 0; // 0=Blue/Chosun, 1=Red/Japan, 2=Neutral
        this.selectedUnitId = 'sword_k';
        this.selectedBuildingId = 1;

        // Map state
        this.currentMapName = '(2인,100X100)수성.map';
        this.currentThemeId = 0;
        this.currentThemeName = 'normal';

        // Tracking changes for bit-exact binary export
        this.playerStarts = [
            { player_id: 0, x: 20, y: 20 },
            { player_id: 1, x: (this.grid ? this.grid.width : 180) - 20, y: (this.grid ? this.grid.height : 180) - 20 }
        ];
        this.placedUnits = [];
        this.removedResources = [];
        this.modifiedTerrain = new Map(); // key "x,y" => { walkability, terrain_type }

        // Interaction state
        this.isMouseDown = false;
        this.hoveredGridPos = null;
        this.lastAppliedCoord = null;

        // DOM elements
        this.dom = {
            wrapper: null,
            modeToggleBtn: null,
            toolbar: null,
            statusBadge: null,
            mapSelect: null
        };

        if (this.container) {
            this.mount(this.container);
        }
        if (this.canvas) {
            this.attachCanvas(this.canvas);
        }
    }

    /**
     * Getter / Setter for editor mode state.
     */
    get isEditorMode() {
        return this.isEnabled;
    }

    set isEditorMode(value) {
        this.toggle(Boolean(value));
    }

    /**
     * Switches between Game Mode and Map Editor Mode.
     * In editor mode: pauses unit AI/combat, enables editing toolbars & tile highlight.
     *
     * @param {boolean} [forceState] - Optional explicit target state
     */
    toggle(forceState) {
        const nextState = forceState !== undefined ? Boolean(forceState) : !this.isEnabled;
        if (this.isEnabled === nextState) return;

        this.isEnabled = nextState;

        // 1. Pause or resume unit AI & combat
        if (this.entityManager) {
            if (typeof this.entityManager.setAIPaused === 'function') {
                this.entityManager.setAIPaused(this.isEnabled);
            } else if (Array.isArray(this.entityManager)) {
                for (const ent of this.entityManager) {
                    if (ent) ent.aiPaused = this.isEnabled;
                }
            }
        }

        // 2. Update DOM UI state
        if (this.dom.wrapper) {
            if (this.isEnabled) {
                this.dom.wrapper.classList.add('editor-active');
            } else {
                this.dom.wrapper.classList.remove('editor-active');
            }
        }

        if (this.dom.modeToggleBtn) {
            if (this.isEnabled) {
                this.dom.modeToggleBtn.classList.add('active');
                this.dom.modeToggleBtn.innerHTML = '🗺️ <strong>Map Editor Mode</strong>';
                this.dom.modeToggleBtn.title = 'Click to switch back to Game Mode';
            } else {
                this.dom.modeToggleBtn.classList.remove('active');
                this.dom.modeToggleBtn.innerHTML = '⚔️ <strong>Game Mode</strong>';
                this.dom.modeToggleBtn.title = 'Click to switch to Map Editor Mode';
            }
        }

        if (this.dom.toolbar) {
            this.dom.toolbar.style.display = this.isEnabled ? 'block' : 'none';
        }

        // 3. Fire callbacks and custom event
        if (this.onModeChange) {
            this.onModeChange(this.isEnabled);
        }

        if (typeof window !== 'undefined' && window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('map-editor-mode-changed', {
                detail: { isEnabled: this.isEnabled }
            }));
        }
    }

    /**
     * Sets the active editing tool.
     *
     * @param {string} tool - Tool name
     */
    setTool(tool) {
        this.activeTool = tool;
        if (this.dom.toolbar) {
            const toolButtons = this.dom.toolbar.querySelectorAll('.tool-btn');
            toolButtons.forEach(btn => {
                if (btn.dataset.tool === tool) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
            this.updateToolPanels();
        }
    }

    /**
     * Sets the brush radius size (1 = 1x1, 2 = 2x2, 3 = 3x3).
     *
     * @param {number} size - 1, 2, or 3
     */
    setBrushSize(size) {
        this.brushSize = Math.max(1, Math.min(3, parseInt(size, 10) || 1));
        if (this.dom.toolbar) {
            const sizeBtns = this.dom.toolbar.querySelectorAll('.brush-size-btn');
            sizeBtns.forEach(btn => {
                if (parseInt(btn.dataset.size, 10) === this.brushSize) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
    }

    /**
     * Sets tile ID and target layer.
     *
     * @param {number} tileId - Tile sprite index
     * @param {number} [layer=1] - 1 or 2
     */
    setTileId(tileId, layer = 1) {
        this.selectedTileId = parseInt(tileId, 10) || 1;
        this.targetLayer = layer;
    }

    /**
     * Sets resource type and quantity.
     *
     * @param {number} typeId - Resource type ID (1=potato, 2=bamboo, 3=tree, 100=rice)
     * @param {number} [amount] - Quantity
     */
    setResourceType(typeId, amount) {
        this.selectedResource = parseInt(typeId, 10) || 1;
        if (amount !== undefined) {
            this.resourceAmount = Math.max(1, Math.min(500, parseInt(amount, 10) || 100));
        } else {
            const resDef = RESOURCE_TYPES.find(r => r.typeId === this.selectedResource);
            if (resDef) this.resourceAmount = resDef.defaultAmount;
        }
    }

    /**
     * Applies the current active tool at (gx, gy) across the active brush radius.
     *
     * @param {number} gx - Center grid tile X
     * @param {number} gy - Center grid tile Y
     */
    applyBrush(gx, gy) {
        if (!this.isEnabled || !this.grid) return;
        if (gx < 0 || gx >= this.grid.width || gy < 0 || gy >= this.grid.height) return;

        // Calculate brush boundary box
        const half = Math.floor(this.brushSize / 2);
        const isEven = (this.brushSize % 2 === 0);
        const minX = Math.max(0, gx - half);
        const maxX = Math.min(this.grid.width - 1, isEven ? gx + half - 1 : gx + half);
        const minY = Math.max(0, gy - half);
        const maxY = Math.min(this.grid.height - 1, isEven ? gy + half - 1 : gy + half);

        let elevationChanged = false;

        for (let ty = minY; ty <= maxY; ty++) {
            for (let tx = minX; tx <= maxX; tx++) {
                const idx = this.grid.getIndex(tx, ty);

                switch (this.activeTool) {
                    case 'paint_tile':
                        if (this.targetLayer === 1) {
                            this.grid.tileLayer1[idx] = this.selectedTileId;
                        } else if (this.targetLayer === 2) {
                            this.grid.tileLayer2[idx] = this.selectedTileId;
                        }
                        // If painting water tile, update terrain type
                        if (this.selectedCategory === 'water') {
                            this.grid.terrainType[idx] = 1;
                            this.grid.walkability[idx] = 1; // Impassable
                            this.modifiedTerrain.set(`${tx},${ty}`, { walkability: 1, terrain_type: 1 });
                        } else {
                            if (this.grid.terrainType[idx] === 1) {
                                this.grid.terrainType[idx] = 2; // Ground
                                this.modifiedTerrain.set(`${tx},${ty}`, { walkability: 0, terrain_type: 2 });
                            }
                        }
                        break;

                    case 'raise_elev':
                        this.grid.elevation[idx] = Math.min(5, this.grid.elevation[idx] + 1);
                        elevationChanged = true;
                        break;

                    case 'lower_elev':
                        this.grid.elevation[idx] = Math.max(0, this.grid.elevation[idx] - 1);
                        elevationChanged = true;
                        break;

                    case 'set_elev':
                        this.grid.elevation[idx] = Math.max(0, Math.min(5, this.selectedElevation));
                        elevationChanged = true;
                        break;

                    case 'place_resource':
                        this.grid.setResource(tx, ty, this.selectedResource, this.resourceAmount);
                        // Trees (3) and Bamboo (2) block walkability
                        if (this.selectedResource === 2 || this.selectedResource === 3) {
                            this.grid.walkability[idx] = 1;
                        }
                        break;

                    case 'place_unit':
                        if (tx === gx && ty === gy) { // Place unit once at center
                            this.spawnUnitAt(tx, ty, this.selectedUnitId, this.selectedFaction);
                        }
                        break;

                    case 'place_building':
                        if (tx === gx && ty === gy) {
                            this.placeBuildingAt(tx, ty, this.selectedBuildingId, this.selectedFaction);
                        }
                        break;

                    case 'player_start':
                        if (tx === gx && ty === gy) {
                            this.setPlayerStart(this.selectedFaction, tx, ty);
                        }
                        break;

                    case 'erase':
                        // Clear resources
                        if (this.grid.resourceTypes[idx] > 0) {
                            this.removedResources.push({ x: tx, y: ty });
                            this.grid.clearResource(tx, ty);
                        }
                        // Clear buildings
                        if (this.grid.buildingIds && this.grid.buildingIds[idx] > 0) {
                            this.grid.buildingIds[idx] = 0;
                            this.grid.buildingOwners[idx] = 0;
                        }
                        // Restore walkability if ground
                        if (this.grid.terrainType[idx] === 2) {
                            this.grid.walkability[idx] = 0;
                        }
                        elevationChanged = true;
                        break;
                }
            }
        }

        // Recalculate local cliff walkability if elevation changed
        if (elevationChanged) {
            this.recalculateLocalWalkability(gx, gy, half + 1);
        }
    }

    /**
     * Recalculates local cliff walkability around (gx, gy).
     * Any adjacent tile pair with height difference |elev1 - elev2| > 1 is marked as an impassable cliff.
     *
     * @param {number} gx - Center grid tile X
     * @param {number} gy - Center grid tile Y
     * @param {number} [radius=1] - Radius of local recalculation
     */
    recalculateLocalWalkability(gx, gy, radius = 1) {
        if (!this.grid) return;
        const w = this.grid.width;
        const h = this.grid.height;

        const minX = Math.max(0, gx - radius - 1);
        const maxX = Math.min(w - 1, gx + radius + 1);
        const minY = Math.max(0, gy - radius - 1);
        const maxY = Math.min(h - 1, gy + radius + 1);

        const neighbors = [
            [-1, 0], [1, 0], [0, -1], [0, 1],
            [-1, -1], [1, -1], [-1, 1], [1, 1]
        ];

        for (let cy = minY; cy <= maxY; cy++) {
            for (let cx = minX; cx <= maxX; cx++) {
                const idx = cy * w + cx;
                const currentElev = this.grid.elevation[idx];

                // If water, always impassable
                if (this.grid.terrainType[idx] === 1) {
                    this.grid.walkability[idx] = 1;
                    continue;
                }

                // Check for cliffs with any neighbor
                let isCliff = false;
                for (const [dx, dy] of neighbors) {
                    const nx = cx + dx;
                    const ny = cy + dy;
                    if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
                        const nIdx = ny * w + nx;
                        const nElev = this.grid.elevation[nIdx];
                        if (Math.abs(nElev - currentElev) > 1) {
                            isCliff = true;
                            break;
                        }
                    }
                }

                if (isCliff) {
                    this.grid.walkability[idx] = 2; // Cliff obstacle
                    this.modifiedTerrain.set(`${cx},${cy}`, { walkability: 2, terrain_type: this.grid.terrainType[idx] });
                } else {
                    // Check if blocked by building or tree resource
                    const resType = this.grid.resourceTypes[idx];
                    const bldId = this.grid.buildingIds ? this.grid.buildingIds[idx] : 0;
                    if (bldId > 0 || resType === 2 || resType === 3) {
                        this.grid.walkability[idx] = 1;
                    } else {
                        this.grid.walkability[idx] = 0; // Passable
                    }
                    this.modifiedTerrain.set(`${cx},${cy}`, { walkability: this.grid.walkability[idx], terrain_type: this.grid.terrainType[idx] });
                }
            }
        }
    }

    /**
     * Spawns a unit instance onto the map grid.
     */
    spawnUnitAt(gx, gy, unitId, faction) {
        const archetype = MAP_EDITOR_UNITS.find(u => u.id === unitId) || MAP_EDITOR_UNITS[0];
        const unitData = {
            id: Date.now() + Math.floor(Math.random() * 1000),
            archetype: archetype.id,
            name: archetype.name,
            korean_name: archetype.name,
            sprite_name: archetype.sprite,
            gx,
            gy,
            wx: gx + 0.5,
            wy: gy + 0.5,
            owner: faction,
            move_speed: archetype.speed,
            hp: archetype.hp,
            max_hp: archetype.hp
        };

        this.placedUnits.push(unitData);

        if (this.onPlaceUnit) {
            this.onPlaceUnit(unitData);
        } else if (this.entityManager) {
            if (typeof this.entityManager.spawnUnit === 'function') {
                this.entityManager.spawnUnit(unitData);
            } else if (Array.isArray(this.entityManager)) {
                this.entityManager.push(unitData);
            }
        }

        if (this.grid.setUnitOccupancy) {
            this.grid.setUnitOccupancy(gx, gy, unitData.id);
        }
    }

    /**
     * Places a building on the map grid.
     */
    placeBuildingAt(gx, gy, buildingId, faction) {
        const bld = MAP_EDITOR_BUILDINGS.find(b => b.id === buildingId) || MAP_EDITOR_BUILDINGS[0];
        if (this.grid.setBuilding) {
            this.grid.setBuilding(gx, gy, bld.id, faction, bld.width, bld.height);
        }
        for (let dy = 0; dy < bld.height; dy++) {
            for (let dx = 0; dx < bld.width; dx++) {
                const tx = gx + dx;
                const ty = gy + dy;
                if (this.grid.isValid(tx, ty)) {
                    this.grid.walkability[this.grid.getIndex(tx, ty)] = 1;
                }
            }
        }
    }

    /**
     * Sets player starting coordinate.
     */
    setPlayerStart(playerId, x, y) {
        const existing = this.playerStarts.find(ps => ps.player_id === playerId);
        if (existing) {
            existing.x = x;
            existing.y = y;
        } else {
            this.playerStarts.push({ player_id: playerId, x, y });
        }
        this.showStatus(`Player ${playerId} start set to (${x}, ${y})`, 'success');
    }

    /**
     * Switches the active map to another exported .map file.
     *
     * @param {string} mapName - Filename of map (e.g. '(2인,100x100)태극.map')
     */
    async switchMap(mapName) {
        this.currentMapName = mapName;
        this.showStatus(`Loading map: ${mapName}...`, 'info');

        const mapDef = POPULAR_MAPS.find(m => m.id === mapName || m.assetKey === mapName || m.name === mapName) || {
            id: mapName,
            name: mapName,
            width: 100,
            height: 100,
            theme: 'normal'
        };

        this.currentThemeName = mapDef.theme || 'normal';

        // Attempt fetching parsed map JSON from asset pipeline
        let mapData = null;
        const candidateUrls = [];
        if (mapDef.assetKey) {
            candidateUrls.push(`${this.apiBaseUrl}/assets/maps/${mapDef.assetKey}.json`);
        }
        const cleanName = mapName.replace(/\.map$/i, '');
        candidateUrls.push(`${this.apiBaseUrl}/assets/maps/${encodeURIComponent(cleanName)}.json`);
        candidateUrls.push(`${this.apiBaseUrl}/assets/maps/${cleanName}.json`);

        for (const url of candidateUrls) {
            try {
                const res = await fetch(url);
                if (res.ok) {
                    mapData = await res.json();
                    break;
                }
            } catch (err) {
                // Try next candidate URL
            }
        }

        // Normalize mapData from Phase 1 / Phase 2 extractor structure
        if (mapData) {
            if (mapData.layers) {
                if (!mapData.tile_layer_1 && mapData.layers.tile1) mapData.tile_layer_1 = mapData.layers.tile1;
                if (!mapData.tile_layer_2 && mapData.layers.tile2) mapData.tile_layer_2 = mapData.layers.tile2;
                if (!mapData.tile_layer_3 && mapData.layers.tile3) mapData.tile_layer_3 = mapData.layers.tile3;
                if (!mapData.walkability && mapData.layers.walkability) mapData.walkability = mapData.layers.walkability;
                if (!mapData.elevation && mapData.layers.elevation) mapData.elevation = mapData.layers.elevation;
                if (!mapData.terrain_type && mapData.layers.terrain_type) mapData.terrain_type = mapData.layers.terrain_type;
            }
            if (Array.isArray(mapData.resources) && !mapData.resource_type) {
                const w = mapData.width || mapDef.width || 100;
                const h = mapData.height || mapDef.height || 100;
                const size = w * h;
                const rTypes = new Uint8Array(size);
                const rAmounts = new Uint16Array(size);
                for (const r of mapData.resources) {
                    const idx = r.y * w + r.x;
                    if (idx >= 0 && idx < size) {
                        rTypes[idx] = r.type_id || r.typeId || 1;
                        rAmounts[idx] = r.amount || 50;
                    }
                }
                mapData.resource_type = rTypes;
                mapData.resource_amount = rAmounts;
            }
            if (mapData.player_starts && Array.isArray(mapData.player_starts)) {
                this.playerStarts = mapData.player_starts;
            }
            if (mapData.theme_name) this.currentThemeName = mapData.theme_name;
            if (mapData.theme_id !== undefined) this.currentThemeId = mapData.theme_id;
        }

        if (!mapData) {
            mapData = this.generateFallbackMap(mapDef.width || 100, mapDef.height || 100, mapDef.theme);
        }

        if (this.grid) {
            this.grid.loadFromMapData(mapData);
            if (this.camera && typeof this.camera.centerOnGrid === 'function') {
                this.camera.centerOnGrid(Math.floor(this.grid.width / 2), Math.floor(this.grid.height / 2));
            }
        }

        // Reset tracking collections
        this.placedUnits = [];
        this.removedResources = [];
        this.modifiedTerrain.clear();

        if (this.onMapChange) {
            this.onMapChange(mapName, mapData);
        }

        this.showStatus(`Map switched: ${mapDef.name} (${this.grid.width}x${this.grid.height})`, 'success');
        return mapData;
    }

    /**
     * Generates a realistic fallback map matching the requested size and theme.
     */
    generateFallbackMap(width = 100, height = 100, theme = 'normal') {
        const size = width * height;
        const tileLayer1 = new Uint16Array(size).fill(1);
        const tileLayer2 = new Uint16Array(size).fill(0);
        const terrainType = new Uint8Array(size).fill(2); // Ground
        const walkability = new Uint8Array(size).fill(0); // Passable
        const elevation = new Uint8Array(size).fill(0);
        const resourceTypes = new Uint8Array(size).fill(0);
        const resourceAmounts = new Uint16Array(size).fill(0);

        // Add plateaus and resources procedurally
        const centerX = Math.floor(width / 2);
        const centerY = Math.floor(height / 2);

        // Center elevated hill
        for (let y = centerY - 15; y <= centerY + 15; y++) {
            for (let x = centerX - 15; x <= centerX + 15; x++) {
                if (x >= 0 && x < width && y >= 0 && y < height) {
                    const dist = Math.hypot(x - centerX, y - centerY);
                    if (dist < 12) {
                        elevation[y * width + x] = 1;
                    }
                }
            }
        }

        // Resources around starting bases
        const placeCluster = (cx, cy, type, amount, count) => {
            for (let i = 0; i < count; i++) {
                const rx = cx + Math.floor((Math.random() - 0.5) * 6);
                const ry = cy + Math.floor((Math.random() - 0.5) * 6);
                if (rx >= 0 && rx < width && ry >= 0 && ry < height) {
                    const idx = ry * width + rx;
                    resourceTypes[idx] = type;
                    resourceAmounts[idx] = amount;
                    if (type === 2 || type === 3) walkability[idx] = 1;
                }
            }
        };

        // Player 0 base resources (top-left)
        placeCluster(20, 20, 100, 40, 6); // Rice
        placeCluster(24, 18, 3, 170, 8);   // Trees
        placeCluster(18, 24, 1, 70, 4);    // Potatoes

        // Player 1 base resources (bottom-right)
        placeCluster(width - 20, height - 20, 100, 40, 6);
        placeCluster(width - 24, height - 18, 3, 170, 8);
        placeCluster(width - 18, height - 24, 1, 70, 4);

        return {
            width,
            height,
            tile_layer_1: Array.from(tileLayer1),
            tile_layer_2: Array.from(tileLayer2),
            terrain_type: Array.from(terrainType),
            walkability: Array.from(walkability),
            elevation: Array.from(elevation),
            resource_type: Array.from(resourceTypes),
            resource_amount: Array.from(resourceAmounts)
        };
    }

    /**
     * Serializes active 180x180 grid layers to complete JSON object.
     *
     * @returns {Object} Full map state JSON
     */
    exportJSON() {
        if (!this.grid) return {};

        const data = {
            format_version: '1.0',
            name: this.currentMapName,
            width: this.grid.width,
            height: this.grid.height,
            theme_name: this.currentThemeName,
            theme_id: this.currentThemeId,
            player_starts: this.playerStarts,
            tile_layer_1: Array.from(this.grid.tileLayer1),
            tile_layer_2: Array.from(this.grid.tileLayer2),
            tile_layer_3: Array.from(this.grid.tileLayer3 || []),
            terrain_type: Array.from(this.grid.terrainType),
            walkability: Array.from(this.grid.walkability),
            elevation: Array.from(this.grid.elevation),
            water_depth: Array.from(this.grid.waterDepth || []),
            resource_type: Array.from(this.grid.resourceTypes),
            resource_amount: Array.from(this.grid.resourceAmounts),
            building_id: Array.from(this.grid.buildingIds || []),
            building_owner: Array.from(this.grid.buildingOwners || []),
            placed_units: this.placedUnits,
            exported_at: new Date().toISOString()
        };

        return data;
    }

    /**
     * Triggers in-browser file download of the exported JSON.
     *
     * @param {string} [filename] - Target filename
     */
    downloadJSON(filename) {
        const data = this.exportJSON();
        const jsonStr = JSON.stringify(data, null, 2);
        const name = filename || `${this.currentMapName.replace(/\.map$/i, '')}_export.json`;

        if (typeof document !== 'undefined') {
            const blob = new Blob([jsonStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.showStatus(`Exported JSON downloaded: ${name}`, 'success');
        }

        return data;
    }

    /**
     * Calls POST /api/export_map on the backend server, generating a bit-exact
     * 1,132,876-byte .map binary file in web_prototype/mod_export/.
     *
     * @param {Object} [customOptions] - Optional export parameter overrides
     * @returns {Promise<Object>} Backend API response
     */
    async exportBinaryMap(customOptions = {}) {
        this.showStatus('Exporting bit-exact binary .map file...', 'info');

        // Collect all active resources
        const resources = [];
        if (this.grid) {
            for (let y = 0; y < this.grid.height; y++) {
                for (let x = 0; x < this.grid.width; x++) {
                    const idx = this.grid.getIndex(x, y);
                    const resType = this.grid.resourceTypes[idx];
                    if (resType > 0) {
                        resources.push({
                            x,
                            y,
                            type_id: resType,
                            amount: this.grid.resourceAmounts[idx] || 50
                        });
                    }
                }
            }
        }

        // Collect terrain modifications
        const terrainMods = [];
        for (const [key, val] of this.modifiedTerrain.entries()) {
            const [x, y] = key.split(',').map(Number);
            terrainMods.push({
                x,
                y,
                walkability: val.walkability,
                terrain_type: val.terrain_type
            });
        }

        const outName = customOptions.output_filename || `custom_${Date.now()}.map`;
        const baseMap = customOptions.base_map || (this.currentMapName.endsWith('.map') ? this.currentMapName : `${this.currentMapName}.map`);

        const payload = {
            base_map: baseMap,
            output_filename: outName,
            theme_id: this.currentThemeId,
            player_starts: this.playerStarts,
            resources,
            remove_resources: this.removedResources,
            terrain_modifications: terrainMods,
            ...customOptions
        };

        try {
            const endpoint = `${this.apiBaseUrl}/api/export_map`;
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errBody = await res.json().catch(() => ({}));
                throw new Error(errBody.error || `HTTP ${res.status}: ${res.statusText}`);
            }

            const data = await res.json();
            if (data.success && data.file_size === 1132876) {
                this.showStatus(`✅ Bit-exact 1,132,876-byte .map saved: ${outName}`, 'success');
            } else {
                this.showStatus(`Map export complete: ${data.output_file || outName}`, 'success');
            }

            if (this.onExportMap) {
                this.onExportMap(data);
            }

            return data;
        } catch (err) {
            this.showStatus(`Export failed: ${err.message}`, 'error');
            throw err;
        }
    }

    /**
     * Renders editor visual overlay on canvas:
     * - Hover tile highlight (diamond outline & semi-transparent fill)
     * - Brush radius boundary
     * - Elevation indicator text
     *
     * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
     * @param {Object} camera - Active camera instance
     */
    renderOverlay(ctx, camera) {
        if (!this.isEnabled || !this.hoveredGridPos || !this.grid || !camera) return;

        const { gx, gy } = this.hoveredGridPos;
        if (gx < 0 || gx >= this.grid.width || gy < 0 || gy >= this.grid.height) return;

        const half = Math.floor(this.brushSize / 2);
        const isEven = (this.brushSize % 2 === 0);
        const minX = Math.max(0, gx - half);
        const maxX = Math.min(this.grid.width - 1, isEven ? gx + half - 1 : gx + half);
        const minY = Math.max(0, gy - half);
        const maxY = Math.min(this.grid.height - 1, isEven ? gy + half - 1 : gy + half);

        // Tool-specific color theme
        let strokeColor = '#ffd700'; // Gold for terrain
        let fillColor = 'rgba(255, 215, 0, 0.25)';

        if (this.activeTool === 'raise_elev' || this.activeTool === 'lower_elev' || this.activeTool === 'set_elev') {
            strokeColor = '#00ffff'; // Cyan
            fillColor = 'rgba(0, 255, 255, 0.3)';
        } else if (this.activeTool === 'place_resource') {
            strokeColor = '#00ff66'; // Green
            fillColor = 'rgba(0, 255, 102, 0.3)';
        } else if (this.activeTool === 'place_unit') {
            strokeColor = this.selectedFaction === 0 ? '#00bfff' : '#ff4444';
            fillColor = this.selectedFaction === 0 ? 'rgba(0, 191, 255, 0.35)' : 'rgba(255, 68, 68, 0.35)';
        } else if (this.activeTool === 'place_building') {
            strokeColor = '#ffaa00'; // Orange
            fillColor = 'rgba(255, 170, 0, 0.35)';
        } else if (this.activeTool === 'erase') {
            strokeColor = '#ff2222'; // Red
            fillColor = 'rgba(255, 34, 34, 0.35)';
        }

        ctx.save();
        ctx.lineWidth = 2;
        ctx.strokeStyle = strokeColor;
        ctx.fillStyle = fillColor;

        for (let ty = minY; ty <= maxY; ty++) {
            for (let tx = minX; tx <= maxX; tx++) {
                const elev = this.grid.getElevation ? this.grid.getElevation(tx, ty) : (this.grid.elevation[ty * this.grid.width + tx] || 0);
                const pos = IsometricMath.gridToScreen(tx, ty, elev, camera);

                // Draw diamond shape
                ctx.beginPath();
                ctx.moveTo(pos.x, pos.y);
                ctx.lineTo(pos.x + HALF_WIDTH, pos.y + HALF_HEIGHT);
                ctx.lineTo(pos.x, pos.y + TILE_HEIGHT);
                ctx.lineTo(pos.x - HALF_WIDTH, pos.y + HALF_HEIGHT);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();

                // Draw tile info text on center tile
                if (tx === gx && ty === gy) {
                    ctx.font = '10px monospace';
                    ctx.fillStyle = '#ffffff';
                    ctx.textAlign = 'center';
                    const walk = this.grid.isWalkable ? this.grid.isWalkable(tx, ty) : (this.grid.walkability[ty * this.grid.width + tx] === 0);
                    const label = `(${tx},${ty}) e:${elev} ${walk ? 'OK' : 'CLIFF'}`;
                    ctx.fillText(label, pos.x, pos.y + HALF_HEIGHT - 2);
                }
            }
        }

        ctx.restore();
    }

    /**
     * Attaches mouse & interaction listeners to the canvas for painting/sculpting.
     *
     * @param {HTMLCanvasElement} canvas - Main viewport canvas
     */
    attachCanvas(canvas) {
        if (!canvas) return;
        this.canvas = canvas;

        const getGridCoords = (e) => {
            const rect = canvas.getBoundingClientRect();
            const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
            const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
            return IsometricMath.screenToGrid(sx, sy, this.camera, this.grid.elevation, this.grid.width, this.grid.height);
        };

        canvas.addEventListener('mousemove', (e) => {
            if (!this.isEnabled) return;
            const pt = getGridCoords(e);
            this.hoveredGridPos = pt;

            if (this.isMouseDown && pt.valid) {
                // Apply brush along drag stroke
                const key = `${pt.gx},${pt.gy}`;
                if (this.lastAppliedCoord !== key) {
                    this.lastAppliedCoord = key;
                    this.applyBrush(pt.gx, pt.gy);
                }
            }
        });

        canvas.addEventListener('mousedown', (e) => {
            if (!this.isEnabled) return;
            if (e.button === 0) { // Left click
                this.isMouseDown = true;
                const pt = getGridCoords(e);
                if (pt.valid) {
                    this.lastAppliedCoord = `${pt.gx},${pt.gy}`;
                    this.applyBrush(pt.gx, pt.gy);
                }
                e.stopPropagation(); // Stop RTS unit selection drag
            }
        });

        const onMouseUp = () => {
            this.isMouseDown = false;
            this.lastAppliedCoord = null;
        };

        window.addEventListener('mouseup', onMouseUp);

        canvas.addEventListener('mouseleave', () => {
            this.hoveredGridPos = null;
            this.isMouseDown = false;
        });

        this._cleanupCanvas = () => {
            window.removeEventListener('mouseup', onMouseUp);
        };
    }

    /**
     * Mounts the Map Editor UI Toolbar into a parent DOM container.
     *
     * @param {HTMLElement|string} container - Element or selector
     */
    mount(container) {
        const root = typeof container === 'string' ? document.querySelector(container) : container;
        if (!root) return;

        // Inject default stylesheet if not already present in document
        if (typeof document !== 'undefined' && !document.getElementById('map-editor-styles')) {
            const style = document.createElement('style');
            style.id = 'map-editor-styles';
            style.textContent = `
                .map-editor-container { position: relative; font-family: 'Malgun Gothic', Dotum, sans-serif; z-index: 100; }
                .editor-mode-toggle-btn { padding: 6px 14px; background: #2b2b2b; color: #e0e0e0; border: 1px solid #555; border-radius: 4px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
                .editor-mode-toggle-btn.active { background: #b8860b; color: #fff; border-color: #ffd700; box-shadow: 0 0 8px rgba(255, 215, 0, 0.4); }
                .map-editor-toolbar { position: absolute; top: 40px; right: 0; width: 320px; background: rgba(20, 24, 28, 0.95); border: 2px solid #5a4d33; border-radius: 6px; padding: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.8); color: #ddd; max-height: 85vh; overflow-y: auto; }
                .editor-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #443c28; padding-bottom: 6px; margin-bottom: 8px; }
                .editor-header h4 { margin: 0; color: #ffd700; font-size: 14px; }
                .editor-status-badge { font-size: 11px; padding: 2px 6px; background: #333; border-radius: 3px; color: #aaa; }
                .editor-status-badge.status-success { background: #1b4d24; color: #7cfc00; }
                .editor-status-badge.status-error { background: #5c1818; color: #ff6b6b; }
                .editor-section { margin-bottom: 10px; }
                .editor-section label { display: block; font-size: 11px; color: #aaa; margin-bottom: 4px; }
                .editor-select { width: 100%; padding: 4px 6px; background: #111; border: 1px solid #444; color: #fff; border-radius: 3px; font-size: 12px; }
                .tool-btn-group, .brush-size-group, .palette-category-tabs { display: flex; flex-wrap: wrap; gap: 4px; }
                .tool-btn, .brush-size-btn, .cat-tab, .resource-btn { flex: 1 1 auto; padding: 5px 8px; background: #25282c; border: 1px solid #444; color: #ccc; border-radius: 3px; cursor: pointer; font-size: 11px; text-align: center; }
                .tool-btn.active, .brush-size-btn.active, .cat-tab.active, .resource-btn.active { background: #4a3c18; border-color: #ffd700; color: #ffd700; font-weight: bold; }
                .tile-swatches { display: flex; flex-wrap: wrap; gap: 4px; margin: 6px 0; max-height: 80px; overflow-y: auto; background: #111; padding: 4px; border-radius: 3px; }
                .tile-swatch { width: 40px; height: 28px; background: #2c322b; border: 1px solid #555; border-radius: 2px; display: flex; align-items: center; justify-content: center; font-size: 9px; cursor: pointer; color: #aaa; }
                .tile-swatch.selected { border-color: #00ffff; box-shadow: 0 0 4px #00ffff; color: #fff; font-weight: bold; }
                .layer-selector { display: flex; gap: 12px; font-size: 11px; margin-top: 4px; }
                .export-section { display: flex; flex-direction: column; gap: 6px; margin-top: 14px; border-top: 1px solid #443c28; padding-top: 10px; }
                .export-btn { padding: 8px; font-size: 12px; font-weight: bold; border-radius: 4px; cursor: pointer; border: 1px solid #555; }
                .json-btn { background: #1c3248; color: #64b5f6; border-color: #2b5278; }
                .binary-btn { background: #382c16; color: #ffd700; border-color: #7d6325; }
                .export-btn:hover { filter: brightness(1.2); }
            `;
            document.head.appendChild(style);
        }

        this.container = root;
        this.dom.wrapper = document.createElement('div');
        this.dom.wrapper.className = 'map-editor-container';

        // 1. Toggle Button
        this.dom.modeToggleBtn = document.createElement('button');
        this.dom.modeToggleBtn.className = 'editor-mode-toggle-btn';
        this.dom.modeToggleBtn.id = 'editor-mode-toggle';
        this.dom.modeToggleBtn.innerHTML = '⚔️ <strong>Game Mode</strong>';
        this.dom.modeToggleBtn.addEventListener('click', () => this.toggle());

        // 2. Toolbar Panel
        this.dom.toolbar = document.createElement('div');
        this.dom.toolbar.className = 'map-editor-toolbar';
        this.dom.toolbar.id = 'map-editor-toolbar';
        this.dom.toolbar.style.display = 'none';

        this.dom.toolbar.innerHTML = `
            <div class="editor-header">
                <h4>🗺️ Imjinrok 2+ Map Editor</h4>
                <div class="editor-status-badge" id="editor-status-badge">Ready</div>
            </div>

            <!-- Map Selector Section -->
            <div class="editor-section">
                <label><strong>Select Map (공식 맵 선택):</strong></label>
                <select id="map-editor-select" class="editor-select">
                    ${POPULAR_MAPS.map(m => `<option value="${m.id}" ${m.id === this.currentMapName ? 'selected' : ''}>${m.name}</option>`).join('')}
                </select>
            </div>

            <!-- Tool Palette -->
            <div class="editor-section">
                <label><strong>Editing Tool (편집 도구):</strong></label>
                <div class="tool-btn-group">
                    <button class="tool-btn active" data-tool="paint_tile" title="Paint Terrain Tiles">🎨 Terrain Brush</button>
                    <button class="tool-btn" data-tool="raise_elev" title="Raise Elevation (+1)">⛰️ Raise Elev</button>
                    <button class="tool-btn" data-tool="lower_elev" title="Lower Elevation (-1)">⛏️ Lower Elev</button>
                    <button class="tool-btn" data-tool="place_resource" title="Place Resources">🌾 Resource</button>
                    <button class="tool-btn" data-tool="place_unit" title="Place Units">👤 Unit</button>
                    <button class="tool-btn" data-tool="place_building" title="Place Buildings">🏰 Building</button>
                    <button class="tool-btn" data-tool="erase" title="Erase Resources/Buildings">🧹 Erase</button>
                </div>
            </div>

            <!-- Brush Size -->
            <div class="editor-section">
                <label><strong>Brush Radius (브러시 크기):</strong></label>
                <div class="brush-size-group">
                    <button class="brush-size-btn active" data-size="1">1x1</button>
                    <button class="brush-size-btn" data-size="2">2x2</button>
                    <button class="brush-size-btn" data-size="3">3x3</button>
                </div>
            </div>

            <!-- Subpanel: Terrain Brush Options -->
            <div class="tool-subpanel" id="subpanel-paint_tile">
                <label><strong>Terrain Palette (지형 종류):</strong></label>
                <div class="palette-category-tabs">
                    <button class="cat-tab active" data-cat="grss">Grass (평원)</button>
                    <button class="cat-tab" data-cat="diff">Dirt (황토)</button>
                    <button class="cat-tab" data-cat="castle">Castle (석벽)</button>
                    <button class="cat-tab" data-cat="water">Water (수역)</button>
                </div>
                <div class="tile-swatches" id="tile-swatches-container"></div>
                <div class="layer-selector">
                    <label>Target Layer:</label>
                    <label><input type="radio" name="target_layer" value="1" checked> Layer 1 (Base)</label>
                    <label><input type="radio" name="target_layer" value="2"> Layer 2 (Decal)</label>
                </div>
            </div>

            <!-- Subpanel: Resource Options -->
            <div class="tool-subpanel" id="subpanel-place_resource" style="display:none;">
                <label><strong>Resource Type (자원 종류):</strong></label>
                <div class="resource-selector">
                    ${RESOURCE_TYPES.map(r => `
                        <button class="resource-btn ${r.typeId === 1 ? 'active' : ''}" data-type="${r.typeId}" data-amount="${r.defaultAmount}">
                            ${r.icon} ${r.name}
                        </button>
                    `).join('')}
                </div>
                <div class="field-row">
                    <label>Amount (수량): <span id="res-amount-val">70</span></label>
                    <input type="range" id="res-amount-slider" min="10" max="500" value="70">
                </div>
            </div>

            <!-- Subpanel: Unit Options -->
            <div class="tool-subpanel" id="subpanel-place_unit" style="display:none;">
                <label><strong>Faction (진영):</strong></label>
                <select id="unit-faction-select" class="editor-select">
                    <option value="0">Player 0 (Chosun / 조선 - Blue)</option>
                    <option value="1">Player 1 (Japan / 일본 - Red)</option>
                    <option value="2">Player 2 (Neutral / 명/중립 - Green)</option>
                </select>
                <label><strong>Unit Archetype (유닛 종류):</strong></label>
                <select id="unit-archetype-select" class="editor-select">
                    ${MAP_EDITOR_UNITS.map(u => `<option value="${u.id}">${u.name} (HP: ${u.hp}, Spd: ${u.speed})</option>`).join('')}
                </select>
            </div>

            <!-- Subpanel: Building Options -->
            <div class="tool-subpanel" id="subpanel-place_building" style="display:none;">
                <label><strong>Faction (진영):</strong></label>
                <select id="building-faction-select" class="editor-select">
                    <option value="0">Player 0 (조선)</option>
                    <option value="1">Player 1 (일본)</option>
                    <option value="2">Neutral (중립)</option>
                </select>
                <label><strong>Building Archetype (건물 종류):</strong></label>
                <select id="building-archetype-select" class="editor-select">
                    ${MAP_EDITOR_BUILDINGS.map(b => `<option value="${b.id}">${b.name} (${b.width}x${b.height})</option>`).join('')}
                </select>
            </div>

            <!-- Export Actions -->
            <div class="editor-section export-section">
                <button id="btn-export-map-json" class="export-btn json-btn">💾 Export Map JSON</button>
                <button id="btn-export-binary-map" class="export-btn binary-btn">📦 Export Binary .map (1.13MB)</button>
            </div>
        `;

        this.dom.wrapper.appendChild(this.dom.modeToggleBtn);
        this.dom.wrapper.appendChild(this.dom.toolbar);
        this.container.appendChild(this.dom.wrapper);

        this.bindToolbarEvents();
        this.renderTileSwatches('grss');
    }

    /**
     * Binds DOM event listeners for toolbar controls.
     */
    bindToolbarEvents() {
        const tb = this.dom.toolbar;
        if (!tb) return;

        // Map selector
        const mapSelect = tb.querySelector('#map-editor-select');
        if (mapSelect) {
            mapSelect.addEventListener('change', (e) => {
                this.switchMap(e.target.value);
            });
        }

        // Tool buttons
        const toolBtns = tb.querySelectorAll('.tool-btn');
        toolBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                this.setTool(btn.dataset.tool);
            });
        });

        // Brush size buttons
        const sizeBtns = tb.querySelectorAll('.brush-size-btn');
        sizeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                this.setBrushSize(parseInt(btn.dataset.size, 10));
            });
        });

        // Palette category tabs
        const catTabs = tb.querySelectorAll('.cat-tab');
        catTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                catTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.selectedCategory = tab.dataset.cat;
                this.renderTileSwatches(this.selectedCategory);
            });
        });

        // Target layer radio buttons
        const layerRadios = tb.querySelectorAll('input[name="target_layer"]');
        layerRadios.forEach(r => {
            r.addEventListener('change', (e) => {
                this.targetLayer = parseInt(e.target.value, 10) || 1;
            });
        });

        // Resource buttons
        const resBtns = tb.querySelectorAll('.resource-btn');
        resBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                resBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const typeId = parseInt(btn.dataset.type, 10);
                const amount = parseInt(btn.dataset.amount, 10);
                this.setResourceType(typeId, amount);
                const slider = tb.querySelector('#res-amount-slider');
                const label = tb.querySelector('#res-amount-val');
                if (slider) slider.value = amount;
                if (label) label.textContent = amount;
            });
        });

        // Resource amount slider
        const resSlider = tb.querySelector('#res-amount-slider');
        const resLabel = tb.querySelector('#res-amount-val');
        if (resSlider && resLabel) {
            resSlider.addEventListener('input', (e) => {
                resLabel.textContent = e.target.value;
                this.resourceAmount = parseInt(e.target.value, 10);
            });
        }

        // Unit selector
        const unitFaction = tb.querySelector('#unit-faction-select');
        const unitArch = tb.querySelector('#unit-archetype-select');
        if (unitFaction) unitFaction.addEventListener('change', (e) => this.selectedFaction = parseInt(e.target.value, 10));
        if (unitArch) unitArch.addEventListener('change', (e) => this.selectedUnitId = e.target.value);

        // Building selector
        const bldFaction = tb.querySelector('#building-faction-select');
        const bldArch = tb.querySelector('#building-archetype-select');
        if (bldFaction) bldFaction.addEventListener('change', (e) => this.selectedFaction = parseInt(e.target.value, 10));
        if (bldArch) bldArch.addEventListener('change', (e) => this.selectedBuildingId = parseInt(e.target.value, 10));

        // Export JSON button
        const btnJson = tb.querySelector('#btn-export-map-json');
        if (btnJson) {
            btnJson.addEventListener('click', () => this.downloadJSON());
        }

        // Export Binary .map button
        const btnBin = tb.querySelector('#btn-export-binary-map');
        if (btnBin) {
            btnBin.addEventListener('click', () => this.exportBinaryMap());
        }
    }

    /**
     * Renders tile swatches for the given palette category.
     */
    renderTileSwatches(category) {
        const container = this.dom.toolbar ? this.dom.toolbar.querySelector('#tile-swatches-container') : null;
        if (!container) return;

        container.innerHTML = '';
        const pal = TILE_PALETTES[category] || TILE_PALETTES.grss;

        pal.tiles.forEach((t, i) => {
            const swatch = document.createElement('div');
            swatch.className = `tile-swatch ${i === 0 ? 'selected' : ''}`;
            swatch.dataset.tileId = t.id;
            swatch.title = `${t.label} (ID: ${t.id})`;
            swatch.innerHTML = `<span>#${t.id}</span>`;
            swatch.addEventListener('click', () => {
                container.querySelectorAll('.tile-swatch').forEach(s => s.classList.remove('selected'));
                swatch.classList.add('selected');
                this.setTileId(t.id, this.targetLayer);
            });
            container.appendChild(swatch);
            if (i === 0) this.setTileId(t.id, this.targetLayer);
        });
    }

    /**
     * Toggles visibility of tool subpanels according to active tool.
     */
    updateToolPanels() {
        const tb = this.dom.toolbar;
        if (!tb) return;

        const subpanels = tb.querySelectorAll('.tool-subpanel');
        subpanels.forEach(p => p.style.display = 'none');

        const activeSub = tb.querySelector(`#subpanel-${this.activeTool}`);
        if (activeSub) {
            activeSub.style.display = 'block';
        }
    }

    /**
     * Shows a status notification message in the toolbar badge.
     */
    showStatus(msg, type = 'info') {
        const badge = this.dom.toolbar ? this.dom.toolbar.querySelector('#editor-status-badge') : null;
        if (badge) {
            badge.textContent = msg;
            badge.className = `editor-status-badge status-${type}`;
            clearTimeout(this._statusTimer);
            this._statusTimer = setTimeout(() => {
                badge.textContent = 'Ready';
                badge.className = 'editor-status-badge';
            }, 6000);
        }
    }

    /**
     * Cleans up event listeners and removes DOM elements.
     */
    destroy() {
        if (this._cleanupCanvas) this._cleanupCanvas();
        if (this.dom.wrapper && this.dom.wrapper.parentNode) {
            this.dom.wrapper.parentNode.removeChild(this.dom.wrapper);
        }
    }
}
