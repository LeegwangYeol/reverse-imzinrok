/**
 * Automated Test Suite for Live Modding Studio (web_prototype/js/ui/modding_studio.js)
 *
 * Verifies:
 * 1. Unit Stat Live Editor (sliders & number inputs for move_speed, hp, attack_power, attack_range, attack_delay, scale)
 * 2. Real-time immediate in-memory unit update (next simulation step without reload)
 * 3. Custom New Unit Creator (faction, sprite, Korean name, custom stats, projectile, command card slot)
 * 4. Spawning custom unit at camera center and binding to Command Card
 * 5. Export Mod Config (POST /api/save_mod_config serialization)
 * 6. Patch Local dawn.exe (POST /api/patch_binary call and result presentation)
 * 7. Global window.gameEngine integration and headless browser compatibility
 */

import { LiveModdingStudio, BUILTIN_UNIT_TEMPLATES } from '../web_prototype/js/ui/modding_studio.js';
import { Unit, UnitState } from '../web_prototype/js/simulation/entities.js';
import { IsometricMath } from '../web_prototype/js/engine/isometric.js';
import { GameGrid } from '../web_prototype/js/simulation/grid.js';
import { Camera } from '../web_prototype/js/engine/camera.js';

// --- Lightweight Mock DOM System for Node.js Testing ---
class MockElement {
    constructor(tagName = 'div') {
        this.tagName = tagName.toUpperCase();
        this.id = '';
        this.className = '';
        this._value = '';
        this.type = '';
        this.title = '';
        this.style = {};
        this.children = [];
        this.parentNode = null;
        this.eventListeners = {};
        this._innerHTML = '';
        this.dataset = {};
    }

    get value() {
        return this._value;
    }

    set value(v) {
        this._value = v !== undefined && v !== null ? String(v) : '';
    }

    get innerHTML() {
        return this._innerHTML;
    }

    set innerHTML(html) {
        this._innerHTML = html;
        this.children = [];
        this._parseHTML(html);
    }

    get textContent() {
        let text = '';
        if (this._text !== undefined) text += this._text;
        for (const c of this.children) text += c.textContent;
        return text;
    }

    set textContent(txt) {
        this._text = txt;
        this.children = [];
        this._innerHTML = txt;
    }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    removeChild(child) {
        const idx = this.children.indexOf(child);
        if (idx !== -1) {
            this.children.splice(idx, 1);
            child.parentNode = null;
        }
        return child;
    }

    addEventListener(event, cb) {
        if (!this.eventListeners[event]) this.eventListeners[event] = [];
        this.eventListeners[event].push(cb);
    }

    dispatchEvent(event) {
        const type = typeof event === 'string' ? event : event.type;
        const listeners = this.eventListeners[type] || [];
        for (const cb of listeners) {
            cb(typeof event === 'string' ? { type, target: this } : { ...event, target: this });
        }
        return true;
    }

    querySelector(selector) {
        const list = this.querySelectorAll(selector);
        return list.length > 0 ? list[0] : null;
    }

    querySelectorAll(selector) {
        const matches = [];
        const isId = selector.startsWith('#');
        const isClass = selector.startsWith('.');
        const target = selector.substring(1);

        const traverse = (node) => {
            for (const child of node.children) {
                if (isId && child.id === target) {
                    matches.push(child);
                } else if (isClass && child.className.split(' ').includes(target)) {
                    matches.push(child);
                } else if (!isId && !isClass && child.tagName.toLowerCase() === selector.toLowerCase()) {
                    matches.push(child);
                }
                traverse(child);
            }
        };
        traverse(this);
        return matches;
    }

