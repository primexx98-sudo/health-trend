import requests
import logging
from urllib.parse import quote
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

HEALTH_KEYWORDS = [
    "비타민", "영양제", "유산균", "오메가3", "콜라겐", "홍삼",
    "마그네슘", "건강기능식품", "프로바이오틱스", "글루타치온",
    "코엔자임", "루테인", "아연", "칼슘", "철분", "보충제",
    "단백질", "크레아틴", "밀크시슬", "엽산", "비오틴",
    "NAD", "NMN", "면역", "항산화", "장건강", "피로회복"
]

EXCLUDE_KEYWORDS = [
    "패션", "뷰티", "헤어", "네일", "메이크업", "셀럽", "연예",
    "드라마", "영화", "아이돌", "세금", "부동산", "주식", "교육청"
]

QUERIES = [
    ("코엔자임Q10 건강", 8),
    ("마그네슘 영양제 효능", 8),
    ("글루타치온 효과", 8),
    ("유산균 장건강", 8),
    ("오메가3 심혈관", 8),
    ("비타민D 면역", 8),
    ("건강기능식품 성분", 8),
    ("NMN NAD 항노화", 5),
]

def get_naver_news(query, display=10):
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {"query": quote(query), "display": display, "start": 1, "sort": "date"}
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        logger.error(f"뉴스 수집 실패 [{query}]: {e}")
        return []

def is_relevant(title, desc):
    combined = title + desc
    if any(ex in combined for ex in EXCLUDE_KEYWORDS):
        return False
    if any(kw in title for kw in HEALTH_KEYWORDS):
        return True
    if any(kw in desc for kw in HEALTH_KEYWORDS):
        return True
    return False

def collect_all_news():
    all_news, seen = [], set()

    for query, display in QUERIES:
        items = get_naver_news(query, display)
        for item in items:
            title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
            desc = item["description"].replace("<b>", "").replace("</b>", "")
            if title not in seen and is_relevant(title, desc):
                seen.add(title)
                all_news.append({
                    "title": title,
                    "link": item.get("originallink") or item["link"],
                    "pubDate": item["pubDate"],
                    "description": desc
                })

    all_news = all_news[:12]
    logger.info(f"뉴스 {len(all_news)}건 수집 완료")
    return {"news": all_news, "mfds": []}
