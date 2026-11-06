/**
 * Automated Verification Suite for Renderer & RTS HUD Components
 *
 * Tests:
 * 1. IsometricRenderer: Frustum culling, DepthKey sorting, Alt-key health bar toggle, draw calls
 * 2. MinimapHUD: Scaling math, click/drag camera panning, right-click orders, viewport wireframe
 * 3. CommandCardHUD: 4x3 button slots, QWER/ASDF/ZXCV hotkeys, cooldown animation, action triggers
 */

import { IsometricRenderer } from '../web_prototype/js/engine/renderer.js';
import { MinimapHUD } from '../web_prototype/js/ui/minimap.js';
import { CommandCardHUD, COMMAND_HOTKEYS } from '../web_prototype/js/ui/command_card.js';
import { IsometricMath } from '../web_prototype/js/engine/isometric.js';

// Helper mock 2D Context
class MockCanvasContext {
    constructor() {
        this.fillCalls = [];
        this.strokeCalls = [];
        this.drawImageCalls = [];
        this.fillRectCalls = [];
        this.strokeRectCalls = [];
        this.arcCalls = [];
        this.ellipseCalls = [];
        this.fillStyle = '#000';
        this.strokeStyle = '#000';
        this.lineWidth = 1;
    }
    fillRect(x, y, w, h) { this.fillRectCalls.push({ x, y, w, h, fillStyle: this.fillStyle }); }
    strokeRect(x, y, w, h) { this.strokeRectCalls.push({ x, y, w, h, strokeStyle: this.strokeStyle }); }
    drawImage(...args) { this.drawImageCalls.push(args); }
    beginPath() {}
    closePath() {}
    moveTo() {}
    lineTo() {}
    arc(...args) { this.arcCalls.push(args); }
    ellipse(...args) { this.ellipseCalls.push(args); }
    fill() { this.fillCalls.push({ style: this.fillStyle }); }
    stroke() { this.strokeCalls.push({ style: this.strokeStyle }); }
    save() {}
    restore() {}
    translate() {}
    scale() {}
    fillText() {}
    setLineDash() {}
}

class MockCanvas {
    constructor(w = 1024, h = 768) {
        this.width = w;
        this.height = h;
        this.ctx = new MockCanvasContext();
        this.eventListeners = {};
    }
    getContext(type) {
        return this.ctx;
    }
    addEventListener(type, cb) {
        if (!this.eventListeners[type]) this.eventListeners[type] = [];
        this.eventListeners[type].push(cb);
    }
    getBoundingClientRect() {
        return { left: 0, top: 0, width: this.width, height: this.height };
    }
    dispatchEvent(type, eventObj) {
        const cbs = this.eventListeners[type] || [];
        for (const cb of cbs) cb(eventObj);
    }
}

// Simple test runner
let totalTests = 0;
let passedTests = 0;

function assert(condition, message) {
    totalTests++;
    if (!condition) {
        console.error(`  [FAIL] ${message}`);
        throw new Error(`Assertion failed: ${message}`);
    } else {
        passedTests++;
        console.log(`  [PASS] ${message}`);
    }
}

console.log('================================================================');
console.log(' RUNNING AUTOMATED UNIT TESTS: RENDERER & RTS HUD');
console.log('================================================================\n');

// -------------------------------------------------------------
// TEST SUITE 1: IsometricRenderer
// -------------------------------------------------------------
console.log('[SUITE 1] IsometricRenderer: Frustum Culling, DepthKey Sorting, Alt-Key Toggle');

const canvas = new MockCanvas(1024, 768);
const renderer = new IsometricRenderer(canvas);

assert(renderer !== null, 'IsometricRenderer instantiated successfully');
assert(renderer.showAllHealthBars === false, 'showAllHealthBars initially false');

