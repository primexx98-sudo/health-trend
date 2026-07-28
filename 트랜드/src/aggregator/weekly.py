import glob
import json
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 트랜드/src
from collectors.ecommerce_collector import PLATFORMS
from summarizer.ai_summary import summarize

logger = logging.getLogger(__name__)

# 트랜드/src/aggregator/weekly.py → 4단계 위가 repo root. weekly.yml은 main.py를 거치지 않고
# 이 스크립트를 바로 실행하므로, main.py의 OUTPUT_DIR(트랜드/docs)이 아니라 실제 커밋되는
# repo-root docs/를 직접 읽고 쓴다 — daily.yml의 cp 단계 없이도 결과가 그대로 커밋 대상이 됨.
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(_repo_root, "docs", "data")
WEEKLY_DIR = os.path.join(DATA_DIR, "weekly")


def _week_dates(iso_year, iso_week):
    monday = datetime.fromisocalendar(iso_year, iso_week, 1)
    return [(monday + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"{path} 읽기 실패: {e}")
        return None


def _month_label_for_week(iso_year, iso_week):
    """월~일 ISO 주 기준 "YYYY년 M월 N주차" 표기. 그 주의 목요일이 속한 달을 기준으로
    월을 정하고(주 절반 이상이 걸친 달), 그 달 1일이 포함된 ISO 주를 1주차로 상대 계산한다."""
    thursday = datetime.fromisocalendar(iso_year, iso_week, 4)
    month_start = thursday.replace(day=1)
    first_iso_year, first_iso_week, _ = month_start.isocalendar()
    week_index = iso_week - first_iso_week + 1
    if iso_year != first_iso_year:
        week_index = 1  # 해 경계를 넘는 드문 경우 — 안전하게 1주차로 표기
    return f"{thursday.year}년 {thursday.month}월 {week_index}주차"


def _aggregate_top_keywords(naver_days):
    sums, counts = {}, {}
    for _, day_data in naver_days:
        for item in day_data:
            kw = item.get("keyword")
            if not kw:
                continue
            sums[kw] = sums.get(kw, 0) + item.get("ratio", 0)
            counts[kw] = counts.get(kw, 0) + 1
    averaged = [(kw, sums[kw] / counts[kw]) for kw in sums]
    averaged.sort(key=lambda x: x[1], reverse=True)
    return [{"keyword": kw, "avg_ratio": round(ratio, 1)} for kw, ratio in averaged]


def _aggregate_news_highlights(digests):
    seen = set()
    lines = []
    for digest in digests:
        news_data = digest.get("news_data") or {}
        for cat_key, cat_label in (("regulatory", "규제"), ("research", "연구"), ("news", "일반")):
            for item in news_data.get(cat_key, []):
                title = item.get("title")
                if not title or title in seen:
                    continue
                seen.add(title)
                lines.append({"category": cat_label, "title": title, "link": item.get("link", "")})
    return lines


def _aggregate_ecommerce_highlights(ecommerce_days):
    seen = set()
    lines = []
    for _, day_data in ecommerce_days:
        for platform in PLATFORMS:
            for item in day_data.get(platform, []):
                badge = item.get("badge")
                name = item.get("name")
                if not name or not badge or badge in (None, "same"):
                    continue
                key = (platform, name)
                if key in seen:
                    continue
                seen.add(key)
                kind = "new" if badge == "new" else "up"
                lines.append({"platform": platform, "name": name, "badge": badge, "kind": kind})
    return lines


def build_weekly_summary(iso_year=None, iso_week=None):
    if iso_year is None or iso_week is None:
        target = datetime.now() - timedelta(days=1)  # 실행일 전날 = 직전 완료된 주 안의 날짜
        iso_year, iso_week, _ = target.isocalendar()

    date_strs = _week_dates(iso_year, iso_week)
    label = _month_label_for_week(iso_year, iso_week)

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

    material = {
        "이번 주 검색 상위 키워드": [f"{k['keyword']} (평균 {k['avg_ratio']:.0f}위)" for k in top_keywords[:10]],
        "이번 주 주요 뉴스": [f"[{n['category']}] {n['title']}" for n in news_highlights[:10]],
        "이번 주 이커머스 동향": [
            f"{e['platform']} " + ("신규진입: " if e['kind'] == "new" else "순위상승: ") + e['name']
            for e in ecommerce_highlights[:10]
        ],
    }
    ai_result = summarize(label, material)

    return {
        "period_label": label,
        "iso_year": iso_year,
        "iso_week": iso_week,
        "date_range": [date_strs[0], date_strs[-1]],
        # digest(뉴스 등)만 기준으로 하면 초기(digest 미축적 기간)에 검색순위·이커머스는
        # 실제로 있는데도 "0일치"로 오해를 살 수 있어, 셋 중 가장 많이 확보된 걸로 표시
        "days_collected": max(len(digests), len(naver_days), len(ecommerce_days)),
        "top_keywords": top_keywords[:10],
        "news_highlights": news_highlights[:10],
        "ecommerce_highlights": ecommerce_highlights[:10],
        "ai_summary": ai_result,
    }


def save_weekly_summary(result):
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    path = os.path.join(WEEKLY_DIR, f"weekly_{result['iso_year']}-W{result['iso_week']:02d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    logger.info(f"저장 완료: {path}")
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = build_weekly_summary()
    save_weekly_summary(result)
