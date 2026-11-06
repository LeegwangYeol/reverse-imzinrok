/**
 * 4x3 Command Card HUD for Imjinrok 2+: Dawn
 *
 * Implements the 12-slot RTS Command Card HUD conforming to screenPt_plus.dat:
 * - 4 columns x 3 rows grid placed in the bottom-right HUD area
 * - Standard keyboard hotkeys (QWER / ASDF / ZXCV) and custom unit hotkeys (Y, K, N, F, B, T, M, S, D, U)
 * - Cooldown overlay animation with timer and visual shading
 * - Full suite of RTS actions: Move, Stop, Hold, Attack, Patrol, Produce/Spawn Unit
 * - Native support for 10 custom Joseon units (0x70~0x79) with 34x34 button icons, tooltips & hotkeys
 * - Headless-friendly architecture supporting both DOM and pure JavaScript simulation
 */

export const COMMAND_HOTKEYS = [
    { code: 'KeyQ', key: 'q', label: 'Q', slot: 0 },
    { code: 'KeyW', key: 'w', label: 'W', slot: 1 },
    { code: 'KeyE', key: 'e', label: 'E', slot: 2 },
    { code: 'KeyR', key: 'r', label: 'R', slot: 3 },

    { code: 'KeyA', key: 'a', label: 'A', slot: 4 },
    { code: 'KeyS', key: 's', label: 'S', slot: 5 },
    { code: 'KeyD', key: 'd', label: 'D', slot: 6 },
    { code: 'KeyF', key: 'f', label: 'F', slot: 7 },

    { code: 'KeyZ', key: 'z', label: 'Z', slot: 8 },
    { code: 'KeyX', key: 'x', label: 'X', slot: 9 },
    { code: 'KeyC', key: 'c', label: 'C', slot: 10 },
    { code: 'KeyV', key: 'v', label: 'V', slot: 11 }
];

/**
 * 10 Custom Joseon Units (0x70 ~ 0x79) Metadata & Production Mapping
 */
