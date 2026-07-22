import io
import logging
from datetime import datetime, timedelta

import requests
from openpyxl import load_workbook

logger = logging.getLogger(__name__)

RAW_BASE = "https://raw.githubusercontent.com/primexx98-sudo/online-mall-ranking/master/data/daily"
PLATFORMS = ["카카오선물하기", "다이소몰", "올리브영"]
TOP_N = 3


def _fetch_workbook():
    """online-mall-ranking 저장소의 최신 일별 xlsx를 오늘부터 최대 3일 역순으로 시도"""
    for delta in range(3):
        date_str = (datetime.now() - timedelta(days=delta)).strftime("%Y-%m-%d")
        url = f"{RAW_BASE}/{date_str[:7]}/{date_str}.xlsx"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                logger.info(f"이커머스 판매순위 데이터 확보: {date_str}")
                return load_workbook(io.BytesIO(resp.content), data_only=True), date_str
        except Exception as e:
            logger.warning(f"이커머스 판매순위 수집 실패 [{date_str}]: {e}")
    return None, None


def get_ecommerce_rankings():
    wb, date_str = _fetch_workbook()
    if wb is None:
        logger.warning("이커머스 판매순위 데이터 없음 (최근 3일 모두 실패)")
        return {}

    result = {"date": date_str}
    for platform in PLATFORMS:
        if platform not in wb.sheetnames:
            result[platform] = []
            continue
        ws = wb[platform]
        rows = list(ws.iter_rows(min_row=2, max_row=1 + TOP_N, values_only=True))
        result[platform] = [
            {"rank": r[1], "name": r[2], "brand": r[3], "price": r[4], "url": r[5]}
            for r in rows if r and r[1] is not None
        ]
    return result
