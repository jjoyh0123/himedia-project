# LandingUp AI — 프로젝트 전체 구조 정리

> 팝업스토어 자동 배치 AI 플랫폼  
> 브랜드 매뉴얼 + 도면 이미지 → AI 분석 → 3D 배치 레이아웃 생성

---

## 1. 디렉토리 전체 구조

```
landing-up-demo/
├── .env                          # ANTHROPIC_API_KEY 보관
├── .venv/                        # Python 가상환경
├── package.json                  # 루트 (폰트 패키지만)
│
├── frontend/                     # React + TypeScript + Vite (UI)
│   ├── index.html
│   └── src/
│       ├── main.tsx              # React 진입점
│       ├── App.tsx               # 메인 컴포넌트 (UI 전체 로직)
│       ├── types.ts              # TypeScript 인터페이스
│       ├── index.css
│       └── components/
│           └── FloorPlanVisualizer.tsx  # Three.js 3D 뷰어
│
├── backend/
│   └── server.py                 # FastAPI 서버 (파이프라인 진입점)
│
├── ai/
│   ├── agent1/                   # 브랜드 규칙 추출
│   │   ├── extract_brand.py      # Claude API → 브랜드 제약 추출
│   │   ├── read_floor_vectors.py # PDF CAD 벡터 경로 추출
│   │   └── read_inputs.py        # 파일 입력 처리
│   │
│   ├── agent2/                   # 도면 분석 & 공간 계산
│   │   ├── pipeline.py           # Agent2 오케스트레이션
│   │   ├── detect_facilities.py  # Claude Vision → 설비 위치 탐지
│   │   ├── calculate_usable_ranges.py  # Shapely 기반 가용 공간 계산
│   │   ├── render_floor_image.py # 도면 렌더링
│   │   └── schema.py             # Pydantic 데이터 모델
│   │
│   └── agent3/                   # 레이아웃 최적화 & 동선 생성
│       ├── pipeline.py           # Agent3 오케스트레이션
│       ├── layout_optimizer.py   # 테트리스 방식 배치 알고리즘
│       ├── pathing_validator.py  # NetworkX Dijkstra 동선 생성
│       ├── reference_db.py       # 팝업 오브젝트 Mock DB (Hello Kitty 등)
│       └── schema.py             # Pydantic 데이터 모델
│
├── db/                           # DB 폴더 (미구현)
├── image/                        # 샘플 도면 이미지
└── docs/                         # 기획/문서
    ├── project_fw.md             # ← 이 파일
    ├── project-overview.md
    ├── hello-kitty-brand-manual.md
    ├── landing-up-agent-spec.md
    └── legal_rules.txt
```

---

## 2. 기술 스택

| 영역 | 기술 |
|------|------|
| **Frontend** | React 19, TypeScript ~5.9, Vite 8 |
| **3D 시각화** | Three.js 0.183, @react-three/fiber, @react-three/drei |
| **스타일링** | TailwindCSS 4.2 |
| **HTTP 통신** | Axios 1.14 |
| **Backend** | FastAPI, Uvicorn (Python) |
| **AI** | Anthropic SDK, Claude Sonnet 4.6 (텍스트 + Vision) |
| **기하학 계산** | Shapely (폴리곤 연산, 충돌 감지) |
| **그래프/동선** | NetworkX (Dijkstra 알고리즘) |
| **PDF 파싱** | PyMuPDF (fitz) |
| **이미지 처리** | Pillow (PIL) |
| **데이터 검증** | Pydantic |
| **환경설정** | python-dotenv |

---

## 3. 데이터 흐름 (전체 파이프라인)