export const CUSTOM_JOSEON_UNITS = [
    {
        kindId: 0x70,
        kindHex: '0x70',
        id: 'yusaeng',
        name: '유생',
        englishName: 'Scholar',
        description: '백색 도포와 갓을 착용하고 책을 읽는 선비 (도술·마법 지원)',
        hotkey: 'Y',
        slot: 9,
        buildingId: 'chosun_hq',
        buildingName: '조선 본영',
        costRice: 250,
        costPotato: 0,
        buildTime: 6,
        speed: 18,
        attackMin: 15,
        attackMax: 20,
        hp: 450,
        nativeButtonId: 0x44,
        iconUrl: 'assets/ui/buttons/btn_unit_0x70.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_yusaeng.png'
    },
    {
        kindId: 0x71,
        kindHex: '0x71',
        id: 'geomsul_nangin',
        name: '검술 낭인',
        englishName: 'Ronin Swordsman',
        description: '푸른 두건과 일본도를 들고 돌격하는 검술 낭인',
        hotkey: 'K',
        slot: 8,
        buildingId: 'chosun_barracks',
        buildingName: '조선 훈련소',
        costRice: 180,
        costPotato: 0,
        buildTime: 5,
        speed: 21,
        attackMin: 22,
        attackMax: 28,
        hp: 600,
        nativeButtonId: 0x45,
        iconUrl: 'assets/ui/buttons/btn_unit_0x71.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_geomsul_nangin.png'
    },
    {
        kindId: 0x72,
        kindHex: '0x72',
        id: 'jochong_nangin',
        name: '조총 낭인',
        englishName: 'Ronin Musketeer',
        description: '삿갓을 쓰고 조총을 연사하는 저격형 조총 낭인',
        hotkey: 'N',
        slot: 9,
        buildingId: 'chosun_barracks',
        buildingName: '조선 훈련소',
        costRice: 240,
        costPotato: 0,
        buildTime: 6,
        speed: 18,
        attackMin: 12,
        attackMax: 16,
        hp: 480,
        nativeButtonId: 0x46,
        iconUrl: 'assets/ui/buttons/btn_unit_0x72.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_jochong_nangin.png'
    },
    {
        kindId: 0x73,
        kindHex: '0x73',
        id: 'gumiho',
        name: '구미호',
        englishName: 'Nine-Tailed Fox',
        description: '아홉 개 꼬리를 펼치며 주술과 화염을 구사하는 여우 요괴',
        hotkey: 'F',
        slot: 11,
        buildingId: 'chosun_hq',
        buildingName: '조선 본영',
        costRice: 280,
        costPotato: 50,
        buildTime: 7,
        speed: 22,
        attackMin: 28,
        attackMax: 34,
        hp: 750,
        nativeButtonId: 0x47,
        iconUrl: 'assets/ui/buttons/btn_unit_0x73.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_gumiho.png'
    },
    {
        kindId: 0x74,
        kindHex: '0x74',
        id: 'wangbeol',
        name: '조선왕벌',
        englishName: 'Joseon Hornet',
        description: '날개를 퍼덕이며 급습 독침을 쏘는 거대 비행 왕벌 (공중 유닛)',
        hotkey: 'B',
        slot: 7,
        buildingId: 'chosun_stables',
        buildingName: '조선 목장/마구간',
        costRice: 200,
        costPotato: 50,
        buildTime: 6,
        speed: 25,
        attackMin: 24,
        attackMax: 28,
        hp: 500,
        isAir: true,
        nativeButtonId: 0x48,
        iconUrl: 'assets/ui/buttons/btn_unit_0x74.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_wangbeol.png'
    },
    {
        kindId: 0x75,
        kindHex: '0x75',
        id: 'horangi',
        name: '조선 호랑이',
        englishName: 'Joseon Tiger',
        description: '사나운 줄무늬와 날카로운 발톱으로 적을 찢는 맹수 호랑이',
        hotkey: 'T',
        slot: 8,
        buildingId: 'chosun_stables',
        buildingName: '조선 목장/마구간',
        costRice: 300,
        costPotato: 0,
        buildTime: 7,
        speed: 24,
        attackMin: 38,
        attackMax: 46,
        hp: 950,
        nativeButtonId: 0x49,
        iconUrl: 'assets/ui/buttons/btn_unit_0x75.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_horangi.png'
    },
    {
        kindId: 0x76,
        kindHex: '0x76',
        id: 'teolgamyeon',
        name: '털가면',
        englishName: 'FurHead Demon',
        description: '백색 털가면과 철제 갈퀴로 급소를 타격하는 귀신 전사',
        hotkey: 'M',
        slot: 10,
        buildingId: 'chosun_barracks',
        buildingName: '조선 훈련소',
        costRice: 220,
        costPotato: 40,
        buildTime: 6,
        speed: 19,
        attackMin: 25,
        attackMax: 32,
        hp: 700,
        nativeButtonId: 0x4A,
        iconUrl: 'assets/ui/buttons/btn_unit_0x76.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_teolgamyeon.png'
    },
    {
        kindId: 0x77,
        kindHex: '0x77',
        id: 'seolnyeo',
        name: '설녀',
        englishName: 'Snow Woman',
        description: '하얀 소복과 냉기 파편으로 적 부대를 얼어붙게 하는 설녀',
        hotkey: 'S',
        slot: 9,
        buildingId: 'chosun_stables',
        buildingName: '조선 목장/마구간',
        costRice: 280,
        costPotato: 60,
        buildTime: 7,
        speed: 20,
        attackMin: 32,
        attackMax: 40,
        hp: 850,
        nativeButtonId: 0x4B,
        iconUrl: 'assets/ui/buttons/btn_unit_0x77.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_seolnyeo.png'
    },
    {
        kindId: 0x78,
        kindHex: '0x78',
        id: 'dokkaebi',
        name: '조선 도깨비',
        englishName: 'Joseon Dokkaebi',
        description: '은색 뿔과 가시 박힌 도깨비 방망이를 휘두르는 붉은 괴력 도깨비',
        hotkey: 'D',
        slot: 10,
        buildingId: 'chosun_stables',
        buildingName: '조선 목장/마구간',
        costRice: 320,
        costPotato: 0,
        buildTime: 7,
        speed: 17,
        attackMin: 36,
        attackMax: 45,
        hp: 1100,
        nativeButtonId: 0x4C,
        iconUrl: 'assets/ui/buttons/btn_unit_0x78.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_dokkaebi.png'
    },
    {
        kindId: 0x79,
        kindHex: '0x79',
        id: 'bulgasari',
        name: '불가살이',
        englishName: 'Bulgasari',
        description: '쇠와 불을 먹으며 체력을 불리는 전설의 묵직한 괴수 (최고 체력)',
        hotkey: 'U',
        slot: 10,
        buildingId: 'chosun_hq',
        buildingName: '조선 본영',
        costRice: 380,
        costPotato: 100,
        buildTime: 8,
        speed: 15,
        attackMin: 40,
        attackMax: 52,
        hp: 1400,
        nativeButtonId: 0x4D,
        iconUrl: 'assets/ui/buttons/btn_unit_0x79.png',
        iconAliasUrl: 'assets/ui/buttons/btn_unit_bulgasari.png'
    }
];

