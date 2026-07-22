import os

# GitHub Actions Secrets에서 자동으로 읽어옴
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "여기에_Client_ID_입력")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "여기에_Client_Secret_입력")

# 앞 20개는 국내 인기순위(naver_trends.get_top_keywords)가 그대로 사용하는 순서 — 변경 시 순위 결과가 바뀜
HEALTH_KEYWORDS = [
    "비타민", "유산균", "오메가3", "콜라겐", "홍삼",
    "프로바이오틱스", "마그네슘", "아연", "철분", "칼슘",
    "루테인", "밀크시슬", "가르시니아", "NAD", "코엔자임Q10",
    "글루타치온", "비오틴", "엽산", "크레아틴", "단백질보충제",
    # 아래는 뉴스 필터링·SNS 집계 커버리지 확장을 위해 추가된 항목 (news_collector.py에서 이관)
    "건강기능식품", "영양제", "보충제", "기능성식품", "서플리먼트",
    "다이어트보조제", "스포츠영양제", "기능성건강식품",
    "NMN", "레스베라트롤", "커큐민", "베타글루칸", "아스타잔틴",
    "쏘팔메토", "크릴오일", "스피루리나", "클로렐라", "강황",
    "포스파티딜세린", "글루코사민", "콘드로이틴", "히알루론산", "보스웰리아",
    "인삼", "흑삼", "산양삼", "홍경천", "바나바", "여주추출물",
    "HMB", "L-카르니틴", "아르기닌", "퀘르세틴", "베르베린",
    "GABA", "테아닌", "멜라토닌",
    "면역력", "항산화", "장건강", "피로회복",
    "콜레스테롤", "체지방", "수면 개선",
    "혈당", "혈압", "뼈건강", "관절건강", "눈건강", "기억력", "인지기능",
    "갱년기", "체중관리",
    "개별인정", "개별인정형", "고시형", "기능성 원료", "개정고시", "GMP",
    "식품의약품안전처",
]

NAVER_CATEGORY_ID = "50000008"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "docs")
LOG_DIR = os.path.join(BASE_DIR, "logs")
