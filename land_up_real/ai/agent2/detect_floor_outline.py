"""
ai/agent2/detect_floor_outline.py

목적: 도면 이미지에서 코드(OpenCV + OCR)로 바닥 외곽선과 스케일을 추출.
      Claude Vision이 담당하던 dimensions_mm, outline_vertices 역할을 분리.

처리 순서:
  1. OpenCV  → 이미지 외곽 윤곽선(contour) 추출 → 바닥 polygon (픽셀 좌표)
  2. OCR     → 도면 치수선 숫자 인식 → mm/px 스케일 계산
  3. 실패 시 → scale_confidence = "low" 로 기록하여 Vision 폴백 신호
"""

import os
import io
import json
import numpy as np

# Windows 환경에서 PATH 등록 전에도 동작하도록 Tesseract 경로 명시
try:
    import pytesseract
    _TESSERACT_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_TESSERACT_DEFAULT):
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_DEFAULT
except ImportError:
    pass

def _load_image_as_ndarray(image_path: str) -> np.ndarray:
    """
    이미지 파일(PNG/JPG/PDF)을 OpenCV가 처리할 수 있는 BGR ndarray로 변환.
    PDF는 첫 페이지를 고해상도(2배)로 렌더링 후 변환.
    """
    import cv2

    if image_path.lower().endswith(".pdf"):
        print(f"📄 [OutlineDetector] PDF 도면 감지 → 첫 페이지 이미지 변환 중...")
        import fitz
        with fitz.open(image_path) as doc:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    else:
        img = cv2.imread(image_path)

    if img is None:
        raise ValueError(f"[OutlineDetector] 이미지 로드 실패: {image_path}")
    return img


def extract_floor_polygon(image_path: str) -> dict:
    """
    OpenCV로 도면의 바닥 외곽 polygon을 픽셀 좌표로 추출합니다.

    반환값:
        {
            "polygon_px": [[x,y], ...],   # 시계방향 꼭짓점 픽셀 좌표
            "img_width":  int,            # 이미지 전체 너비 (픽셀)
            "img_height": int,            # 이미지 전체 높이 (픽셀)
            "success":    bool
        }
    """
    import cv2

    try:
        img = _load_image_as_ndarray(image_path)
        h, w = img.shape[:2]
        print(f"🖼️ [OutlineDetector] 이미지 크기: {w}x{h}px")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 이진화: 도면 배경(흰색)과 선(검정)을 분리
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        # 모폴로지: 작은 노이즈 제거, 끊긴 선 연결
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 외곽 윤곽선 탐색
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print("⚠️ [OutlineDetector] 외곽선을 찾지 못했습니다.")
            return {"polygon_px": [], "img_width": w, "img_height": h, "success": False}

        # 가장 넓은 면적의 윤곽선 = 바닥 외곽선
        floor_contour = max(contours, key=cv2.contourArea)

        # Douglas-Peucker 알고리즘으로 꼭짓점 단순화
        epsilon = 0.01 * cv2.arcLength(floor_contour, True)
        approx = cv2.approxPolyDP(floor_contour, epsilon, True)
        polygon_px = approx.squeeze().tolist()

        # squeeze() 결과가 1D(꼭짓점 1개)일 경우 2D로 보정
        if isinstance(polygon_px[0], (int, float)):
            polygon_px = [polygon_px]

        print(f"✅ [OutlineDetector] 바닥 polygon 추출 완료: {len(polygon_px)}개 꼭짓점")
        return {"polygon_px": polygon_px, "img_width": w, "img_height": h, "success": True}

    except Exception as e:
        print(f"⚠️ [OutlineDetector] polygon 추출 실패: {e}")
        return {"polygon_px": [], "img_width": 0, "img_height": 0, "success": False}


