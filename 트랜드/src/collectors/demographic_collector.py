import json
import logging
import os
import sys
from datetime import datetime, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

_URL = "https://openapi.naver.com/v1/datalab/search"

# 네이버 데이터랩 연령대 코드(1:0-12,2:13-18,3:19-24,4:25-29,5:30-34,6:35-39,
# 7:40-44,8:45-49,9:50-54,10:55-59,11:60+)를 10년 단위 4개 구간으로 묶어 사용 —
# 급상승 리포트 카드에 "40대 여성 검색량↑" 처럼 간단히 표시하기 위한 단순화.
_AGE_BUCKETS = [
    ("20대", ["3", "4"]),
    ("30대", ["5", "6"]),
    ("40대", ["7", "8"]),
    ("50대+", ["9", "10", "11"]),
]
_GENDERS = ["m", "f"]


def _headers():
    return {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type": "application/json",
    }


def _post(payload):
    try:
        resp = requests.post(_URL, headers=_headers(), data=json.dumps(payload), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"데이터랩 조회 실패: {e}")
        return None


def get_one_year_trend(keyword):
    """최근 1년치 월별 검색 추이(상대지수) — 급상승 리포트 카드의 1년 쿼리 그래프용."""
    end = datetime.now()
    start = end - timedelta(days=365)
    payload = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": "month",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
        "device": "", "ages": [], "gender": "",
    }
    data = _post(payload)
    if not data or not data.get("results"):
        return []
    return [{"period": d["period"], "ratio": d["ratio"]} for d in data["results"][0].get("data", [])]


def get_demographic_breakdown(keyword):
    """연령대x성별 조합별 검색 비중(최근 3개월 평균 상대지수)을 조회해 성별/연령 막대와
    가장 비중이 큰 세그먼트 라벨을 함께 반환한다. 4연령대 x 2성별 = 8회 API 호출."""
    end = datetime.now()
    start = end - timedelta(days=90)
    bars = []
    top = None
    for age_label, age_codes in _AGE_BUCKETS:
        row = {"age": age_label}
        for gender_code in _GENDERS:
            payload = {
                "startDate": start.strftime("%Y-%m-%d"),
                "endDate": end.strftime("%Y-%m-%d"),
                "timeUnit": "month",
                "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
                "device": "", "ages": age_codes, "gender": gender_code,
            }
            data = _post(payload)
            avg_ratio = 0
            if data and data.get("results"):
                points = data["results"][0].get("data", [])
                if points:
                    avg_ratio = sum(p["ratio"] for p in points) / len(points)
            row[gender_code] = round(avg_ratio, 1)
            gender_label = "남성" if gender_code == "m" else "여성"
            if avg_ratio > 0 and (top is None or avg_ratio > top[0]):
                top = (avg_ratio, age_label, gender_label)
        bars.append(row)
    top_label = f"{top[1]} {top[2]} 검색량↑" if top else None
    return {"bars": bars, "top_label": top_label}