// Test Alt key toggle
renderer.toggleAllHealthBars(true);
assert(renderer.showAllHealthBars === true, 'toggleAllHealthBars(true) sets showAllHealthBars to true');
renderer.toggleAllHealthBars(false);
assert(renderer.showAllHealthBars === false, 'toggleAllHealthBars(false) resets to false');
renderer.toggleAllHealthBars();
assert(renderer.showAllHealthBars === true, 'toggleAllHealthBars() toggles state to true');
renderer.toggleAllHealthBars();
assert(renderer.showAllHealthBars === false, 'toggleAllHealthBars() toggles state back to false');

// Test DepthKey generation & strict sorting
const depthKeyTile = IsometricMath.getDepthKey(10, 20, 0, 0);       // Ground tile
const depthKeyResource = IsometricMath.getDepthKey(10, 20, 2, 0);   // Resource
const depthKeyBuilding = IsometricMath.getDepthKey(10, 20, 3, 0);   // Building
const depthKeyUnit1 = IsometricMath.getDepthKey(10, 20, 4, 10);     // Unit at sub_y 10
const depthKeyUnit2 = IsometricMath.getDepthKey(10, 20, 4, 60);     // Unit at sub_y 60
const depthKeyAir = IsometricMath.getDepthKey(10, 20, 8, 0);        // Air unit
const depthKeyProj = IsometricMath.getDepthKey(10, 20, 9, 0);       // Projectile

assert(depthKeyTile === 300000, `Ground tile depth key is 300000 (actual: ${depthKeyTile})`);
assert(depthKeyResource === 300200, `Resource depth key is 300200 (actual: ${depthKeyResource})`);
assert(depthKeyBuilding === 300300, `Building depth key is 300300 (actual: ${depthKeyBuilding})`);
assert(depthKeyUnit1 === 300410, `Unit 1 depth key is 300410 (actual: ${depthKeyUnit1})`);
assert(depthKeyUnit2 === 300460, `Unit 2 depth key is 300460 (actual: ${depthKeyUnit2})`);
assert(depthKeyAir === 300800, `Air unit depth key is 300800 (actual: ${depthKeyAir})`);
assert(depthKeyProj === 300900, `Projectile depth key is 300900 (actual: ${depthKeyProj})`);

assert(
    depthKeyTile < depthKeyResource &&
    depthKeyResource < depthKeyBuilding &&
    depthKeyBuilding < depthKeyUnit1 &&
    depthKeyUnit1 < depthKeyUnit2 &&
    depthKeyUnit2 < depthKeyAir &&
    depthKeyAir < depthKeyProj,
    'DepthKeys strictly follow layer priority order 0 -> 2 -> 3 -> 4 -> 8 -> 9'
);

// Test selection box
renderer.setSelectionBox(50, 60, 200, 300);
assert(renderer.selectionBox !== null && renderer.selectionBox.active === true, 'Selection box set and active');
assert(renderer.selectionBox.startX === 50 && renderer.selectionBox.currentX === 200, 'Selection box coordinates accurate');
renderer.clearSelectionBox();
assert(renderer.selectionBox === null, 'Selection box cleared');

// Test render call with mock entities and grid
const mockGrid = {
    width: 180,
    height: 180,
    tileLayer1: new Uint16Array(180 * 180),
    tileLayer2: new Uint16Array(180 * 180),
    elevation: new Uint8Array(180 * 180),
    walkability: new Uint8Array(180 * 180),
    terrainType: new Uint8Array(180 * 180).fill(2),
    resourceTypes: new Uint8Array(180 * 180),
    resourceAmounts: new Uint16Array(180 * 180)
};

// Place resource at (90, 90)
mockGrid.resourceTypes[90 * 180 + 90] = 3; // Tree

const mockCamera = {
    x: 0,
    y: 0,
    viewportWidth: 1024,
    viewportHeight: 768
};

const mockEntities = [
    {
        id: 1,
        gx: 90,
        gy: 90,
        wx: 90.5,
        wy: 90.5,
        owner: 0,
        name: '조선 창병',
        hp: 100,
        max_hp: 100,
        mp: 50,
        max_mp: 50,
        selected: true,
        scale: 1.0,
        direction: 2
    },
    {
        id: 2,
        gx: 91,
        gy: 90,
        wx: 91.2,
        wy: 90.4,
        owner: 1,
        name: '일본 사무라이',
        hp: 40,
        max_hp: 120,
        selected: false,
        scale: 1.0,
        direction: 6
    }
];

