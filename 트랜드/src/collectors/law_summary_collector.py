import logging

import requests

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://raw.githubusercontent.com/primexx98-sudo/FOODLAW-MONITORING/main/data/archive.json"


def get_law_weekly_summary():
    """FOODLAW-MONITORING(별도 프로젝트)이 Claude API로 생성해둔 주간 법령 요약을 그대로 가져온다.
    반환: {"label": "2026년 30주차", "summary": "...", "weekly_summary": "...", "count": 0, "items": [...]}
    """
    try:
        resp = requests.get(ARCHIVE_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        weeks = data.get("weeks", [])
        if not weeks:
            return None
        latest = weeks[-1]
        result = {
            "label": latest.get("label", ""),
            "summary": latest.get("summary", ""),
            "weekly_summary": latest.get("weekly_summary", ""),
            "count": latest.get("counts", {}).get("total", 0),
            "items": latest.get("items", [])[:3],
        }
        logger.info(f"법령 주간요약 확보: {result['label']} (항목 {result['count']}건)")
        return result
    except Exception as e:
        logger.warning(f"법령 주간요약 수집 실패: {e}")
        return None
