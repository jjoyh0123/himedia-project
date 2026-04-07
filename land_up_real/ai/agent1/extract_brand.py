"""
ai/agent1/extract_brand.py

목적: 브랜드 매뉴얼 파일 경로를 입력받아 Anthropic API(Claude)를 사용하여
       Pydantic 모델로 정의된 형태로 수치/제약 조건들을 추출.

       PDF → Claude Document API (파일 직접 전달)
       비PDF(md/txt 등) → 텍스트 읽어서 text 블록으로 전달
"""

import os
import json
import base64
import asyncio
from typing import List, Literal, Union
from pydantic import BaseModel, field_validator
import anthropic

class ExtractedValue(BaseModel):
    value: Union[int, str, None]
    confidence: Literal["high", "medium", "low", None] = None
    source: Literal["manual", "default", "user_input", None] = None

class RelationshipRule(BaseModel):
    rule: str
    confidence: Literal["high", "medium", "low", None]

# Agent 1 출력 Pydantic 스키마 정의
class BrandConstraints(BaseModel):
    brand_name: ExtractedValue
    clearspace_mm: ExtractedValue
    character_orientation: ExtractedValue
    prohibited_material: ExtractedValue
    logo_clearspace_mm: ExtractedValue
    relationships: List[RelationshipRule] = []

    @field_validator("clearspace_mm")
    @classmethod
    def check_clearspace_range(cls, v: ExtractedValue):
        if v.value is not None:
            if not isinstance(v.value, int):
                # LLM이 숫자에 'mm'를 붙이거나 문자열로 반환했을 경우 방어
                v.value = int(str(v.value).replace(',', '').replace('mm', '').strip())

            if v.value < 300:
                print(f"⚠️ [Agent 1] 경고: 추출된 clearspace({v.value}mm)가 너무 작아 최소치(300mm)로 보정합니다.")
                v.value = 300
            elif v.value > 5000:
                print(f"⚠️ [Agent 1] 경고: 추출된 clearspace({v.value}mm)가 너무 커 최대치(5000mm)로 보정합니다.")
                v.value = 5000
        return v

    @field_validator("logo_clearspace_mm")
    @classmethod
    def check_logo_range(cls, v: ExtractedValue):
        if v.value is not None:
            try:
                if not isinstance(v.value, int):
                    v.value = int(str(v.value).replace(',', '').replace('mm', '').strip())
                if v.value < 0: v.value = 0
                if v.value > 3000: v.value = 3000
            except:
                v.value = 0
        return v


