import os
import io
import ssl
import urllib.request
import tempfile
import base64
from contextlib import asynccontextmanager

import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
import torchvision.models as models
from torchvision.models.detection import (
    fasterrcnn_mobilenet_v3_large_fpn,
    FasterRCNN_MobileNet_V3_Large_FPN_Weights
)
from PIL import Image

# 웹 프레임워크
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

# 외부 모델 라이브러리
import easyocr
from ultralytics import YOLO
from deepface import DeepFace


# ----------------- 전역 모델 캐시 -----------------
models_cache = {}

# ----------------- COCO 클래스 (Object Detection 용) -----------------
COCO_CLASSES = [
    "__background__", "person", "bicycle", "car", "motorcycle", "airplane", "bus",
    "train", "truck", "boat", "traffic light", "fire hydrant", "N/A", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "N/A", "backpack", "umbrella", "N/A",
    "N/A", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "N/A", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "N/A", "dining table", "N/A", "N/A", "toilet", "N/A",
    "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "N/A", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]

# ----------------- 유틸리티 함수 -----------------
def load_imagenet_labels():
    """ImageNet 클래스 레이블을 로드합니다."""
    labels_path = os.path.join(os.path.dirname(__file__), "imagenet_labels.txt")
    if not os.path.exists(labels_path):
        url = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
        try:
            urllib.request.urlretrieve(url, labels_path)
        except Exception as e:
            print(f"Warning: Failed to download imagenet labels: {e}")
            return None
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = [line.strip() for line in f.readlines()]
    return labels


# ----------------- Lifespan (앱 시작/종료 시점의 동작) -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server starting with Lazy Loading strategy (Models will load on first request).")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models_cache["device"] = device
    yield
    print("🧹 Cleaning up models from memory...")
    models_cache.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # -- 서버 종료 시 메모리 정리 --
    print("🧹 Cleaning up models from memory...")
    models_cache.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ----------------- FastAPI App 및 템플릿 설정 -----------------
app = FastAPI(title="Deep Learning Models API", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """메인 웹 인터페이스(Jinja2)를 반환합니다."""
    return templates.TemplateResponse("index.html", {"request": request})


# ----------------- 1. Image Classification 엔드포인트 -----------------
@app.post("/classify")
async def classify_image(file: UploadFile = File(...)):
    """단일 이미지를 입력받아 Top-5 클래스와 확률을 반환합니다."""
    try:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        
        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])
        input_tensor = transform(img).unsqueeze(0)
        
        device = models_cache["device"]
        
        # Lazy Loading for Classification
        if "classification" not in models_cache:
            print("  [Lazy] Loading Classification model...")
            clf_model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1)
            clf_model.eval()
            clf_model.to(device)
            models_cache["classification"] = clf_model
            models_cache["imagenet_labels"] = load_imagenet_labels()
            
        model = models_cache["classification"]
        input_tensor = input_tensor.to(device)
        
        with torch.no_grad():
            output = model(input_tensor)
            probs = torch.nn.functional.softmax(output[0], dim=0)
            top5_probs, top5_indices = torch.topk(probs, 5)
            
        labels = models_cache["imagenet_labels"]
        results = []
        for i in range(5):
            idx = top5_indices[i].item()
            prob = top5_probs[i].item()
            label_name = labels[idx] if labels and idx < len(labels) else f"class_{idx}"
            results.append({"label": label_name, "probability": float(prob)})
            
        return JSONResponse(content={"predictions": results})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------- 2. Object Detection 엔드포인트 -----------------
@app.post("/detect")
async def detect_objects(file: UploadFile = File(...)):
    """단일 이미지를 입력받아 감지된 객체의 위치(bbox)와 클래스, 신뢰도를 반환합니다."""
    try:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Detection Transform: (0~255 RGB -> 0.0~1.0 Tensor)
        transform = transforms.ToTensor()
        input_tensor = transform(img).unsqueeze(0)
        
        device = models_cache["device"]
        
        # Lazy Loading for Detection
        if "detection" not in models_cache:
            print("  [Lazy] Loading Object Detection model...")
            det_model = fasterrcnn_mobilenet_v3_large_fpn(weights=FasterRCNN_MobileNet_V3_Large_FPN_Weights.COCO_V1)
            det_model.eval()
            det_model.to(device)
            models_cache["detection"] = det_model
            
        model = models_cache["detection"]
        input_tensor = input_tensor.to(device)
        
        with torch.no_grad():
            predictions = model(input_tensor)
            
        pred = predictions[0]
        boxes = pred["boxes"].cpu().numpy()
        labels = pred["labels"].cpu().numpy()
        scores = pred["scores"].cpu().numpy()
        
        # 신뢰도 0.5 이상 필터링
        threshold = 0.5
        mask = scores >= threshold
        filtered_boxes = boxes[mask]
        filtered_labels = labels[mask]
        filtered_scores = scores[mask]
        
        results = []
        for box, label, score in zip(filtered_boxes, filtered_labels, filtered_scores):
            class_name = COCO_CLASSES[label] if label < len(COCO_CLASSES) else f"class_{label}"
            results.append({
                "class_name": class_name,
                "confidence": float(score),
                "box": [float(c) for c in box]  # [x1, y1, x2, y2]
            })
            
        return JSONResponse(content={"detections": results})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect-visualize", response_class=HTMLResponse)
