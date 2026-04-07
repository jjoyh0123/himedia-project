import networkx as nx
from shapely.geometry import Polygon, box, Point
from ai.agent3.schema import PlacedObject, Dimensions, PlacedCoordinate

def optimize_object_layout(space_data: dict, objects_to_place: list, agent3_directives: list) -> list:
    """
    Agent 3의 '의도(Directives)'를 수신하여 Shapely와 NetworkX로 물리적 배치를 확정합니다.
    (증분 검증: 하나씩 배치하며 통로 막힘을 실시간으로 체크)
    """
    floor_plan = space_data.get("floor_plan", {})
    usable_ranges = floor_plan.get("usable_ranges", [])
    ref_points = floor_plan.get("reference_points", {})
    
    # 1. 초기 맵 데이터 복원
    w = floor_plan.get("dimensions_mm", {}).get("width", 20000)
    h = floor_plan.get("dimensions_mm", {}).get("height", 15000)
    grid_size = 200
    
    # NetworkX 그래프 재생성 (G_base)
    G = nx.grid_2d_graph(int(w / grid_size) + 1, int(h / grid_size) + 1)
    
    # 기초 장애물 제거 (Usable Range 외부 노드 제거)
    usable_poly = None
    if usable_ranges:
        polys = [Polygon([(p["x"], p["y"]) for p in r["polygon_bounds"]]) for r in usable_ranges]
        from shapely.ops import unary_union
        usable_poly = unary_union(polys)

    nodes_to_remove = []
    for node in G.nodes():
        mx, my = node[0] * grid_size, node[1] * grid_size
        if usable_poly and not usable_poly.contains(Point(mx, my)):
            nodes_to_remove.append(node)
    G.remove_nodes_from(nodes_to_remove)
    
    # 입구 노드 특정
    entrance_pt = ref_points.get("entrance_zone", {"x": w / 2, "y": 0})
    entrance_node = (int(entrance_pt["x"] / grid_size), int(entrance_pt["y"] / grid_size))
    if entrance_node not in G:
        available_nodes = list(G.nodes())
        if available_nodes:
            entrance_node = min(available_nodes, key=lambda n: (n[0]-entrance_node[0])**2 + (n[1]-entrance_node[1])**2)

    placed_objects = []
    placed_polygons = []
    
    # 2. 우선순위 순으로 배치 시도
    directives = sorted(agent3_directives, key=lambda x: getattr(x, 'priority', 10))
    
    for directive in directives:
        # DB에서 오브젝트 스펙 찾기
        obj_spec = next((o for o in objects_to_place if o["object_id"] == directive.object_type), None)
        if not obj_spec:
            continue
            
        # 배치 시도
        result = _attempt_placement(obj_spec, directive, placed_polygons, G, entrance_node, ref_points, grid_size)
        
        if result["success"]:
            placed_objects.append(result["placed_obj"])
            placed_polygons.append(result["polygon"])
            # 그래프 업데이트 (오브젝트가 점유한 공간의 노드 제거)
            nodes_in_obj = _get_nodes_in_polygon(result["polygon"], grid_size)
            G.remove_nodes_from([n for n in nodes_in_obj if n in G])
        else:
            print(f"⚠️ 배치 실패: {directive.object_type} at {directive.reference_point} ({result['reason']})")
            
    return placed_objects

def _attempt_placement(obj_spec, directive, placed_polygons, G, entrance_node, ref_points, grid_size):
    ref = ref_points.get(directive.reference_point)
    if not ref:
        return {"success": False, "reason": "invalid_reference_point"}

    w = obj_spec["dimensions_mm"]["width"]
    d = obj_spec["dimensions_mm"]["height"]

    # 기본 위치: 참조점 중심
    cx, cy = ref["x"], ref["y"]

    # 방향에 따른 미세 조정 (MVP: 일단 단순 중앙 배치 후 충돌 체크)
    # TODO: inward, wall_facing 등에 따른 오프셋 계산 고도화

    obj_poly = box(cx - w/2, cy - d/2, cx + w/2, cy + d/2)

    # 1. Shapely 충돌 체크 (기존 배치와 겹치는지)
    for p in placed_polygons:
        if obj_poly.intersects(p):
            return {"success": False, "reason": "collision_with_objects"}

    # 2. NetworkX 통로 체크 (이걸 놓으면 입구가 막히는가?)
    G_temp = G.copy()
    nodes_in_obj = _get_nodes_in_polygon(obj_poly, grid_size)
    G_temp.remove_nodes_from([n for n in nodes_in_obj if n in G_temp])

    # 입구 노드가 사라졌다면 (입구 바로 위에 배치됨)
    if entrance_node not in G_temp:
        # 꼼꼼한 확인: 입구에서 멀어지는 방향으로 800mm만 밀어보자 (Nudge)
        ex, ey = entrance_node[0] * grid_size, entrance_node[1] * grid_size
        dx, dy = cx - ex, cy - ey
        dist = (dx**2 + dy**2)**0.5
        if dist > 0:
            cx += (dx/dist) * 800
            cy += (dy/dist) * 800
            # 다시 폴리곤 생성 및 체크
            obj_poly = box(cx - w/2, cy - d/2, cx + w/2, cy + d/2)
            G_temp = G.copy()
            nodes_in_obj = _get_nodes_in_polygon(obj_poly, grid_size)
            G_temp.remove_nodes_from([n for n in nodes_in_obj if n in G_temp])

            if entrance_node not in G_temp:
                return {"success": False, "reason": "entrance_blocked_nudge_failed"}
        else:
            return {"success": False, "reason": "entrance_blocked_no_offset"}

    placed_obj = PlacedObject(
        object_id=obj_spec["object_id"],
        dimensions=Dimensions(width=w, height=d),
        placed_coordinates=PlacedCoordinate(x=cx, y=cy),
        facing=directive.direction
    )
    
    return {"success": True, "placed_obj": placed_obj, "polygon": obj_poly}

def _get_nodes_in_polygon(poly, grid_size):
    minx, miny, maxx, maxy = poly.bounds
    nodes = []
    for ix in range(int(minx/grid_size), int(maxx/grid_size) + 1):
        for iy in range(int(miny/grid_size), int(maxy/grid_size) + 1):
            if poly.contains(Point(ix*grid_size, iy*grid_size)):
                nodes.append((ix, iy))
    return nodes
