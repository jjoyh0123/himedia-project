import os
import sys
import shutil
import tempfile

# ModuleNotFoundError: No module named 'ai' 에러 방지용 (프로젝트 루트 경로 추가)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional

# 비동기 파이프라인 오케스트레이터
from backend.services.pipeline import execute_realtime_pipeline

app = FastAPI(title="LandingUp Pipeline Server")

# React 프론트엔드(5173) 호출 허용 (CORS 오픈)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/generate", response_model=Dict[str, Any])
async def generate_layout(
    brand_manual: UploadFile = File(...), 
    floor_plan: UploadFile = File(...),
    user_markings: Optional[str] = Form(None)
):
    """
    브랜드 룰(brand_manual.md) 파일과 공간 도면(floor_plan.png) 2개의 파일을 업로드 받아
    Agent 1~3의 전체 배치 및 검증 과정을 거쳐 최종 3D 구조 좌표도를 JSON으로 반환합니다.
    user_markings 가 있으면 AI 분석을 건너뛰고 수동 마킹된 좌표를 사용합니다.
    """
    # 1. 임시 파일 보관소(Temp)에 원본 확장자를 유지하여 파일 브릿지 생성
    _, manual_ext = os.path.splitext(brand_manual.filename)
    with tempfile.NamedTemporaryFile(delete=False, suffix=manual_ext) as tmp_manual:
        shutil.copyfileobj(brand_manual.file, tmp_manual)
        manual_path = tmp_manual.name
    
    brand_manual.file.close() # FastAPI 파일 핸들 해제
        
    _, image_ext = os.path.splitext(floor_plan.filename)
    with tempfile.NamedTemporaryFile(delete=False, suffix=image_ext) as tmp_image:
        shutil.copyfileobj(floor_plan.file, tmp_image)
        image_path = tmp_image.name

    floor_plan.file.close() # FastAPI 파일 핸들 해제

    print(f"\n🚀 [서버 수신 완료] 도면: {floor_plan.filename} / 브랜드: {brand_manual.filename}")

    try:
        result = await execute_realtime_pipeline(manual_path, image_path, user_markings)

        # Human-in-the-loop: Vision 탐지 확신 부족 시 수동 마킹 모드로 즉시 반환
        if isinstance(result, dict) and result.get("status") == "manual_marking_required":
            print("🚨 [서버] Vision 탐지 실패 또는 확신 부족. 수동 마킹 모드로 응답합니다.")
            return result

        return result

    except Exception as e:
        print(f"❌ 파이프라인 런타임 에러: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 파일 수신 흔적 청소 (Clean-up) - 윈도우 파일 잠금 대비 예외 처리
        for path in [manual_path, image_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"⚠️ 임시 파일 삭제 실패 (사용 중일 수 있음): {path} - {e}")

if __name__ == "__main__":
    import uvicorn
    # 터미널 실행: python backend/server.py 
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
