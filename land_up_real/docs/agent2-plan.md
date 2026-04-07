# Agent 2: Floor Plan Vision Analyzer & Constraint Modeler (도면 환경 및 제약조건 통합 모듈)

## 📌 목표 (Goal)
Agent 2는 시각 모델(Vision/OCR)을 이용해 PDF 도면의 고정 설비와 출입구를 스캔하고, Agent 1에서 넘겨준 '브랜드 규칙(Brand Manual)'을 하나로 통합합니다.
최종적으로 조형물이 배치될 수 없는 불가침 영역들을 제외하고, 파이프라인의 종착지인 Agent 3(배치/수학 연산기)가 수학적 알고리즘을 돌리기 좋도록 **'안전하게 물건을 놔도 되는 가용 범위(Usable Range)'의 딕셔너리 구조 좌표 맵**을 생성합니다.

---

## 👁️ 핵심 기능 (Core Features)

### 1단계: 도면 시각화 인지 (Vision / OCR)
- `demo_floor_rendered.png`를 기반으로 Claude Vision 모델을 관측자로 활용하여 도면의 핵심 설비(소화전, 분전함, 스프링클러) 및 출입구(Entrance)의 방향과 예상 좌표를 파악합니다.
- **예외 처리 (Fallback)**: Vision AI가 도면 화질 저하나 복잡도 때문에 설비를 제대로 탐지하지 못하거나 신뢰도(Confidence)가 낮다고 판단할 경우, 절대 임의의 좌표를 할당하지 않고 파이프라인을 일시 중단한 뒤 **사용자에게 직접 마킹을 요청하는 플래그**를 띄웁니다.

### 2단계: 브랜드 규정 및 필수 설비 제약 공간화 
- **설비 제약 (소방법 등)**: 1단계에서 획득하거나 사용자가 직접 입력해준 소화기, 스프링클러 주변의 반경(예: 2300mm)을 "배치 불가 영역(Blocked Zone)"으로 딕셔너리에 추가합니다.
- **브랜드 제약 (Agent 1 데이터 결합)**: 
  - 캐릭터 조형물 여유 공간 (`clearspace_mm`), 로고 이격 거리 처리.
  - "캐릭터는 입구 정면을 봐야 함" 같은 방향성 규칙을 해당 좌표 구역의 메타데이터로 부여.

### 3단계: 가용 범위 도출 (Usable Range Dictionary)
- 도면의 전체 테두리 면적에서, 위 2단계의 제약 영역들을 뺀 **'실질적 가용 좌표 박스(Bounding Boxes)'**들을 도출해 냅니다.
- 이렇게 정제된 가용 범위 딕셔너리를 Agent 3(Shapely, NetworkX)로 넘겨, 3이 실제 조형물의 사이즈를 맞춰보고 통로(Network)를 짜는 집중 연산을 하도록 서포트합니다.

---

## 📦 최종 출력 스키마 (Expected Agent 2 Output)
```python
space_data["floor_plan"] = {
    # 1. OCR/Vision으로 딴 고정 객체 요소들 (실패시 사용자 마킹값으로 대체됨)
    "facilities": [
        {"id": "SP-1", "type": "sprinkler", "position": {"x": 1000, "y": 1000}, "alert_zone_mm": 2300, "confidence": "high"},
        {"id": "FH-1", "type": "fire_hydrant", "position": {"x": 5000, "y": 8000}, "alert_zone_mm": 1000, "confidence": "high"}
    ],
    "entrances": [
        {"position": {"x": 4000, "y": 9000}, "direction": "South", "confidence": "high"}
    ],
    "user_marking_required": False, # 만약 객체 파악 신뢰도가 낮으면 True로 변환되어 파이프라인 블록
    
    # 2. Agent 1 브랜드 룰 + 시설물이 제외된 실제 가용(설치 허용) 범위
    "usable_ranges": [
        {
            "zone_id": "zone-a",
            "polygon_bounds": [{"x":0, "y":0}, {"x": 4000, "y": 0}, {"x":4000, "y":2000}, {"x":0, "y":2000}],
            "allowed_properties": ["character_placement", "logo_placement"],
            "constraints_applied": ["sprinkler_avoided", "entrance_faced"]
        },
        ...
    ]
}
```

---

이 기획에 맞춰 코드를 구현하면, 모호성을 방지하고 Agent 3이 온전히 수학적 경로 연산 및 조립에만 집중할 수 있는 깔끔한 분업 체계가 완성됩니다.
