import os

# GitHub Actions Secrets에서 자동으로 읽어옴
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "여기에_Client_ID_입력")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "여기에_Client_Secret_입력")

HEALTH_KEYWORDS = [
    "비타민", "유산균", "오메가3", "콜라겐", "홍삼",
    "프로바이오틱스", "마그네슘", "아연", "철분", "칼슘",
    "루테인", "밀크시슬", "가르시니아", "NAD", "코엔자임Q10",
    "글루타치온", "비오틴", "엽산", "크레아틴", "단백질보충제"
]

NAVER_CATEGORY_ID = "50000008"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "docs")
LOG_DIR = os.path.join(BASE_DIR, "logs")
