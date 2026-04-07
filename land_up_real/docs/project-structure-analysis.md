# LandingUp Demo — 프로젝트 구조 분석

> 분석 기준일: 2026-04-03

---

## 프로젝트 파일 트리

```
landing-up-demo/
├── .env                              # ANTHROPIC_API_KEY
├── package.json
│
├── ai/
│   ├── agent1/
│   │   ├── extract_brand.py          # 브랜드 메뉴얼 → 수치 추출 (Claude API)
│   │   ├── read_floor_vectors.py     # PDF 벡터 도형 → mm 좌표 추출
│   │   └── read_inputs.py            # 입력 재료 점검 스크립트 (유틸)
│   │
│   ├── agent2/
│   │   ├── schema.py                 # Pydantic 스키마 정의
│   │   ├── pipeline.py               # Agent1 → Agent2 체인 오케스트레이터
│   │   ├── detect_facilities.py      # Claude Vision → 시설물 탐지
│   │   ├── calculate_usable_ranges.py # Shapely + NetworkX → 가용 영역 계산
│   │   └── render_floor_image.py     # PDF → PNG 렌더링 유틸
│   │
│   └── agent3/
│       ├── schema.py                 # Pydantic 스키마 정의
│       ├── pipeline.py               # Agent3 오케스트레이터
│       ├── reference_db.py           # 조형물 Mock DB
│       ├── layout_optimizer.py       # Shapely + NetworkX → 배치 최적화
│       └── pathing_validator.py      # Dijkstra 동선 시뮬레이션
│
├── backend/
│   └── server.py                     # FastAPI 서버 (단일 엔드포인트)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                   # 메인 React 앱
│   │   ├── components/
│   │   │   └── FloorPlanVisualizer.tsx  # Canvas 기반 도면 시각화
│   │   └── types.ts                  # TypeScript 타입 정의
│   └── (vite, tailwind, tsconfig 등 설정 파일들)
│
├── docs/
│   ├── landing-up-agent-spec.md
│   ├── landing-up-agent-io.md
│   ├── project-overview.md
│   └── ... (설계/계획 문서들)
│
└── image/
    ├── demo_floor_cad.pdf            # 샘플 도면 (벡터)
    └── demo_floor_rendered.png       # 렌더링된 도면 이미지
```

---

## Agent 파일 역할 및 상태 분석

### Agent 1 — 브랜드/법령 수치 추출

| 파일 | 역할 | Input | Output | 구현 상태 |
|------|------|-------|--------|-----------|
| `extract_brand.py` | 브랜드 메뉴얼 텍스트를 Claude API에 전달해 제약 수치를 JSON으로 추출, Pydantic으로 검증 | `manual_text: str` (Markdown/PDF 텍스트) | `BrandConstraints` dict: `clearspace_mm`, `character_orientation`, `prohibited_material`, `logo_clearspace_mm`, `relationships` | **완성** — API 호출, regex 파싱, Pydantic validator(범위 보정), 에러 핸들링 모두 구현 |
| `read_floor_vectors.py` | PDF CAD 도면의 벡터 경로(선/사각형/곡선)를 pt → mm로 좌표 변환해 반환. 프론트 렌더링용 | `pdf_path: str`, `target_width/height: float` | `List[List[[x,y]]]` — 경로 좌표 목록 | **완성** — `extract_floor_vector_paths()` export 함수 완성, `server.py`에서 실제 호출됨 |
| `read_inputs.py` | PDF/메뉴얼 파일이 정상 읽히는지 디버깅 확인용 스크립트 | (하드코딩된 파일 경로) | stdout 출력 전용 | **유틸/진단용** — 파이프라인 외부 도구. 직접 실행용 |

---

### Agent 2 — 공간 분석 및 가용 영역 계산

| 파일 | 역할 | Input | Output | 구현 상태 |
|------|------|-------|--------|-----------|
| `schema.py` | Agent 2 전체 Pydantic 모델 정의 | — | `Facility`, `Entrance`, `UsableRange`, `FloorPlanData` | **완성** |
| `detect_facilities.py` | 도면 이미지를 Claude Vision에 전달해 시설물(스프링클러/소화전/분전반/입구)과 외곽 꼭짓점을 0~1000 상대좌표로 탐지 후 mm 변환 | `image_path: str` (PNG or PDF) | `FloorPlanData` dict: `dimensions_mm`, `outline_vertices`, `facilities`, `entrances`, `user_marking_required` | **완성** — 이미지 리사이징, base64 인코딩, Vision API 호출, fallback(수동 마킹 요청) 포함 |
| `calculate_usable_ranges.py` | Shapely로 데드존 차집합 계산 + NetworkX 격자 그래프로 보행 거리 계산 → 참조점 라벨링 | `floor_data: dict`, `brand_data: dict` | `floor_data`에 `usable_ranges`(Polygon 좌표 목록)와 `reference_points`(zone_label + walk_distance) 추가 후 반환 | **완성** — 200mm 격자, Shapely buffer/difference, Dijkstra 거리, 라벨링(entrance/mid/deep_zone) 구현 |
| `pipeline.py` | Agent1 → detect → calculate 전체 체인 오케스트레이터. Human-in-the-loop 분기 처리(수동 마킹 / Vision 실패) | `manual_path`, `image_path`, `user_markings_json` | `space_data: dict` = `{"brand": {...}, "floor_plan": {...}}` 또는 `{"status": "manual_marking_required"}` | **완성** — PDF/MD 분기, 수동 마킹 파싱, fallback 분기 모두 구현 |
| `render_floor_image.py` | PDF를 300DPI PNG로 렌더링 저장하는 1회성 유틸 | (하드코딩 경로) | `image/demo_floor_rendered.png` 파일 저장 | **유틸/준비용** — 직접 실행용, 파이프라인 외부 |

