# 임진록 2+ 조선의 반격 모던 웹 엔진 이식 청사진 (Web Engine Blueprint)

## 1. 개요 및 비전 (Overview & Tech Stack)

본 문서는 2000년대 명작 RTS 《임진록 2+ 조선의 반격: 여명》을 브라우저 환경에서 플러그인 없이 네이티브에 준하는 60FPS로 완벽히 구동하기 위한 **모던 웹 RTS 엔진 (HTML5 / WebGL 2.0 / WebAudio / WebAssembly) 기술 청사진**입니다.

### 1.1 목표 아키텍처 및 기술 스택
- **렌더링 파이프라인**: **WebGL 2.0 / WebGPU** (Instanced Sprite Rendering, 64×48 아이소메트릭 타일맵, 셰이더 기반 팔레트 사이클링)
- **코어 시뮬레이션 & 물리/길찾기**: **WebAssembly (Rust / C++)** — 결정론적(Deterministic) 틱 시뮬레이션, 계층형 A* (HPA*) 길찾기
- **오디오 엔진**: **Web Audio API** — 3D 공간 음향(Spatial Audio), 음원 풀링, 무손실 PCM 스트리밍
- **UI 및 입력 계층**: **HTML5 Canvas / CSS3 Grid HUD** — 4×3 커맨드 카드, 2D 레이더 미니맵, 마우스 드래그 박스 선택
- **실제 인게임 플레이 레퍼런스 영상**: [https://youtu.be/7aVyKR41bak](https://youtu.be/7aVyKR41bak) (유닛 모션, 투사체 궤적, 사운드 이펙트, UI 애니메이션 분석 기준)

---

## 2. 에셋 변환 및 웹 로딩 파이프라인 (Asset Pipeline)

원본의 사유(Proprietary) 바이너리 에셋들을 웹 표준 포맷으로 사전/실시간 변환하여 HTTP 스트리밍 및 IndexedDB에 캐싱합니다.

```
[고유 에셋 원본]                     [웹 변환 파이프라인]                    [웹 브라우저 런타임]
.pal (768B 6-bit DAC)       ──► RGBA Lookup Array / 1D Texture  ──► WebGL Fragment Shader
.spr (Version 9 0xFE RLE)   ──► Atlas PNG + Spritesheet JSON    ──► GPU Texture2D + SpriteBatch
.ytl / .ypr (Diamond/Hill)  ──► 64x48 Diamond Tile Sheet PNG    ──► Isometric Tilemap Layer
.YAV (26B + PCM Audio)      ──► RIFF .wav / WebM Audio Buffer   ──► Web Audio API AudioBuffer
.map (1.13MB Binary)        ──► TypedArray Buffer / JSON        ──► WASM World Simulation Grid
```

### 2.1 팔레트 처리 (`.pal` -> WebGL 텍스처)
- 768바이트 6-bit DAC 데이터를 256색 RGBA 텍스처(256×1, `RGBA8`)로 로드.
- 인덱스 0번은 투명 알파(`Alpha = 0`), 1~255번은 불투명(`Alpha = 255`).
- 색상 변환: $\text{RGB}_8 = (\text{DAC}_6 \times 255) / 63$.
- 셰이더에서 인덱스 텍스처의 픽셀 값을 팔레트 텍스처의 UV로 샘플링하여 실시간 팔레트 교체(국가별 팀 색상, 피격 플래시)를 GPU 레벨에서 0비용으로 처리.

### 2.2 스프라이트 아틀라스 (`.spr` -> WebGL SpriteSheet)
- Version 9 헤더(`0xBF4` 바이트)의 `atlas_width`와 `atlas_height`에 맞춰 전체 프레임을 단일 PNG 아틀라스로 패킹.
- 메타데이터 JSON:
  ```json
  {
    "name": "char_swordk",
    "frame_width": 80,
    "frame_height": 60,
    "frame_count": 192,
    "hotspots": [{"x": 40, "y": 45}, ...],
    "animations": {
      "idle_south": [0, 1, 2, 3],
      "walk_south": [4, 5, 6, 7, 8, 9],
      "attack_south": [10, 11, 12, 13, 14]
    }
  }
  ```

---

## 3. 다이아몬드 타일 아이소메트릭 투영 수학 (Isometric Projection Mathematics)

임진록 2+ 엔진은 가로 64픽셀, 세로 48픽셀의 2:1.5 비율 다이아몬드 아이소메트릭 그리드를 채택하고 있습니다.

```
       (gx, gy)
          /\
         /  \
        /    \  TILE_HEIGHT = 48px
        \    /
         \  /
          \/
      TILE_WIDTH = 64px
```

### 3.1 맵 격자 -> 화면 픽셀 좌표 (World to Screen)
그리드 좌표 $(gx, gy)$와 고도 $\text{elev}$($0 \dots 5$)를 화면 좌표 $(sx, sy)$로 변환하는 공식:

$$sx = (gx - gy) \times \frac{\text{TILE\_WIDTH}}{2} + \text{CAMERA\_X}$$

$$sy = (gx + gy) \times \frac{\text{TILE\_HEIGHT}}{2} + \text{CAMERA\_Y} - (\text{elev} \times \text{ELEVATION\_HEIGHT})$$

- $\text{TILE\_WIDTH} = 64$
- $\text{TILE\_HEIGHT} = 48$
- $\text{ELEVATION\_HEIGHT} = 16$ (단차 1단계당 16픽셀 상향 이동)

### 3.2 화면 픽셀 좌표 -> 맵 격자 역투영 (Screen to World Mouse Picking)
마우스 클릭 위치 $(sx, sy)$로부터 타겟 타일 $(gx, gy)$를 판별하는 공식:

1. 카메라 및 고도 보정 좌표 계산:
   $$X_{\text{norm}} = \frac{sx - \text{CAMERA\_X}}{32}$$
   $$Y_{\text{norm}} = \frac{sy - \text{CAMERA\_Y} + \text{elev\_offset}}{24}$$
2. 그리드 좌표 산출:
   $$gx = \left\lfloor \frac{X_{\text{norm}} + Y_{\text{norm}}}{2} \right\rfloor$$
   $$gy = \left\lfloor \frac{Y_{\text{norm}} - X_{\text{norm}}}{2} \right\rfloor$$

### 3.3 뷰포트 컬링 (Viewport Culling)
180×180 맵 전체 타일 수는 32,400개에 달하므로, 화면 시야에 들어오는 마름모꼴 바운딩 박스 영역 내의 타일($\approx 40 \times 30$개)만 GPU 인스턴싱 버퍼에 적재하여 드로우 콜(Draw Call)을 1~2회로 최소화합니다.

---

## 4. 깊이 정렬 및 레이어링 아키텍처 (Depth Sorting & Layering)

아이소메트릭 2.5D 시점에서는 뒤쪽에 있는 유닛과 건물이 앞쪽 유닛에 자연스럽게 가려져야 합니다.

### 4.1 정렬 키 (Depth Key) 계산 공식
각 렌더러 엔티티의 Z-소팅 값은 지형 격자 상의 발밑 기준점 $(gx, gy)$에 기반합니다:

$$\text{DepthKey} = (gx + gy) \times 10000 + (\text{LayerPriority} \times 100) + \text{sub\_y}$$

- **`LayerPriority` 우선순위**:
  1. 지형 바닥 타일 (`LayerPriority = 0`)
  2. 수면/해안선 데칼 (`LayerPriority = 1`)
  3. 자원 (감자밭/벼/대나무/나무) (`LayerPriority = 2`)
  4. 사전 배치 건물 / 시나리오 오브젝트 (`LayerPriority = 3`)
  5. 지상 유닛 / 영웅 (`LayerPriority = 4`)
  6. 공중 유닛 (비거/풍선) (`LayerPriority = 8`, Z-소팅 오버라이드)
  7. 투사체 / 이펙트 화염 (`LayerPriority = 9`)

---

## 5. 길찾기 및 시뮬레이션 엔진 (WASM Pathfinding & Collision)

실시간으로 수백 기의 유닛이 원활히 기동할 수 있도록 **WebAssembly 기반 2계층 계층형 A\*(HPA\*) 알고리즘**을 구현합니다.

```
+-------------------------------------------------------------+
| 상위 계층: 90×90 매크로 클러스터 그래프 (장거리 경로 고속 탐색)  |
+-------------------------------------------------------------+
                              ▲
                              │ 국소 경로 쿼리
                              ▼
+-------------------------------------------------------------+
| 하위 계층: 180×180 마이크로 셀 그리드 (타일 통행성 + 동적 장애물)|
+-------------------------------------------------------------+
                              ▲
                              │ 충돌 회피
                              ▼
+-------------------------------------------------------------+
| 연속 공간: RVO (Reciprocal Velocity Obstacles) 로컬 회피      |
+-------------------------------------------------------------+
```

1. **지형 통행성 비트맵**: `ByteGrid 1`(`0x3b0d4`, 절벽/장애물)과 건물 풋프린트 배열을 32,400바이트 비트마스크로 WASM 선형 메모리에 매핑.
2. **동적 유닛 밀치기 (Soft Collision)**: 유닛 간 이동 시 겹침을 방지하기 위해 상호 역속도 장애물(RVO) 알고리즘을 틱당 30Hz 주기로 연산.

---

## 6. 오디오 엔진 아키텍처 (Web Audio Sound Engine)

### 6.1 `EffectSound.dat` 매핑 및 풀링
- `EffectSound.dat`에 기술된 효과음 ID(공격음, 이동 명령음, 피격음, 사망음)와 `.YAV` 변환 음원을 `Map<SoundID, AudioBuffer>`에 프리로드.
- 동시 재생 제한: 동일한 폭발음이나 활소리가 5개 이상 중첩되어 클리핑(Clipping)이 발생하는 현상을 방지하기 위해 사운드 채널당 최대 3개 인스턴스로 음성 제한(Voice Limiting) 적용.

### 6.2 3D 입체 음향 (Stereo Panner Node)
화면 중심 $(cx, cy)$ 대비 사운드 발생 위치 $(sx, sy)$의 거리와 방향에 따라 실시간 패닝 및 볼륨 감쇄 적용:
```javascript
const panner = audioCtx.createStereoPanner();
const gainNode = audioCtx.createGain();

const pan = Math.max(-1.0, Math.min(1.0, (eventX - cameraX - screenWidth / 2) / (screenWidth / 2)));
const dist = Math.hypot(eventX - cameraCenterX, eventY - cameraCenterY);
const volume = Math.max(0.0, 1.0 - (dist / MAX_AUDIO_DISTANCE));

panner.pan.value = pan;
gainNode.gain.value = volume;
```

---

## 7. 게임 루프 및 네트워크 록스텝 통신 (Game Loop & Deterministic Lockstep)

### 7.1 프레임 분리 아키텍처
- **시뮬레이션 틱 (Logic Tick)**: 30 TPS (Ticks Per Second, 매 33.3ms) 고정 틱.
- **렌더링 프레임 (Render Frame)**: 브라우저 주사율(60Hz / 120Hz / 144Hz)에 맞춘 `requestAnimationFrame` 가변 프레임.
- 렌더러는 이전 틱과 현재 틱 사이의 보간(Linear Interpolation, $\alpha = \text{accumTime} / \Delta t$)을 통해 버벅임 없는 부드러운 유닛 이동을 표현.

### 7.2 WebRTC 기반 록스텝 멀티플레이어
- RTS의 방대한 유닛 동기화를 위해 각 클라이언트는 유닛 좌표가 아닌 **플레이어의 입력 명령(Command Packet)** 만을 P2P(WebRTC DataChannel)로 교환.
- 모든 클라이언트가 동일한 난수 시드(Seed)와 고정 소수점(Fixed-Point) 수학 라이브러리를 사용하여 완전한 결정론(Determinism) 보장.

---

## 8. 실전 게임플레이 레퍼런스 분석 및 UI/UX 구현 명세

유튜브 레퍼런스 영상([https://youtu.be/7aVyKR41bak](https://youtu.be/7aVyKR41bak)) 분석을 바탕으로 구현해야 할 인게임 인터페이스 세부 사항:

### 8.1 4×3 커맨드 카드 UI (`screenPt_plus.dat` 준수)
- 화면 우측 하단(`X: 652, Y: 486`, 4열 3행 12칸 그리드).
- 단축키(Q, W, E, R / A, S, D, F / Z, X, C, V) 매핑.
- 생산 쿨다운 오버레이 애니메이션 (시계방향 부채꼴 음영 마스크).

### 8.2 미니맵 레이더 HUD
- 화면 좌측 하단 200×200 영역.
- 현재 카메라 시야 영역을 직사각형 와이어프레임으로 오버레이.
- 미니맵 클릭 시 해당 지점으로 카메라 즉시 점프 이동.
- 미니맵 우클릭 시 선택된 부대에 즉시 이동/공격 명령 전달.

### 8.3 유닛 선택 및 상태 표시
- 녹색/노란색/빨간색 체력 게이지 바(Health Bar) 및 파란색 마나 바(Mana Bar).
- Shift 다중 선택, Ctrl + 숫자키(0~9) 부대 지정 및 빠른 더블 탭 부대 화면 전환.
- 100% 원작 감성을 재현한 폰트(돋움체/Arial, `FontInfo_kor.dat`) 렌더링.