async def detect_visualize(request: Request, file: UploadFile = File(...)):
    """이미지를 업로드받아 탐지 결과를 그린 결과를 HTML로 렌더링합니다."""
    try:
        contents = await file.read()
        
        # 1. 원본 이미지 준비 (Base64)
        original_base64 = base64.b64encode(contents).decode('utf-8')
        
        # 2. OpenCV를 위한 변환
        nparr = np.frombuffer(contents, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_cv is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        # 추론용 PIL 변환
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        transform = transforms.ToTensor()
        input_tensor = transform(pil_img).unsqueeze(0)
        
        device = models_cache["device"]
        
        # Lazy Loading for Detection (Visualizer)
        if "detection" not in models_cache:
            print("  [Lazy] Loading Object Detection model for visualizer...")
            det_model = fasterrcnn_mobilenet_v3_large_fpn(weights=FasterRCNN_MobileNet_V3_Large_FPN_Weights.COCO_V1)
            det_model.eval()
            det_model.to(device)
            models_cache["detection"] = det_model
            
        model = models_cache["detection"]
        input_tensor = input_tensor.to(device)
        
        with torch.no_grad():
            predictions = model(input_tensor)
            
        pred = predictions[0]
        boxes = pred["boxes"].cpu().numpy()
        labels = pred["labels"].cpu().numpy()
        scores = pred["scores"].cpu().numpy()
        
        threshold = 0.5
        mask = scores >= threshold
        
        detections = []
        result_img_cv = img_cv.copy()
        
        for box, label, score in zip(boxes[mask], labels[mask], scores[mask]):
            class_name = COCO_CLASSES[label] if label < len(COCO_CLASSES) else f"class_{label}"
            detections.append({
                "class_name": class_name,
                "confidence": float(score),
                "box": box.tolist()
            })
            
            # 시각화 (OpenCV)
            x1, y1, x2, y2 = box.astype(int)
            color = (0, 255, 0) # Green
            cv2.rectangle(result_img_cv, (x1, y1), (x2, y2), color, 2)
            label_str = f"{class_name}: {score:.2f}"
            cv2.putText(result_img_cv, label_str, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
        # 3. 결과 이미지 인코딩 (Base64)
        _, buffer = cv2.imencode('.jpg', result_img_cv)
        result_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "original_image": original_base64,
            "result_image": result_base64,
            "detections": detections
        })
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)


# ----------------- 3. Face Verification 엔드포인트 -----------------
@app.post("/face-verify")
async def face_verify(img1: UploadFile = File(...), img2: UploadFile = File(...)):
    """두 사람의 이미지를 입력받아 동일 인물인지 여부 및 거리(유사도)를 반환합니다."""
    img1_path, img2_path = None, None
    try:
        # DeepFace.verify는 파일 경로나 OpenCV numpy 형식 등을 지원하므로 안전하게 임시파일 사용
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp1:
            tmp1.write(await img1.read())
            img1_path = tmp1.name
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp2:
            tmp2.write(await img2.read())
            img2_path = tmp2.name
            
        # 얼굴 인식 수행 (DeepFace 기본 distance metric=cosine, model=VGG-Face, 여기선 Facenet 적용해봄)
        result = DeepFace.verify(
            img1_path=img1_path, 
            img2_path=img2_path, 
            model_name="Facenet",
            enforce_detection=False  # 얼굴을 완벽하게 못찾아도 에러 대신 진행
        )
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 임시 파일 정리
        if img1_path and os.path.exists(img1_path):
            os.remove(img1_path)
        if img2_path and os.path.exists(img2_path):
            os.remove(img2_path)


