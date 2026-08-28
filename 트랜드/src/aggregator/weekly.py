import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 트랜드/src
from collectors.ecommerce_collector import PLATFORMS
from summarizer.ai_summary import summarize
from aggregator.rising_report import build_period_report, retry_issue_bullets

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


def _prev_week_dates(iso_year, iso_week):
    """직전 ISO 주의 날짜 목록 — 급상승 리포트의 전주 대비 검색량 비교 기준."""
    monday = datetime.fromisocalendar(iso_year, iso_week, 1)
    prev_monday = monday - timedelta(days=7)
    py, pw, _ = prev_monday.isocalendar()
    return _week_dates(py, pw)


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
    return f"{thursday.year % 100:02d}년 {thursday.month}월 {week_index}주차"


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


def _aggregate_ecommerce_highlights(ecommerce_days, max_per_platform=4):
    """플랫폼별로 '신규진입(new)' 빈도가 크게 다르다 — 특히 다이소몰은 순위 매칭 특성상
    거의 매일 TOP10 전체가 new로 잡혀 신호가 아니라 잡음에 가깝다(2026-07-28 실데이터로
    확인: 07-26/27/28 다이소몰 배지가 사실상 전부 new). 그대로 두면 이 잡음이 :10 슬라이스를
    독점해 카카오·올리브영의 실제 순위 상승(up) 같은 의미 있는 신호가 밀려난다 — up을 먼저,
    플랫폼당 상한을 둬서 다양성을 확보한다."""
    seen = set()
    ups, news = [], []
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
                if badge.startswith("up:"):
                    ups.append({"platform": platform, "name": name, "badge": badge, "kind": "up",
                                "_gain": int(badge.split(":")[1])})
                elif badge == "new":
                    news.append({"platform": platform, "name": name, "badge": badge, "kind": "new"})

    ups.sort(key=lambda x: -x["_gain"])
    for it in ups:
        it.pop("_gain", None)

    def _cap_per_platform(items):
        counts = {}
        capped = []
        for it in items:
            c = counts.get(it["platform"], 0)
            if c >= max_per_platform:
                continue
            counts[it["platform"]] = c + 1
            capped.append(it)
        return capped

    return _cap_per_platform(ups) + _cap_per_platform(news)


# 베이지안 스무딩 가상표본 수 (online-mall-ranking의 monthly_aggregate.py와 동일 값 사용)
BAYESIAN_K = 5

# 상품URL에서 플랫폼별 고유 상품코드를 뽑아내는 패턴 (online-mall-ranking의 monthly_aggregate.py와
# 동일). 상세페이지 제목은 프로모션 문구 때문에 거의 매일 바뀌지만(예: "1일 1정"→"1일1정") URL 속
# 상품코드는 실제로 다른 상품이 등록되지 않는 한 고정이라 동일 상품 판별에 훨씬 안전하다.
_PRODUCT_ID_PATTERNS = {
    "올리브영": re.compile(r"goodsNo=([A-Za-z0-9]+)"),
    "다이소몰": re.compile(r"[?&]pdNo=(\d+)"),
    "카카오선물하기": re.compile(r"/product/(\d+)"),
}


def _extract_product_id(url, platform):
    pattern = _PRODUCT_ID_PATTERNS.get(platform)
    if pattern is None or not isinstance(url, str):
        return None
    m = pattern.search(url)
    return m.group(1) if m else None


def _normalize_product_name(name):
    """상품URL 파싱 실패 시(수집 실패 등)를 위한 대체 키. 대괄호 프로모션 태그를 통째로
    제거하고 공백을 모두 없애 "1일 1정"/"1일1정"처럼 표기만 다른 경우를 흡수한다."""
    if not isinstance(name, str):
        return ""
    no_brackets = re.sub(r"\[[^\]]*\]", "", name)
    return re.sub(r"\s+", "", no_brackets)


def _item_keys(item, platform):
    """항목 하나에서 (id_key, name_key)를 뽑는다. id_key는 상품URL 파싱 실패 시 None."""
    pid = _extract_product_id(item.get("url"), platform)
    id_key = f"id::{pid}" if pid else None
    brand = str(item.get("brand") or "").strip()
    name_norm = _normalize_product_name(item.get("name", ""))
    if brand and name_norm.startswith(brand):
        name_norm = name_norm[len(brand):]
    name_key = f"name::{brand}::{name_norm}"
    return id_key, name_key


