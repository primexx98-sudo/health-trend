import requests
import logging
from urllib.parse import quote
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

def get_naver_news(query="건강기능식품", display=10):
    """네이버 뉴스 검색 API"""
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {
        "query": quote(query),
        "display": display,
        "start": 1,
        "sort": "date"
    }
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
            cleaned.append({
                "title": title,
                "link": item["link"],
                "pubDate": item["pubDate"],
                "description": item["description"].replace("<b>", "").replace("</b>", "")
            })
        logger.info(f"뉴스 {len(cleaned)}건 수집 완료 [{query}]")
        return cleaned
    except Exception as e:
        logger.error(f"뉴스 수집 실패: {e}")
        return []

def get_mfds_rss():
    """식품의약품안전처 RSS 피드 수집"""
    url = "https://www.mfds.go.kr/rss/rss_01.do"
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.encoding = "utf-8"
        root = ET.fromstring(resp.text)
        items = []
        for item in root.findall(".//item")[:5]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pubdate = item.findtext("pubDate", "")
            items.append({"title": title, "link": link, "pubDate": pubdate})
        logger.info(f"식약처 공지 {len(items)}건 수집 완료")
        return items
    except Exception as e:
        logger.error(f"식약처 RSS 수집 실패: {e}")
        return []

def collect_all_news():
    queries = ["건강기능식품", "영양제 트랜드", "건강보조제"]
    all_news = []
    seen = set()
    for q in queries:
        for item in get_naver_news(q, display=5):
            if item["title"] not in seen:
                seen.add(item["title"])
                all_news.append(item)
    mfds = get_mfds_rss()
    return {"news": all_news[:10], "mfds": mfds}
