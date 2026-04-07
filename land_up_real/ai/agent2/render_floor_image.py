"""
ai/agent2/render_floor_image.py

목적: demo_floor_cad.pdf를 고해상도 이미지로 렌더링
      → 도면 구조를 눈으로 확인 + Claude Vision 입력 준비
"""

import fitz
import os

PT_TO_MM = 25.4 / 72

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF_PATH = os.path.join(PROJECT_ROOT, "image", "demo_floor_cad.pdf")
OUT_PATH = os.path.join(PROJECT_ROOT, "image", "demo_floor_rendered.png")

doc = fitz.open(PDF_PATH)
page = doc[0]

# 300 DPI로 렌더링 (2x 스케일 = 144dpi 기본 → 4.17x = 300dpi)
# fitz 기본 해상도: 72 dpi → 300dpi = 300/72 ≈ 4.167
DPI = 300
SCALE = DPI / 72  # ≈ 4.167

mat = fitz.Matrix(SCALE, SCALE)
pix = page.get_pixmap(matrix=mat, alpha=False)

pix.save(OUT_PATH)

print("=" * 55)
print("🖼️  도면 이미지 렌더링 완료")
print("=" * 55)
print(f"  DPI        : {DPI}")
print(f"  scale      : {SCALE:.3f}x")
print(f"  이미지 크기 : {pix.width} x {pix.height} px")
print(f"  실제 크기   : {page.rect.width * PT_TO_MM:.1f} x {page.rect.height * PT_TO_MM:.1f} mm")
print(f"  저장 경로   : {OUT_PATH}")
print(f"  파일 크기   : {os.path.getsize(OUT_PATH):,} bytes")
print()
print("✅ image/demo_floor_rendered.png 를 열어서 도면을 확인하세요")

doc.close()