async def extract_brand_guidelines(manual_path: str) -> dict:
    """
    브랜드 매뉴얼 파일 경로를 받아 Claude API로 제약 조건을 추출합니다.
    - PDF: Claude Document API (base64 인코딩 후 document 블록으로 직접 전달)
    - 비PDF: 텍스트로 읽어서 text 블록으로 전달
    """
    # 파이썬 캐싱 방지: 무조건 물리적 파일(.env) 경로에서 텍스트로 읽어오기
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(agent_dir))
    env_path = os.path.join(project_root, ".env")

    # 법령 텍스트 비동기 읽기 (논블로킹)
    legal_rules_path = os.path.join(project_root, "docs", "legal_rules.txt")
    legal_rules_text = ""
    if os.path.exists(legal_rules_path):
        def _read_legal():
            with open(legal_rules_path, "r", encoding="utf-8") as f:
                return f.read()
        legal_rules_text = await asyncio.to_thread(_read_legal)

    api_key = ""
    if os.path.exists(env_path):
        def _read_env():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY"):
                        return line.split("=", 1)[1].strip()
            return ""
        api_key = await asyncio.to_thread(_read_env)

    # 시스템에 남아있을지 모르는 외부 프록시 Base URL을 무시하고, 무조건 공식 서버로 통신 강제
    client = anthropic.AsyncAnthropic(
        api_key=api_key,
        base_url="https://api.anthropic.com"
    )

    # ── 매뉴얼 파일 형식에 따라 content 블록 분기 ──────────────────────────────
    # Document API 전송 크기 제한 기준 (base64 오버헤드 감안, 원본 기준 ~3MB)
    PDF_SIZE_LIMIT_BYTES = 3 * 1024 * 1024  # 3MB

    if manual_path.lower().endswith(".pdf"):
        # PDF → Claude Document API: base64 인코딩 후 document 블록으로 직접 전달
        def _read_pdf():
            with open(manual_path, "rb") as f:
                return f.read()
        pdf_bytes = await asyncio.to_thread(_read_pdf)
        pdf_size_kb = len(pdf_bytes) // 1024

        if len(pdf_bytes) > PDF_SIZE_LIMIT_BYTES:
            # 크기 초과 → fitz로 압축 후 재시도
            print(f"⚠️ [Agent 1] PDF 크기 초과 ({pdf_size_kb}KB) → fitz 압축 시도")
            def _compress_pdf():
                import fitz
                import io
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                buf = io.BytesIO()
                doc.save(buf, garbage=4, deflate=True, clean=True)
                doc.close()
                return buf.getvalue()
            pdf_bytes = await asyncio.to_thread(_compress_pdf)
            compressed_kb = len(pdf_bytes) // 1024
            print(f"📦 [Agent 1] fitz 압축 완료: {pdf_size_kb}KB → {compressed_kb}KB")

        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        print(f"📄 [Agent 1] PDF 브랜드 매뉴얼 → Claude Document API 전달 ({len(pdf_bytes) // 1024}KB)")
        manual_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_base64
            }
        }
    else:
        # 비PDF(md/txt 등) → 텍스트로 읽어서 text 블록으로 전달
        def _read_text():
            try:
                with open(manual_path, "r", encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(manual_path, "r", encoding="cp949", errors="replace") as f:
                    return f.read()
        manual_text = await asyncio.to_thread(_read_text)
        print(f"📄 [Agent 1] 텍스트 매뉴얼 읽기 완료 ({len(manual_text)}자)")
        manual_block = {
            "type": "text",
            "text": f"[메뉴얼 원문]\n{manual_text}"
        }

    # ── 프롬프트 (instruction) ──────────────────────────────────────────────────
    instruction = f"""
다음은 팝업스토어 브랜드 메뉴얼 내용이야. 이 메뉴얼을 읽고 아래의 5가지 핵심 항목만 추출해.
문서에 명확히 없는 내용은 절대 추측하지 말고 속성들을 null 처리해.

[추출 대상 및 규칙]
0. brand_name (str): 브랜드 상표명 또는 캐릭터 시리즈 이름 (예: 헬로키티, 포켓몬, 마이멜로디 등).
1. clearspace_mm (int): 메인 캐릭터 조형물의 사방 최소 이격 거리/여유 공간/여백을 숫자(mm)만 추출해.
2. character_orientation (str): 캐릭터 배치의 정면 방향 (방향 규정).
3. prohibited_material (str): 금지된 소재.
4. logo_clearspace_mm (int): 공간 설치물/사이니지 기준 로고의 사방 최소 이격 거리를 숫자(mm)만 추출해. (인쇄용이 아님)
5. relationships (List): 조형물 간의 '관계 제약'을 원문 그대로 추출 (예: 쿠로미와 헬로키티 분리 등).

모든 추출값은 JSON 형태로 반환해야 하며, 각 항목마다 추출 신뢰도 'confidence' (high, medium, low)와 출처 'source' (기본은 "manual") 값을 함께 포함해.
만약 문서에 없는 항목이라면 'value', 'confidence', 'source' 모두 null 로 처리해.

[관련 건축 및 소방 법령 조문]
아래는 팝업스토어 건축 설계에 필요한 법령 조문들입니다. 추출이나 로직에 필요한 경우 참고하십시오.
{legal_rules_text}

JSON 응답 포맷 예시:
{{
    "brand_name": {{"value": "헬로키티", "confidence": "high", "source": "manual"}},
    "clearspace_mm": {{"value": 1500, "confidence": "high", "source": "manual"}},
    "character_orientation": {{"value": "입구 정면", "confidence": "high", "source": "manual"}},
    "prohibited_material": {{"value": "금속, 투명 아크릴", "confidence": "medium", "source": "manual"}},
    "logo_clearspace_mm": {{"value": 500, "confidence": "high", "source": "manual"}},
    "relationships": [
        {{"rule": "A와 B는 떨어뜨릴 것", "confidence": "high"}}
    ]
}}
"""

    try:
        print(f"Claude API 호출 중... (모델: claude-sonnet-4-6, 키시작: {api_key[:12]}...)")
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        manual_block,
                        {"type": "text", "text": instruction}
                    ]
                }
            ]
        )
        content = response.content[0].text.strip()
    except Exception as e:
        print(f"⚠️ API 호출 실패: {repr(e)}")
        return None

    import re
    # 정규식 패턴으로 '{' 부터 '}' 까지의 가장 바깥쪽 블럭만 안전하게 추출
    match = re.search(r'\{[\s\S]*\}', content)
    if match:
        content = match.group(0).strip()

    try:
        parsed_json = json.loads(content)
        validated_data = BrandConstraints(**parsed_json)
        return validated_data.model_dump()

    except json.JSONDecodeError as e:
        print("JSON 파싱 에러:", e)
        return None
    except Exception as e:
        print("유효성 검증 에러 (Pydantic Validator):", e)
        return None


if __name__ == "__main__":
    AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(AGENT_DIR))
    MANUAL_PATH = os.path.join(PROJECT_ROOT, "docs", "hello-kitty-brand-manual.md")

    print("=" * 65)
    print("🧠 [Agent 1] 브랜드/기준법 수치 추출 테스트")
    print("=" * 65)

    result = asyncio.run(extract_brand_guidelines(MANUAL_PATH))

    if result:
        print("\n✅ 추출 성공 및 Pydantic 검증 통과!\n")

        space_data = {
            "brand": result
        }

        # 디버깅/확인용으로 예쁘게 출력
        print(json.dumps(space_data, indent=2, ensure_ascii=False))
    else:
        print("\n❌ 정보 추출 실패")