class _UnionFind:
    """id 키와 이름 키를 같은 그룹으로 묶기 위한 최소 union-find (online-mall-ranking과 동일 구현).
    상품URL이 있는 날은 id 키로, 없는 날은 이름 키로만 잡히는데, 같은 상품이 어느 날은 URL이
    있고 어느 날은 없으면 두 키가 한 번이라도 같은 행에서 만나야 병합된다."""
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _aggregate_ecommerce_rankings(ecommerce_days, top_n=10):
    """일간 대시보드의 '이커머스 판매순위 TOP10'을 기간 단위로 다시 뽑는다.
    online-mall-ranking의 monthly_aggregate.py(aggregate_platform)와 동일한 선정 방식을 차용:
    순위 점수(1위=5점~10위=0.5점)를 베이지안 평균으로 집계한다 — 등장횟수가 적을수록
    점수가 이 플랫폼·기간의 전체 평균 쪽으로 당겨져서, 1~2일만 반짝 상위권에 든 상품이
    표본 부족에도 불구하고 꾸준히 등장한 상품을 제치는 왜곡을 완화한다. 최소 등장횟수
    미달 상품은 제외한다(부족하면 기준 완화). 같은 상품이 프로모션 문구 변경으로 여러 항목
    으로 쪼개지지 않도록 상품URL 코드(우선) 또는 정규화된 이름(대체)으로 그룹핑한다."""
    total_days = len(ecommerce_days)
    result = {}
    for platform in PLATFORMS:
        uf = _UnionFind()
        entries = []
        for _, day_data in ecommerce_days:
            for item in day_data.get(platform, []):
                if not item.get("name"):
                    continue
                id_key, name_key = _item_keys(item, platform)
                if id_key:
                    uf.union(id_key, name_key)
                entries.append((id_key, name_key, item))

        rank_sums, score_sums, counts, latest, name_votes = {}, {}, {}, {}, {}
        for id_key, name_key, item in entries:
            group = uf.find(id_key if id_key else name_key)
            rank = item.get("rank", 999)
            rank_sums[group] = rank_sums.get(group, 0) + rank
            score_sums[group] = score_sums.get(group, 0) + (11 - rank) * 0.5  # 1위=5점...10위=0.5점
            counts[group] = counts.get(group, 0) + 1
            latest[group] = item  # 마지막으로 덮어쓴 값 = 기간 내 가장 최근 정보
            votes = name_votes.setdefault(group, {})
            votes[item["name"]] = votes.get(item["name"], 0) + 1

        # 등장횟수 3회 미만 상품은 제외(1~2회 등장한 상품이 평균순위만으로 상위권에 오르는 것 방지).
        # 단, 필터 후 top_n이 안 채워지면 기준을 3→1로 순차 완화해 최대한 채운다.
        min_appear = min(3, total_days) if total_days else 1
        groups = [g for g in counts if counts[g] >= min_appear]
        while len(groups) < top_n and min_appear > 1:
            min_appear -= 1
            groups = [g for g in counts if counts[g] >= min_appear]

        # 베이지안 스무딩의 사전확률(prior): 이 플랫폼·이 기간의 일별점수 전체 평균
        total_appearances = sum(counts.values())
        global_mean_score = (sum(score_sums.values()) / total_appearances) if total_appearances else 2.75

        scored = [
            {
                "name": max(name_votes[g], key=name_votes[g].get),  # 그룹 내 가장 흔한 표기를 대표명으로 사용
                "avg_rank": round(rank_sums[g] / counts[g], 1),
                "days_seen": counts[g],
                "category": latest[g].get("category"),
                "brand": latest[g].get("brand"),
                "price": latest[g].get("price"),
                "url": latest[g].get("url"),
                "image": latest[g].get("image"),
                "_score": (score_sums[g] + BAYESIAN_K * global_mean_score) / (counts[g] + BAYESIAN_K),
            }
            for g in groups
        ]
        scored.sort(key=lambda x: -x["_score"])
        for it in scored:
            it.pop("_score", None)
        result[platform] = scored[:top_n]
    return result


