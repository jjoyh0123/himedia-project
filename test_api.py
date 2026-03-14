import os
import requests
import time

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(endpoint, files):
    print(f"\n[{endpoint.upper()}] API 테스트 중...")
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/{endpoint}", files=files)
        elapsed = time.time() - start_time
        
        print(f"상태 코드: {response.status_code} ({elapsed:.2f}초 반환)")
        if response.status_code == 200:
            print("응답 JSON (일부):")
            # JSON 출력이 너무 길어질 수 있으므로 적절히 잘라서 보여주거나 그대로 출력
            data = response.json()
            print(str(data)[:500] + ("..." if len(str(data)) > 500 else ""))
        else:
            print("에러:", response.text)
    except Exception as e:
        print(f"요청 실패: {e}")

def main():
    print(f"대상 서버: {BASE_URL}")
    print("=" * 40)
    
    # 서버 응답 체크 (기본 루트)
    try:
        if requests.get(BASE_URL).status_code != 200:
            print("서버가 시작되지 않았거나 응답하지 않습니다.")
            return
    except requests.exceptions.ConnectionError:
        print("서버에 연결할 수 없습니다. 'uvicorn main:app --reload'를 먼저 실행해주세요.")
        return

    # 1. Classify 테스트
    sample_img = "sample_image.jpg"
    if os.path.exists(sample_img):
        with open(sample_img, "rb") as f:
            test_endpoint("classify", {"file": f})
    else:
        print(f"\n[CLASSIFY] 생략: '{sample_img}' 이미지를 찾을 수 없습니다.")

    # 2. Detect 테스트
    detect_img = "sample_detection.jpg"
    if os.path.exists(detect_img):
        with open(detect_img, "rb") as f:
            test_endpoint("detect", {"file": f})
    else:
        print(f"\n[DETECT] 생략: '{detect_img}' 이미지를 찾을 수 없습니다.")

    # 3. Face Verify 테스트
    img1, img2 = "tom1.jpg", "tom2.jpg"
    if os.path.exists(img1) and os.path.exists(img2):
        with open(img1, "rb") as f1, open(img2, "rb") as f2:
            test_endpoint("face-verify", {"img1": f1, "img2": f2})
    else:
        print(f"\n[FACE-VERIFY] 생략: '{img1}' 혹은 '{img2}' 이미지를 찾을 수 없습니다.")

    # 4. OCR 테스트
    ocr_img = "sample_korean2.jpg"
    if os.path.exists(ocr_img):
        with open(ocr_img, "rb") as f:
            test_endpoint("ocr", {"file": f})
    else:
        print(f"\n[OCR] 생략: '{ocr_img}' 이미지를 찾을 수 없습니다.")

    # 5. Pose 테스트
    pose_img = "sample_pose.jpg"
    if os.path.exists(pose_img):
        with open(pose_img, "rb") as f:
            test_endpoint("pose", {"file": f})
    else:
        print(f"\n[POSE] 생략: '{pose_img}' 이미지를 찾을 수 없습니다.")

    print("\n=" * 40)
    print("API 테스트가 완료되었습니다.")

if __name__ == "__main__":
    main()