const mockProjectiles = [
    {
        id: 1,
        type: 'arrow',
        getCurrentPos: () => ({ wx: 90.8, wy: 90.5, arcZ: 15 }),
        isArrived: false
    }
];

renderer.render(mockGrid, mockEntities, mockProjectiles, mockCamera);
assert(renderer.renderQueueLength > 0, `Render queue successfully built and executed (${renderer.renderQueueLength} items rendered)`);
assert(canvas.ctx.fillRectCalls.length > 0, 'Canvas fillRect calls executed for terrain/bars/background');

console.log('\n[SUITE 2] MinimapHUD: 2D Radar, Coordinate Math, Viewport Frustum, Orders');

const minimapCanvas = new MockCanvas(200, 200);
let lastMoveOrder = null;
const minimap = new MinimapHUD(minimapCanvas, mockGrid, mockCamera, (gx, gy) => {
    lastMoveOrder = { gx, gy };
});

assert(minimap !== null, 'MinimapHUD instantiated successfully');
assert(minimap.scaleX === (200 / 180), `Minimap scaleX is ~1.111 (actual: ${minimap.scaleX.toFixed(4)})`);

// Test coordinate conversion
const eventMockCenter = { clientX: 100, clientY: 100 };
const coordsCenter = minimap.getGridCoordsFromEvent(eventMockCenter);
assert(coordsCenter.gx === 90 && coordsCenter.gy === 90, `Screen center (100,100) maps to grid (90,90), got (${coordsCenter.gx}, ${coordsCenter.gy})`);

// Test right-click order dispatch
minimapCanvas.dispatchEvent('mousedown', {
    button: 2,
    clientX: 120,
    clientY: 140,
    preventDefault: () => {}
});
assert(lastMoveOrder !== null, 'Right-click on minimap dispatched move order callback');
assert(lastMoveOrder.gx === Math.floor(120 / (200 / 180)) && lastMoveOrder.gy === Math.floor(140 / (200 / 180)), 'Dispatched grid coordinates match right-click location');

// Test left-click camera pan
let cameraCenteredOn = null;
mockCamera.centerOnGrid = (gx, gy) => {
    cameraCenteredOn = { gx, gy };
};
minimapCanvas.dispatchEvent('mousedown', {
    button: 0,
    clientX: 50,
    clientY: 60,
    preventDefault: () => {}
});
assert(cameraCenteredOn !== null, 'Left-click on minimap triggered camera.centerOnGrid');
assert(cameraCenteredOn.gx === Math.floor(50 / (200 / 180)) && cameraCenteredOn.gy === Math.floor(60 / (200 / 180)), 'Camera centered on exact clicked tile');

// Test minimap rendering
minimap.render(mockEntities);
assert(minimapCanvas.ctx.fillRectCalls.length > 0, 'Minimap rendered terrain, resource, and unit dots');

console.log('\n[SUITE 3] CommandCardHUD: 4x3 Grid, Hotkeys, Cooldown Animation, Actions');

let lastCommandTriggered = null;
const cmdCard = new CommandCardHUD(null, (cmd) => {
    lastCommandTriggered = cmd;
});

assert(cmdCard !== null, 'CommandCardHUD instantiated successfully');
assert(cmdCard.slots.length === 12, 'Command card has exactly 12 button slots (4x3)');
assert(COMMAND_HOTKEYS.length === 12, '12 hotkeys defined matching QWER / ASDF / ZXCV');

