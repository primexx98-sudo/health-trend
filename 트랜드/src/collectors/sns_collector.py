import requests
import logging
from urllib.parse import quote
from collections import Counter
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, HEALTH_KEYWORDS

logger = logging.getLogger(__name__)

def search_naver_blog(query, display=20):
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

def extract_hashtags(text):
    return re.findall(r"#(\w+)", text)

def get_sns_keywords():
    """네이버 블로그 기반 SNS 화제 키워드 추출"""
    keyword_counter = Counter()

    for kw in HEALTH_KEYWORDS[:10]:
        items = search_naver_blog(f"#{kw} 영양제", display=10)
        for item in items:
            tags = extract_hashtags(item.get("description", ""))
            for tag in tags:
                if any(health_kw in tag for health_kw in ["비타민", "영양", "건강", "유산균", "오메가", "콜라겐", "홍삼", "단백질", "보충제", "프로바이오"]):
                    keyword_counter[tag] += 1

        for kw_name in HEALTH_KEYWORDS:
            if kw_name in item.get("description", "") or kw_name in item.get("title", ""):
                keyword_counter[f"#{kw_name}"] += 1

    top_keywords = [{"tag": f"#{kw}", "count": cnt} for kw, cnt in keyword_counter.most_common(20)]
    logger.info(f"SNS 키워드 {len(top_keywords)}개 추출 완료")
    return top_keywords
