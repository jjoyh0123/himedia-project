"""
backend/services/pipeline.py

비동기 파이프라인 오케스트레이터.
Agent 1(브랜드 추출)과 Agent 2(Vision 탐지)를 asyncio.gather로 병렬 실행한 뒤,
수학 연산(calculate_usable_area) → Agent 3 순으로 파이프라인을 완성합니다.

Agent 1은 manual_path를 직접 받아 내부에서 파일을 읽으므로,
오케스트레이터에서 별도 파일 읽기 없이 경로만 전달합니다.
"""

import asyncio

from ai.agent1.extract_brand import extract_brand_guidelines
from ai.agent2.pipeline import run_agent2_vision
from ai.agent2.calculate_usable_ranges import calculate_usable_area
from ai.agent3.pipeline import run_agent3_pipeline
from ai.agent1.read_floor_vectors import extract_floor_vector_paths


async def execute_realtime_pipeline(manual_path: str, image_path: str, user_markings_json: str = None) -> dict:
    """
    전체 AI 배치 파이프라인을 비동기로 실행합니다.

    흐름:
      ① asyncio.gather — Agent 1(브랜드 추출, manual_path 직접 전달)
                       + Agent 2(OpenCV→OCR→Vision 탐지) 병렬 실행
      ② calculate_usable_area — 기하학 수학 연산 (동기)
      ③ run_agent3_pipeline — 배치 최적화 + 동선 시뮬레이션 (비동기)
    """

    print("="*60)
    print("🚀 [오케스트레이터] Agent 1 + Agent 2 병렬 실행 시작")
    print("="*60)

    # ① Agent 1(브랜드 추출)과 Agent 2(Vision 탐지) 동시 실행
    #    extract_brand_guidelines는 manual_path를 직접 받아 내부에서 파일을 읽음
    #    (PDF → Document API, 비PDF → 텍스트 읽기)
    brand_dict, floor_dict = await asyncio.gather(
        extract_brand_guidelines(manual_path),
        run_agent2_vision(image_path, user_markings_json)
    )

    # Human-in-the-loop: Vision 탐지 확신 부족 시 즉시 반환
    if floor_dict.get("user_marking_required"):
        return {"status": "manual_marking_required", "brand": brand_dict}

    if not brand_dict:
        raise RuntimeError("Agent 1 브랜드 추출 실패 (파이프라인 중단)")

    print(f"✅ [Agent 1] 브랜드 룰 추출 성공!")
    print(f"   - 최소 이격 거리: {brand_dict.get('clearspace_mm', {}).get('value')} mm")
    print(f"   - 캐릭터 방향: {brand_dict.get('character_orientation', {}).get('value')}")
    print(f"   - 관계 제약: {len(brand_dict.get('relationships', []))}개 발견")

    # ② 기하학(Shapely) 규칙 교집합 연산 — 수학 연산이므로 동기 실행
    print("\n" + "="*60)
    print("🚀 [Step 3] Agent 2 활성화: 기하학(Shapely) 규칙 교집합 연산 (가용 범위 추출)")
    print("="*60)
    final_floor_data = calculate_usable_area(floor_dict, brand_dict)

    space_data = {
        "brand": brand_dict,
        "floor_plan": final_floor_data
    }

    # ③ Agent 3: 배치 최적화 + 동선 시뮬레이션
    final_layout = await run_agent3_pipeline(space_data)

    # 프론트엔드 시각적 증명을 위해 Agent 2의 설비(데드존) 및 가용 범위 데이터 병합
    final_layout["facilities"] = space_data.get("floor_plan", {}).get("facilities", [])
    final_layout["usable_ranges"] = space_data.get("floor_plan", {}).get("usable_ranges", [])
    final_layout["entrances"] = space_data.get("floor_plan", {}).get("entrances", [])
    final_layout["dimensions_mm"] = space_data.get("floor_plan", {}).get("dimensions_mm", {"width": 20000, "height": 15000})
    final_layout["outline_vertices"] = space_data.get("floor_plan", {}).get("outline_vertices", [])

    # PDF 원본 벡터 데이터 (도면 스케치 라인) 프론트 렌더링을 위한 주입
    if image_path.lower().endswith(".pdf"):
        dw = space_data.get("floor_plan", {}).get("dimensions_mm", {}).get("width", 20000)
        dh = space_data.get("floor_plan", {}).get("dimensions_mm", {}).get("height", 15000)
        vectors = extract_floor_vector_paths(image_path, target_width=dw, target_height=dh)
        final_layout["floor_vector_paths"] = vectors
    else:
        final_layout["floor_vector_paths"] = []

    return final_layout
