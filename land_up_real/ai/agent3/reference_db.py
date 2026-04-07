import json

# Agent 3 내부 가동용 참조 데이터베이스 (Mock DB)
# - 실제 운영 시 이 모듈에서 외부 VectorDB(Pinecone/Milvus)나 RDB(Supabase) API를 호출하여 최적의 부스 모듈을 긁어옴
# - 여기서는 헬로키티(산리오) 팝업 관례에 따라 필수(Required) 오브젝트 리스트와 규격을 반환

def get_pop_up_reference_objects(theme_name: str = "generic") -> list:
    """
    주어진 테마에 속하는 팝업스토어 관례적 배치 참조 객체들의 목록을 리턴합니다.
    theme_name이 'hello_kitty' 계열이면 산리오 조형물을, 아니면 범용 조형물을 반환합니다.
    """
    # 소문자 변환 및 한글 대응
    theme_clean = str(theme_name).lower().replace(" ", "")
    
    if "hello" in theme_clean or "kitty" in theme_clean or "키티" in theme_clean or "산리오" in theme_clean:
        return [
            {
                "object_id": "hello_kitty_statue_main",
                "object_type": "statue",
                "needs_clearspace": True,
                "dimensions_mm": {"width": 1000, "height": 1200},
                "importance": 1
            },
            {
                "object_id": "my_melody_photo_zone",
                "object_type": "photo_zone",
                "needs_clearspace": False,
                "dimensions_mm": {"width": 1500, "height": 1500},
                "importance": 2
            },
            {
                "object_id": "pompompurin_island",
                "object_type": "statue",
                "needs_clearspace": False,
                "dimensions_mm": {"width": 1200, "height": 1200},
                "importance": 3
            },
            {
                "object_id": "merchandise_cashier",
                "object_type": "facility",
                "needs_clearspace": False,
                "dimensions_mm": {"width": 2500, "height": 800},
                "importance": 4
            }
        ]
    
    # 기본 폴백: 일반 팝업스토어용 범용 가구 세트 (어떤 브랜드든 사용 가능)
    return [
        {
            "object_id": "brand_logo_main_statue",
            "object_type": "statue",
            "needs_clearspace": True,
            "dimensions_mm": {"width": 1200, "height": 1200},
            "importance": 1
        },
        {
            "object_id": "brand_concept_photo_zone",
            "object_type": "photo_zone",
            "needs_clearspace": False,
            "dimensions_mm": {"width": 2000, "height": 1000},
            "importance": 2
        },
        {
            "object_id": "brand_merchandise_shelf",
            "object_type": "facility",
            "needs_clearspace": False,
            "dimensions_mm": {"width": 1800, "height": 600},
            "importance": 3
        },
        {
            "object_id": "mobile_information_kiosk",
            "object_type": "facility",
            "needs_clearspace": False,
            "dimensions_mm": {"width": 800, "height": 800},
            "importance": 4
        }
    ]

if __name__ == "__main__":
    db = get_pop_up_reference_objects()
    print("📚 [Reference DB] 가상의 헬로키티 팝업 조형물 평균 사이즈 로딩 완료!")
    for item in db:
        print(f" - {item['object_id']}: {item['dimensions_mm']['width']}x{item['dimensions_mm']['height']}mm")
