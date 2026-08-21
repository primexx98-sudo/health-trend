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


def get_rising_brand_candidates(data, limit=15):
    """당일 신규진입·순위상승(▲3 이상) 상품에서 브랜드명을 추출해 급상승 브랜드/제품
    리포트의 검색량 조회 후보로 삼는다. attach_rank_changes()로 badge가 붙은 뒤 호출해야 함.
    브랜드명 자체에 통계적 의미가 있는 건 아니고, 이커머스에서 눈에 띄게 움직인 상품의
    브랜드를 시장 신호 후보로만 사용 — 상승폭이 클수록/등장 빈도가 높을수록 가중치 부여."""
    weights = {}
    for platform in PLATFORMS:
        for it in data.get(platform, []):
            brand = (it.get("brand") or "").strip()
            if not brand:
                continue
            badge = it.get("badge")
            if badge == "new":
                weight = 1
            elif badge and badge.startswith("up:") and int(badge.split(":")[1]) >= 3:
                weight = 1 + int(badge.split(":")[1])
            else:
                continue
            weights[brand] = weights.get(brand, 0) + weight
    ranked = sorted(weights.items(), key=lambda x: -x[1])
    return [brand for brand, _ in ranked[:limit]]


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
