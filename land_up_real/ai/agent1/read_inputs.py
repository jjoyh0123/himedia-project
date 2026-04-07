"""
ai/agent1/read_inputs.py
목적: demo_floor_cad.pdf(도면)와 hello-kitty-brand-manual.md(브랜드 메뉴얼)가
      정상적으로 읽히는지 확인 — Agent 1 파이프라인 진입 전 재료 점검
"""

import fitz
import os

# ai/agent1/ 기준 → 두 단계 위가 프로젝트 루트
AGENT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(AGENT_DIR))
PDF_PATH     = os.path.join(PROJECT_ROOT, "image", "demo_floor_cad.pdf")
MANUAL_PATH  = os.path.join(PROJECT_ROOT, "docs", "hello-kitty-brand-manual.md")

# ─────────────────────────────────────────────────────────
# 1. 도면 PDF 구조 파악
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("📐 도면 PDF 분석 — demo_floor_cad.pdf")
print("=" * 60)

doc = fitz.open(PDF_PATH)
print(f"파일 크기   : {os.path.getsize(PDF_PATH):,} bytes")
print(f"총 페이지   : {doc.page_count}")
print(f"PDF 여부    : {doc.is_pdf}")

# 메타데이터
meta = {k: v for k, v in doc.metadata.items() if v}
print(f"\n[메타데이터]")
for k, v in meta.items():
    print(f"  {k}: {v}")

page = doc[0]
rect = page.rect
print(f"\n[페이지 크기]")
print(f"  pt  : {rect.width:.1f} x {rect.height:.1f}")
print(f"  mm  : {rect.width*0.3528:.1f} x {rect.height*0.3528:.1f}")

# 텍스트 레이어
text = page.get_text("text").strip()
print(f"\n[텍스트 레이어]")
if text:
    print(f"  글자 수: {len(text)}자")
    print(f"  내용:\n{text}")
else:
    print("  ⚠️  텍스트 없음 (이미지 전용 or 벡터 전용)")

# 텍스트 블록(위치 포함)
blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
print(f"\n[텍스트 블록] {len(blocks)}개")
for i, b in enumerate(blocks):
    print(f"  [{i}] ({b[0]:.0f},{b[1]:.0f})~({b[2]:.0f},{b[3]:.0f}) → {repr(b[4].strip()[:80])}")

# 벡터 도형
drawings = page.get_drawings()
print(f"\n[벡터 도형] {len(drawings)}개")
for i, d in enumerate(drawings[:10]):
    print(f"  [{i}] rect={d.get('rect')} | stroke={d.get('color')} | fill={d.get('fill')} | width={d.get('width')}")
if len(drawings) > 10:
    print(f"  ... 외 {len(drawings)-10}개 더 있음")

# 내장 이미지
imgs = page.get_images(full=True)
print(f"\n[내장 이미지] {len(imgs)}개")
for i, img in enumerate(imgs[:5]):
    print(f"  [{i}] {img[2]}x{img[3]}px | colorspace={img[5]} | filter={img[8]}")

# 치수 텍스트
words = page.get_text("words")
dim_words = [w for w in words if any(kw in w[4] for kw in ["mm","cm","㎜","1:","M="])]
print(f"\n[치수 텍스트] {len(dim_words)}개")
for w in dim_words:
    print(f"  ({w[0]:.0f},{w[1]:.0f}) → {w[4]}")

doc.close()

# ─────────────────────────────────────────────────────────
# 2. 브랜드 메뉴얼 읽기
# ─────────────────────────────────────────────────────────
print("\n")
print("=" * 60)
print("📋 브랜드 메뉴얼 — hello-kitty-brand-manual.md")
print("=" * 60)

with open(MANUAL_PATH, encoding="utf-8") as f:
    manual = f.read()

print(f"파일 크기 : {os.path.getsize(MANUAL_PATH):,} bytes")
print(f"총 라인   : {len(manual.splitlines())}줄")
print()
print(manual)

print("\n" + "=" * 60)
print("✅ 재료 읽기 완료 — Agent 1 파이프라인 준비됨")
print("=" * 60)