def _search_sales_gap_lines(top_keywords, ecommerce_rankings, top_n=15, show_n=6):
    """검색 상위 키워드 중 판매순위 TOP10 상품명에 등장하지 않는 키워드 — "신제품 제안"
    AI 프롬프트의 근거 자료용(대시보드 렌더링용 HTML 버전은 dashboard.py에 별도로 있음,
    여기는 AI material 텍스트만 필요해 가볍게 재계산)."""
    product_names = " ".join(
        it.get("name", "") for items in ecommerce_rankings.values() for it in items
    )
    gaps = [
        f"{i + 1}위 {k['keyword']}" for i, k in enumerate(top_keywords[:top_n])
        if k["keyword"] not in product_names
    ]
    return gaps[:show_n]


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
    ecommerce_rankings = _aggregate_ecommerce_rankings(ecommerce_days)

    volume_days = [(d, _load_json(os.path.join(DATA_DIR, f"keyword_volume_{d}.json"))) for d in date_strs]
    volume_days = [(d, v) for d, v in volume_days if v]
    prev_date_strs = _prev_week_dates(iso_year, iso_week)
    prev_volume_days = [(d, _load_json(os.path.join(DATA_DIR, f"keyword_volume_{d}.json"))) for d in prev_date_strs]
    prev_volume_days = [(d, v) for d, v in prev_volume_days if v]
    rising_report = build_period_report(ecommerce_days, volume_days, prev_volume_days, period_label="전주")

    material = {
        "이번 주 검색 상위 키워드": [f"{k['keyword']} (평균 {k['avg_ratio']:.0f}위)" for k in top_keywords[:10]],
        "이번 주 주요 뉴스": [f"[{n['category']}] {n['title']}" for n in news_highlights[:10]],
        "이번 주 이커머스 동향": [
            f"{e['platform']} " + ("신규진입: " if e['kind'] == "new" else "순위상승: ") + e['name']
            for e in ecommerce_highlights[:10]
        ],
        "이번 주 급상승 원료": [
            f"{c['name']} (검색량 {c['total']:.0f}, 상위 브랜드: {', '.join(c['top_brands']) or '없음'})"
            for c in (rising_report or {}).get("ingredients", [])
        ],
        "이번 주 급상승 브랜드/제품": [
            f"{c['name']} (검색량 {c['total']:.0f}, 상위 브랜드: {', '.join(c['top_brands']) or '없음'})"
            for c in (rising_report or {}).get("brands", [])
        ],
        "검색은 늘었지만 대표 판매상품이 없는 키워드(신제품 기회 후보)":
            _search_sales_gap_lines(top_keywords, ecommerce_rankings),
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
        "ecommerce_rankings": ecommerce_rankings,
        "rising_report": rising_report,
        "ai_summary": ai_result,
    }


def _material_from_saved(result):
    """저장된 weekly 결과에서 build_weekly_summary()가 만들었던 것과 동일한 material을
    원본 수집 없이 다시 조립한다 — retry_missing_ai()가 실패했던 AI 요약만 값싸게
    재시도할 수 있게 해준다."""
    rising_report = result.get("rising_report") or {}
    return {
        "이번 주 검색 상위 키워드": [f"{k['keyword']} (평균 {k['avg_ratio']:.0f}위)" for k in result.get("top_keywords") or []],
        "이번 주 주요 뉴스": [f"[{n['category']}] {n['title']}" for n in result.get("news_highlights") or []],
        "이번 주 이커머스 동향": [
            f"{e['platform']} " + ("신규진입: " if e['kind'] == "new" else "순위상승: ") + e['name']
            for e in result.get("ecommerce_highlights") or []
        ],
        "이번 주 급상승 원료": [
            f"{c['name']} (검색량 {c['total']:.0f}, 상위 브랜드: {', '.join(c['top_brands']) or '없음'})"
            for c in rising_report.get("ingredients", [])
        ],
        "이번 주 급상승 브랜드/제품": [
            f"{c['name']} (검색량 {c['total']:.0f}, 상위 브랜드: {', '.join(c['top_brands']) or '없음'})"
            for c in rising_report.get("brands", [])
        ],
        "검색은 늘었지만 대표 판매상품이 없는 키워드(신제품 기회 후보)":
            _search_sales_gap_lines(result.get("top_keywords") or [], result.get("ecommerce_rankings") or {}),
    }


def retry_missing_ai(result):
    """daily.yml이 매일 최신 주간 스냅샷을 읽을 때 호출 — weekly.yml 실행 시점에 Gemini
    503으로 비어버린 전체 요약/급상승 이슈 카드를 재시도한다. 재료가 없거나 이미 채워져
    있으면 API를 호출하지 않아 낭비가 없다. 반환: (result, 하나라도 채워졌는지)"""
    changed = False
    if result.get("ai_summary") is None:
        material = _material_from_saved(result)
        ai_result = summarize(result["period_label"], material)
        if ai_result is not None:
            result["ai_summary"] = ai_result
            changed = True
    rising_report = result.get("rising_report")
    if rising_report:
        _, cards_changed = retry_issue_bullets(rising_report)
        changed = changed or cards_changed
    return result, changed


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
