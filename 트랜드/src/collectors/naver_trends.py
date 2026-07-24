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


def get_rising_from_previous(today_data, prev_data, top_n=8):
    """전일 대비 검색량(ratio) 증가폭이 큰 키워드 추출 — 급상승 키워드 대체 산출식.

    Google Trends(pytrends)가 2026-07-21부터 GitHub Actions IP에서 상시 429를 반환해
    (글로벌 트랜드 폐지와 동일 원인) get_top_keywords()가 이미 수집한 국내 인기순위 20개의
    전일 대비 증감만으로 계산 — 추가 API 호출 없이 naver_prev_data 스냅샷 재사용.
    """
    if not prev_data:
        return []
    prev_ratio = {d["keyword"]: d["ratio"] for d in prev_data}
    rising = []
    for d in today_data:
        prev = prev_ratio.get(d["keyword"])
        if prev is None:
            continue
        delta = d["ratio"] - prev
        if delta > 0:
            rising.append({"keyword": d["keyword"], "value": round(delta, 1)})
    rising.sort(key=lambda r: r["value"], reverse=True)
    return rising[:top_n]