def extract_scale_from_ocr(image_path: str) -> dict:
    """
    pytesseract OCR로 도면의 치수선 숫자를 읽어 mm/px 스케일을 계산합니다.

    전략:
      - 이미지 상단/하단/좌측 여백 영역(치수선이 주로 위치)을 크롭하여 OCR
      - 숫자 + 단위(mm, m, cm) 패턴 탐색
      - 탐지된 숫자와 해당 방향의 픽셀 길이로 스케일 계산

    반환값:
        {
            "scale_mm_per_px": float or None,
            "scale_confidence": "high" | "medium" | "low",
            "detected_dimension_mm": int or None,
            "detected_dimension_px": int or None
        }
    """
    import cv2
    import re

    try:
        import pytesseract
    except ImportError:
        print("⚠️ [OutlineDetector] pytesseract 미설치 → OCR 스킵, scale_confidence=low")
        return {
            "scale_mm_per_px": None,
            "scale_confidence": "low",
            "detected_dimension_mm": None,
            "detected_dimension_px": None
        }

    try:
        img = _load_image_as_ndarray(image_path)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 치수선 탐색 영역: 상단 15%, 하단 15%, 좌측 10% 크롭
        regions = {
            "top":    gray[0:int(h * 0.15), :],
            "bottom": gray[int(h * 0.85):,  :],
            "left":   gray[:, 0:int(w * 0.10)]
        }

        # 숫자 + 단위 패턴 (예: 20,000 / 15000 / 15m / 20.0m)
        pattern = re.compile(r'(\d[\d,\.]+)\s*(mm|m|cm)?', re.IGNORECASE)

        best_mm = None
        best_px = None
        confidence = "low"

        for region_name, region_img in regions.items():
            # 대비 강화 후 OCR
            _, thresh = cv2.threshold(region_img, 128, 255, cv2.THRESH_BINARY)
            text = pytesseract.image_to_string(thresh, config='--psm 6 -c tessedit_char_whitelist=0123456789.,mM ')

            matches = pattern.findall(text)
            for num_str, unit in matches:
                try:
                    num = float(num_str.replace(',', ''))
                    # 단위 정규화
                    if unit.lower() == 'm':
                        num_mm = int(num * 1000)
                    elif unit.lower() == 'cm':
                        num_mm = int(num * 10)
                    else:
                        num_mm = int(num)

                    # 도면 치수 유효 범위: 3,000mm ~ 100,000mm (3m ~ 100m)
                    if 3000 <= num_mm <= 100000:
                        # 해당 방향의 픽셀 길이를 기준으로 스케일 추정
                        px_length = w if region_name in ("top", "bottom") else h
                        scale = num_mm / px_length
                        best_mm = num_mm
                        best_px = px_length
                        confidence = "high" if unit else "medium"
                        print(f"📐 [OutlineDetector] OCR 치수 탐지: {num_mm}mm ({region_name} 영역)")
                        break
                except (ValueError, ZeroDivisionError):
                    continue

            if best_mm:
                break

        if best_mm and best_px:
            return {
                "scale_mm_per_px": best_mm / best_px,
                "scale_confidence": confidence,
                "detected_dimension_mm": best_mm,
                "detected_dimension_px": best_px
            }
        else:
            print("⚠️ [OutlineDetector] OCR 치수 탐지 실패 → scale_confidence=low")
            return {
                "scale_mm_per_px": None,
                "scale_confidence": "low",
                "detected_dimension_mm": None,
                "detected_dimension_px": None
            }

    except Exception as e:
        print(f"⚠️ [OutlineDetector] OCR 처리 실패: {e}")
        return {
            "scale_mm_per_px": None,
            "scale_confidence": "low",
            "detected_dimension_mm": None,
            "detected_dimension_px": None
        }


def build_auto_detected(image_path: str) -> dict:
    """
    OpenCV polygon + OCR scale을 합산하여 auto_detected 임시 딕셔너리를 반환합니다.
    Vision 단계(detect_facilities)에 전달되어 설비 감지 결과와 합쳐집니다.

    반환값:
        {
            "floor_polygon_px": [[x,y], ...],
            "img_width":        int,
            "img_height":       int,
            "scale_mm_per_px":  float or None,
            "scale_confidence": "high" | "medium" | "low",
            "polygon_success":  bool
        }
    """
    print("="*60)
    print("🚀 [OutlineDetector] Step 1: OpenCV 바닥 polygon 추출")
    print("="*60)
    polygon_result = extract_floor_polygon(image_path)

    print("\n" + "="*60)
    print("🚀 [OutlineDetector] Step 2: OCR 치수선 → mm 스케일 계산")
    print("="*60)
    scale_result = extract_scale_from_ocr(image_path)

    return {
        "floor_polygon_px": polygon_result["polygon_px"],
        "img_width":        polygon_result["img_width"],
        "img_height":       polygon_result["img_height"],
        "scale_mm_per_px":  scale_result["scale_mm_per_px"],
        "scale_confidence": scale_result["scale_confidence"],
        "polygon_success":  polygon_result["success"]
    }


def polygon_px_to_mm(polygon_px: list, dw: float, dh: float) -> list:
    """
    픽셀 polygon 좌표를 mm 좌표로 변환합니다.
    dw, dh: 도면 실제 가로/세로 크기 (mm)

    - 원점 기준: polygon bounding box 좌상단 = (0, 0)
    - 가로/세로 스케일을 각각 독립적으로 계산하여 비율 왜곡 방지
    - detect_facilities.py의 norm_to_mm_x/y와 동일한 공식 사용
    """
    if not polygon_px:
        return []
    xs = [pt[0] for pt in polygon_px]
    ys = [pt[1] for pt in polygon_px]
    min_x, min_y = min(xs), min(ys)
    w_px = max(xs) - min_x
    h_px = max(ys) - min_y
    if w_px == 0 or h_px == 0:
        return []
    return [
        {"x": round((pt[0] - min_x) / w_px * dw, 2),
         "y": round((pt[1] - min_y) / h_px * dh, 2)}
        for pt in polygon_px
    ]


if __name__ == "__main__":
    import sys
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(agent_dir))
    img_path = os.path.join(project_root, "image", "demo_floor_rendered.png")

    print("=" * 60)
    print("🧠 [OutlineDetector] OpenCV + OCR 단독 테스트")
    print("=" * 60)

    if not os.path.exists(img_path):
        print(f"❌ 이미지를 찾을 수 없습니다: {img_path}")
        sys.exit(1)

    result = build_auto_detected(img_path)
    print("\n📊 최종 auto_detected 결과:")
    print(json.dumps({
        "polygon_vertices": len(result["floor_polygon_px"]),
        "img_size": f"{result['img_width']}x{result['img_height']}px",
        "scale_mm_per_px": result["scale_mm_per_px"],
        "scale_confidence": result["scale_confidence"],
        "polygon_success": result["polygon_success"]
    }, indent=2, ensure_ascii=False))
