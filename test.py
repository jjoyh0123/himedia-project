"""
GPU 경량 이미지 분류 모델 벤치마크 테스트 스크립트
=================================================
대표적인 경량 이미지 분류 모델들의 GPU 추론 성능을 비교합니다.

테스트 모델:
  - MobileNetV2
  - MobileNetV3 Small
  - EfficientNet-B0
  - ResNet-18
  - ShuffleNet V2 x1.0
  - SqueezeNet 1.1

측정 항목:
  - 모델 파라미터 수
  - 모델 크기 (MB)
  - GPU 메모리 사용량
  - 단일 추론 시간
  - 배치 추론 시간 (throughput)
  - 워밍업 후 평균 추론 시간
"""

import time
import os
import sys
from collections import OrderedDict

import torch
import torch.nn as nn
import torchvision.models as models
from torchvision import transforms
from PIL import Image
import urllib.request


# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
BATCH_SIZE = 32
NUM_WARMUP = 10       # 워밍업 반복 횟수
NUM_ITERATIONS = 100  # 측정 반복 횟수
INPUT_SIZE = 224      # 입력 이미지 크기
NUM_CLASSES = 1000    # ImageNet 클래스 수


# ──────────────────────────────────────────────
# 모델 정의
# ──────────────────────────────────────────────
def get_models():
    """테스트할 경량 모델들을 반환합니다."""
    model_dict = OrderedDict({
        "MobileNetV2": models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1),
        "MobileNetV3-Small": models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1),
        "EfficientNet-B0": models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1),
        "ResNet-18": models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1),
        "ShuffleNetV2-x1.0": models.shufflenet_v2_x1_0(weights=models.ShuffleNet_V2_X1_0_Weights.IMAGENET1K_V1),
        "SqueezeNet-1.1": models.squeezenet1_1(weights=models.SqueezeNet1_1_Weights.IMAGENET1K_V1),
    })
    return model_dict


# ──────────────────────────────────────────────
# 유틸리티 함수
# ──────────────────────────────────────────────
def count_parameters(model):
    """모델의 총 파라미터 수를 반환합니다."""
    return sum(p.numel() for p in model.parameters())


def get_model_size_mb(model):
    """모델의 크기를 MB 단위로 반환합니다."""
    param_size = 0
    for param in model.parameters():
        param_size += param.nelement() * param.element_size()
    buffer_size = 0
    for buffer in model.buffers():
        buffer_size += buffer.nelement() * buffer.element_size()
    return (param_size + buffer_size) / (1024 ** 2)


def get_gpu_memory_mb():
    """현재 GPU 메모리 사용량을 MB로 반환합니다."""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / (1024 ** 2)
    return 0.0


def download_sample_image():
    """테스트용 샘플 이미지를 다운로드합니다."""
    img_path = os.path.join(os.path.dirname(__file__), "sample_image.jpg")
    if not os.path.exists(img_path):
        print("📥 샘플 이미지 다운로드 중...")
        url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/1200px-Cat_November_2010-1a.jpg"
        try:
            urllib.request.urlretrieve(url, img_path)
            print(f"   ✅ 다운로드 완료: {img_path}")
        except Exception as e:
            print(f"   ⚠️ 다운로드 실패: {e}")
            print("   → 랜덤 텐서로 대체합니다.")
            return None
    return img_path


def load_imagenet_labels():
    """ImageNet 클래스 레이블을 로드합니다."""
    labels_path = os.path.join(os.path.dirname(__file__), "imagenet_labels.txt")
    if not os.path.exists(labels_path):
        url = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
        try:
            urllib.request.urlretrieve(url, labels_path)
        except Exception:
            return None
    with open(labels_path, "r") as f:
        labels = [line.strip() for line in f.readlines()]
    return labels


def preprocess_image(img_path):
    """이미지를 모델 입력에 맞게 전처리합니다."""
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(INPUT_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
    ])
    img = Image.open(img_path).convert("RGB")
    return transform(img).unsqueeze(0)  # (1, 3, 224, 224)


