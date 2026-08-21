import calendar
import json
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 트랜드/src
from collectors.foodnews_monthly_collector import get_foodnews_monthly
from summarizer.ai_summary import summarize
from aggregator.weekly import (
    _aggregate_top_keywords,
    _aggregate_news_highlights,
    _aggregate_ecommerce_highlights,
    _aggregate_ecommerce_rankings,
    _load_json,
    DATA_DIR,
)
from aggregator.rising_report import build_period_report

logger = logging.getLogger(__name__)

MONTHLY_DIR = os.path.join(DATA_DIR, "monthly")


def _month_dates(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return [f"{year}{month:02d}{d:02d}" for d in range(1, last_day + 1)]


def _prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def build_monthly_summary(year=None, month=None):
    if year is None or month is None:
        # monthly.yml은 매월 1일에 실행 — 기본값은 "방금 끝난 전달"을 집계
        target = datetime.now().replace(day=1) - timedelta(days=1)
        year, month = target.year, target.month

    label = f"{year % 100:02d}년 {month}월"
    today_str = datetime.now().strftime("%Y%m%d")
    date_strs = [d for d in _month_dates(year, month) if d <= today_str]

    digests, naver_days, ecommerce_days = [], [], []
    for d in date_strs:
        digest = _load_json(os.path.join(DATA_DIR, f"digest_{d}.json"))
        if digest:
            digests.append(digest)
        naver = _load_json(os.path.join(DATA_DIR, f"naver_{d}.json"))
        if naver:
            naver_days.append((d, naver))
        ecom = _load_json(os.path.join(DATA_DIR, f"ecommerce_{d}.json"))
        if ecom:
            ecommerce_days.append((d, ecom))

    logger.info(f"[{label}] digest {len(digests)}일치 / naver {len(naver_days)}일치 / ecommerce {len(ecommerce_days)}일치 확보")

    top_keywords = _aggregate_top_keywords(naver_days)
    news_highlights = _aggregate_news_highlights(digests)
    ecommerce_highlights = _aggregate_ecommerce_highlights(ecommerce_days)
    ecommerce_rankings = _aggregate_ecommerce_rankings(ecommerce_days)
    foodnews = get_foodnews_monthly(year, month)

    volume_days = [(d, _load_json(os.path.join(DATA_DIR, f"keyword_volume_{d}.json"))) for d in date_strs]
    volume_days = [(d, v) for d, v in volume_days if v]
    prev_year, prev_month = _prev_month(year, month)
    prev_date_strs = _month_dates(prev_year, prev_month)
    prev_volume_days = [(d, _load_json(os.path.join(DATA_DIR, f"keyword_volume_{d}.json"))) for d in prev_date_strs]
    prev_volume_days = [(d, v) for d, v in prev_volume_days if v]
    rising_report = build_period_report(ecommerce_days, volume_days, prev_volume_days)

    material = {
        "이번 달 검색 상위 키워드": [f"{k['keyword']} (평균 {k['avg_ratio']:.0f}위)" for k in top_keywords[:15]],
        "이번 달 주요 뉴스": [f"[{n['category']}] {n['title']}" for n in news_highlights[:15]],
        "이번 달 이커머스 동향": [
            f"{e['platform']} " + ("신규진입: " if e['kind'] == "new" else "순위상승: ") + e['name']
            for e in ecommerce_highlights[:15]
        ],
        "식품저널 건강기능식품 뉴스": [it["title"] for it in foodnews.get("건강기능식품", [])],
        "식품저널 신상품 소식": [it["title"] for it in foodnews.get("신상품", [])],
    }
    ai_result = summarize(label, material)

    return {
        "period_label": label,
        "year": year,
        "month": month,
        "date_range": [date_strs[0], date_strs[-1]] if date_strs else [],
        # weekly.py와 동일 이유 — digest 미축적 기간에도 검색순위·이커머스 실데이터가
        # 있으면 그 일수를 표시(0일치로 오해하지 않도록)
        "days_collected": max(len(digests), len(naver_days), len(ecommerce_days)),
        "top_keywords": top_keywords[:15],
        "news_highlights": news_highlights[:15],
        "ecommerce_highlights": ecommerce_highlights[:15],
        "ecommerce_rankings": ecommerce_rankings,
        "foodnews": foodnews,
        "rising_report": rising_report,
        "ai_summary": ai_result,
    }


def save_monthly_summary(result):
    os.makedirs(MONTHLY_DIR, exist_ok=True)
    path = os.path.join(MONTHLY_DIR, f"monthly_{result['year']}{result['month']:02d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    logger.info(f"저장 완료: {path}")
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = build_monthly_summary()
    save_monthly_summary(result)
