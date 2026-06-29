import requests
import logging
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

HEALTH_KEYWORDS = [
    "비타민", "영양제", "유산균", "오메가3", "콜라겐", "홍삼",
    "마그네슘", "건강기능식품", "프로바이오틱스", "글루타치온",
    "코엔자임", "루테인", "아연", "칼슘", "철분", "보충제",
    "크레아틴", "밀크시슬", "엽산", "비오틴", "NAD", "NMN",
    "면역", "항산화", "장건강", "피로회복", "식품의약품안전처"
]

EXCLUDE_KEYWORDS = [
    "패션", "헤어", "네일", "메이크업", "셀럽", "연예",
    "드라마", "영화", "아이돌", "세금", "부동산", "주식", "교육청"
]

# ─── 분류 키워드 (직접 수정 가능) ─────────────────────────────────
RESEARCH_KEYWORDS = [
    "연구", "임상", "논문", "학회", "발표", "분석",
    "효능 확인", "실험", "메타분석", "성분 연구", "임상시험"
]
REGULATORY_KEYWORDS = [
    "식약처", "허가", "인정", "고시", "규정", "기준",
    "승인", "행정처분", "개정", "안전성 평가", "식품의약품안전처"
]
# ──────────────────────────────────────────────────────────────────

QUERIES_GENERAL = [
    "건강기능식품 영양제",
    "유산균 장건강",
    "오메가3 효능",
    "비타민D 면역",
    "마그네슘 영양제",
    "글루타치온 건강",
    "NMN NAD 영양제",
    "코엔자임Q10 효능",
]

QUERIES_RESEARCH = [
    "건강기능식품 연구 논문",
    "영양제 임상 연구",
    "프로바이오틱스 임상",
    "오메가3 연구 결과",
    "건강기능식품 성분 효능 연구",
]

QUERIES_REGULATORY = [
    "식품의약품안전처 건강기능식품",
    "식약처 영양제 허가",
    "건강기능식품 기준 고시",
    "식약처 보도자료 건강기능식품",
]


def is_recent(pub_date_str, days=14):
    try:
        dt = parsedate_to_datetime(pub_date_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return dt > cutoff
    except Exception:
        return True


def is_relevant(title, desc):
    combined = title + " " + desc
    if any(ex in combined for ex in EXCLUDE_KEYWORDS):
        return False
    return any(kw in title for kw in HEALTH_KEYWORDS) or \
           any(kw in desc for kw in HEALTH_KEYWORDS)


def categorize(title, desc):
    combined = title + " " + desc
    if any(kw in combined for kw in REGULATORY_KEYWORDS):
        return "regulatory"
    if any(kw in combined for kw in RESEARCH_KEYWORDS):
        return "research"
    return "general"


def get_naver_news(query, display=10):
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {"query": quote(query), "display": display, "start": 1, "sort": "date"}
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        logger.error(f"뉴스 수집 실패 [{query}]: {e}")
        return []


def _collect_from_queries(queries, days=14):
    results, seen = [], set()
    for query in queries:
        items = get_naver_news(query, display=10)
        for item in items:
            title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
            desc = item["description"].replace("<b>", "").replace("</b>", "")
            pub_date = item.get("pubDate", "")
            if title in seen:
                continue
            if not is_recent(pub_date, days=days):
                continue
            if not is_relevant(title, desc):
                continue
            seen.add(title)
            results.append({
                "title": title,
                "link": item.get("originallink") or item["link"],
                "pubDate": pub_date,
                "description": desc,
                "category": categorize(title, desc),
            })
    return results


def collect_all_news():
    general_items = _collect_from_queries(QUERIES_GENERAL, days=7)
    research_items = _collect_from_queries(QUERIES_RESEARCH, days=30)
    regulatory_items = _collect_from_queries(QUERIES_REGULATORY, days=30)

    seen = set()
    research, regulatory, general = [], [], []

    for item in research_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            research.append(item)

    for item in regulatory_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            regulatory.append(item)

    for item in general_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            general.append(item)

    logger.info(f"뉴스 수집 - 일반:{len(general)} 연구:{len(research)} 규제:{len(regulatory)}")
    mfds = [r for r in regulatory if "mfds.go.kr" in r.get("link", "")]

    return {
        "news": general[:8],
        "research": research[:8],
        "regulatory": regulatory[:8],
        "mfds": mfds[:5],
    }