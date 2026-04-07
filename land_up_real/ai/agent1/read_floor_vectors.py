"""
ai/agent1/read_floor_vectors.py

목적: demo_floor_cad.pdf의 벡터 도형 131개를
      모두 mm 단위로 변환해서 출력
      → 바닥 polygon 추출 준비 단계
"""

import fitz
import os

PT_TO_MM = 25.4 / 72  # 1 pt → mm 변환 상수

PDF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "image", "demo_floor_cad.pdf"
)

def pt2mm(val):
    """단일 숫자 변환"""
    return round(val * PT_TO_MM, 2)


def rect2mm(r):
    """fitz.Rect → mm 튜플 (x0, y0, x1, y1)"""
    if r is None:
        return None
    return (pt2mm(r.x0), pt2mm(r.y0), pt2mm(r.x1), pt2mm(r.y1))


def pt2mm_w(w):
    """선 두께 변환"""
    return round(w * PT_TO_MM, 3) if w else 0


def extract_floor_vector_paths(pdf_path: str, target_width: float = 20000.0, target_height: float = 15000.0) -> list:
    """메인 서버 파이프라인(server.py)에서 도면 선을 그리기 위해 호출하는 익스포트 함수"""
    try:
        with fitz.open(pdf_path) as doc:
            page = doc[0]
            rect = page.rect  # PDF 페이지 크기 (pt)
            width_pt, height_pt = rect.width, rect.height

            # 가변 공간으로의 스케일 팩터 계산 (기본 20,000mm x 15,000mm)
            scale_x = target_width / width_pt
            scale_y = target_height / height_pt

            def normalize_pt(p):
                # pt 좌표를 12000x9000 mm 규격으로 선형 투영
                return [round(p.x * scale_x, 2), round(p.y * scale_y, 2)]

            drawings = page.get_drawings()

            paths = []
            for d in drawings:
                items = d.get("items", [])
                for item in items:
                    item_type = item[0]
                    if item_type == "re":
                        r = item[1]
                        paths.append([
                            normalize_pt(fitz.Point(r.x0, r.y0)),
                            normalize_pt(fitz.Point(r.x1, r.y0)),
                            normalize_pt(fitz.Point(r.x1, r.y1)),
                            normalize_pt(fitz.Point(r.x0, r.y1)),
                            normalize_pt(fitz.Point(r.x0, r.y0))
                        ])
                    elif item_type == "l":
                        p1, p2 = item[1], item[2]
                        paths.append([
                            normalize_pt(p1),
                            normalize_pt(p2)
                        ])
                    elif item_type == "c":
                        p1, p4 = item[1], item[4]
                        paths.append([
                            normalize_pt(p1),
                            normalize_pt(p4)
                        ])
                    elif item_type == "qu":
                        p1, p3 = item[1], item[3]
                        paths.append([
                            normalize_pt(p1),
                            normalize_pt(p3)
                        ])
        return paths
    except Exception as e:
        print(f"⚠️ 벡터 도면 추출 에러: {e}")
        return []


if __name__ == "__main__":
    # 이 블록은 파일을 직접 실행(python read_floor_vectors.py)할 때만 동작합니다.
    # 서버에서 import할 때는 실행되지 않습니다.
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ 파일을 찾을 수 없습니다: {PDF_PATH}")
    else:
        doc = fitz.open(PDF_PATH)
        page = doc[0]
        rect = page.rect

        print("=" * 65)
        print("📐 도면 벡터 분석 (단위: mm)")
        print("=" * 65)
        print(f"페이지 크기 : {rect.width * PT_TO_MM:.1f} x {rect.height * PT_TO_MM:.1f} mm  (A4 Landscape)")
        print(f"변환 상수   : 1 pt = {PT_TO_MM:.5f} mm")

        drawings = page.get_drawings()
        print(f"벡터 도형 수: {len(drawings)}개")

        # ── 도형 타입별 분류 ──────────────────────────────────────────
        type_counter = {}
        for d in drawings:
            t = d.get("type", "unknown")
            type_counter[t] = type_counter.get(t, 0) + 1

        print()
        print("── 도형 타입 분포 ──")
        for t, cnt in sorted(type_counter.items(), key=lambda x: -x[1]):
            print(f"  {t:<12} : {cnt}개")

        # ── 전체 도형 목록 (mm 변환) ──────────────────────────────────
        print()
        print("── 전체 벡터 도형 목록 (mm) ──")
        print(f"  {'#':<4} {'type':<10} {'rect (x0,y0,x1,y1) mm':<42} {'stroke':<18} {'fill':<18} {'width_mm'}")
        print("  " + "-" * 110)

        for i, d in enumerate(drawings):
            t      = d.get("type", "?")
            r_mm   = rect2mm(d.get("rect"))
            color  = d.get("color")
            fill   = d.get("fill")
            width  = pt2mm_w(d.get("width") or 0)

            r_str = str(r_mm) if r_mm else "-"
            c_str = str(tuple(round(c, 2) for c in color)) if color else "-"
            f_str = str(tuple(round(c, 2) for c in fill))  if fill  else "-"

            print(f"  {i:<4} {t:<10} {r_str:<42} {c_str:<18} {f_str:<18} {width}")

        # ── 크기별 사각형 정렬 (큰 것 = 방/공간 윤곽 후보) ──────────
        print()
        print("── 사각형(rect) 크기 TOP 10 — 바닥 윤곽 후보 ──")
        rects = []
        for d in drawings:
            r = d.get("rect")
            if r:
                w_mm = pt2mm(r.width)
                h_mm = pt2mm(r.height)
                area = w_mm * h_mm
                rects.append({
                    "w": w_mm, "h": h_mm, "area": area,
                    "x0": pt2mm(r.x0), "y0": pt2mm(r.y0),
                    "stroke": d.get("color"), "fill": d.get("fill"),
                    "line_w": pt2mm_w(d.get("width") or 0)
                })

        rects_sorted = sorted(rects, key=lambda x: -x["area"])
        print(f"  {'#':<4} {'w(mm)':<10} {'h(mm)':<10} {'area(mm²)':<14} {'x0':<8} {'y0':<8} {'stroke':<16} {'fill'}")
        print("  " + "-" * 90)
        for i, r in enumerate(rects_sorted[:10]):
            s = str(tuple(round(c,2) for c in r["stroke"])) if r["stroke"] else "-"
            f = str(tuple(round(c,2) for c in r["fill"]))   if r["fill"]   else "-"
            print(f"  {i:<4} {r['w']:<10.1f} {r['h']:<10.1f} {r['area']:<14.0f} {r['x0']:<8.1f} {r['y0']:<8.1f} {s:<16} {f}")

        # ── 선(line/curve) 두께별 분포 ──
        print()
        print("── 선 두께(width) 분포 ──")
        width_counter = {}
        for d in drawings:
            w = round(pt2mm_w(d.get("width") or 0), 2)
            width_counter[w] = width_counter.get(w, 0) + 1
        for w, cnt in sorted(width_counter.items()):
            print(f"  {w:.3f} mm  →  {cnt}개")

        doc.close()
        print()
        print("=" * 65)
        print("✅ 벡터 분석 완료 — Agent 2 전반부 polygon 추출 준비됨")
        print("=" * 65)
