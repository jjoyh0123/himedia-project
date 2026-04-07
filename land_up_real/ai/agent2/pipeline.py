"""
ai/agent2/pipeline.py

Agent 2 Vision 전담 파이프라인.
설계 문서 3단계 순서를 그대로 따릅니다:
  Step 1: OpenCV  → 바닥 polygon 추출 (픽셀)
  Step 2: OCR     → 치수선 읽어서 mm 스케일 계산
  Step 3: Vision  → 설비(스프링클러·소화전·분전반·입구) 위치 감지

Agent 1(브랜드 추출)과 파일 읽기는 오케스트레이터(backend/services/pipeline.py)에서 처리합니다.
"""

import json
from ai.agent2.detect_floor_outline import build_auto_detected, polygon_px_to_mm
from ai.agent2.detect_facilities import detect_facilities_from_vision


async def run_agent2_vision(image_path: str, user_markings_json: str = None) -> dict:
    """
    도면 이미지 경로와 선택적 수동 마킹 좌표를 받아 floor_dict를 반환합니다.

    수동 마킹이 있으면 OpenCV/OCR/Vision을 건너뛰고 마킹 좌표를 그대로 변환합니다.
    수동 마킹이 없으면 OpenCV → OCR → Vision 순서로 자동 탐지합니다.
    """

    print("\n" + "="*60)
    print("🚀 [Step 2] Agent 2 활성화: Vision/OCR 기반 도면 시설물 탐색")
    print("="*60)

    if user_markings_json:
        print("📍 [Agent 2] 사용자가 제공한 수동 마킹 좌표를 사용합니다. (AI 분석 스킵)")
        try:
            raw_markings = json.loads(user_markings_json)
            # 수동 마킹 시에도 기본 도면 크기를 20,000 x 15,000으로 설정 (자동 인식 불가 시 대비)
            dw, dh = 20000, 15000

            facilities = []
            entrances = []

            for idx, m in enumerate(raw_markings):
                if m['type'] == 'sprinkler':
                    alert_zone = 2300
                elif m['type'] == 'pillar':
                    alert_zone = 800
                else:
                    alert_zone = 1000

                pos = {"x": m['x'] * dw, "y": m['y'] * dh}

                if m['type'] == 'entrance':
                    entrances.append({"position": pos, "direction": "South", "confidence": "manual"})
                else:
                    facilities.append({
                        "id": f"MANUAL-{idx}",
                        "type": m['type'],
                        "position": pos,
                        "alert_zone_mm": alert_zone,
                        "confidence": "manual"
                    })

            floor_dict = {
                "dimensions_mm": {"width": dw, "height": dh},
                "facilities": facilities,
                "entrances": entrances,
                "user_marking_required": False
            }
        except Exception as e:
            print(f"❌ [Agent 2] 수동 마킹 데이터 파싱 실패: {e}")
            # 파싱 실패 시 자동 탐지로 폴백
            floor_dict = await _run_auto_detect(image_path)
    else:
        floor_dict = await _run_auto_detect(image_path)

    # 예외 상황 분기 (Human-in-the-loop)
    if floor_dict.get("user_marking_required"):
        print("\n🚨 [경고] Vision 모델이 픽셀 오차 및 정확도 문제로 탐지에 확신을 갖지 못했습니다.")
        print("🚨 파이프라인 자동 진행을 중단하고 UI 쪽으로 '사용자 직접 마킹 인터페이스'를 호출합니다.")

    return floor_dict


async def _run_auto_detect(image_path: str) -> dict:
    """
    Step 1 OpenCV → Step 2 OCR → Step 3 Vision 자동 탐지를 실행합니다.
    auto_detected(polygon + scale)를 Vision에 전달해 mm 변환에 활용합니다.
    """
    # ── Step 1 + 2: OpenCV polygon 추출 & OCR 스케일 계산 ────────────────────
    print("\n" + "="*60)
    print("🚀 [Step 2-1] OpenCV 바닥 polygon + OCR 스케일 계산")
    print("="*60)
    auto_detected = build_auto_detected(image_path)

    scale_conf = auto_detected.get("scale_confidence", "low")
    print(f"📐 [Agent 2] OCR 스케일 신뢰도: {scale_conf}")
    if not auto_detected.get("polygon_success"):
        print("⚠️ [Agent 2] OpenCV polygon 추출 실패 — 도면 외곽선 없이 진행합니다.")

    # ── Step 3: Claude Vision 설비 감지 ──────────────────────────────────────
    print("\n" + "="*60)
    print("🚀 [Step 2-2] Claude Vision 설비(시설물·입구) 위치 감지")
    print("="*60)
    vision_result = await detect_facilities_from_vision(image_path, auto_detected)

    if vision_result.get("user_marking_required"):
        return vision_result

    # ── OpenCV polygon → mm 변환 후 outline_vertices에 주입 ──────────────────
    scale = auto_detected.get("scale_mm_per_px")
    polygon_px = auto_detected.get("floor_polygon_px", [])

    dims = vision_result.get("dimensions_mm")
    if scale and polygon_px and dims:
        outline_mm = polygon_px_to_mm(polygon_px, dims["width"], dims["height"])
        vision_result["outline_vertices"] = outline_mm
        print(f"✅ [Agent 2] outline_vertices {len(outline_mm)}개 꼭짓점 mm 변환 완료")
    elif polygon_px and vision_result.get("dimensions_mm"):
        # OCR 스케일 없음 → Vision dimensions_mm + polygon 바운딩박스로 스케일 역산
        dw = vision_result["dimensions_mm"]["width"]
        dh = vision_result["dimensions_mm"]["height"]
        xs = [pt[0] for pt in polygon_px]
        ys = [pt[1] for pt in polygon_px]
        poly_w = max(xs) - min(xs)
        poly_h = max(ys) - min(ys)
        if poly_w > 0 and poly_h > 0:
            scale_x = dw / poly_w
            scale_y = dh / poly_h
            min_x = min(xs)
            min_y = min(ys)
            outline_mm = [
                {"x": round((pt[0] - min_x) * scale_x, 2),
                 "y": round((pt[1] - min_y) * scale_y, 2)}
                for pt in polygon_px
            ]
            vision_result["outline_vertices"] = outline_mm
            print(f"✅ [Agent 2] Vision 치수 역산으로 outline_vertices {len(outline_mm)}개 꼭짓점 변환 완료 (scale_x={scale_x:.2f}, scale_y={scale_y:.2f} mm/px)")
        else:
            print("⚠️ [Agent 2] polygon 바운딩박스 계산 실패 → outline_vertices 빈 상태로 진행합니다.")
    else:
        print("⚠️ [Agent 2] 스케일 미확보 → outline_vertices 빈 상태로 진행합니다.")

    return vision_result


if __name__ == "__main__":
    import os
    import asyncio

    agent_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(agent_dir))
    img_path = os.path.join(project_root, "image", "demo_floor_rendered.png")

    print("🌐 Agent 2 (OpenCV+OCR+Vision) 단독 테스트 가동...")
    result = asyncio.run(run_agent2_vision(img_path))

    if result:
        print(f"\n✅ 시설물 탐지 완료: {len(result.get('facilities', []))}개")
        print(f"   출입구: {len(result.get('entrances', []))}개")
        print(f"   도면 크기: {result.get('dimensions_mm')}")
        print(f"   outline 꼭짓점: {len(result.get('outline_vertices', []))}개")