    _parseHTML(html) {
        // Regex-based tag extractor for mock DOM
        const tagRegex = /<([a-zA-Z0-9]+)([^>]*)>(?:([\s\S]*?)<\/\1>)?/g;
        let match;
        while ((match = tagRegex.exec(html)) !== null) {
            const tagName = match[1];
            const attrs = match[2];
            const inner = match[3] || '';

            const elem = new MockElement(tagName);
            const idMatch = attrs.match(/id=["']([^"']+)["']/);
            if (idMatch) elem.id = idMatch[1];
            const classMatch = attrs.match(/class=["']([^"']+)["']/);
            if (classMatch) elem.className = classMatch[1];
            const valMatch = attrs.match(/value=["']([^"']+)["']/);
            if (valMatch) elem.value = valMatch[1];
            const minMatch = attrs.match(/min=["']([^"']+)["']/);
            if (minMatch) elem.min = minMatch[1];
            const maxMatch = attrs.match(/max=["']([^"']+)["']/);
            if (maxMatch) elem.max = maxMatch[1];
            const typeMatch = attrs.match(/type=["']([^"']+)["']/);
            if (typeMatch) elem.type = typeMatch[1];

            if (inner.includes('<')) {
                elem._parseHTML(inner);
            } else {
                elem.textContent = inner;
            }
            this.appendChild(elem);
        }
    }
}

// Global DOM setup
class MockDocument {
    constructor() {
        this.body = new MockElement('body');
    }
    createElement(tag) {
        return new MockElement(tag);
    }
    getElementById(id) {
        return this.body.querySelector(`#${id}`);
    }
    querySelector(selector) {
        return this.body.querySelector(selector);
    }
    querySelectorAll(selector) {
        return this.body.querySelectorAll(selector);
    }
}

const mockDoc = new MockDocument();
global.document = mockDoc;
global.window = {
    document: mockDoc,
    gameEngine: {}
};
global.Event = class {
    constructor(type) {
        this.type = type;
    }
};

let passedCount = 0;
let totalCount = 0;

function assert(condition, message) {
    totalCount++;
    if (!condition) {
        console.error(`  [FAIL] ${message}`);
        throw new Error(`Assertion failed: ${message}`);
    } else {
        console.log(`  [PASS] ${message}`);
        passedCount++;
    }
}

// Mock Fetch for API Testing
const fetchCalls = [];
global.fetch = async (url, options = {}) => {
    fetchCalls.push({ url, options });
    if (url === '/api/dataset') {
        return {
            ok: true,
            status: 200,
            json: async () => ({
                total: 2,
                units: [
                    { index: 51, korean_name: '조선 창병', speed_field: { dawn_val: 12 }, hp_field: { dawn_val: 120 } },
                    { index: 49, korean_name: '조선 이순신', speed_field: { dawn_val: 14 }, hp_field: { dawn_val: 800 } }
                ]
            })
        };
    } else if (url === '/api/save_mod_config') {
        const payload = JSON.parse(options.body || '{}');
        return {
            ok: true,
            status: 200,
            json: async () => ({
                success: true,
                profile_name: payload.profile_name,
                file_path: `C:\\src\\reverse-imzinrok\\web_prototype\\mod_export\\${payload.profile_name}.json`,
                stat_overrides_count: Object.keys(payload.stat_overrides || {}).length,
                custom_units_count: (payload.custom_units || []).length
            })
        };
    } else if (url === '/api/patch_binary') {
        const payload = JSON.parse(options.body || '{}');
        return {
            ok: true,
            status: 200,
            json: async () => ({
                success: true,
                output_file: `C:\\src\\reverse-imzinrok\\web_prototype\\mod_export\\${payload.target_filename}`,
                file_size: 1032192,
                output_sha256: '9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b',
                patch_result: {
                    unit_id: payload.unit_id,
                    unit_name: '조선 창병',
                    stat_field: payload.stat_name,
                    new_value: payload.new_value
                }
            })
        };
    }
    return { ok: false, status: 404, json: async () => ({ error: 'Not found' }) };
};

// --- Test Suites ---