---

### Agent 3 — 레이아웃 최적화 및 동선 시뮬레이션

| 파일 | 역할 | Input | Output | 구현 상태 |
|------|------|-------|--------|-----------|
| `schema.py` | Agent 3 Pydantic 모델 정의 | — | `PlacedObject`, `Pathway`, `FinalLayoutData`, `PlacementDirective`, `Agent3Output` | **완성** |
| `reference_db.py` | 브랜드 테마별 배치 가능 조형물 목록과 규격을 반환하는 Mock DB | `theme_name: str` | `List[dict]`: `object_id`, `dimensions_mm`, `importance` | **완성 (Mock)** — 헬로키티/산리오 및 generic fallback 구현. 향후 VectorDB 연동 예정 |
| `layout_optimizer.py` | Agent3의 배치 의도(Directives)를 받아 Shapely 충돌 체크 + NetworkX 통로 막힘 체크를 순차적으로 수행해 절대 좌표 확정 | `space_data: dict`, `objects_db: list`, `agent3_directives: List[PlacementDirective]` | `List[PlacedObject]`: 확정된 조형물 중심 좌표, 크기, 방향 | **완성** — 증분 배치, 충돌 체크, 입구 막힘 시 800mm Nudge 재시도 구현 |
| `pathing_validator.py` | 배치 확정된 조형물을 장애물로 설정, Dijkstra로 입구→각 조형물 최단 동선 계산 | `usable_polygons_data`, `placed_objects`, `entrance_data` | `List[Pathway]`: 경로별 노드 좌표 목록 | **완성** — 1000mm 격자, 인간 통과폭 600mm buffer, 도달 불가 시 경고 출력 |
| `pipeline.py` | 공간 요약(자연어) 생성 → Claude에게 배치 의도 추출 요청 → optimizer → pathing → 최종 패키징 | `space_data: dict` (Agent2 출력), `theme: str` | `FinalLayoutData` dict: `placed_objects`, `visitor_pathways`, `status`, `brand_rules`, `entrances` | **완성** — LLM 배치 결정, Directive 파싱, 모듈 체이닝, 에러 시 `raise` (fallback 없음) |

---

### Backend / Frontend

| 파일 | 역할 | Input | Output | 구현 상태 |
|------|------|-------|--------|-----------|
| `backend/server.py` | FastAPI 서버. 단일 엔드포인트 `/api/generate`. Agent1~3 전체 파이프라인 호출 및 결과 병합 | `multipart/form-data`: `brand_manual` (File), `floor_plan` (File), `user_markings` (Form, optional) | JSON: `placed_objects`, `visitor_pathways`, `facilities`, `usable_ranges`, `floor_vector_paths`, `dimensions_mm` 등 통합 응답 | **완성** — CORS 설정, 임시파일 브릿지, human-in-the-loop 분기, 벡터 경로 주입 구현 |
| `frontend/src/components/FloorPlanVisualizer.tsx` | Canvas 기반 도면 시각화 컴포넌트. 벡터선/가용영역/시설물/조형물/동선 레이어를 겹쳐 렌더링 | `FinalLayoutResponse` (API 응답 전체) | SVG/Canvas 렌더링 | **구현 중** — `frontend-plan.md` 존재, 컴포넌트 파일은 있음 |

---

## 전체 데이터 흐름

```
[사용자]
  ↓ brand_manual + floor_plan 업로드
[server.py /api/generate]
  ↓
[Agent 1] extract_brand.py
  브랜드 메뉴얼 텍스트 → BrandConstraints (clearspace, 금지 소재 등)
  ↓
[Agent 2-a] detect_facilities.py
  도면 이미지 → Claude Vision → 시설물/입구/외곽선 좌표
  ↓ (Vision 실패 시 → manual_marking_required 반환)
[Agent 2-b] calculate_usable_ranges.py
  Shapely 차집합 + NetworkX 격자 → 가용 폴리곤 + 참조점 zone_label
  ↓
[Agent 3-a] pipeline.py (LLM 의사결정)
  공간 자연어 요약 → Claude → PlacementDirective 목록
  ↓
[Agent 3-b] layout_optimizer.py
  Directive + Shapely 충돌체크 + 통로막힘 체크 → PlacedObject 절대 좌표
  ↓
[Agent 3-c] pathing_validator.py
  Dijkstra 최단 동선 → Pathway 노드 목록
  ↓
[server.py] 전체 결과 병합 + floor_vector_paths 추가
  ↓
[Frontend] FloorPlanVisualizer.tsx 렌더링
```
