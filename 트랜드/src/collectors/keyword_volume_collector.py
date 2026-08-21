import base64
import hashlib
import hmac
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.naver.com"
_URI = "/keywordstool"


def _signature(secret_key, timestamp, method, uri):
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _headers(customer_id, access_license, secret_key, method, uri):
    timestamp = str(int(time.time() * 1000))
    return {
        "X-Timestamp": timestamp,
        "X-API-KEY": access_license,
        "X-Customer": customer_id,
        "X-Signature": _signature(secret_key, timestamp, method, uri),
    }


def _parse_count(v):
    """네이버 API가 소량 구간을 "< 10" 문자열로 반환하는 경우가 있어 대표값(5)으로 치환."""
    if isinstance(v, str):
        return 5 if v.strip().startswith("<") else 0
    return int(v) if v is not None else 0


def get_keyword_volumes(keywords):
    """키워드 리스트의 월간 PC/모바일 검색수(절대값, 네이버 검색광고 키워드도구)를 조회한다.
    최대 5개씩 배치 처리. 반환: {원본키워드: {"pc":int,"mobile":int,"total":int}} —
    API가 못 찾은 키워드는 결과에서 빠진다. 인증정보 미설정 시 빈 dict 반환."""
    customer_id = os.environ.get("NAVER_CUSTOMER_ID")
    access_license = os.environ.get("NAVER_ACCESS_LICENSE")
    secret_key = os.environ.get("NAVER_SECRET_KEY")
    if not (customer_id and access_license and secret_key):
        logger.warning("네이버 검색광고 API 인증정보 미설정 — 검색량 조회 건너뜀")
        return {}

    result = {}
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        # 네이버 API는 공백을 무시하고 정규화하므로 원본 키워드를 결과에 다시 매핑해야 함
        norm_map = {kw.replace(" ", ""): kw for kw in batch}
        hint = ",".join(norm_map.keys())
        headers = _headers(customer_id, access_license, secret_key, "GET", _URI)
        try:
            resp = requests.get(
                BASE_URL + _URI,
                params={"hintKeywords": hint, "showDetail": 1},
                headers=headers, timeout=10,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            for row in resp.json().get("keywordList", []):
                rel = str(row.get("relKeyword", "")).replace(" ", "")
                if rel not in norm_map:
                    continue  # 연관키워드 확장분은 사용하지 않음 — 요청한 키워드만 채택
                orig = norm_map[rel]
                pc = _parse_count(row.get("monthlyPcQcCnt"))
                mobile = _parse_count(row.get("monthlyMobileQcCnt"))
                result[orig] = {"pc": pc, "mobile": mobile, "total": pc + mobile}
        except Exception as e:
            logger.warning(f"검색광고 API 조회 실패 [{batch}]: {e}")
        time.sleep(0.2)
    logger.info(f"검색광고 키워드 검색량 {len(result)}/{len(keywords)}건 조회 완료")
    return result
