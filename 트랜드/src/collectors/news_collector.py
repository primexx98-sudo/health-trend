import requests
import logging
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

HEALTH_KEYWORDS = [
    "비타민", "영양제", "유산균", "오메가3", "콜라겐", "홍삼",
    "마그네슘", "건강기능식품", "프로바이오틱스", "글루타치온",
    "코엔자임", "루테인", "아연", "칼슘", "철분", "보충제",
    "크레아틴", "밀크시슬", "엽산", "비오틴", "NAD", "NMN",
    "면역", "항산화", "장건강", "피로회복", "식품의약품안전처"
]

EXCLUDE_KEYWORDS = [
    "패션", "헤어", "네일", "메이크업", "셀럽", "연예",
    "드라마", "영화", "아이돌", "세금", "부동산", "주식", "교육청"
]

QUERIES = [
    "코엔자임Q10 효능",
    "마그네슘 영양제",
    "글루타치온 건강",
    "유산균 장건강",
    "오메가3 효능",
    "비타민D 면역",
    "건강기능식품 성분",
    "NMN NAD 영양제",
    "식품의약품안전처 건강기능식품",
    "식품의약품안전처 영양제 성분",
]

def is_recent(pub_date_str, days=30):
    try:
        dt = parsedate_to_datetime(pub_date_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return dt > cutoff
    except Exception:
        return True

def is_relevant(title, desc):
    combined = title + " " + desc
    if any(ex in combined for ex in EXCLUDE_KEYWORDS):
        return False
    return any(kw in title for kw in HEALTH_KEYWORDS) or \
           any(kw in desc for kw in HEALTH_KEYWORDS)

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

def collect_all_news():
    all_news, seen = [], set()

    for query in QUERIES:
        items = get_naver_news(query, display=10)
        for item in items:
            title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
            desc = item["description"].replace("<b>", "").replace("</b>", "")
            pub_date = item.get("pubDate", "")

            if title in seen:
                continue
            if not is_recent(pub_date, days=30):
                continue
            if not is_relevant(title, desc):
                continue

            seen.add(title)
            all_news.append({
                "title": title,
                "link": item.get("originallink") or item["link"],
                "pubDate": pub_date,
                "description": desc
            })

    logger.info(f"뉴스 {len(all_news)}건 수집 완료 (30일 이내)")
    return {"news": all_news[:12], "mfds": []}
