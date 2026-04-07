# 도면 вектор 시각화 해결 계획 및 작업 명세 (Implementation Plan)

## 📌 문제 요약
현재 사용자가 PDF 도면 파일을 업로드해도 3D 시각화 화면(`FloorPlanVisualizer.tsx`)에는 수학적으로 렌더링된 가상 박스(12m x 9m)와 파란색 `usable_ranges` 구역만 보이고, 도면의 정확한 공간 형태(벽면, 문, 스케치)가 보이지 않습니다. 이를 해결하기 위해 백엔드에 단절된 모듈을 연결하고 프론트엔드 타입을 확장하는 과정을 거쳐야 합니다.

## ✔️ 작업 목표
Agent 1에 존재하는 `read_floor_vectors.py` 로직을 메인 서버(`server.py`) 흐름에 태우고, 추출된 도면 벡터 데이터(선/라인 폴리곤)를 JSON으로 묶어 프론트엔드로 전달 후 `React Three Fiber`로 시각화합니다.

---

## 🛠️ 세부 개발 계획 (단계별)

### [Phase 1] 백엔드 - 벡터 추출 로직 함수화 (Agent 1)
- **대상 파일**: `ai/agent1/read_floor_vectors.py` 
- **수정 계획**:
  - 기존에 `print`로 분석만 하던 모듈을 실 기능인 `extract_vector_paths(pdf_path: str)` 함수로 리팩토링합니다.
  - PDF의 `drawings(벡터 도형)` 객체들을 추출하여 선 두께(Stroke)와 함께 `[ [x1, y1], [x2, y2], ... ]` 형태의 경로 배열로 리턴합니다. (도면 요소이므로 x,y 위치와 폭, 높이 좌표 변형 포함)

### [Phase 2] 메인 API 파이프라인 연동 (Server)
- **대상 파일**: `api/server.py`
- **수정 계획**:
  - `generate_layout` API 핸들러에서 사용자가 올린 `floor_plan`이 `.pdf` 확장자인지 파악합니다.
  - PDF라면 **Phase 1**에서 만든 `extract_vector_paths(image_path)` 모듈을 호출해 좌표 배열(`floor_vectors`) 데이터를 얻습니다.
  - 최종 반환되는 JSON인 `final_layout` 객체 안에 `original_floor_vectors` 프로퍼티로 해당 선형(Line) 배열 데이터를 끼워 넣습니다.
  - (이미지일 경우 빈 배열을 리턴하여 프론트 통신에서 에러가 없게 합니다.)

### [Phase 3] 프론트엔드 타입 정의 연동 (Types)
- **대상 파일**: `frontend/src/types.ts`
- **수정 계획**:
  - `FinalLayoutData` 인터페이스에 도면 배관선/벽체 정보를 담을 `original_floor_vectors?: number[][][];` 항목을 추가합니다.

### [Phase 4] 프론트엔드 - 3D 렌더링 (Visualizer)
- **대상 파일**: `frontend/src/components/FloorPlanVisualizer.tsx`
- **수정 계획**:
  - `layoutData.original_floor_vectors` 배열이 존재할 경우, 이를 반복문(map)으로 돕니다.
  - Drei의 `<Line>` 컴포넌트나 기초 `shapeGeometry` 등을 활용해, 기존 12m x 9m 바닥면 살짝 위(`y = 0.05` 등)에 **건축 도면 원본 라인**을 그려줍니다.
  - 이 라인 색상은 설계도 느낌이 나도록 어두운 펜 선 색상(예: `#1E293B`)으로 적용합니다.

---

## ❓ 논의 필요 (Open Questions)
- PDF가 아닌 일반 이미지 파일(PNG)이 업로드 되었을 경우, 선을 딸 수 없습니다. 이 때는 기존처럼 12x9 바닥만 나오게 둘까요, 아니면 컴퓨터 비전(OpenCV 계열)을 돌려 추가로 추출하는 옵션을 넣을까요? (일단 1차 배포는 PDF 업로드시에만 벡터 선을 그려주는 것으로 진행하는 것이 효율적일 수 있습니다.)

현재까지의 해결 계획을 보고 확인 및 승인을 부탁드립니다. 승인해주시면 즉시 개발(Execution)에 착수하겠습니다!
