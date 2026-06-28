import requests
import json
import logging
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_CATEGORY_ID, HEALTH_KEYWORDS

logger = logging.getLogger(__name__)

def get_shopping_trend():
    """네이버 쇼핑인사이트 - 건강식품 인기 검색어 수집"""
    url = "https://openapi.naver.com/v1/datalab/shopping/categories"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "category": [{"name": "건강식품", "param": [NAVER_CATEGORY_ID]}],
        "device": "",
        "ages": [],
        "gender": ""
    }
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"네이버 쇼핑 트랜드 수집 실패: {e}")
        return None

def get_keyword_trend(keywords):
    """네이버 데이터랩 - 키워드별 검색 트랜드 비교"""
    url = "https://openapi.naver.com/v1/datalab/search"
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords[:5]]
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": "date",
        "keywordGroups": groups,
        "device": "",
        "ages": [],
        "gender": ""
    }
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"네이버 키워드 트랜드 수집 실패: {e}")
        return None

def get_top_keywords():
    """키워드별 최근 검색량 순위 반환"""
    results = []
    batch_size = 5
    keyword_batches = [HEALTH_KEYWORDS[i:i+batch_size] for i in range(0, min(len(HEALTH_KEYWORDS), 20), batch_size)]

    for batch in keyword_batches:
        data = get_keyword_trend(batch)
        if data and "results" in data:
            for item in data["results"]:
                keyword = item["title"]
                if item["data"]:
                    latest = item["data"][-1]["ratio"]
                    results.append({"keyword": keyword, "ratio": latest})

    results.sort(key=lambda x: x["ratio"], reverse=True)
    logger.info(f"네이버 키워드 {len(results)}개 수집 완료")
    return results
