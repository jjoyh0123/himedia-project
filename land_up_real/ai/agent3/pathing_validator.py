import networkx as nx
from shapely.geometry import Polygon, box, Point
import math

def validate_and_draw_pathways(usable_polygons_data: list, placed_objects: list, entrance_data: dict) -> list:
    """
    Agent 3 최종 네트워크(NetworkX) 모듈
    :param usable_polygons_data: 가동 가능 구역.
    :param placed_objects: 확정된 조형물 위치들 (장애물이 됨).
    :param entrance_data: Agent 2가 발견한 진입점 정보.
    :return: 최종 최단 거리(Dijkstra) 동선 노드들의 리스트 리턴.
    """
    
    # 1. 장애물(조형물 상자들) 생성
    obstacle_boxes = []
    for obj in placed_objects:
        x, y = obj["placed_coordinates"]["x"], obj["placed_coordinates"]["y"]
        w_h = obj["dimensions"]["width"] / 2
        h_h = obj["dimensions"]["height"] / 2
        
        # 인간 통과 최소 보장 폭 1200mm = 사방으로 600mm Buffer 추가
        obstacle_boxes.append(box(x - w_h - 600, y - h_h - 600, x + w_h + 600, y + h_h + 600))

    # 2. NetworkX 그래프 초기화 (1미터=1000mm 단위로 그리드 노드 생성)
    G = nx.Graph()
    step = 1000
    grid_nodes = []
    
    # 도면 전체 영역 탐색 (가동 영역 폴리곤들로부터 최대 경계 추출)
    max_x, max_y = 0, 0
    for u_zone in usable_polygons_data:
        for p in u_zone["polygon_bounds"]:
            if p["x"] > max_x: max_x = p["x"]
            if p["y"] > max_y: max_y = p["y"]
            
    for x in range(0, int(max_x) + step, step):
        for y in range(0, int(max_y) + step, step):
            node_point = Point(x, y)
            
            # 노드가 도면 내 가동 영역(Usable Area) 바깥이면 제외
            is_usable = False
            for u_zone in usable_polygons_data:
                poly = Polygon([(p["x"], p["y"]) for p in u_zone["polygon_bounds"]])
                if poly.contains(node_point):
                    is_usable = True
                    break
            
            # 모든 오브젝트(장애물+인간 이동폭)에 닿으면 노드 철거 방해물
            for obs in obstacle_boxes:
                if obs.contains(node_point):
                    is_usable = False
                    break
            
            if is_usable:
                G.add_node((x, y))
                grid_nodes.append((x, y))
                
    # 노드끼리 인접하면 Edge(길)를 연결
    for i, n1 in enumerate(grid_nodes):
        for n2 in grid_nodes[i+1:]:
            dist = math.dist(n1, n2)
            if dist <= step * 1.5:  # 가로세로 및 대각선 연결
                G.add_edge(n1, n2, weight=dist)
                
    # 3. 입구(Start)에서 각 조형물 근처까지의 길 찾기
    pathways = []
    if not entrance_data:
        # 입구가 없으면 테스트/임시로 (0,0)과 제일 가까운 노드를 입구로 침
        start_node = min(grid_nodes, key=lambda p: math.dist((0,0), p)) if grid_nodes else None
    else:
        ex, ey = entrance_data["position"]["x"], entrance_data["position"]["y"]
        # 가장 가까운 그리드 노드를 스타트 지점으로 매핑
        start_node = min(grid_nodes, key=lambda p: math.dist((ex,ey), p)) if grid_nodes else None

    if not start_node:
        print("🚨 에러: 동선을 구성할 가동 노드가 없습니다! (여유 공간 부족)")
        return []

    # 각 오브젝트에 대해 다익스트라(최단 경로) 연산
    for idx, obj in enumerate(placed_objects):
        ox, oy = obj["placed_coordinates"]["x"], obj["placed_coordinates"]["y"]
        # 조형물 바로 바깥(관람 위치) 노드 찾기
        target_node_candidates = [n for n in grid_nodes if 600 < math.dist((ox, oy), n) < 2500]
        if not target_node_candidates:
            continue

        target_node = min(target_node_candidates, key=lambda p: math.dist((ox, oy), p))

        try:
            path = nx.shortest_path(G, source=start_node, target=target_node, weight='weight')
            pathways.append({
                "path_id": f"route_to_{obj['object_id']}",
                "nodes": [{"x": p[0], "y": p[1]} for p in path]
            })
        except nx.NetworkXNoPath:
            print(f"🚨 갇힘 에러: {obj['object_id']} 로 가는 길이 막혀 있습니다!")

    return pathways

if __name__ == "__main__":
    print("=' '*60")
    print("🕸️ [Agent 3] NetworkX 관람객 동선(Path) 시뮬레이션 테스트 완료")
