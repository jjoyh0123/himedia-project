import json
import networkx as nx
from shapely.geometry import Polygon, Point, MultiPolygon
from ai.agent2.schema import FloorPlanData, UsableRange, Position

def calculate_usable_area(floor_data: dict, brand_data: dict) -> dict:
    """
    Agent 2 후반부 핵심:
    1. Shapely를 사용해 물리적 공간(Usable Area)과 데드존(Dead Zone) 계산
    2. NetworkX를 사용해 공간을 격자(Grid)로 분할하고 보행 경로와 거리를 계산
    3. 참조점(Reference Points)별로 자연어 라벨(Zone Label)을 부여하여 Agent 3에게 전달
    """
    
    # 도면 치수 및 격자 해상도 초기화
    dims = floor_data.get("dimensions_mm", {"width": 20000, "height": 15000})
    w = dims.get("width", 20000)
    h = dims.get("height", 15000)
    grid_size = 200  # mm 단위 격자 해상도 (Agent 2 spec 기준)

    # 1. 기본 전체 공간 및 벽면 이격(Clearspace) 처리 (Shapely)
    outline = floor_data.get("outline_vertices", [])
    if outline:
        base_polygon = Polygon([(p["x"], p["y"]) for p in outline])
    else:
        base_polygon = Polygon([(0, 0), (w, 0), (w, h), (0, h)])
        
    clearspace = brand_data.get("clearspace_mm", {}).get("value", 500)
    wall_clearance = 300 # 소방/시공 기본값
    total_margin = max(clearspace, wall_clearance)

    # [DEBUG] outline_vertices 첫 3개 좌표 확인
    outline_dbg = floor_data.get("outline_vertices", [])
    for i, pt in enumerate(outline_dbg[:3]):
        print(f"[DEBUG] outline_vertices[{i}]: x={pt.get('x')} mm, y={pt.get('y')} mm")
    print(f"[DEBUG] outline_vertices total points: {len(outline_dbg)}")

    # [DEBUG] floor polygon area
    print(f"[DEBUG] floor area: {base_polygon.area:.0f} mm²")

    usable_polygon = base_polygon.buffer(-total_margin)

    # 2. 시설물 데드존 파내기 (차집합)
    facilities = floor_data.get("facilities", [])
    dead_zones = []
    for fac in facilities:
        pos = fac.get("position", {})
        zone_mm = fac.get("alert_zone_mm", 0)
        # [DEBUG] 각 facility center와 radius
        print(f"[DEBUG] facility '{fac.get('id', '?')}' ({fac.get('type', '?')}): center=({pos.get('x')}, {pos.get('y')}) mm, radius={zone_mm} mm")
        if zone_mm > 0:
            circle = Point(pos["x"], pos["y"]).buffer(zone_mm)
            dead_zones.append(circle)
            usable_polygon = usable_polygon.difference(circle)

    # [DEBUG] dead_zone_union area
    if dead_zones:
        from shapely.ops import unary_union
        dead_zone_union = unary_union(dead_zones)
        print(f"[DEBUG] dead_zone area: {dead_zone_union.area:.0f} mm²")
    else:
        print(f"[DEBUG] dead_zone area: 0 mm² (시설물 없음)")

    # [DEBUG] 가용 면적 (floor - wall_margin - dead_zones)
    print(f"[DEBUG] usable area: {usable_polygon.area:.0f} mm²")

    # 3. NetworkX 격자 그래프 구축 및 보행 거리 계산
    G = nx.grid_2d_graph(int(w / grid_size) + 1, int(h / grid_size) + 1)
    
    # 장애물 지역 노드 제거 (데드존 + 벽면 이격 외부)
    nodes_to_remove = []
    for node in G.nodes():
        mx, my = node[0] * grid_size, node[1] * grid_size
        p = Point(mx, my)
        # 가용 영역 밖이거나 데드존 내부면 제거
        if not usable_polygon.contains(p):
            nodes_to_remove.append(node)
    
    G.remove_nodes_from(nodes_to_remove)

    # [DEBUG] NetworkX 유효 노드 수
    print(f"[DEBUG] graph nodes: {G.number_of_nodes()} (removed: {len(nodes_to_remove)})")

    # 4. 참조점(Reference Points) 및 보행 거리 계산
    # 입구 찾기
    entrances = floor_data.get("entrances", [])
    main_entrance = entrances[0] if entrances else None
    
    reference_points = {
        "entrance_zone": main_entrance["position"] if main_entrance else {"x": w / 2, "y": 0},
        "north_wall_mid": {"x": w / 2, "y": total_margin},
        "south_wall_mid": {"x": w / 2, "y": h - total_margin},
        "east_wall_mid": {"x": w - total_margin, "y": h / 2},
        "west_wall_mid": {"x": total_margin, "y": h / 2},
        "inner_corner": {"x": w - total_margin, "y": h - total_margin}
    }
    
    # 입구 노드 특정
    if main_entrance:
        start_node = (int(main_entrance["position"]["x"] / grid_size), int(main_entrance["position"]["y"] / grid_size))
    else:
        start_node = (int(w / 2 / grid_size), 0)
        
    # 시작 노드가 제거되었다면 가장 가까운 노드 찾기
    if start_node not in G:
        available_nodes = list(G.nodes())
        if available_nodes:
            start_node = min(available_nodes, key=lambda n: (n[0]-start_node[0])**2 + (n[1]-start_node[1])**2)

    walk_distances = {}
    for key, pt in reference_points.items():
        target_node = (int(pt["x"] / grid_size), int(pt["y"] / grid_size))
        if target_node not in G:
            available_nodes = list(G.nodes())
            if available_nodes:
                target_node = min(available_nodes, key=lambda n: (n[0]-target_node[0])**2 + (n[1]-target_node[1])**2)
        
        try:
            if start_node in G and target_node in G:
                dist_steps = nx.shortest_path_length(G, start_node, target_node)
                dist_mm = dist_steps * grid_size
            else:
                dist_mm = 999999 # 도달 불가
        except nx.NetworkXNoPath:
            dist_mm = 999999
            
        # 거리 기반 라벨링 (agent_spec.md 기준)
        if dist_mm < 3000: label = "entrance_zone"
        elif dist_mm < 7000: label = "mid_zone"
        else: label = "deep_zone"
        
        walk_distances[key] = {
            "x": int(pt["x"]),
            "y": int(pt["y"]),
            "walk_distance_mm": dist_mm,
            "zone_label": label
        }

    # 5. 최종 데이터 구조화 및 반환
    usable_ranges = []
    if usable_polygon.geom_type == 'Polygon':
        polygons = [usable_polygon]
    elif usable_polygon.geom_type == 'MultiPolygon':
        polygons = list(usable_polygon.geoms)
    else:
        polygons = []

    for idx, poly in enumerate(polygons):
        coords = list(poly.exterior.coords)
        positions = [Position(x=round(pt[0], 1), y=round(pt[1], 1)) for pt in coords]
        usable_ranges.append({
            "zone_id": f"zone-{idx+1}",
            "polygon_bounds": [p.dict() for p in positions],
            "allowed_properties": ["brand_placement"],
        })

    # Agent 3 전달용 자연어 데이터(참조점 요약) 추가
    floor_data["usable_ranges"] = usable_ranges
    floor_data["reference_points"] = walk_distances
    
    return floor_data
