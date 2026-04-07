import os
import json
import anthropic
from ai.agent3.schema import FinalLayoutData, Agent3Output
from ai.agent3.reference_db import get_pop_up_reference_objects
from ai.agent3.layout_optimizer import optimize_object_layout
from ai.agent3.pathing_validator import validate_and_draw_pathways

async def run_agent3_pipeline(space_data: dict, theme: str = None) -> dict:
    """
    Agent 3: 자연어 공간 요약을 기반으로 배치를 결정하고, 수치 기반 최적화 모듈을 제어합니다.
    """
    floor_plan = space_data.get("floor_plan", {})
    brand_rules = space_data.get("brand", {})
    ref_points = floor_plan.get("reference_points", {})
    
    # 1. 자연어 공간 요약 및 입구 위치 특정
    space_summary = ""
    entrance_wall = "unknown"
    min_dist = 999999
    
    _entrances = floor_plan.get("entrances", [])
    main_entrance = _entrances[0] if _entrances else None
    if main_entrance:
        ex, ey = main_entrance["position"]["x"], main_entrance["position"]["y"]
        # 어느 벽면 참조점이 입구와 제일 가까운가?
        for wall in ["north_wall_mid", "south_wall_mid", "east_wall_mid", "west_wall_mid"]:
            w_pt = ref_points.get(wall)
            if w_pt:
                d = ((w_pt["x"] - ex)**2 + (w_pt["y"] - ey)**2)**0.5
                if d < min_dist:
                    min_dist = d
                    entrance_wall = wall.split("_")[0] # 'north', 'south' 등

    for key, data in ref_points.items():
        note = " (입구 근처)" if key == "entrance_zone" or key.startswith(entrance_wall) else ""
        space_summary += f"- {key}: {data['zone_label']} (보행거리: {data['walk_distance_mm']}mm){note}\n"
    
    if entrance_wall != "unknown":
        space_summary += f"\n[중요] 입구가 {entrance_wall.upper()} 벽면 근처에 위치해 있습니다. 입구 정면은 비워두거나 작은 것만 배치하세요.\n"
    
    # 2. 브랜드 테마 결정 및 레퍼런스 조형물 불러오기
    if not theme:
        theme = brand_rules.get("brand_name", {}).get("value", "generic")
    
    objects_db = get_pop_up_reference_objects(theme)
    objects_summary = "\n".join([f"- {obj['object_id']} (유형: {obj['object_type']}, 중요도: {obj['importance']})" for obj in objects_db])

    brand_summary = f"Brand: {theme}\nRule: {brand_rules.get('relationships', [])}\nClearspace: {brand_rules.get('clearspace_mm', {}).get('value')}mm"
    
    # 3. LLM(Claude) 호출하여 배치 의도(Directives) 추출
    # API 키 로드
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(agent_dir))
    env_path = os.path.join(project_root, ".env")
    api_key = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY"):
                    api_key = line.split("=", 1)[1].strip()
                    break
    
    client = anthropic.AsyncAnthropic(api_key=api_key)
    
    prompt = f"""
너는 팝업스토어 설계 전문가 Agent 3야. 
Agent 2가 분석한 공간 정보와 Agent 1의 브랜드 룰을 바탕으로 어떤 가구를 어디에 놓을지 '의도(Directives)'를 결정해줘.

[공간 요약 (자연어)]
{space_summary}

[브랜드 룰]
{brand_summary}

[배치 가능한 가구 목록]
{objects_summary}

[출력 규칙]
1. 반드시 JSON 형식으로만 대답해.
2. 절대 좌표(x, y)나 mm 수치를 출력하지 마. 대신 'reference_point' 키워드를 사용해.
3. 'direction'은 [inward, wall_facing, entrance_facing, freestanding] 중 하나만 사용해.
4. 모든 조형물이 다 들어가지 못할 수도 있어. 우선순위(priority)를 잘 정해줘.

JSON 예시:
{{
    "placements": [
        {{"object_type": "hello_kitty_main_statue", "reference_point": "entrance_zone", "direction": "inward", "priority": 1, "placed_because": "입구에서 바로 보이게 배치"}},
        {{"object_type": "photo_zone_backdrop", "reference_point": "north_wall_mid", "direction": "wall_facing", "priority": 2, "placed_because": "벽면을 활용한 포토존 구성"}}
    ]
}}
"""

    try:
        print("🧠 [Agent 3] 자연어 공간 분석 및 배치 의도 결정 중 (Sonnet 4.6)...")
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # JSON 블록 추출 (마크다운 기호 제거)
        res_text = response.content[0].text.strip()
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        elif "```" in res_text:
            res_text = res_text.split("```")[1].split("```")[0].strip()
            
        directives_raw = json.loads(res_text)
        agent3_output = Agent3Output(**directives_raw)
    except Exception as e:
        print(f"❌ [Agent 3] LLM 판단 및 배치 의도 결정 실패: {e}")
        # 하드코딩된 폴백 대신 에러를 명시적으로 던져서 사용자가 문제를 확인하도록 함
        raise e

    # 3. 수치 기반 레이아웃 최적화 실행 (Shapely + NetworkX)
    objects_db = get_pop_up_reference_objects(theme)
    placed_objects = optimize_object_layout(space_data, objects_db, agent3_output.placements)
    
    # 4. 동선 시뮬레이션
    # pathing_validator는 딕셔너리 접근을 선호하므로 변환해서 전달
    placed_objects_dict = [obj.model_dump() for obj in placed_objects]
    _entrances2 = floor_plan.get("entrances", [])
    main_entrance = _entrances2[0] if _entrances2 else None
    visitor_pathways = validate_and_draw_pathways(floor_plan.get("usable_ranges", []), placed_objects_dict, main_entrance)

    # 5. 최종 결과 패키징
    final_output = FinalLayoutData(
        placed_objects=placed_objects,
        visitor_pathways=visitor_pathways,
        status="success" if len(placed_objects) > 0 else "partial_success",
        brand_rules=brand_rules,
        entrances=floor_plan.get("entrances", [])
    )
    
    return final_output.model_dump()
