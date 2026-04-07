# 파이프라인 1대1 비교 — Jo vs Shin (우리)

> 작성일: 2026-04-06
> 목적: 두 데모 구조의 차이점 분석 → 팀 데모 v1.0 통합 시 장점 채택

---

## 1. 아키텍처 구조

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 전체 단계 수 | 3단계 (업로드 → Agent1+2 병렬 → 가용영역 계산 → Agent3 배치+동선) | 5단계 (업로드→감지/마킹→에어리얼확인→배치→3D편집) |
| 백엔드 | FastAPI (Python) | FastAPI (Python) |
| 프론트엔드 | React + TypeScript (Vite) | Next.js + TypeScript |
| 3D 렌더링 | Three.js (@react-three/fiber + drei) | Three.js (@react-three/fiber + drei) |
| AI 모델 | Claude Sonnet 4.6 | Claude Sonnet 4.6 |
| DB | 미사용 (stateless) | 미사용 (stateless — NDA 대응) |
| 모듈 구성 | Agent 3 + 엔진 2(Shapely/NetworkX) + 파서 1(OpenCV/OCR/fitz) + reference_db 1 | Agent 3 + 엔진 2(Shapely/NetworkX) + 파서 1 + 레퍼런스 1 |
| API 수 | 1개 (POST /api/generate) | 6개 |
| 처리 방식 | Agent1 + Agent2 병렬(asyncio.gather) → calculate_usable_area 순차 → Agent3 순차 | Agent1+2a 병렬 → 2b 순차 → 3 순차 |

## 2. 입력 처리

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 지원 파일 형식 | PNG/JPG/PDF (도면) + MD/PDF (브랜드 매뉴얼) | PDF only (벡터+래스터) |
| 벡터 파일 파싱 방식 | PyMuPDF(fitz) get_drawings() → 좌표 추출 후 프론트 렌더링 (read_floor_vectors.py) | PDF: pymupdf get_drawings() → Shapely polygonize |
| 래스터 파일 처리 방식 | OpenCV contour + OCR 치수선 + Claude Vision 설비 감지 | OpenCV contour + Vision API polygon 감지 |
| 파서 확장 구조 | 3단계 (OpenCV → OCR → Vision) + Vision 실패 시 수동 마킹 fallback | 4중 방어 (polygonize → drawing별 → Vision → 수동) |
| 스케일 산출 방식 | OCR 치수선 자동 + Vision 치수 역산 (OCR 실패 시) | 치수선 텍스트 최대값 자동 + 수동 입력 |
| 단면도 처리 | 미처리 (평면도만) | 미처리 (평면도만) |

## 3. 공간 분석

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 좌표계 단위 | mm | mm |
| 바닥 polygon 추출 | OpenCV contour (1순위) + Vision fallback + 수동 마킹 | 자동 (polygonize 1순위) + Vision fallback + 수동 예정 |
| 배치 불가 영역 처리 | 설비 type별 alert_zone (sprinkler 2300 / pillar 800 / 기타 1000mm) + 브랜드 clearspace + 벽면 300mm | Dead Zone (SP 900mm/FH 1000mm/EP 600mm) + 입구 exclusion |
| Zone 분할 방식 | 보행 거리 기반 zone_label (entrance_zone <3000mm / mid_zone <7000mm / deep_zone 7000mm+) | 보행 거리 기반 zone_label (entrance/near/mid/deep) |
| 통로 그래프 | NetworkX 격자 (200mm 간격) — Agent2용, 동선 시뮬레이션은 1000mm 간격 별도 구성 | NetworkX 격자 (300mm 간격) |
| 비상 통로 모델링 | 경로 존재 확인 (입구 연결성 NetworkX 체크) | 경로 존재 확인 (정밀 폭 검증은 단순화) |
| 입구 모델링 | type='entrance' 좌표 + 방향 + 수동 마킹 지원 (비율 좌표 → mm 변환) | 점/선분/polyline + 폭 비례 exclusion (1200/800/500mm) |