# ──────────────────────────────────────────────
# 벤치마크 함수
# ──────────────────────────────────────────────
def benchmark_latency(model, device, input_tensor):
    """단일 이미지 추론 지연 시간을 측정합니다."""
    model.eval()
    x = input_tensor.to(device)

    # 워밍업
    with torch.no_grad():
        for _ in range(NUM_WARMUP):
            _ = model(x)

    # GPU 동기화
    if device.type == "cuda":
        torch.cuda.synchronize()

    # 측정
    times = []
    with torch.no_grad():
        for _ in range(NUM_ITERATIONS):
            if device.type == "cuda":
                torch.cuda.synchronize()
            start = time.perf_counter()
            _ = model(x)
            if device.type == "cuda":
                torch.cuda.synchronize()
            end = time.perf_counter()
            times.append((end - start) * 1000)  # ms

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    return avg_time, min_time, max_time


def benchmark_throughput(model, device, batch_size=BATCH_SIZE):
    """배치 처리 처리량(throughput)을 측정합니다."""
    model.eval()
    x = torch.randn(batch_size, 3, INPUT_SIZE, INPUT_SIZE).to(device)

    # 워밍업
    with torch.no_grad():
        for _ in range(NUM_WARMUP):
            _ = model(x)

    if device.type == "cuda":
        torch.cuda.synchronize()

    # 측정
    with torch.no_grad():
        if device.type == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        for _ in range(NUM_ITERATIONS):
            _ = model(x)
        if device.type == "cuda":
            torch.cuda.synchronize()
        end = time.perf_counter()

    total_time = end - start
    throughput = (NUM_ITERATIONS * batch_size) / total_time
    return throughput, total_time


def run_inference(model, device, input_tensor, labels=None):
    """단일 이미지에 대한 추론 결과를 반환합니다."""
    model.eval()
    x = input_tensor.to(device)

    with torch.no_grad():
        output = model(x)
        probs = torch.nn.functional.softmax(output[0], dim=0)
        top5_probs, top5_indices = torch.topk(probs, 5)

    results = []
    for i in range(5):
        idx = top5_indices[i].item()
        prob = top5_probs[i].item()
        label = labels[idx] if labels and idx < len(labels) else f"class_{idx}"
        results.append((label, prob))
    return results


# ──────────────────────────────────────────────
# 출력 포맷팅
# ──────────────────────────────────────────────
def print_header():
    """헤더를 출력합니다."""
    print()
    print("=" * 80)
    print("🚀 GPU 경량 이미지 분류 모델 벤치마크 테스트")
    print("=" * 80)


def print_system_info(device):
    """시스템 정보를 출력합니다."""
    print()
    print("📋 시스템 정보")
    print("-" * 50)
    print(f"  Python     : {sys.version.split()[0]}")
    print(f"  PyTorch    : {torch.__version__}")
    print(f"  CUDA 사용  : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  CUDA 버전  : {torch.version.cuda}")
        print(f"  GPU 이름   : {torch.cuda.get_device_name(0)}")
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"  GPU 메모리 : {gpu_mem:.1f} GB")
    print(f"  디바이스   : {device}")
    print(f"  배치 크기  : {BATCH_SIZE}")
    print(f"  측정 횟수  : {NUM_ITERATIONS}")
    print()


def print_model_info(name, model):
    """모델 기본 정보를 출력합니다."""
    params = count_parameters(model)
    size_mb = get_model_size_mb(model)
    print(f"  파라미터 수  : {params:>12,} ({params / 1e6:.2f}M)")
    print(f"  모델 크기    : {size_mb:>12.2f} MB")


def print_benchmark_result(avg_ms, min_ms, max_ms, throughput, gpu_mem_mb):
    """벤치마크 결과를 출력합니다."""
    print(f"  평균 추론    : {avg_ms:>12.2f} ms")
    print(f"  최소 추론    : {min_ms:>12.2f} ms")
    print(f"  최대 추론    : {max_ms:>12.2f} ms")
    print(f"  처리량       : {throughput:>12.1f} img/s (batch={BATCH_SIZE})")
    print(f"  GPU 메모리   : {gpu_mem_mb:>12.2f} MB")


def print_inference_result(top5):
    """추론 결과(Top-5)를 출력합니다."""
    print(f"  Top-5 예측:")
    for rank, (label, prob) in enumerate(top5, 1):
        bar = "█" * int(prob * 30)
        print(f"    {rank}. {label:<25s} {prob:6.2%} {bar}")


