import io
import logging
from datetime import datetime, timedelta

import requests
from openpyxl import load_workbook

logger = logging.getLogger(__name__)

RAW_BASE = "https://raw.githubusercontent.com/primexx98-sudo/online-mall-ranking/master/data/daily"
PLATFORMS = ["카카오선물하기", "다이소몰", "올리브영"]
TOP_N = 10


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
            {
                "rank": r[1],
                "category": r[0],
                "name": r[2],
                "brand": r[3],
                "price": r[4],
                "url": r[5],
                "image": r[6] if len(r) > 6 else "",
            }
            for r in rows if r and r[1] is not None
        ]
    return result


def attach_rank_changes(data, prev_data):
    """전일 스냅샷과 비교해 상품별 순위 변동 배지를 붙인다 (상품명+브랜드로 매칭).
    badge: "new" | "same" | "up:N" | "down:N" — prev_data 없으면 아무 배지도 안 붙임."""
    if not prev_data:
        return data
    for platform in PLATFORMS:
        prev_rank_by_key = {
            (it.get("name"), it.get("brand")): it.get("rank")
            for it in prev_data.get(platform, [])
        }
        for it in data.get(platform, []):
            key = (it.get("name"), it.get("brand"))
            prev_rank = prev_rank_by_key.get(key)
            if prev_rank is None:
                it["badge"] = "new"
            else:
                diff = prev_rank - it["rank"]
                if diff > 0:
                    it["badge"] = f"up:{diff}"
                elif diff < 0:
                    it["badge"] = f"down:{abs(diff)}"
                else:
                    it["badge"] = "same"
    return data
