# 작업 공간 안전 및 무결성 보장 가이드 (Workspace Safety & Integrity Guide)

## 1. 개요 및 안전 원칙 (Core Principles)

본 문서는 《임진록 2+ 조선의 반격: 여명》 역공학, 모딩 도구 개발 및 웹 엔진 에셋 변환 프로젝트를 수행함에 있어, 원본 게임 자산과 분석 리포지토리의 원형을 100% 보존하기 위한 **작업 공간 안전 및 불변성(Immutability) 무결성 체계**를 기술합니다.

### 핵심 안전 원칙
1. **절대적 읽기 전용 (Strict Read-Only)**:
   - `C:\src\reverse-imzinrok\YM` (원본 게임 패키지 및 여명 모드 배포본)과 `C:\src\rea` (역공학 리포지토리) 내부의 모든 파일은 엄격한 읽기 전용으로 보호됩니다.
   - 어떠한 도구, 스크립트, 에이전트도 해당 디렉터리 내의 파일을 수정, 이동, 덮어쓰기, 삭제해서는 안 됩니다.
2. **사본 기반 작업 (Copy-on-Write / Working Copies)**:
   - 바이너리 패칭(`dawn.exe`), 아카이브 언패킹(`Data`, `Data.hq`), 맵 수정(`*.map`) 등의 모든 모딩 작업은 반드시 `C:\src\reverse-imzinrok` 하위의 별도 출력 디렉터리에 사본을 생성하여 수행합니다.
3. **지속적 무결성 감사 (Continuous Integrity Audit)**:
   - 자동화된 안전 검증 도구(`tools/verify_safety.py`)를 통해 Git 워킹 트리의 청결도와 204개 핵심 원본 자산의 SHA-256 해시를 주기적으로 전수 대조합니다.

---

## 2. 보호 대상 자산 명세

### 2.1 `C:\src\reverse-imzinrok\YM` (원본 게임 배포본)
- **`YM\dawn\dawn.exe`**: PE32 x86 실행 바이너리 (ImageBase `0x00400000`, 1,032,192 바이트). 여명 모드의 389바이트 코드 케이브(`0x004e4ae6`~`0x004e4c6a`) 및 밸런스 패치 코드가 포함됨.
- **`YM\dawn\UseMap.exe`**: 바닐라 임진록 2+ V 1.158 기준 실행 바이너리 (1,032,192 바이트).
- **`YM\dawn\Map Editor.exe`**: 맵 에디터 언락 바이너리 (1,032,192 바이트).
- **`YM\dawn\Data.hq` (인덱스) & `YM\dawn\Data` (패키지)**: 109개 핵심 설정/데이터 테이블 파일이 난독화되어 저장된 아카이브 (각각 5,408 바이트 및 230,202 바이트).
- **`YM\dawn\syw2x.dll` & `syw2xinjector.exe`**: 여명 모드 UI 및 메모리 후킹 라이브러리.
- **`YM\dawn\_inmm.dll` & `_inmmserv.exe`**: BGM 재생 제어 라이브러리.
- **`YM\dawn\pal\*.pal`**: 37종의 768바이트 6-bit VGA DAC 팔레트.
- **`YM\dawn\cusmap\*.map`**: 58종의 1,132,876바이트 고정 크기 커스텀 맵.

### 2.2 `C:\src\rea` (역공학 리포지토리)
- REA 분석 툴체인 및 사전 역공학 조사 보고서가 포함된 Git 리포지토리입니다.
- Git 트리의 Clean 상태(`git status --porcelain` 결과 0행)가 항상 유지되어야 합니다.

---

## 3. 안전 검증 도구: `tools/verify_safety.py`

### 3.1 기능 및 검증 절차
`tools/verify_safety.py`는 다음 2단계 감사를 독립적으로 수행합니다:

1. **`rea` 리포지토리 상태 감사**:
   - `git -C C:\src\rea status --porcelain` 명령을 실행합니다.
   - 추적되지 않은 파일(Untracked), 스테이징된 변경사항(Staged), 수정된 파일(Modified), 삭제된 파일(Deleted)이 단 하나도 존재하지 않는지 검증합니다.
2. **`YM` 핵심 파일 204개 전수 바이트/해시 감사**:
   - `YM` 내 모든 실행 파일(`.exe`), 동적 라이브러리(`.dll`), 데이터 아카이브(`Data`, `Data.hq`), 팔레트 파일(`.pal`), 커스텀 맵(`.map`) 등 총 204개 파일의 존재 여부를 확인합니다.
   - 파일 크기(Byte Size)를 1바이트 오차 없이 검증합니다.
   - 전체 파일 바이트를 청크 단위로 스트리밍하여 암호학적 해시(SHA-256)를 계산하고, 원본 기준값과 비트 단위로 비교합니다.

