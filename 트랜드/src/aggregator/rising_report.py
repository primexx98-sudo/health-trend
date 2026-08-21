import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 트랜드/src
from config import INGREDIENT_KEYWORDS
from collectors.ecommerce_collector import PLATFORMS, get_rising_brand_candidates
from collectors.keyword_volume_collector import get_keyword_volumes
from collectors.demographic_collector import get_one_year_trend, get_demographic_breakdown
from collectors.news_collector import get_naver_news
from summarizer.ai_summary import summarize_keyword_issue

logger = logging.getLogger(__name__)

TOP_N = 3
MIN_TOTAL_VOLUME = 100  # 노이즈 방지용 최소 월간 검색량(PC+모바일)


def collect_today_volumes(ecommerce_data):
    """오늘의 원료 후보(고정 리스트) + 브랜드 후보(이커머스 신규·급등에서 추출)의
    검색량을 함께 조회한다. 반환: (ingredient_volumes, brand_volumes, brand_candidates, combined)"""
    brand_candidates = get_rising_brand_candidates(ecommerce_data or {})
    all_keywords = list(dict.fromkeys(INGREDIENT_KEYWORDS + brand_candidates))
    volumes = get_keyword_volumes(all_keywords)
    ingredient_volumes = {k: v for k, v in volumes.items() if k in INGREDIENT_KEYWORDS}
    brand_volumes = {k: v for k, v in volumes.items() if k in brand_candidates}
    return ingredient_volumes, brand_volumes, brand_candidates, volumes


def _find_top_brands(keyword, ecommerce_data, limit=2):
    """이커머스 데이터의 상품명에 키워드가 포함된 상품을 찾아 브랜드명을 최대 limit개 반환
    (등장 순서 기준, 중복 제거) — "상위 브랜드" 표시용."""
    found = []
    for platform in PLATFORMS:
        for it in (ecommerce_data or {}).get(platform, []):
            name = it.get("name") or ""
            brand = (it.get("brand") or "").strip()
            if brand and keyword in name and brand not in found:
                found.append(brand)
    return found[:limit]


def _rank_movers(today_volumes, prev_volumes, candidates, top_n=TOP_N):
    """검색량 증가폭 기준 상위 top_n 후보를 뽑는다. prev 스냅샷에 없던(신규 발견) 후보는
    증가폭 계산이 불가능하므로, 기존 후보만으로 top_n을 못 채울 때 절대 검색량 순으로 보충한다."""
    scored, new_entrants = [], []
    for kw in candidates:
        cur = today_volumes.get(kw)
        if not cur or cur.get("total", 0) < MIN_TOTAL_VOLUME:
            continue
        prev = (prev_volumes or {}).get(kw)
        if prev is None:
            new_entrants.append((cur["total"], kw, cur))
            continue
        delta = cur["total"] - prev.get("total", 0)
        if delta > 0:
            scored.append((delta, kw, cur))
    scored.sort(key=lambda x: -x[0])
    result = scored[:top_n]
    if len(result) < top_n:
        new_entrants.sort(key=lambda x: -x[0])
        result += new_entrants[: top_n - len(result)]
    return result


def _build_card(keyword, cur_volume, ecommerce_data, kind_label):
    top_brands = _find_top_brands(keyword, ecommerce_data, limit=2)

    news_items = get_naver_news(keyword, display=5)
    news_titles = [
        n["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
        for n in news_items
    ]
    bullets = summarize_keyword_issue(keyword, kind_label, news_titles)

    trend = get_one_year_trend(keyword)
    demo = get_demographic_breakdown(keyword)

    return {
        "name": keyword,
        "pc": cur_volume.get("pc", 0),
        "mobile": cur_volume.get("mobile", 0),
        "total": cur_volume.get("total", 0),
        "top_brands": top_brands,
        "issue_bullets": bullets or [],
        "trend": trend,
        "demo_bars": demo["bars"],
        "demo_top_label": demo["top_label"],
    }


def build_report(ecommerce_data, today_volumes, prev_volumes, brand_candidates):
    """일간 급상승 리포트 — main.py가 오늘/전일 검색량 스냅샷을 넘겨 호출한다."""
    ing_movers = _rank_movers(today_volumes, prev_volumes, INGREDIENT_KEYWORDS)
    brand_movers = _rank_movers(today_volumes, prev_volumes, brand_candidates)
    return {
        "ingredients": [_build_card(kw, cur, ecommerce_data, "원료") for _, kw, cur in ing_movers],
        "brands": [_build_card(kw, cur, ecommerce_data, "브랜드/제품") for _, kw, cur in brand_movers],
    }


def _aggregate_keyword_volumes(volume_days):
    """일별 keyword_volume 스냅샷 여러 개를 기간 평균으로 합산."""
    sums, counts = {}, {}
    for _, day_data in volume_days:
        for kw, v in day_data.items():
            total = v.get("total", 0)
            sums[kw] = sums.get(kw, 0) + total
            counts[kw] = counts.get(kw, 0) + 1
    return {kw: {"total": sums[kw] / counts[kw]} for kw in sums}


def _combine_ecommerce_days(ecommerce_days):
    """기간 내 여러 날의 이커머스 스냅샷을 상품명 기준으로 합쳐 "상위 브랜드" 매칭 커버리지를
    넓힌다(하루치만 쓰면 그날 TOP10에 없는 상품의 원료 매칭을 놓칠 수 있음)."""
    combined = {p: [] for p in PLATFORMS}
    seen = {p: set() for p in PLATFORMS}
    for _, day_data in ecommerce_days:
        for platform in PLATFORMS:
            for it in day_data.get(platform, []):
                name = it.get("name")
                if name and name not in seen[platform]:
                    seen[platform].add(name)
                    combined[platform].append(it)
    return combined


def _period_brand_candidates(ecommerce_days, limit=15):
    """기간 내 일별 이커머스 스냅샷 각각에서 신규·급등 브랜드 후보를 뽑아 빈도순으로 합산."""
    from collectors.ecommerce_collector import get_rising_brand_candidates as _get_candidates
    counts = {}
    for _, day_data in ecommerce_days:
        for brand in _get_candidates(day_data, limit=30):
            counts[brand] = counts.get(brand, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: -x[1])
    return [b for b, _ in ranked[:limit]]


def build_period_report(ecommerce_days, volume_days, prev_volume_days):
    """주간/월간 급상승 리포트 — weekly.py/monthly.py가 자기 기간의 일별 스냅샷
    리스트(현재 기간·직전 기간)를 넘겨 호출한다. 스냅샷이 아직 없는 과거 기간은
    prev_volume_days가 비어있을 수 있고, 그 경우 절대 검색량 순으로 대체된다."""
    if not volume_days:
        return None
    ecommerce_data = _combine_ecommerce_days(ecommerce_days)
    brand_candidates = _period_brand_candidates(ecommerce_days)
    cur_volumes = _aggregate_keyword_volumes(volume_days)
    prev_volumes = _aggregate_keyword_volumes(prev_volume_days) if prev_volume_days else {}

    ing_movers = _rank_movers(cur_volumes, prev_volumes, INGREDIENT_KEYWORDS)
    brand_movers = _rank_movers(cur_volumes, prev_volumes, brand_candidates)
    return {
        "ingredients": [_build_card(kw, cur, ecommerce_data, "원료") for _, kw, cur in ing_movers],
        "brands": [_build_card(kw, cur, ecommerce_data, "브랜드/제품") for _, kw, cur in brand_movers],
    }