## 4. 브랜드 데이터

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 브랜드 규정 입력 방식 | MD/PDF 파일 자동 추출 (PDF → Claude Document API, MD → 텍스트 블록) | PDF 자동 추출 |
| 추출 방법 | LLM only (Claude Sonnet 4.6) + Pydantic 검증 (field_validator로 범위 보정) | LLM only (Claude) + Pydantic 검증 |
| 오브젝트 DB 연동 | reference_db.py — 테마(brand_name)별 오브젝트 목록 조회 | 미사용 (placement_rules에서 직접 추출) |
| 쌍 규정(pair rules) 지원 | relationships 자연어 추출 — 배치 prompt 참고용 (강제 검증 미구현) | relationships 자연어 + min_clearspace_mm |
| 금지 소재 필터링 | prohibited_material 추출 (MVP — reference_db 필터 미연동) | prohibited_material 기반 필터 |

## 5. 배치 기획 (AI)

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| AI 역할 범위 | reference_point + direction + priority + placed_because (좌표 금지) | ref_point + direction + priority + 수량 (좌표 금지) |
| 좌표 계산 주체 | 코드 (Shapely box 중심 배치 + NetworkX 연결성 확인) | 코드 (Shapely/NetworkX) |
| 회전 제약 | direction 4종 (inward/wall_facing/entrance_facing/freestanding) — MVP 회전 미구현, 0도 고정 | wall_facing: wall_angle_deg 자동 / freestanding: 45도 단위 |
| 배치 수 제한 | LLM 자유 판단 (priority 정렬 후 순차 시도) | 벽 수용량 상한 + LLM 자유 판단 (60~70% 활용 가이드) |
| 재시도 메커니즘 | Nudge (입구 방향 반대로 800mm 1회 밀기) → 실패 시 skip | 코드 조정(±100mm 8방향) → 대안 ref → LLM 재호출 1회 |

## 6. 배치 엔진

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 충돌 감지 방식 | Shapely polygon.intersects() | Shapely polygon intersection + buffer(gap_mm) |
| 통로 폭 검증 | 경로 존재만 (1000mm 그리드 + 600mm 버퍼 적용) | 경로 존재만 (데모 단순화) |
| 통로 연결성 검증 | NetworkX shortest_path (배치마다 즉시 체크) | NetworkX shortest_path (배치마다 체크) |
| 벽면 정렬(snap) | 미구현 (direction 지정만, 실제 snap 없음) | wall_angle_deg 기반 자동 회전 (wall_facing만) |
| 관계 제약 검증 | placed_because 참고만 (pair 강제 미구현) | placement_rules 하네스 (preferred_wall, required_direction 강제) |
| 증분 검증 | 오브젝트 단위 즉시 (placed_polygons 누적) | 오브젝트 단위 즉시 (placed_polygons 누적) |
| 격자점 탐색 | Nudge 800mm 1방향 1회 | 8방향 ±100mm × 10스텝 + 대안 ref 순회 |

## 7. 실패 처리

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 실패 분류 방식 | invalid_reference_point / collision_with_objects / entrance_blocked / entrance_blocked_nudge_failed / entrance_blocked_no_offset | out_of_floor / dead_zone_collision / shapely_collision / corridor_blocked |
| fallback 전략 | Nudge(800mm 1회) → 실패 시 skip + 경고 출력 | 코드 조정 → 대안 ref → LLM 재호출 (3단계) |
| AI 재호출 | 미구현 | 구현 (최대 1회, 실패 사유 + 점유 현황 전달) |
| Graceful Degradation | 배치 가능한 것만 표시 (partial_success 반환) | violation warning 기록 + 배치 가능한 것만 표시 |

## 8. 검증

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 검증 항목 수 | 2개 (오브젝트 충돌, 입구 연결성) | 3개 (바닥 이탈, dead zone 충돌, 오브젝트 충돌) |
| 소방 규정 검증 | 설비 type별 alert_zone exclusion (sprinkler/fire_hydrant/electrical_panel) | 입구 exclusion 1200mm, 통로 경로 존재 확인 |
| 시공 규정 검증 | 벽면 이격 300mm + brand clearspace 병합 적용 | wall_clearance 300mm + object_gap 300mm |
| 결과 분류 | success / partial_success (placed_objects 수 기준) | blocking / warning |

## 9. 출력

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 3D 모델 포맷 | JSON → Three.js WebGL 렌더링 (GLB 미사용) | GLB (Three.js GLTFExporter) |
| 비정형 바닥 지원 | outline_vertices (OpenCV polygon → ShapeGeometry) | ShapeGeometry (2D polygon → 3D 바닥) |
| 텍스트 리포트 | 미구현 | 미구현 (Agent 5 MVP 예정) |

