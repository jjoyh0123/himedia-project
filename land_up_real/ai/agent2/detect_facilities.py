import os
import json
import base64
import io
import anthropic
from PIL import Image
from ai.agent2.schema import FloorPlanData

def encode_image_base64(image_path: str) -> tuple:
    """Returns (base64_str, actual_width, actual_height) after any resizing."""
    try:
        if image_path.lower().endswith(".pdf"):
            print(f"📄 [Agent 2] PDF 도면 감지. 이미지로 변환하여 분석합니다.")
            import fitz
            with fitz.open(image_path) as doc:
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
        else:
            with Image.open(image_path) as opened_img:
                img = opened_img.copy()

        with img:
            max_size = 3500
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"🖼️ [Agent 2] 이미지가 너무 커서 {new_size}로 리사이징했습니다.")

            actual_w, actual_h = img.size

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            return base64.b64encode(buffer.getvalue()).decode("utf-8"), actual_w, actual_h
    except Exception as e:
        print(f"⚠️ [Agent 2] 이미지 전처리 실패: {e}")
        return "", 0, 0

async def detect_facilities_from_vision(image_path: str, auto_detected: dict) -> dict:
    """
    Claude Vision으로 도면에서 설비(스프링클러·소화전·분전반)와 입구만 감지합니다.
    도면 치수(dimensions_mm)와 외곽선(outline_vertices)은 auto_detected(OpenCV/OCR 결과)에서 가져옵니다.

    auto_detected 필수 키:
        img_width        (int)   이미지 전체 너비 px
        img_height       (int)   이미지 전체 높이 px
        floor_polygon_px (list)  OpenCV로 추출한 도면 polygon 픽셀 좌표 [[x,y], ...]
        scale_mm_per_px  (float) OCR로 계산된 mm/px 스케일 (None이면 저신뢰도)
        scale_confidence (str)   "high" | "medium" | "low"
    """
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

    base64_image, vision_w, vision_h = encode_image_base64(image_path)

    img_w = auto_detected.get("img_width", 1000)
    img_h = auto_detected.get("img_height", 1000)
    scale = auto_detected.get("scale_mm_per_px")
    scale_conf = auto_detected.get("scale_confidence", "low")

    # Vision에 보낸 이미지가 리사이징된 경우 polygon 좌표도 같은 비율로 스케일링
    ratio_x = (vision_w / img_w) if (vision_w > 0 and img_w > 0) else 1.0
    ratio_y = (vision_h / img_h) if (vision_h > 0 and img_h > 0) else 1.0
    if ratio_x != 1.0 or ratio_y != 1.0:
        print(f"📐 [Agent 2] Vision 이미지 리사이징 감지: 원본 {img_w}x{img_h}px → Vision {vision_w}x{vision_h}px (ratio {ratio_x:.3f}, {ratio_y:.3f})")

    # Vision 이미지 기준 좌표를 프롬프트에 사용
    prompt_w = vision_w if vision_w > 0 else img_w
    prompt_h = vision_h if vision_h > 0 else img_h

    # ── polygon bounding box를 Vision 이미지 공간 기준으로 스케일링 ──────────
    poly_px = auto_detected.get("floor_polygon_px", [])
    if poly_px:
        xs = [p[0] * ratio_x for p in poly_px]
        ys = [p[1] * ratio_y for p in poly_px]
        poly_min_x = min(xs)
        poly_min_y = min(ys)
        poly_w_px = max(xs) - min(xs)
        poly_h_px = max(ys) - min(ys)
        print(f"📦 [Agent 2] 도면 polygon bbox (Vision 기준): offset=({poly_min_x:.1f},{poly_min_y:.1f}), size={poly_w_px:.1f}x{poly_h_px:.1f}px")
    else:
        poly_min_x, poly_min_y = 0, 0
        poly_w_px, poly_h_px = prompt_w, prompt_h
        print(f"⚠️ [Agent 2] polygon 없음 → Vision 이미지 전체 크기를 도면 영역으로 사용")
    # ────────────────────────────────────────────────────────────────────────

    request_dimensions = scale is None or scale_conf == "low"
    if request_dimensions:
        print("⚠️ [Agent 2] OCR 스케일 저신뢰도 → Vision에 도면 치수 추가 요청(폴백)")

    dimensions_request = """
[추가 임무 — OCR 스케일 미확보 시 폴백]
도면 치수선(Dimension Lines)에서 가로(Width)와 세로(Height) 실제 크기(mm)를 읽어줘.
숫자 옆에 단위가 없으면 mm로 간주해.
결과를 아래처럼 "dimensions_mm" 키에 포함시켜.
""" if request_dimensions else ""

    dimensions_example = """
    "dimensions_mm": {"width": 20000, "height": 15000},""" if request_dimensions else ""

    prompt = f"""
첨부된 이미지는 실제 팝업스토어가 설치될 도면(Floor Plan)이야.

너의 임무는 이 도면에서 다음 4가지 핵심 시설물(Facilities)의 위치를 정확하게 찾아내는 거야.
도면 크기나 외곽선 꼭짓점은 출력하지 않아도 돼. 시설물 위치에만 집중해.
{dimensions_request}

[탐지 대상 및 시각적 단서]
1. 스프링클러 (Sprinkler):
   - 도면 전체에 일정한 간격으로 배치된 작은 '빨간색 원형' 기호.
   - 원 안에 'SP', 'S', 또는 번호(SP-1)가 적혀 있을 거야.
   - 모든 스프링클러를 다 찾아야 해.

2. 소화전 (Fire Hydrant):
   - 벽면에 붙어 있는 '빨간색 사각형' 기호.
   - 보통 'FH' 또는 '소화전' 글자가 함께 적혀 있어.

3. 분전반 (Electrical Panel):
   - 벽면에 있는 작은 '번개 모양(⚡)' 또는 'EPS', '분전반'이라고 적힌 사각형 박스.

4. 주 출입구 (Entrance):
   - 도면 외곽 벽면에 '화살표(↑)' 또는 'ENT', '입구'라고 표시된 지점.
   - 평면도 상에서 사람들이 들어오는 유일한 통로를 찾아.

[좌표 규칙 — 반드시 준수]
- 이미지 픽셀 크기: 너비 {prompt_w}px, 높이 {prompt_h}px
- 모든 좌표는 반드시 이 픽셀 크기 기준의 실제 픽셀 좌표로 반환하라.
  예: 이미지 정중앙 → {{"x": {prompt_w//2}, "y": {prompt_h//2}}}
      좌상단 모서리 → {{"x": 0, "y": 0}}
      우하단 모서리 → {{"x": {prompt_w}, "y": {prompt_h}}}
- x 범위: 0 ~ {prompt_w}, y 범위: 0 ~ {prompt_h}
- 결과는 반드시 순수한 JSON 형식으로만 대답해.
- 각 시설물의 'confidence'는 네가 얼마나 확신하는지에 따라 high, medium, low 중 하나로 표시해.
- 만약 특정 시설이 도면에 전혀 없다면 리스트를 비워둬.

[출력 JSON 포맷 예시]
{{{dimensions_example}
    "facilities": [
        {{
            "id": "SP-1",
            "type": "sprinkler",
            "position": {{"x": 450, "y": 350}},
            "alert_zone_mm": 2300,
            "confidence": "high"
        }},
        {{
            "id": "FH-1",
            "type": "fire_hydrant",
            "position": {{"x": 2700, "y": 300}},
            "alert_zone_mm": 1000,
            "confidence": "medium"
        }}
    ],
    "entrances": [
        {{
            "position": {{"x": 1680, "y": {prompt_h}}},
            "direction": "South",
            "confidence": "high"
        }}
    ]
}}

[시설물 타입별 alert_zone_mm 기준값]
- sprinkler: 2300mm
- fire_hydrant: 1000mm
- electrical_panel: 800mm
- pillar: 800mm
- other: 500mm
"""

    try:
        print("👁️ Claude Vision (Sonnet 4.6) 으로 도면 분석 중... (CoT 가동)")
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        content = response.content[0].text.strip()

        print("-" * 50)
        print("🔍 [Agent 2] Claude Vision RAW Response (분석 결과):")
        print(content)
        print("-" * 50)
    except Exception as e:
        print(f"⚠️ Vision API 에러 ({e}) -> 사용자 마킹 우회 모드(fallback) 가동")
        content = """
        {
            "facilities": [],
            "entrances": [],
            "user_marking_required": true
        }
        """

    import re
    match = re.search(r'\{[\s\S]*\}', content)
    if match:
        content = match.group(0).strip()

    try:
        parsed_json = json.loads(content)

        # ── 도면 크기(dw, dh) 결정 ───────────────────────────────────────────
        # scale은 원본 픽셀 기준(mm/original_px)이므로, Vision 공간으로 스케일된 poly_w_px를
        # ratio로 나눠 원본 polygon 크기로 되돌린 뒤 곱해야 정확한 mm 치수가 나옴
        if scale and scale_conf != "low":
            orig_poly_w = poly_w_px / ratio_x if ratio_x > 0 else poly_w_px
            orig_poly_h = poly_h_px / ratio_y if ratio_y > 0 else poly_h_px
            dw = round(orig_poly_w * scale)
            dh = round(orig_poly_h * scale)
            print(f"📐 [Agent 2] 도면 규격 (polygon bbox * OCR 스케일): {dw}mm x {dh}mm")
        elif request_dimensions and parsed_json.get("dimensions_mm"):
            dim_raw = parsed_json["dimensions_mm"]
            dw = dim_raw.get("width", 20000)
            dh = dim_raw.get("height", 15000)
            if isinstance(dw, str): dw = int(''.join(filter(str.isdigit, dw)) or 20000)
            if isinstance(dh, str): dh = int(''.join(filter(str.isdigit, dh)) or 15000)
            print(f"📐 [Agent 2] 도면 규격 (Vision 폴백 기준): {dw}mm x {dh}mm")
        else:
            dw, dh = 20000, 15000
            print(f"📐 [Agent 2] 도면 규격 (기본값): {dw}mm x {dh}mm")

        # ── Vision 픽셀 좌표 → mm 변환 함수 ────────────────────────────────
        # polygon bbox 좌상단을 (0,0) 기준으로 정규화 후 mm 변환.
        # 클램핑 제거: Vision이 polygon 경계 바깥 좌표를 반환해도 그대로 비율 변환.
        # (클램핑 시 경계값 0 또는 max에 시설물이 몰리는 문제 방지)
        def norm_to_mm_x(val: float) -> float:
            return round(((val - poly_min_x) / poly_w_px) * dw, 2)

        def norm_to_mm_y(val: float) -> float:
            return round(((val - poly_min_y) / poly_h_px) * dh, 2)
        # ────────────────────────────────────────────────────────────────────

        for fac in parsed_json.get("facilities", []):
            if "position" in fac:
                fac["position"]["x"] = norm_to_mm_x(fac["position"]["x"])
                fac["position"]["y"] = norm_to_mm_y(fac["position"]["y"])

        for ent in parsed_json.get("entrances", []):
            if "position" in ent:
                ent["position"]["x"] = norm_to_mm_x(ent["position"]["x"])
                ent["position"]["y"] = norm_to_mm_y(ent["position"]["y"])

        parsed_json["dimensions_mm"] = {"width": dw, "height": dh}

        for fac in parsed_json.get("facilities", []):
            pos = fac.get("position", {})
            print(f"[DEBUG] facility '{fac.get('id', '?')}': center=({pos.get('x')}, {pos.get('y')}) mm  ← 0~{dw} / 0~{dh} 범위여야 정상")

        validated = FloorPlanData(**parsed_json)
        return validated.model_dump()

    except Exception as e:
        print("Agent 2 데이터 규격(Pydantic) 파싱 실패:", e)
        return FloorPlanData(user_marking_required=True).model_dump()

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(agent_dir))
    img_path = os.path.join(project_root, "image", "demo_floor_rendered.png")
    
    print("=" * 60)
    print("🧠 [Agent 2] OCR/Vision 객체 탐지 테스트 시작")
    print("=" * 60)
    
    if os.path.exists(img_path):
        result = detect_facilities_from_vision(img_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("user_marking_required"):
            print("🚨 경고: 시각적 확신도가 낮아 사용자 수동 마킹 인터페이스 호출이 켜졌습니다.")
    else:
        print(f"❌ 이미지를 찾을 수 없습니다: {img_path}")