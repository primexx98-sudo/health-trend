import requests
import logging
from urllib.parse import quote
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

HEALTH_FILTER = ["비타민", "영양제", "유산균", "오메가", "콜라겐", "홍삼", "마그네슘",
                 "건강기능", "식약처", "프로바이오틱스", "글루타치온", "코엔자임",
                 "루테인", "아연", "칼슘", "철분", "엽산", "크레아틴", "단백질", "보충제"]

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
            if any(kw in title for kw in HEALTH_FILTER):
                cleaned.append({
                    "title": title,
                    "link": item["originallink"] or item["link"],
                    "pubDate": item["pubDate"],
                    "description": item["description"].replace("<b>", "").replace("</b>", "")
                })
        return cleaned
    except Exception as e:
        logger.error(f"뉴스 수집 실패 [{query}]: {e}")
        return []

def get_mfds_rss():
    url = "https://www.mfds.go.kr/r
    try:
        import xml.etree.ElementTre
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.encoding = "utf-8"
        root = ET.fromstring(resp.text)
        items = []
        for item in root.findall(".//item")[:5]:
            items.append({
                "title": item.findtext("title", ""),
                "link": item.findte
                "pubDate": item.findtext("pubDate", "")
            })
        return items
    except Exception as e:
        logger.error(f"식약처 RSS 수집 실패: {e}")
        return []

def collect_all_news():
    queries = [
        "건강기능식품 효능", "영양
        "유산균 연구", "오메가3 건강", "식약처 건강기능식품"
    ]
    all_news, seen = [], set()
    for q in queries:
        for item in get_naver_news(q, display=8):
            if item["title"] not in
                seen.add(item["title"])
                all_news.append(ite
    logger.info(f"뉴스 {len(all_news)}건 수집 완료")
    return {"news": all_news[:10],
