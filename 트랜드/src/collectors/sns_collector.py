import requests
import logging
from urllib.parse import quote
from collections import Counter
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, HEALTH_KEYWORDS

logger = logging.getLogger(__name__)

def search_naver_blog(query, display=10):
    url = "https://openapi.naver.com/v1/search/blog.json"
    params = {"query": quote(query), "display": display, "sort": "date"}
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        logger.error(f"블로그 수집 실패 [{query}]: {e}")
        return []

def get_sns_keywords():
    keyword_counter = Counter()

    for kw in HEALTH_KEYWORDS:
        items = search_naver_blog(kw, display=10)
        if items:
            keyword_counter[kw] += len(items)
            for item in items:
                text = (item.get("title", "") + " " + item.get("description", ""))
                text = text.replace("<b>", "").replace("</b>", "")
                for other_kw in HEALTH_KEYWORDS:
                    if other_kw in text and other_kw != kw:
                        keyword_counter[other_kw] += 1

    top_keywords = [
        {"tag": f"#{kw}", "count": cnt}
        for kw, cnt in keyword_counter.most_common(20)
        if cnt > 0
    ]
    logger.info(f"SNS 키워드 {len(top_keywords)}개 추출 완료")
    return top_keywords