## 10. 사용자 개입

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 도면 편집 UI | Vision 실패 시 수동 마킹 캔버스 자동 전환 — 도면 위 클릭으로 type별(sprinkler/fire_hydrant/electrical_panel/entrance/pillar) 시설물 위치 지정 + 재실행 버튼 | 입구 polyline + 설비 클릭 마킹 + "다시 인식" 버튼 |
| 스케일 교정 | OCR 자동 + Vision 역산 (수동 mm/px 입력 없음) | 수동 mm/px 입력 (1점) |
| 배치 후 조정 | 미구현 (결과 JSON 조회 + 목록 클릭 시 3D 하이라이트만) | 방향키 이동 + 드래그 이동 + 핸들 크기조절 + 45도 회전 + SizePanel |

## 11. 성능

| 비교 기준 | Jo | Shin (우리) |
|----------|-------|------------|
| 배치 성공률 | 미측정 (MVP 단계) | ~80% (Vision polygon 오인 시 하락) |
| 드랍률 | 미측정 (MVP 단계) | ~20% |
| Verification 결과 | success / partial_success (배치 성공 여부로 판단) | blocking 0 (violation은 warning으로 처리) |
| E2E 소요 시간 | 미측정 (LLM 2회 — Agent1+3, Agent1·2 병렬로 대기 시간 단축) | ~30초 (LLM 2~3회 + Tavily 검색 포함) |

---

## 비교 분석

### Jo가 앞서는 점

| 항목 | 내용 | 우리에게 시사점 |
|------|------|---------------|
| Human-in-the-loop 수동 마킹 UI | Vision 탐지 실패 시 UI가 자동으로 수동 마킹 캔버스로 전환. 사용자가 도면 위를 클릭해 type별 시설물 좌표를 직접 지정 후 파이프라인 재가동 | 현재 우리 파이프라인에 Vision 실패 시 대안이 없음. 동일 흐름 도입 검토 |
| Agent1 + Agent2 병렬 실행 | asyncio.gather로 브랜드 추출과 Vision 분석을 동시 실행 → 전체 대기 시간 단축 | 우리 파이프라인에서도 독립적인 단계는 병렬화 가능 |
| PDF 브랜드 매뉴얼 처리 | Claude Document API로 PDF 브랜드 매뉴얼을 직접 전달. PDF 크기 초과 시 fitz로 자동 압축 후 재전송 | MD 외 PDF 형식 브랜드 매뉴얼 지원 시 참고 |
| PDF 벡터 경로 프론트 렌더링 | PyMuPDF로 도면 원본 벡터 선 데이터를 추출해 프론트에 전달 → 실제 도면 선 위에 배치 결과 오버레이 | 도면 원본과 배치 결과 동시 시각화로 사용자 신뢰도 향상 |

### 우리가 앞서는 점

| 항목 | 내용 | Jo에게 시사점 |
|------|------|---------------|
| 4중 방어 파서 구조 | polygonize → drawing별 → Vision → 수동으로 단계적 fallback | Jo의 3단계 파서에 polygonize 1순위 추가 검토 |
| Dead Zone 세분화 규정 | SP 900mm / FH 1000mm / EP 600mm — 시설물 종류별 법령 기준 적용 | Jo는 sprinkler 2300mm로 과대 산정, 설비별 세분화 필요 |
| 회전 제약 구현 | wall_angle_deg 자동 계산 + freestanding 45도 단위 | Jo는 현재 0도 고정(MVP) — direction 지정만으로는 배치가 비논리적 |
| AI 재호출 메커니즘 | 실패 사유 + 점유 현황을 포함해 LLM 최대 1회 재호출 | Jo는 Nudge 1회로 끝, 복잡한 공간에서 배치 실패율 높아질 수 있음 |
| 8방향 탐색 + 3단계 fallback | ±100mm 8방향 × 10스텝 + 대안 ref 순회 + LLM 재호출 | Jo의 Nudge는 1방향 1회 — 탐색 범위 대폭 좁음 |
| 배치 후 조정 UI | 방향키/드래그/크기조절/45도 회전 + SizePanel | Jo는 결과 JSON 조회 + 하이라이트만 — 사용자 수정 불가 |

### 통합 시 채택 검토 대상

