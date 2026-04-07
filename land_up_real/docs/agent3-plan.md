# Agent 3: Intent Decision & Placement Executor (최종 공간 배치기)

## 📌 목표 (Goal)
Agent 3는 랜딩업(Landing Up) AI 파이프라인의 최종 심장부입니다.
Agent 1의 '브랜드 제약 규칙(Brand 룰)'과 Agent 2가 깎아준 '침범 불가/가용 좌표 맵(Floor Usable Range)'을 기반으로, 실제 팝업 장식물(오브젝트)들을 **Shapely와 NetworkX를 사용해 충돌 없이 최적으로 배치(Placement)**하고 그 결과(도면 레이아웃)를 산출합니다.

---

## 👁️ 핵심 기능 (Core Features)

### 1단계: 레퍼런스 스키마 자동 구축 (Reference DB Synthesis)
- **과제**: 현재 프로젝트에 "헬로키티 포토존의 평균 크기" 같은 레퍼런스 DB가 부재한 상태입니다.
- **해결책**: Agent 3 구동 시, 내부적으로 **LLM(Claude) 또는 웹 검색을 활용하여 해당 브랜드(헬로키티 등) 팝업스토어 관례에 맞는 가상의 오브젝트 레퍼런스 DB를 자체 생성**합니다.
  - *예시 파생 데이터:* 
    - `hello_kitty_statue_main`: 크기 1000x1200mm, 관람객 정체도 높음 
    - `my_melody_photo_zone`: 크기 1500x1500mm
    - `merch_sales_stand`: 크기 2500x800mm (동선 최우선 확보 필요)

### 2단계: 위상 기하학 기반 무충돌 배치 연산 (Shapely)
- 1단계에서 얻어낸 조형물들의 실제 규격(Box)을 Agent 2가 제공한 `usable_ranges` 폴리곤 박스 안에 집어넣습니다.
- `Shapely`의 교집합 및 충돌(Intersection) 감지 알고리즘을 반복 수행하여, 조형물 간의 겹침을 방지하고 Agent 1의 룰(예: 헬로키티 조형물 주변 1500mm 내 여백 확보)을 충족시키는 좌표(가로/세로 배치점) 후보군을 탐색합니다.

### 3단계: 관람객 이동 동선 흐름 검증 (NetworkX)
- 입구(Entrance)에서 시작해 메인 존(헬로키티) -> 사이드 존(마이멜로디) -> 굿즈샵(퇴장)으로 이어지는 노드(Node)를 설정합니다.
- 배치된 조형물들 사이의 여백 공간을 바탕으로 `NetworkX`를 돌려, 인간 관람객이 지나다닐 수 있는 너비(최소 1200mm 확보)의 최단 경로 그래프가 막힘없이 이어지는지 검증합니다.
- 동선이 끊기거나 데드스페이스가 발생하면 2단계로 돌아가 배치를 수정(Re-routing)합니다.

---

## 📦 최종 출력 스키마 (Expected Agent 3 Output)
```python
final_layout_data = {
    # 도출된 최종 배치 조형물 리스트
    "placed_objects": [
        {
            "object_id": "hello_kitty_statue_main",
            "dimensions": {"width": 1000.0, "height": 1200.0},
            "placed_coordinates": {"x": 3000.0, "y": 4500.0}, # 중심 좌표 (mm)
            "rotation_degree": 90,
            "facing": "South" # 입구를 바라보도록 설정됨
        },
        ...
    ],
    # NetworkX 기반 관람객 동선 좌표 흐름
    "visitor_pathways": [
        {"path_id": "route-1", "nodes": [{"x": 4000, "y": 9000}, {"x": 3000, "y": 5000}]}
    ],
    "status": "success",
    "collision_warning": None
}
```

---

이 설계 파이프라인이 완성되면, **할루시네이션(임의 좌표 찍기) 에러가 절대 없는 프로페셔널한 AI 인테리어 설계 도면 데이터베이스**가 추출됩니다.