```
[사용자 브라우저]
  ↓ 파일 업로드: 브랜드 매뉴얼(MD/PDF) + 도면 이미지(PNG/JPG/PDF)
  ↓
[Frontend - React @ localhost:5173]
  ↓ POST /api/generate (multipart form)
  ↓
[Backend - FastAPI @ localhost:8000]
  │
  ├─→ [Agent 1] 브랜드 규칙 추출
  │      ├─ MD/PDF 파일 파싱
  │      ├─ Claude API 호출
  │      └─ 반환: BrandConstraints JSON
  │           (clearspace_mm, character_orientation, prohibited_material 등)
  │
  ├─→ [Agent 2a] Claude Vision으로 설비 탐지
  │      ├─ 도면 이미지 인코딩
  │      ├─ Claude Vision API 호출
  │      └─ 반환: 스프링클러, 소화전, 전기패널, 출입구 위치
  │
  ├─→ [Agent 2b] 가용 공간 계산
  │      ├─ Shapely로 설비 경계(alert zone) 버퍼 생성
  │      ├─ 도면 전체 면적 - 경계 = 배치 가능 구역
  │      └─ 반환: UsableRange 폴리곤 목록
  │
  ├─→ [Agent 3a] Claude LLM → 배치 지시문 생성
  │      ├─ 공간 요약 자연어 생성
  │      ├─ Claude에게 "어느 오브젝트를 어디에" 지시 요청
  │      └─ 반환: PlacementDirective 목록
  │
  ├─→ [Agent 3b] 레이아웃 최적화
  │      ├─ Shapely 충돌 감지 기반 테트리스 배치
  │      ├─ reference_db에서 오브젝트 치수 조회
  │      └─ 반환: 각 오브젝트 (x, y) 좌표
  │
  └─→ [Agent 3c] 방문 동선 생성
         ├─ NetworkX Dijkstra로 장애물 회피 경로 탐색
         └─ 반환: Pathway 노드 시퀀스
  ↓
[Backend] FinalLayoutData JSON 반환
  ↓
[Frontend] Three.js 3D 시각화
  ├─ 도면을 3D 바닥면으로 렌더링
  ├─ 오브젝트를 컬러 박스로 배치
  ├─ 설비 경계를 빨간 원으로 표시
  └─ 동선을 초록 점선으로 표시
```

---

## 4. 주요 파일별 역할

### Frontend

| 파일 | 역할 |
|------|------|
| [App.tsx](../frontend/src/App.tsx) | 파일 업로드, 수동 마킹 모드, 결과 표시 등 전체 UI 로직 |
| [FloorPlanVisualizer.tsx](../frontend/src/components/FloorPlanVisualizer.tsx) | Three.js 기반 2D/3D 뷰어, 오브젝트 클릭 하이라이트, 오비트 컨트롤 |
| [types.ts](../frontend/src/types.ts) | FinalLayoutData, PlacedObject, Pathway 등 타입 정의 |

### Backend

| 파일 | 역할 |
|------|------|
| [server.py](../backend/server.py) | `/api/generate` 단일 엔드포인트, Agent1→2→3 파이프라인 조율, 에러 핸들링 |

### AI Agent 1 — 브랜드 규칙 추출

| 파일 | 역할 |
|------|------|
| [extract_brand.py](../ai/agent1/extract_brand.py) | Claude Sonnet에게 브랜드 매뉴얼 전달 → clearspace, 금지재료, 캐릭터 방향 등 추출 |
| [read_floor_vectors.py](../ai/agent1/read_floor_vectors.py) | PDF CAD 도면에서 벡터 선분 경로 추출 |
| [read_inputs.py](../ai/agent1/read_inputs.py) | 입력 파일 읽기 유틸리티 |

### AI Agent 2 — 도면 분석

| 파일 | 역할 |
|------|------|
| [pipeline.py](../ai/agent2/pipeline.py) | Agent1 결과 수신 → Vision 탐지 → 가용 공간 계산 순서 조율 |
| [detect_facilities.py](../ai/agent2/detect_facilities.py) | Claude Vision으로 스프링클러/소화전/전기패널/출입구 위치 탐지 |
| [calculate_usable_ranges.py](../ai/agent2/calculate_usable_ranges.py) | Shapely 폴리곤 연산으로 안전 배치 구역 계산 |
| [render_floor_image.py](../ai/agent2/render_floor_image.py) | 도면 + 탐지 요소 시각화 렌더링 |
| [schema.py](../ai/agent2/schema.py) | FloorPlanData, Facility, Entrance, UsableRange Pydantic 모델 |

### AI Agent 3 — 배치 최적화

| 파일 | 역할 |
|------|------|
| [pipeline.py](../ai/agent3/pipeline.py) | Claude LLM 지시 → 배치 최적화 → 동선 생성 순서 조율 |
| [layout_optimizer.py](../ai/agent3/layout_optimizer.py) | 가용 구역 내 충돌 없는 오브젝트 배치 (테트리스 방식) |
| [pathing_validator.py](../ai/agent3/pathing_validator.py) | NetworkX Dijkstra로 방문 동선 생성 |
| [reference_db.py](../ai/agent3/reference_db.py) | Hello Kitty 팝업 오브젝트 Mock DB (조형물, 포토존, 계산대 등 치수 포함) |
| [schema.py](../ai/agent3/schema.py) | FinalLayoutData, PlacedObject, Pathway Pydantic 모델 |

---

## 5. 데이터 모델 구조