### 3.2 실행 방법 및 결과 해석
```bash
python tools/verify_safety.py
```

- **정상 출력 (Exit Code 0)**:
```text
===========================================================================
       REVERSE-IMZINROK SAFETY & INTEGRITY VERIFICATION AUDIT
===========================================================================
[*] Checking 'rea' repository integrity: C:\src\rea
    [PASS] Working tree is 100% clean.

[*] Checking 'YM' read-only files (204 items): C:\src\reverse-imzinrok\YM
    [PASS] All 204 key files verified bit-exact with original SHA-256 hashes.
===========================================================================
AUDIT RESULT: PASSED (100% Clean & Untouched)
===========================================================================
```
- **오염 감지 시 (Exit Code 1)**:
  - 위반된 파일명, 기대 크기 vs 실제 크기, 기대 SHA-256 vs 실제 SHA-256 해시를 상세히 출력하고 즉시 실패 처리됩니다.

---

## 4. 대표 핵심 파일 무결성 해시 레퍼런스 (Baseline Hashes)

| 상대 경로 | 파일 크기 (Bytes) | SHA-256 해시 |
|:---|:---:|:---|
| `dawn/Data` | 230,202 | `2b16045633fed94972a900686901fbd93266bc1079560b1385c7fed86799a21c` |
| `dawn/Data.hq` | 5,408 | `20ccc1c4e74abf59f7c5847479f20f2703506917fa80af0e4d6571d8eb463dab` |
| `dawn/dawn.exe` | 1,032,192 | `302735c2feaf0467a511a9b3bdb0b87d09e7ab7be903299ca4245a51a54aa67a` |
| `dawn/UseMap.exe` | 1,032,192 | `f899ee92d60c99882c6bb2c5ea118de68b6abb30852114abdf1ea89807a29611` |
| `dawn/Map Editor.exe` | 1,032,192 | `ae301f2f8079fc6b247013f72aac9922bfa9d87ae67843eb7a1e64047adca393` |
| `dawn/syw2x.dll` | 23,040 | `f97b15fb39a286f055c3da9aad50aeeadcb8d464077c21d24691041999a45f2c` |
| `dawn/syw2xinjector.exe` | 37,376 | `8b3a66f919d5dfd5afd8f576bbec1313dcf1951c0e47ad569e0a653b267c9349` |
| `dawn/_inmm.dll` | 167,936 | `03192987e9c877cf344874412d2c0e1a80b5d5f8b91f325771e9615feadbf160` |
| `dawn/_inmmserv.exe` | 151,552 | `1a0bdac8376298d1ef22d0d8b7ed4a57edfdc36219084346979cfba6afc3ab9e` |
| `dawn/ddraw.dll` | 413,184 | `3bc7230d1a6023a8fc0ea52b18d7edda94fcb4c0ae3d178f6e1577d68a62bd19` |
| `dawn/dxwrapper.dll` | 1,957,888 | `96c443193bad8794ebf04738566e092f8b34ae4541cb2433fd0708d49edbe8fe` |
| `dawn/ipxconfig.exe` | 461,600 | `b6190f0bacf3b20612268d72b80b1d0542ec78839737d3000b2bb58aa1b3d252` |
| `dawn/ipxwrapper.dll` | 84,768 | `b6c0bd24e5c623c517ff8bb8b39a133b2a3baa9553519ea7e8fd92f960e848d5` |
| `dawn/mswsock.dll` | 36,128 | `685fcbfd789ea1387297dc2151983138a76a080b4eb495e8c81bab914b4e29aa` |
| `dawn/wsock32.dll` | 35,616 | `d3e15c8cd5523405acbdddd592409344948a896e12a9a2f37f8bfd55f118a3a5` |
| `dawn/dpwsockx.dll` | 39,200 | `11f9db3b946c5e7f7001811257d9bc27d0050ee93701091cc3bf1e0c4c86f972` |

*(참고: 58개 커스텀 맵 및 37개 팔레트 파일의 전체 204개 해시는 `tools/verify_safety.py` 내부에 완전 직렬화되어 있습니다.)*

---

## 5. 결론 및 개발자 수칙

모든 개발 및 테스트 단계에서 다음 규칙을 준수하십시오:
1. 커밋 전 및 모딩 도구 실행 후에는 반드시 `python tools/verify_safety.py`를 실행하여 무결성을 재확인합니다.
2. 테스트 자동화 스위트(CI/CD)의 사전/사후 단계에 `verify_safety.py`가 필수로 편입되어야 합니다.
3. 원본 자산 디렉터리는 오직 읽기(Read) 스트림으로만 접근해야 하며, 쓰기 권한을 요구하는 모든 작업은 즉각 중단되어야 합니다.
