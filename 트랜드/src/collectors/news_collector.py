import requests
import logging
from urllib.parse import quote
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

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
        items = resp.json().get("items", [])
        cleaned = []
        for item in items:
            title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
            desc = item["description"].replace("<b>", "").replace("</b>", "")
            cleaned.append({
                "title": title,
                "link": item.get("originallink") or item["link"],
                "pubDate": item["pubDate"],
                "description": desc
            })
        return cleaned
    except Exception as e:
        logger.error(f"뉴스 수집 실패 [{query}]: {e}")
        return []

def collect_all_news():
    queries = [
        "코엔자임Q10 효능",
        "마그네슘 영양제",
        "글루타치온 효과",
        "유산균 건강",
        "오메가3 효능",
        "건강기능식품 추천 2026"
    ]
    all_news, seen = [], set()
    for q in queries:
        for item in get_naver_news(q, display=5):
            if item["title"] not in seen:
                seen.add(item["title"])
                all_news.append(item)
    logger.info(f"뉴스 {len(all_news)}건 수집 완료")
    return {"news": all_news[:10], "mfds": []}