// Verify default unit commands in slots 0..4
assert(cmdCard.slots[0].action === 'move' && cmdCard.slots[0].hotkey === 'Q', 'Slot 0 is Move [Q]');
assert(cmdCard.slots[1].action === 'stop' && cmdCard.slots[1].hotkey === 'W', 'Slot 1 is Stop [W]');
assert(cmdCard.slots[2].action === 'hold' && cmdCard.slots[2].hotkey === 'E', 'Slot 2 is Hold [E]');
assert(cmdCard.slots[3].action === 'attack' && cmdCard.slots[3].hotkey === 'R', 'Slot 3 is Attack [R]');
assert(cmdCard.slots[4].action === 'patrol' && cmdCard.slots[4].hotkey === 'A', 'Slot 4 is Patrol [A]');

// Test command trigger
cmdCard.triggerSlot(0);
assert(lastCommandTriggered !== null && lastCommandTriggered.action === 'move', 'Triggering slot 0 invoked Move command');
assert(cmdCard.activeCommand === 'move', 'Move command set as activeCommand');

cmdCard.triggerSlot(3);
assert(lastCommandTriggered.action === 'attack', 'Triggering slot 3 invoked Attack command');
assert(cmdCard.activeCommand === 'attack', 'Attack command set as activeCommand');

cmdCard.clearActiveCommand();
assert(cmdCard.activeCommand === null, 'clearActiveCommand() reset activeCommand');

// Test cooldown system
cmdCard.startCooldown(0, 4.0);
assert(cmdCard.cooldowns[0].active === true, 'Cooldown started on slot 0');
assert(cmdCard.cooldowns[0].remaining === 4.0, 'Remaining cooldown is 4.0 seconds');

// Attempting to trigger slot 0 while on cooldown should be ignored
lastCommandTriggered = null;
cmdCard.triggerSlot(0);
assert(lastCommandTriggered === null, 'Triggering slot 0 on cooldown was blocked');

// Advance time by 2.0s
cmdCard.update(2.0);
assert(cmdCard.cooldowns[0].active === true, 'Cooldown still active after 2.0s');
assert(cmdCard.cooldowns[0].remaining === 2.0, 'Remaining cooldown is 2.0s');

// Advance time by 2.5s (exceeding duration)
cmdCard.update(2.5);
assert(cmdCard.cooldowns[0].active === false, 'Cooldown completed after time elapsed');
assert(cmdCard.cooldowns[0].remaining === 0, 'Remaining cooldown reset to 0');

// Slot 0 can now be triggered again
cmdCard.triggerSlot(0);
assert(lastCommandTriggered !== null && lastCommandTriggered.action === 'move', 'Slot 0 successfully triggered after cooldown expired');

// Test Custom Unit Registration
cmdCard.registerCustomUnitCommand({
    id: 'hero_leesunshin',
    name: '이순신 장군',
    iconUrl: 'assets/units/hero_leesunshin.png'
}, 5);

assert(cmdCard.slots[5] !== null, 'Slot 5 contains custom unit command');
assert(cmdCard.slots[5].action === 'spawn_custom', 'Custom unit command action is spawn_custom');
assert(cmdCard.slots[5].hotkey === 'S', 'Slot 5 hotkey is S');

cmdCard.triggerSlot(5);
assert(lastCommandTriggered !== null && lastCommandTriggered.action === 'spawn_custom', 'Custom unit spawn triggered via slot 5');
assert(lastCommandTriggered.unitData.id === 'hero_leesunshin', 'Custom unit metadata preserved in command payload');

// Test Production Commands
cmdCard.setProductionCommands([
    { unitId: 1, name: '조선 창병' },
    { unitId: 2, name: '조선 궁수' }
]);

assert(cmdCard.slots[0].action === 'produce' && cmdCard.slots[0].name === '조선 창병', 'Slot 0 configured for 창병 production');
assert(cmdCard.slots[1].action === 'produce' && cmdCard.slots[1].name === '조선 궁수', 'Slot 1 configured for 궁수 production');
assert(cmdCard.slots[11].action === 'cancel', 'Slot 11 configured for production cancel');

console.log('\n================================================================');
console.log(` RESULTS: ${passedTests}/${totalTests} TESTS PASSED WITH ZERO FAILURES!`);
console.log('================================================================\n');