# ----------------- 4. OCR 엔드포인트 -----------------
@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    """이미지 내의 텍스트를 인식하여 문구와 영역 좌표, 신뢰도를 반환합니다."""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img_cv is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
            
        if "ocr" not in models_cache:
            print("  [Lazy] Loading OCR model...")
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
            except AttributeError:
                pass
            reader = easyocr.Reader(['ko', 'en'], gpu=torch.cuda.is_available())
            models_cache["ocr"] = reader
            
        reader = models_cache["ocr"]
        
        # readtext returns: [(bbox, text, prob), ...]
        # bbox format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        results = reader.readtext(img_cv)
        
        formatted_results = []
        for (bbox, text, prob) in results:
            pts = [[int(pt[0]), int(pt[1])] for pt in bbox]
            formatted_results.append({
                "text": text,
                "confidence": float(prob),
                "box": pts
            })
            
        return JSONResponse(content={"texts": formatted_results})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------- 5. Pose Estimation 엔드포인트 -----------------
@app.post("/pose")
async def pose_estimation(file: UploadFile = File(...)):
    """사람이 포함된 이미지를 입력받아 관절(Keypoints) 정보와 Bounding Box를 반환합니다."""
    try:
        contents = await file.read()
        # YOLOv8 모델 입력으로 PIL Image 허용됨
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Lazy Loading for Pose
        if "pose" not in models_cache:
            print("  [Lazy] Loading Pose Estimation model...")
            pose_model = YOLO('yolov8n-pose.pt')
            models_cache["pose"] = pose_model
            
        model = models_cache["pose"]
        results = model(img)
        result = results[0]  # First image predictions
        
        # 데이터 파싱
        boxes = result.boxes.xyxy.cpu().numpy().tolist() if result.boxes else []
        scores = result.boxes.conf.cpu().numpy().tolist() if result.boxes else []
        classes = result.boxes.cls.cpu().numpy().tolist() if result.boxes else []
        
        keypoints_list = []
        if getattr(result, 'keypoints', None) is not None and result.keypoints.data is not None:
            # shape: (N, 17, 3), 3 represents (x, y, confidence)
            kpts_data = result.keypoints.data.cpu().numpy()
            for kpt in kpts_data:
                person_kpt = [{"x": float(kp[0]), "y": float(kp[1]), "confidence": float(kp[2])} for kp in kpt]
                keypoints_list.append(person_kpt)
        
        persons = []
        for i in range(len(boxes)):
            persons.append({
                "class": int(classes[i]),
                "confidence": float(scores[i]),
                "box": [float(b) for b in boxes[i]], # [x1, y1, x2, y2]
                "keypoints": keypoints_list[i] if i < len(keypoints_list) else []
            })
            
        return JSONResponse(content={"pose_estimations": persons})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------- 6. AI Palm Reader (손금 분석) -----------------