| Jo에서 가져올 것 | 이유 |
|-------------------|------|
| Human-in-the-loop 수동 마킹 캔버스 흐름 | Vision 실패 시 완전 에러 대신 사용자 개입으로 파이프라인 유지 — UX 품질 보장 |
| asyncio.gather 병렬 실행 패턴 | Agent1·2가 독립적이면 병렬화로 E2E 시간 단축 가능 |
| PDF 브랜드 매뉴얼 Document API 처리 | MD 외 PDF 포맷 브랜드 매뉴얼을 받을 경우 즉시 대응 가능 |
| PDF 벡터 경로 추출 + 프론트 오버레이 | 실제 도면 선 위에 배치 결과를 겹쳐 보여주는 시각화 → 사용자 신뢰도 향상 |

| 우리 것 유지할 것 | 이유 |
|-----------------|------|
| 4중 방어 파서 구조 | polygonize 우선 처리로 정확도 높음, Jo의 3단계보다 안정적 |
| Dead Zone 세분화 (SP/FH/EP 별도 기준) | 법령 기준 준수 — Jo의 일괄 적용보다 현실적 |
| 회전 제약 구현 (wall_angle_deg) | 배치 방향성 없이는 결과물이 비논리적으로 보임 |
| 8방향 탐색 + LLM 재호출 3단계 fallback | 탐색 범위·복원력 모두 Jo 대비 월등 |
| 배치 후 조정 UI | 사용자가 결과를 수정할 수 없는 파이프라인은 데모 완성도 낮음 |

---

## Jo 고유 기술 / 기능

> 위 비교 카테고리에 포함되지 않는, Jo만의 독자적인 기술이나 접근 방식

| 기술/기능 | 설명 | 팀 통합 시 활용 가능성 |
|----------|------|---------------------|
| Human-in-the-loop 자동 전환 흐름 | Vision 탐지 확신 부족 시 `user_marking_required: true`를 반환 → 프론트엔드가 자동으로 수동 마킹 캔버스 UI로 전환. 마킹 완료 후 동일 API로 재호출하는 단일 흐름 설계 | 높음 — Vision 실패 시 완전 에러 대신 사용자 개입으로 파이프라인 유지하는 구조 자체를 통합에 도입 가능 |
| PDF 벡터 도면 선 추출 + 프론트 오버레이 | PyMuPDF(fitz) get_drawings()로 CAD 도면 원본 선 데이터를 mm 좌표로 추출 후 프론트에 `floor_vector_paths`로 전달 → Three.js에서 실제 도면 위에 배치 결과 오버레이 렌더링 | 높음 — 도면 원본이 시각화에 함께 표시되면 검토 신뢰도 대폭 향상 |
| asyncio.gather 병렬 파이프라인 오케스트레이션 | 브랜드 추출(Agent1)과 도면 분석(Agent2)을 asyncio.gather로 동시 실행하는 비동기 오케스트레이터 구조. 두 작업이 독립적임을 명시적으로 설계에 반영 | 중간 — 우리 파이프라인에서 독립 단계 식별 후 동일 패턴 적용 가능 |
| 브랜드 매뉴얼 PDF Document API 처리 | 브랜드 매뉴얼이 PDF일 경우 base64 인코딩 후 Claude Document API `document` 블록으로 직접 전달. 3MB 초과 시 fitz로 자동 압축 후 재전송하는 방어 로직 포함 | 중간 — MD 형식 외 PDF 브랜드 자료를 받는 경우 즉시 활용 가능 |

**자유 서술:**

Jo 파이프라인의 가장 두드러진 특징은 **"Vision이 실패해도 파이프라인이 멈추지 않는다"** 는 설계 철학이다.
일반적인 파이프라인은 AI 탐지가 실패하면 에러를 반환하고 종료하지만, Jo는 `user_marking_required` 신호를 통해 사용자를 파이프라인 안으로 끌어들여 부족한 AI 정보를 보완한 뒤 다시 실행하는 Human-in-the-loop 루프를 완성했다.

또한 Agent1과 Agent2를 병렬로 실행하는 `asyncio.gather` 구조는, 두 작업이 서로 독립적임을 명시적으로 코드에 반영한 것으로, Shin 파이프라인 대비 E2E 시간을 단축할 수 있는 구조적 이점이 있다.

반면 배치 엔진 측면에서는 Nudge가 1방향 1회에 그치고, 회전 구현이 MVP 수준(0도 고정)으로 남아 있어 복잡한 공간에서의 배치 성공률과 결과물 품질은 아직 개선 여지가 크다. 통합 시에는 **Jo의 입력 처리 견고성 + Shin의 배치 엔진 정밀도**를 조합하는 방향이 최선으로 보인다.