async function runTests() {
    console.log('================================================================');
    console.log(' RUNNING AUTOMATED UNIT TESTS: LIVE MODDING STUDIO');
    console.log('================================================================\n');

    // Setup Mock Environment
    const panel = mockDoc.createElement('div');
    panel.id = 'live-mod-panel';
    mockDoc.body.appendChild(panel);

    const grid = new GameGrid(180, 180);
    const camera = new Camera(1280, 720);
    const entities = [];

    const mockCommandCard = {
        currentButtons: new Array(12).fill(null),
        slots: new Array(12).fill(null),
        setButton: function(slot, btn) { this.currentButtons[slot] = btn; },
        setButtons: function(btns) { this.currentButtons = btns; }
    };

    const mockAudio = {
        playedSounds: [],
        play: function(name) { this.playedSounds.push(name); }
    };

    const studio = new LiveModdingStudio(panel, {
        grid,
        camera,
        commandCard: mockCommandCard,
        audioManager: mockAudio,
        entities
    });

    console.log('[SUITE 1] DOM Layout & Stat Slider Controls (Ranges & Inputs)');
    assert(studio.panel !== null, 'LiveModdingStudio successfully mounted to DOM container');
    assert(BUILTIN_UNIT_TEMPLATES.length >= 20, `Builtin unit templates contains ${BUILTIN_UNIT_TEMPLATES.length} templates (>= 20)`);

    // Verify presence of all 6 stat controls
    const speedSlider = panel.querySelector('#input-move-speed');
    const speedNum = panel.querySelector('#num-move-speed');
    const speedVal = panel.querySelector('#val-speed');
    assert(speedSlider !== null, 'Movement Speed slider #input-move-speed exists');
    assert(speedSlider.min === '1' && speedSlider.max === '30', 'Speed slider min is 1 and max is 30');
    assert(speedNum !== null, 'Movement Speed number input #num-move-speed exists');

    const hpSlider = panel.querySelector('#input-hp');
    const hpNum = panel.querySelector('#num-hp');
    assert(hpSlider !== null && hpNum !== null, 'HP slider and number inputs exist');
    assert(hpSlider.min === '10' && hpSlider.max === '2000', 'HP slider min is 10 and max is 2000');

    const atkSlider = panel.querySelector('#input-attack-power');
    const atkNum = panel.querySelector('#num-attack-power');
    assert(atkSlider !== null && atkNum !== null, 'Attack Power slider and number inputs exist');
    assert(atkSlider.min === '1' && atkSlider.max === '200', 'Attack Power slider min is 1 and max is 200');

    const rangeSlider = panel.querySelector('#input-attack-range');
    const rangeNum = panel.querySelector('#num-attack-range');
    assert(rangeSlider !== null && rangeNum !== null, 'Attack Range slider and number inputs exist');
    assert(rangeSlider.min === '1' && rangeSlider.max === '15', 'Attack Range slider min is 1 and max is 15');

    const delaySlider = panel.querySelector('#input-attack-delay');
    const delayNum = panel.querySelector('#num-attack-delay');
    assert(delaySlider !== null && delayNum !== null, 'Attack Delay slider and number inputs exist');
    assert(delaySlider.min === '5' && delaySlider.max === '60', 'Attack Delay slider min is 5 and max is 60');

    const scaleSlider = panel.querySelector('#input-scale');
    const scaleNum = panel.querySelector('#num-scale');
    assert(scaleSlider !== null && scaleNum !== null, 'Scale slider and number inputs exist');
    assert(scaleSlider.min === '0.5' && scaleSlider.max === '2.5', 'Scale slider min is 0.5 and max is 2.5');

    console.log('\n[SUITE 2] Real-time In-Memory Unit Stat Modification (No Refresh)');
    // Create live unit in world
    const testArchetype = { index: 51, korean_name: '조선 창병', sprite_name: 'char/swordk.spr', move_speed: 12, hp: 120, attack_power: 14, attack_range: 1.5, attack_delay: 28 };
    const liveUnit = new Unit(101, testArchetype, 45, 45, 0);
    entities.push(liveUnit);

    studio.setSelectedUnit(liveUnit);
    assert(studio.selectedUnit === liveUnit, 'Selected live unit correctly focused in LiveModdingStudio');
    assert(speedSlider.value === '12', `Slider initialized to unit move_speed 12 (actual: ${speedSlider.value})`);
    assert(speedVal.textContent === '12', `Label displays unit move_speed 12 (actual: ${speedVal.textContent})`);

    // Dynamically adjust move_speed slider to 26
    speedSlider.value = '26';
    speedSlider.dispatchEvent(new Event('input'));

    assert(liveUnit.move_speed === 26, `Unit move_speed immediately updated in memory to 26 (actual: ${liveUnit.move_speed})`);
    assert(speedNum.value === '26', `Paired number input synchronized to 26 (actual: ${speedNum.value})`);
    assert(speedVal.textContent === '26', `Speed label updated to 26 (actual: ${speedVal.textContent})`);
    assert(window.gameEngine.getSelectedUnitSpeed() === 26, `window.gameEngine.getSelectedUnitSpeed() returns 26 (actual: ${window.gameEngine.getSelectedUnitSpeed()})`);

    // Test simulation physics distance delta immediately reflects higher speed
    const deltaSec = 0.1;
    const initialWx = liveUnit.wx;
    liveUnit.state = UnitState.WALK;
    liveUnit.waypoints = [{ gx: 55, gy: 45 }];
    liveUnit.update(deltaSec, grid, entities, null);
    const distanceTraversed = liveUnit.wx - initialWx;
    // Base step formula: (move_speed / 4) * deltaSec = (26 / 4) * 0.1 = 0.65
    assert(Math.abs(distanceTraversed - 0.65) < 0.01, `Unit traversed distance proportional to new speed 26 (traversed: ${distanceTraversed.toFixed(3)})`);

    // Dynamically adjust HP slider
    const hpVal = panel.querySelector('#val-hp');
    hpSlider.value = '850';
    hpSlider.dispatchEvent(new Event('input'));
    assert(liveUnit.max_hp === 850, `Unit max_hp immediately updated to 850 (actual: ${liveUnit.max_hp})`);
    assert(hpVal.textContent === '850', `HP label displays 850 (actual: ${hpVal.textContent})`);

    // Dynamically adjust Attack Power
    atkSlider.value = '65';
    atkSlider.dispatchEvent(new Event('input'));
    assert(liveUnit.attack_power === 65, `Unit attack_power immediately updated to 65 (actual: ${liveUnit.attack_power})`);

    // Dynamically adjust Scale
    scaleSlider.value = '1.8';
    scaleSlider.dispatchEvent(new Event('input'));
    assert(liveUnit.scale === 1.8, `Unit scale immediately updated to 1.8 (actual: ${liveUnit.scale})`);

    console.log('\n[SUITE 3] Custom Unit Creator & Spawner (Camera Center & Command Card)');
    const factionSelect = panel.querySelector('#custom-unit-faction');
    const spriteSelect = panel.querySelector('#custom-base-sprite');
    const nameInput = panel.querySelector('#custom-unit-name');
    const customSpeedInput = panel.querySelector('#custom-speed');
    const customHpInput = panel.querySelector('#custom-hp');
    const customAtkInput = panel.querySelector('#custom-atk');
    const customRangeInput = panel.querySelector('#custom-range');
    const customDelayInput = panel.querySelector('#custom-delay');
    const projSelect = panel.querySelector('#custom-projectile-type');
    const slotSelect = panel.querySelector('#custom-command-slot');
    const spawnBtn = panel.querySelector('#spawn-custom-btn');

    assert(spawnBtn !== null, 'Spawn Unit button exists in DOM');

    // Configure brand-new custom unit
    factionSelect.value = 'chosun';
    nameInput.value = '조선 초인검사';
    customSpeedInput.value = '22';
    customHpInput.value = '600';
    customAtkInput.value = '48';
    customRangeInput.value = '3.0';
    customDelayInput.value = '16';
    projSelect.value = 'fireball';
    slotSelect.value = '8'; // Slot 8 (Z)

    // Trigger Spawn
    camera.centerOnGrid(70, 70, true);
    spawnBtn.dispatchEvent(new Event('click'));

    assert(studio.customUnits.length === 1, `Custom unit registered in customUnits list (count: ${studio.customUnits.length})`);
    const customCfg = studio.customUnits[0];
    assert(customCfg.korean_name === '조선 초인검사', `Custom unit name is '${customCfg.korean_name}'`);
    assert(customCfg.move_speed === 22, `Custom unit move_speed is ${customCfg.move_speed}`);
    assert(customCfg.hp === 600, `Custom unit HP is ${customCfg.hp}`);
    assert(customCfg.projectile_type === 'fireball', `Custom projectile type is '${customCfg.projectile_type}'`);

    // Check newly spawned unit in world
    const spawned = entities[entities.length - 1];
    assert(spawned !== undefined && spawned.name === '조선 초인검사', `Spawned unit present in world entities array`);
    assert(spawned.move_speed === 22, `Spawned unit live move_speed is 22`);
    assert(spawned.max_hp === 600, `Spawned unit live max_hp is 600`);
    assert(spawned.attack_power === 48, `Spawned unit live attack_power is 48`);
    assert(Math.abs(spawned.gx - 70) <= 2 && Math.abs(spawned.gy - 70) <= 2, `Spawned near camera center (70, 70), got (${spawned.gx}, ${spawned.gy})`);

    // Verify Command Card Slot Assignment
    assert(mockCommandCard.currentButtons[8] !== null, 'Command Card Slot 8 assigned with custom unit button');
    assert(mockCommandCard.currentButtons[8].name === '조선 초인검사', `Command Card Slot 8 name is '${mockCommandCard.currentButtons[8].name}'`);
    assert(typeof mockCommandCard.currentButtons[8].action === 'function', 'Command Card button action callback defined');

    // Triggering command card action spawns another instance
    mockCommandCard.currentButtons[8].action();
    assert(entities.length === 3, `Triggering command card slot spawned another unit (total entities: ${entities.length})`);

    console.log('\n[SUITE 4] Export to Local Binary & Mod (REST API Integration)');
    const exportConfigBtn = panel.querySelector('#export-mod-config-btn');
    const patchBinaryBtn = panel.querySelector('#patch-local-binary-btn');
    const resultBox = panel.querySelector('#mod-export-result');

    assert(exportConfigBtn !== null, 'Export Mod Config button exists');
    assert(patchBinaryBtn !== null, 'Patch Local dawn.exe button exists');
    assert(resultBox !== null, 'Export result box exists');

    // 1. Export Mod Config
    fetchCalls.length = 0;
    exportConfigBtn.dispatchEvent(new Event('click'));
    await new Promise(r => setTimeout(r, 50));

    assert(fetchCalls.length >= 1, `fetch() was called for save_mod_config`);
    const saveCall = fetchCalls.find(c => c.url === '/api/save_mod_config');
    assert(saveCall !== undefined, 'POST /api/save_mod_config endpoint targeted');
    const savePayload = JSON.parse(saveCall.options.body);
    assert(savePayload.profile_name === 'imzinrok_dawn_mod_v1', `Profile name correctly passed in payload: ${savePayload.profile_name}`);
    assert(savePayload.custom_units.length >= 1, `Custom units serialized in payload (count: ${savePayload.custom_units.length})`);
    assert(resultBox.style.display !== 'none', 'Result status box is visible');
    assert(resultBox.innerHTML.includes('Mod Config Successfully Exported'), 'Confirmation message displayed in result box');

    // 2. Patch Local Binary
    fetchCalls.length = 0;
    patchBinaryBtn.dispatchEvent(new Event('click'));
    await new Promise(r => setTimeout(r, 50));

    assert(fetchCalls.length >= 1, `fetch() was called for patch_binary`);
    const patchCall = fetchCalls.find(c => c.url === '/api/patch_binary');
    assert(patchCall !== undefined, 'POST /api/patch_binary endpoint targeted');
    const patchPayload = JSON.parse(patchCall.options.body);
    assert(patchPayload.target_filename === 'dawn_modded.exe', `Target filename is dawn_modded.exe`);
    assert(patchPayload.new_value > 0, `Patched speed value is ${patchPayload.new_value}`);
    assert(resultBox.innerHTML.includes('dawn.exe Successfully Patched'), 'Patch success confirmation message displayed');
    assert(resultBox.innerHTML.includes('1,032,192 bytes'), 'Verified file size (1,032,192 bytes) displayed');

    console.log('\n================================================================');
    console.log(` RESULTS: ${passedCount}/${totalCount} TESTS PASSED WITH ZERO FAILURES!`);
    console.log('================================================================\n');
}

runTests().catch(err => {
    console.error('Fatal test error:', err);
    process.exit(1);
});