def analyze_palm_lines(img_cv):
    """
    OpenCV를 사용하여 손금의 주요 선들을 추출하고 분석합니다.
    """
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # 1. 엣지 강조를 위한 전처리
    # CLAHE (Contrast Limited Adaptive Histogram Equalization) 적용
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced_gray = clahe.apply(gray)
    
    # 2. 선 추출 (Ridge Detection 컨셉)
    # 가우시안 블러로 노이즈 제거 후 엣지 추출
    blurred = cv2.GaussianBlur(enhanced_gray, (5, 5), 0)
    
    # Adaptive Thresholding으로 선들을 이진화
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # 소형 노이즈 제거 (Morphology)
    kernel = np.ones((3,3), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # 3. 주요 라인 정의 및 점수화 (단순화된 모델)
    h, w = gray.shape
    
    # 결과 시각화용 이미지
    vis_img = img_cv.copy()
    
    # 가상의 손금 위치 기반 분석 (손바닥이 중앙에 있다고 가정)
    # 생명선 (곡선), 두뇌선 (중앙 가로), 감정선 (상단 가로) 점수 계산
    lines_info = {
        "life_line": {"name": "생명선", "score": 0, "color": (0, 0, 255)},    # Red
        "head_line": {"name": "두뇌선", "score": 0, "color": (0, 255, 0)},    # Green
        "heart_line": {"name": "감정선", "score": 0, "color": (255, 0, 0)}    # Blue
    }
    
    # 분석 로직 (픽셀 밀도 기반으로 간단하게 구현)
    # 실제 전문 알고리즘 대신 영역별 선 존재 확률을 계산
    life_roi = opening[int(h*0.4):int(h*0.9), int(w*0.1):int(w*0.5)]
    head_roi = opening[int(h*0.3):int(h*0.6), int(w*0.2):int(w*0.8)]
    heart_roi = opening[int(h*0.1):int(h*0.4), int(w*0.2):int(w*0.9)]
    
    lines_info["life_line"]["score"] = np.mean(life_roi) / 255
    lines_info["head_line"]["score"] = np.mean(head_roi) / 255
    lines_info["heart_line"]["score"] = np.mean(heart_roi) / 255
    
    # 시각화: ROI 영역 표시 (디버그용/재미용)
    cv2.ellipse(vis_img, (int(w*0.3), int(h*0.65)), (int(w*0.2), int(h*0.25)), 0, 0, 180, (0, 0, 255), 2)
    cv2.line(vis_img, (int(w*0.2), int(h*0.45)), (int(w*0.8), int(h*0.55)), (0, 255, 0), 2)
    cv2.line(vis_img, (int(w*0.2), int(h*0.25)), (int(w*0.8), int(h*0.2)), (255, 0, 0), 2)

    return lines_info, vis_img

def generate_fortune(lines_info):
    """분석된 수치를 바탕으로 운세 스토리를 생성합니다."""
    fortunes = []
    
    # 1. 생명선
    s_life = lines_info["life_line"]["score"]
    if s_life > 0.05:
        life_txt = "생명선이 뚜렷하고 길게 뻗어 있군요! 에너지가 넘치고 건강한 체질입니다. 장수하실 운세네요."
    else:
        life_txt = "생명선이 다소 연하거나 짧은 편입니다. 규칙적인 이완과 건강 관리에 조금 더 신경 쓰시면 운이 트일 거예요."
    fortunes.append({"category": "건강/생명운", "text": life_txt})

    # 2. 두뇌선
    s_head = lines_info["head_line"]["score"]
    if s_head > 0.1:
        head_txt = "두뇌선이 매우 선명합니다. 판단력이 빠르고 지적인 호기심이 강한 타입이시네요. 전문직 분야에서 성공할 가능성이 높습니다."
    else:
        head_txt = "창의적이고 직관적인 사고를 하시는 분입니다. 복잡한 계산보다는 예술이나 감성적인 분야에서 빛을 발하실 거예요."
    fortunes.append({"category": "지혜/성공운", "text": head_txt})

    # 3. 감정선
    s_heart = lines_info["heart_line"]["score"]
    if s_heart > 0.1:
        heart_txt = "감정선이 위쪽으로 시원하게 뻗어 있습니다. 매우 정이 많고 따뜻한 사람입니다. 인간관계에서 늘 사랑받는 존재가 되겠네요."
    else:
        heart_txt = "이성적이고 차분한 성격입니다. 감정에 휘둘리지 않고 중심을 잘 잡으시기에 주변 사람들에게 신뢰를 얻습니다."
    fortunes.append({"category": "애정/대인운", "text": heart_txt})

    return fortunes

@app.get("/palm", response_class=HTMLResponse)
async def palm_page(request: Request):
    """손금 서비스 메인 페이지를 반환합니다."""
    return templates.TemplateResponse("palm.html", {"request": request})

@app.post("/palm-read", response_class=HTMLResponse)
async def palm_read(request: Request, file: UploadFile = File(...)):
    """이미지를 받아 손금을 분석하고 결과를 반환합니다."""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_cv is None:
            raise HTTPException(status_code=400, detail="이미지 파일이 올바르지 않습니다.")

        # 1. 손금 분석 수행
        lines_info, vis_img = analyze_palm_lines(img_cv)
        
        # 2. 운세 스토리 생성
        fortunes = generate_fortune(lines_info)
        
        # 3. 이미지 인코딩
        _, buffer = cv2.imencode('.jpg', vis_img)
        vis_base64 = base64.b64encode(buffer).decode('utf-8')
        orig_base64 = base64.b64encode(contents).decode('utf-8')

        return templates.TemplateResponse("palm.html", {
            "request": request,
            "original_image": orig_base64,
            "result_image": vis_base64,
            "fortunes": fortunes,
            "analyzed": True
        })
    except Exception as e:
        return HTMLResponse(content=f"분석 중 오류가 발생했습니다: {str(e)}", status_code=500)

# 직접 실행 시 Uvicorn으로 서버 구동
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