export class CommandCardHUD {
    /**
     * @param {HTMLElement|string|null} [container=null] - DOM element or query selector for command grid
     * @param {Function} [onCommandTrigger=null] - Callback invoked when a command is executed: (cmd) => void
     */
    constructor(container = null, onCommandTrigger = null) {
        this.container = null;
        if (typeof document !== 'undefined') {
            if (typeof container === 'string') {
                this.container = document.querySelector(container);
            } else if (container instanceof HTMLElement) {
                this.container = container;
            }
        }

        this.onCommandTrigger = onCommandTrigger;

        // 12 command slots (4 columns x 3 rows)
        this.slots = new Array(12).fill(null);

        // Active command state (e.g. 'move', 'attack', 'patrol') waiting for ground target click
        this.activeCommand = null;

        // Cooldown state for each of the 12 slots: { active: boolean, duration: number, remaining: number }
        this.cooldowns = new Array(12).fill(null).map(() => ({
            active: false,
            duration: 0,
            remaining: 0
        }));

        // DOM slot button element references
        this.slotElements = [];

        this.initDOM();
        this.initHotkeys();
        this.setDefaultUnitCommands();
    }

    /**
     * Initializes the 4x3 button elements inside the DOM container.
     */
    initDOM() {
        if (!this.container || typeof document === 'undefined') return;

        this.container.innerHTML = '';
        this.container.classList.add('command-card-grid');
        this.slotElements = [];

        for (let i = 0; i < 12; i++) {
            const hotkey = COMMAND_HOTKEYS[i];
            const slotBtn = document.createElement('button');
            slotBtn.className = 'cmd-slot';
            slotBtn.dataset.slot = i;
            slotBtn.disabled = true;

            // Inner slot structure: Hotkey badge, Icon container, Cooldown overlay, Cooldown text
            slotBtn.innerHTML = `
                <span class="cmd-hotkey">${hotkey.label}</span>
                <div class="cmd-icon"></div>
                <div class="cmd-cooldown-overlay" style="height: 0%;"></div>
                <span class="cmd-cooldown-timer"></span>
            `;

            slotBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.triggerSlot(i);
            });