```
BrandConstraints (Agent 1 출력)
├── brand_name: str
├── clearspace_mm: int          # 오브젝트 최소 이격 거리
├── character_orientation: str  # 캐릭터 바라보는 방향
├── prohibited_material: str    # 금지 재료
├── logo_clearspace_mm: int     # 로고 최소 이격
└── relationships: List[{rule, confidence}]

FloorPlanData (Agent 2 출력)
├── dimensions_mm: {width, height}
├── outline_vertices: List[{x, y}]
├── facilities: List[Facility]
│   └── {id, type, position, alert_zone_mm}
├── entrances: List[Entrance]
│   └── {position, direction, confidence}
└── usable_ranges: List[UsableRange]
    └── {zone_id, polygon_bounds[], constraints_applied[]}

FinalLayoutData (Agent 3 출력 / Frontend 수신)
├── placed_objects: List[PlacedObject]
│   └── {object_id, dimensions, placed_coordinates, rotation}
├── visitor_pathways: List[Pathway]
│   └── {path_id, nodes[]}
├── facilities: []              # Agent 2에서 전달
├── usable_ranges: []           # Agent 2에서 전달
├── brand_rules: BrandConstraints
├── dimensions_mm: {width, height}
└── status: "success" | "partial_success"
```

---

## 6. 현재 구현 상태

### 완료된 기능

- **Frontend UI** — 파일 업로드, 2패널 레이아웃, 2D/3D 뷰 전환, 사이드바에서 오브젝트 클릭 하이라이트
- **3D 시각화** — Three.js 기반 도면 렌더링, 오브젝트 박스 배치, 설비 경계(빨간 원), 동선(초록 점선)
- **수동 마킹 모드** — AI 탐지 실패 시 사용자가 직접 설비 위치 클릭 지정 → 재실행
- **Agent 1** — Claude API로 브랜드 매뉴얼 → 제약 조건 JSON 추출 (신뢰도 포함)
- **Agent 2a** — Claude Vision으로 도면 이미지 설비 탐지 (좌표 0~1000 상대 스케일 변환)
- **Agent 2b** — Shapely로 설비 경계 생성 및 가용 공간 폴리곤 계산
- **Agent 3a** — Claude LLM으로 공간 분석 → 배치 지시문 생성
- **Agent 3b** — 충돌 없는 오브젝트 배치 최적화
- **Agent 3c** — NetworkX Dijkstra 방문 동선 계산

### 미구현 / 개선 필요

- PDF 도면 좌표 스케일 매핑 (실제 치수 미반영)
- Agent 2 Vision 탐지 신뢰도 낮을 때 fallback 로직 개선 (현재 일부 하드코딩)
- 오브젝트 회전 처리 (현재 모두 0도 고정)
- 외부 DB 연동 (현재 Mock DB)
- 3D 충돌 경고 → UI 연결 미완성
- 운영 환경 에러 핸들링 보완

---

## 7. 실행 방법

```bash
# Terminal 1 — Frontend
cd frontend
npm run dev
# → http://localhost:5173

# Terminal 2 — Backend
# Windows:
.venv\Scripts\activate
python backend/server.py
# → http://localhost:8000
```

**사용 흐름**:
1. `http://localhost:5173` 접속
2. 브랜드 매뉴얼 (`.md` / `.pdf`) + 도면 이미지 (`.png` / `.jpg` / `.pdf`) 업로드
3. **자동 배치 실행** 클릭
4. Agent 1→2→3 파이프라인 실행 대기
5. 3D 뷰어에서 결과 확인 (설비 탐지 실패 시 수동 마킹 모드 전환)

---

## 8. 다음 작업 방향 (Skills)

| 우선순위 | 작업 | 관련 파일 |
|---------|------|----------|
| 높음 | PDF 도면 좌표 → 실제 mm 스케일 변환 | `agent1/read_floor_vectors.py`, `agent2/calculate_usable_ranges.py` |
| 높음 | Vision 탐지 실패 fallback 로직 완성 | `agent2/detect_facilities.py`, `backend/server.py` |
| 중간 | 오브젝트 회전 각도 반영 | `agent3/layout_optimizer.py`, `FloorPlanVisualizer.tsx` |
| 중간 | 실제 DB 연동 (reference_db 교체) | `agent3/reference_db.py` |
| 낮음 | 3D 충돌 경고 UI 연결 | `App.tsx`, `FloorPlanVisualizer.tsx` |
| 낮음 | CAD 벡터 경로 렌더링 복구 | `agent1/read_floor_vectors.py` |