def print_summary_table(results):
    """전체 결과 비교 요약 테이블을 출력합니다."""
    print()
    print("=" * 80)
    print("📊 결과 비교 요약")
    print("=" * 80)

    # 헤더
    header = f"{'모델':<20s} {'파라미터':>10s} {'크기(MB)':>10s} {'추론(ms)':>10s} {'처리량':>12s} {'GPU(MB)':>10s}"
    print(header)
    print("-" * 80)

    for r in results:
        row = (
            f"{r['name']:<20s} "
            f"{r['params'] / 1e6:>9.2f}M "
            f"{r['size_mb']:>10.2f} "
            f"{r['avg_ms']:>10.2f} "
            f"{r['throughput']:>10.1f}/s "
            f"{r['gpu_mem_mb']:>10.2f}"
        )
        print(row)

    print("-" * 80)

    # 최고 성능 모델 하이라이트
    fastest = min(results, key=lambda x: x["avg_ms"])
    smallest = min(results, key=lambda x: x["size_mb"])
    highest_tp = max(results, key=lambda x: x["throughput"])

    print()
    print("🏆 최고 성능 하이라이트:")
    print(f"  ⚡ 가장 빠른 추론  : {fastest['name']} ({fastest['avg_ms']:.2f} ms)")
    print(f"  📦 가장 작은 모델  : {smallest['name']} ({smallest['size_mb']:.2f} MB)")
    print(f"  🔥 최고 처리량     : {highest_tp['name']} ({highest_tp['throughput']:.1f} img/s)")
    print()


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    print_header()

    # 디바이스 설정
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        print("⚠️  CUDA GPU가 감지되지 않았습니다. CPU로 실행합니다.")
        device = torch.device("cpu")

    print_system_info(device)

    # 샘플 이미지 준비
    img_path = download_sample_image()
    labels = load_imagenet_labels()

    if img_path and os.path.exists(img_path):
        input_tensor = preprocess_image(img_path)
        use_real_image = True
        print(f"🖼️  테스트 이미지: {img_path}")
    else:
        input_tensor = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE)
        use_real_image = False
        print("🖼️  테스트 이미지: 랜덤 텐서 (dummy)")

    print()

    # 모델 로드 및 테스트
    model_dict = get_models()
    results = []

    for idx, (name, model) in enumerate(model_dict.items(), 1):
        print(f"{'─' * 80}")
        print(f"[{idx}/{len(model_dict)}] 🔍 {name}")
        print(f"{'─' * 80}")

        # 모델 정보
        print_model_info(name, model)

        # GPU로 이동
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats()
            mem_before = torch.cuda.memory_allocated()

        model = model.to(device)

        if device.type == "cuda":
            mem_after = torch.cuda.memory_allocated()
            gpu_mem_mb = (mem_after - mem_before) / (1024 ** 2)
        else:
            gpu_mem_mb = 0.0

        # 추론 테스트
        if use_real_image:
            top5 = run_inference(model, device, input_tensor, labels)
            print_inference_result(top5)

        # 벤치마크: 지연 시간
        print(f"\n  ⏱️  지연 시간 측정 중 ({NUM_ITERATIONS}회)...")
        avg_ms, min_ms, max_ms = benchmark_latency(model, device, input_tensor)

        # 벤치마크: 처리량
        print(f"  ⏱️  처리량 측정 중 (batch={BATCH_SIZE}, {NUM_ITERATIONS}회)...")
        throughput, total_time = benchmark_throughput(model, device)

        print()
        print_benchmark_result(avg_ms, min_ms, max_ms, throughput, gpu_mem_mb)

        # 결과 저장
        results.append({
            "name": name,
            "params": count_parameters(model),
            "size_mb": get_model_size_mb(model),
            "avg_ms": avg_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "throughput": throughput,
            "gpu_mem_mb": gpu_mem_mb,
        })

        # GPU 메모리 정리
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

        print()

    # 요약 테이블 출력
    print_summary_table(results)

    print("✅ 벤치마크 완료!")
    print()


if __name__ == "__main__":
    main()