            this.container.appendChild(slotBtn);
            this.slotElements.push(slotBtn);
        }
    }

    /**
     * Binds keyboard hotkey listeners (QWER / ASDF / ZXCV + dynamic custom unit hotkeys).
     */
    initHotkeys() {
        if (typeof window === 'undefined') return;

        window.addEventListener('keydown', (e) => {
            // Do not trigger hotkeys when user is typing in input fields
            if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) {
                return;
            }

            const pressedKey = e.key ? e.key.toLowerCase() : '';

            // 1. Check if any active button slot has an explicit hotkey matching pressed key
            for (let i = 0; i < 12; i++) {
                const cmd = this.slots[i];
                if (cmd && cmd.hotkey && cmd.hotkey.toLowerCase() === pressedKey) {
                    if (!this.cooldowns[i].active) {
                        this.triggerSlot(i);
                        return;
                    }
                }
            }

            // 2. Fall back to standard slot grid hotkey (QWER / ASDF / ZXCV)
            const hotkeyDef = COMMAND_HOTKEYS.find(h => h.code === e.code || h.key.toLowerCase() === pressedKey);
            if (hotkeyDef !== undefined) {
                const slotIndex = hotkeyDef.slot;
                if (this.slots[slotIndex] && !this.cooldowns[slotIndex].active) {
                    this.triggerSlot(slotIndex);
                }
            }
        });
    }

    /**
     * Configures the standard RTS military unit command layout:
     * - Slot 0 [Q]: Move (이동)
     * - Slot 1 [W]: Stop (정지)
     * - Slot 2 [E]: Hold Position (홀드)
     * - Slot 3 [R]: Attack (공격)
     * - Slot 4 [A]: Patrol (순찰)
     */
    setDefaultUnitCommands(unit = null) {
        const buttons = new Array(12).fill(null);

        buttons[0] = {
            id: 'move',
            action: 'move',
            name: '이동 (Move)',
            hotkey: 'Q',
            iconUrl: 'assets/ui/cmd_move.png',
            tooltip: '유닛을 지정한 위치로 이동시킵니다. [Q]'
        };

        buttons[1] = {
            id: 'stop',
            action: 'stop',
            name: '정지 (Stop)',
            hotkey: 'W',
            iconUrl: 'assets/ui/cmd_stop.png',
            tooltip: '현재 모든 명령을 즉시 중지합니다. [W]'
        };

        buttons[2] = {
            id: 'hold',
            action: 'hold',
            name: '홀드 (Hold)',
            hotkey: 'E',
            iconUrl: 'assets/ui/cmd_hold.png',
            tooltip: '현재 위치를 사수하며 접근하는 적을 공격합니다. [E]'
        };

        buttons[3] = {
            id: 'attack',
            action: 'attack',
            name: '공격 (Attack)',
            hotkey: 'R',
            iconUrl: 'assets/ui/cmd_attack.png',
            tooltip: '지정 위치로 이동하며 적을 공격하거나 특정 대상을 공격합니다. [R]'
        };

        buttons[4] = {
            id: 'patrol',
            action: 'patrol',
            name: '순찰 (Patrol)',
            hotkey: 'A',
            iconUrl: 'assets/ui/cmd_patrol.png',
            tooltip: '현재 위치와 지정 위치 사이를 반복 순찰합니다. [A]'
        };

        this.setButtons(buttons);
    }

    /**
     * Configures unit production buttons for buildings or barracks.
     *
     * @param {Array<Object>} produceList - List of produce unit definitions
     */
    setProductionCommands(produceList = []) {
        const buttons = new Array(12).fill(null);

        for (let i = 0; i < Math.min(produceList.length, 11); i++) {
            const item = produceList[i];
            const hotkey = item.hotkey || COMMAND_HOTKEYS[i].label;
            buttons[i] = {
                id: item.id || `produce_${i}`,
                action: item.action || 'produce',
                unitId: item.unitId,
                name: item.name || `생산 (${hotkey})`,
                costRice: item.costRice || item.costCrop || 0,
                costPotato: item.costPotato || 0,
                hotkey: hotkey,
                iconUrl: item.iconUrl || '',
                atlasPos: item.atlasPos || null,
                tooltip: item.tooltip || `${item.name || '유닛'}을(를) 생산합니다. [${hotkey}]`
            };
        }

        // Slot 11 (V): Cancel production
        buttons[11] = {
            id: 'cancel',
            action: 'cancel',
            name: '취소 (Cancel)',
            hotkey: 'V',
            iconUrl: 'assets/ui/cmd_cancel.png',
            tooltip: '대기열의 마지막 생산을 취소합니다. [V]'
        };

        this.setButtons(buttons);
    }

    /**
     * Registers a custom unit spawn/produce button in the command card (e.g. from Live Modding Studio).
     *
     * @param {Object} unitDef - Custom unit configuration
     * @param {number} [slotIndex=5] - Target slot index (default: slot 5 / Hotkey S)
     */
    registerCustomUnitCommand(unitDef, slotIndex = 5) {
        if (slotIndex < 0 || slotIndex >= 12) slotIndex = 5;
        const hotkey = unitDef.hotkey || COMMAND_HOTKEYS[slotIndex].label;

        const cmd = {
            id: unitDef.id || 'custom_unit',
            action: unitDef.action || 'spawn_custom',
            unitData: unitDef,
            unitId: unitDef.id || unitDef.unitId,
            kindId: unitDef.kindId,
            kindHex: unitDef.kindHex,
            name: unitDef.name || `커스텀 유닛 [${hotkey}]`,
            hotkey: hotkey,
            costRice: unitDef.costRice || unitDef.cost_rice || 0,
            costPotato: unitDef.costPotato || unitDef.cost_potato || 0,
            iconUrl: unitDef.iconUrl || unitDef.icon_url || '',
            isCustomUnit: true,
            tooltip: unitDef.tooltip || `커스텀 유닛 [${unitDef.name || '새 유닛'}]을(를) 전장에 소환합니다. [${hotkey}]`
        };

        this.setButton(slotIndex, cmd);
    }

    /**
     * Retrieves a standardized button definition for one of the 10 custom Joseon units (0x70~0x79).
     *
     * @param {number|string} identifier - Kind ID (e.g. 0x70, 112), kind hex ('0x70'), or unit id ('yusaeng')
     * @returns {Object|null} Button definition object or null if not found
     */
    getCustomUnitButtonDef(identifier) {
        let unit = null;
        if (typeof identifier === 'number') {
            unit = CUSTOM_JOSEON_UNITS.find(u => u.kindId === identifier);
        } else if (typeof identifier === 'string') {
            const lower = identifier.toLowerCase();
            unit = CUSTOM_JOSEON_UNITS.find(u =>
                u.id.toLowerCase() === lower ||
                u.kindHex.toLowerCase() === lower ||
                u.name === identifier
            );
        }

        if (!unit) return null;

        return {
            id: `produce_${unit.id}`,
            action: `produce_${unit.id}`,
            produceAction: 'produce_custom_unit',
            unitId: unit.id,
            kindId: unit.kindId,
            kindHex: unit.kindHex,
            name: `${unit.name} (쌀 ${unit.costRice}${unit.costPotato > 0 ? ' 감 ' + unit.costPotato : ''})`,
            unitName: unit.name,
            hotkey: unit.hotkey,
            slot: unit.slot,
            costRice: unit.costRice,
            costPotato: unit.costPotato,
            buildTime: unit.buildTime,
            speed: unit.speed,
            attackMin: unit.attackMin,
            attackMax: unit.attackMax,
            hp: unit.hp,
            isAir: Boolean(unit.isAir),
            iconUrl: unit.iconUrl,
            iconAliasUrl: unit.iconAliasUrl,
            isCustomUnit: true,
            tooltip: `${unit.name} [${unit.hotkey}]\n${unit.description}\n비용: 쌀 ${unit.costRice}${unit.costPotato > 0 ? ', 감자 ' + unit.costPotato : ''} | 체력: ${unit.hp} | 공격력: ${unit.attackMin}~${unit.attackMax}`
        };
    }

    /**
     * Configures the 4x3 command grid exclusively with all 10 custom Joseon unit buttons.
     * Useful for Modding Studio, testing, or custom unit command views.
     */
    setCustomJoseonUnitButtons(filterIds = null) {
        const buttons = new Array(12).fill(null);

        CUSTOM_JOSEON_UNITS.forEach((unit) => {
            if (filterIds && !filterIds.includes(unit.id) && !filterIds.includes(unit.kindHex)) {
                return;
            }
            const btnDef = this.getCustomUnitButtonDef(unit.id);
            if (btnDef && unit.slot >= 0 && unit.slot < 12) {
                // If default slot already occupied by another custom unit, find next free slot
                let targetSlot = unit.slot;
                if (buttons[targetSlot] !== null) {
                    targetSlot = buttons.findIndex((b, idx) => b === null && idx < 11);
                }
                if (targetSlot !== -1 && targetSlot < 12) {
                    buttons[targetSlot] = btnDef;
                }
            }
        });

        // Slot 11: Cancel
        buttons[11] = {
            id: 'cancel',
            action: 'cancel',
            name: '취소 (Cancel)',
            hotkey: 'V',
            iconUrl: 'assets/ui/cmd_cancel.png',
            tooltip: '명령을 취소합니다. [V]'
        };

        this.setButtons(buttons);
    }

    /**
     * Configures a building's command card, automatically injecting the authoritative
     * custom Joseon unit buttons at their engine code-cave slots:
     * - 조선 본영 (HQ): Slot 9 (유생 [Y]), Slot 10 (불가살이 [U]), Slot 11 (구미호 [F])
     * - 조선 훈련소 (Barracks): Slot 8 (검술 낭인 [K]), Slot 9 (조총 낭인 [N]), Slot 10 (털가면 [M])
     * - 조선 목장/마구간 (Stables): Slot 7 (조선왕벌 [B]), Slot 8 (조선 호랑이 [T]), Slot 9 (설녀 [S]), Slot 10 (조선 도깨비 [D])
     *
     * @param {string|Object} building - Building name or building object
     * @param {Array<Object|null>} [baseButtons=null] - Existing 12-element button array (optional)
     */
    setBuildingCustomUnitCommands(building, baseButtons = null) {
        const bName = (typeof building === 'string') ? building : ((building && building.name) ? building.name : '');
        const buttons = baseButtons ? [...baseButtons] : new Array(12).fill(null);

        if (bName.includes('본영') || bName.includes('hq') || bName.includes('HQ')) {
            // Joseon HQ code-cave: Slot 9 (유생), Slot 10 (불가살이), Slot 11 (구미호)
            buttons[9] = this.getCustomUnitButtonDef('yusaeng');
            buttons[10] = this.getCustomUnitButtonDef('bulgasari');
            buttons[11] = this.getCustomUnitButtonDef('gumiho');
        } else if (bName.includes('훈련소') || bName.includes('barracks') || bName.includes('병영')) {
            // Joseon Barracks code-cave: Slot 8 (검술 낭인), Slot 9 (조총 낭인), Slot 10 (털가면)
            buttons[8] = this.getCustomUnitButtonDef('geomsul_nangin');
            buttons[9] = this.getCustomUnitButtonDef('jochong_nangin');
            buttons[10] = this.getCustomUnitButtonDef('teolgamyeon');
        } else if (bName.includes('마구간') || bName.includes('목장') || bName.includes('stables')) {
            // Joseon Stables code-cave: Slot 7 (조선왕벌), Slot 8 (조선 호랑이), Slot 9 (설녀), Slot 10 (조선 도깨비)
            buttons[7] = this.getCustomUnitButtonDef('wangbeol');
            buttons[8] = this.getCustomUnitButtonDef('horangi');
            buttons[9] = this.getCustomUnitButtonDef('seolnyeo');
            buttons[10] = this.getCustomUnitButtonDef('dokkaebi');
        }

        this.setButtons(buttons);
    }

    /**
     * Sets all 12 button definitions at once.
     *
     * @param {Array<Object|null>} buttons - 12-element array of button definitions
     */
    setButtons(buttons) {
        for (let i = 0; i < 12; i++) {
            this.setButton(i, buttons[i] || null);
        }
    }

    /**
     * Sets or clears a single slot button.
     *
     * @param {number} slotIndex - Slot index (0..11)
     * @param {Object|null} buttonDef - Command definition or null to disable
     */
    setButton(slotIndex, buttonDef) {
        if (slotIndex < 0 || slotIndex >= 12) return;
        this.slots[slotIndex] = buttonDef;

        const el = this.slotElements[slotIndex];
        if (!el) return;

        const hotkeyBadge = el.querySelector('.cmd-hotkey');

        if (buttonDef) {
            el.disabled = false;
            const effectiveHotkey = buttonDef.hotkey || COMMAND_HOTKEYS[slotIndex].label;

            // Update hotkey badge if present
            if (hotkeyBadge) {
                hotkeyBadge.textContent = effectiveHotkey;
            }

            // Rich tooltip with costs if available
            if (buttonDef.tooltip) {
                el.title = buttonDef.tooltip;
            } else if (buttonDef.costRice !== undefined || buttonDef.costPotato !== undefined) {
                const costs = [];
                if (buttonDef.costRice) costs.push(`쌀: ${buttonDef.costRice}`);
                if (buttonDef.costPotato) costs.push(`감자: ${buttonDef.costPotato}`);
                el.title = `${buttonDef.name || '유닛'} [${effectiveHotkey}]${costs.length > 0 ? ' (' + costs.join(', ') + ')' : ''}`;
            } else {
                el.title = `${buttonDef.name} [${effectiveHotkey}]`;
            }

            el.classList.add('has-command');
            if (buttonDef.isCustomUnit || (buttonDef.kindId >= 0x70 && buttonDef.kindId <= 0x79)) {
                el.classList.add('custom-unit-cmd');
                el.dataset.kindHex = buttonDef.kindHex || '';
                el.dataset.unitId = buttonDef.unitId || buttonDef.id || '';
            } else {
                el.classList.remove('custom-unit-cmd');
                delete el.dataset.kindHex;
                delete el.dataset.unitId;
            }

            const icon = el.querySelector('.cmd-icon');
            if (icon) {
                if (buttonDef.atlasPos) {
                    icon.style.backgroundImage = "url('assets/ui/button_plus_atlas.png')";
                    icon.style.backgroundSize = 'auto';
                    icon.style.backgroundPosition = buttonDef.atlasPos;
                    icon.textContent = '';
                } else if (buttonDef.iconUrl) {
                    icon.style.backgroundImage = `url('${buttonDef.iconUrl}')`;
                    icon.style.backgroundSize = 'contain';
                    icon.style.backgroundPosition = 'center';
                    icon.textContent = '';
                } else {
                    icon.style.backgroundImage = 'none';
                    icon.textContent = buttonDef.name ? buttonDef.name.substring(0, 2) : '';
                }
            }
        } else {
            el.disabled = true;
            el.title = '';
            el.classList.remove('has-command', 'active-command', 'custom-unit-cmd');
            delete el.dataset.kindHex;
            delete el.dataset.unitId;

            // Reset hotkey badge to slot default
            if (hotkeyBadge) {
                hotkeyBadge.textContent = COMMAND_HOTKEYS[slotIndex].label;
            }

            const icon = el.querySelector('.cmd-icon');
            if (icon) {
                icon.style.backgroundImage = 'none';
                icon.textContent = '';
            }
        }
    }

    /**
     * Clears all 12 slots.
     */
    clearAllSlots() {
        for (let i = 0; i < 12; i++) {
            this.setButton(i, null);
        }
        this.clearActiveCommand();
    }

    /**
     * Triggers the action associated with a specific slot index.
     *
     * @param {number} slotIndex - Slot index (0..11)
     */
    triggerSlot(slotIndex) {
        if (slotIndex < 0 || slotIndex >= 12) return;
        const cmd = this.slots[slotIndex];
        if (!cmd) return;

        // Check active cooldown
        if (this.cooldowns[slotIndex].active) return;

        // Update active command visual state for all targeting commands
        const TARGETING_ACTIONS = [
            'move', 'attack', 'attack_ground', 'patrol',
            'set_rally', 'repair_building', 'skill_shockwave', 'skill_firestorm'
        ];
        if (TARGETING_ACTIONS.includes(cmd.action) || cmd.requiresTarget) {
            this.setActiveCommand(cmd.action, slotIndex);
        } else {
            this.clearActiveCommand();
        }

        // Trigger callback
        if (this.onCommandTrigger) {
            this.onCommandTrigger(cmd);
        }
    }

    /**
     * Marks a command as actively awaiting target click with visual highlight.
     */
    setActiveCommand(actionName, slotIndex = -1) {
        this.activeCommand = actionName;

        if (slotIndex === -1 && actionName) {
            slotIndex = this.slots.findIndex(s => s && (s.action === actionName || s.id === actionName));
        }

        for (let i = 0; i < 12; i++) {
            const el = this.slotElements[i];
            if (!el) continue;
            if (i === slotIndex) {
                el.classList.add('active-command');
            } else {
                el.classList.remove('active-command');
            }
        }
    }

    /**
     * Clears any active waiting command state and highlights.
     */
    clearActiveCommand() {
        this.activeCommand = null;
        for (let i = 0; i < 12; i++) {
            const el = this.slotElements[i];
            if (el) el.classList.remove('active-command');
        }
    }

    /**
     * Initiates a cooldown animation overlay on a specific button slot.
     *
     * @param {number} slotIndex - Slot index (0..11)
     * @param {number} durationSec - Cooldown duration in seconds
     */
    startCooldown(slotIndex, durationSec) {
        if (slotIndex < 0 || slotIndex >= 12 || durationSec <= 0) return;

        this.cooldowns[slotIndex] = {
            active: true,
            duration: durationSec,
            remaining: durationSec
        };

        const el = this.slotElements[slotIndex];
        if (el) {
            el.classList.add('on-cooldown');
            el.disabled = true;
        }
    }

    /**
     * Updates cooldown timers and animation overlays.
     * Call this in the main 60FPS animation loop.
     *
     * @param {number} deltaSec - Frame delta in seconds (e.g. 0.016 for 60FPS)
     */
    update(deltaSec) {
        for (let i = 0; i < 12; i++) {
            const cd = this.cooldowns[i];
            if (!cd || !cd.active) continue;

            cd.remaining -= deltaSec;
            const el = this.slotElements[i];

            if (cd.remaining <= 0) {
                cd.active = false;
                cd.remaining = 0;
                if (el) {
                    el.classList.remove('on-cooldown');
                    if (this.slots[i]) el.disabled = false;
                    const overlay = el.querySelector('.cmd-cooldown-overlay');
                    if (overlay) overlay.style.height = '0%';
                    const timer = el.querySelector('.cmd-cooldown-timer');
                    if (timer) timer.textContent = '';
                }
            } else if (el) {
                const ratio = cd.remaining / cd.duration;
                const overlay = el.querySelector('.cmd-cooldown-overlay');
                if (overlay) {
                    overlay.style.height = `${Math.round(ratio * 100)}%`;
                }
                const timer = el.querySelector('.cmd-cooldown-timer');
                if (timer) {
                    timer.textContent = cd.remaining >= 1.0 ? cd.remaining.toFixed(1) : (cd.remaining.toFixed(1));
                }
            }
        }
    }
}
