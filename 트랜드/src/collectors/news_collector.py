import requests
import logging
from urllib.parse import quote
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, HEALTH_KEYWORDS

logger = logging.getLogger(__name__)

# 명백히 건강기능식품과 무관한 주제 — 병원뉴스 타겟
EXCLUDE_KEYWORDS = [
    # 병원/의료
    "수술", "입원", "응급", "처방", "진료", "병원", "건강보험", "건강검진",
    # 의약품/치료제 (건기식 아님)
    "마약류", "항암", "바이오시밀러", "신약", "치료제", "의약품", "의료기기",
    # 감염병
    "HIV", "에이즈", "감염병",
    # 일반 식품/외식
    "급식", "외식", "음식점", "배달음식", "레시피",
    # 연예/문화
    "패션", "헤어", "네일", "메이크업", "셀럽", "연예",
    "드라마", "영화", "아이돌",
    # 사회/경제
    "세금", "부동산", "주식", "교육청",
]

# ─── 분류 키워드 (직접 수정 가능) ─────────────────────────────────
RESEARCH_KEYWORDS = [
    "연구", "임상", "논문", "학회", "발표", "분석",
    "효능 확인", "실험", "메타분석", "성분 연구", "임상시험",
]

# HEALTH_KEYWORDS 중 "면역력·체지방·혈당" 같은 범용 효능어는 일반 의료/다이어트
# 뉴스에도 흔해 relevance 판정이 너무 헐거워짐 — 관련성·research 분류 판정에는
# 이 범용어를 뺀 "핵심" 성분/제품 키워드만 사용한다 (SNS 집계 등 다른 용도의
# HEALTH_KEYWORDS 원본은 그대로 둠, config.py 참고).
_GENERIC_EFFECT_KEYWORDS = {
    "면역력", "항산화", "장건강", "피로회복", "콜레스테롤", "체지방", "수면 개선",
    "혈당", "혈압", "뼈건강", "관절건강", "눈건강", "기억력", "인지기능",
    "갱년기", "체중관리",
}
CORE_HEALTH_KEYWORDS = [kw for kw in HEALTH_KEYWORDS if kw not in _GENERIC_EFFECT_KEYWORDS]
REGULATORY_KEYWORDS = [
    # 기관
    "식약처", "식품의약품안전처",
    # 행정
    "행정처분", "판매 중지", "리콜", "부작용 보고",
    # 고시/인정 체계
    "개정고시", "안전성 평가",
    "개별인정", "개별인정형", "고시형", "기능성 원료", "원료 인정", "기능성 심사",
    # 품질
    "GMP", "우수건강기능식품",
    # 광고/표시
    "허위광고", "과대광고", "부당광고", "기능성 표시",
]

# ─── 국내 건강 뉴스 RSS (직접 추가/수정 가능) ────────────────────
# trusted=True 피드는 건기식 전문 매체 — HEALTH+RESEARCH+REGULATORY 키워드 통합 필터 적용
KOREAN_RSS_FEEDS = [
    {"name": "연합뉴스 건강",   "url": "https://www.yna.co.kr/rss/health.xml",               "trusted": True},
    {"name": "헬스조선",        "url": "https://health.chosun.com/site/data/rss/rss.xml",    "trusted": True},
    {"name": "식품음료신문",    "url": "http://www.thinkfood.co.kr/rss/allArticle.xml",       "trusted": True},
    {"name": "히트뉴스",        "url": "http://www.hitnews.co.kr/rss/allArticle.xml",         "trusted": True},
    {"name": "코메디닷컴",      "url": "https://kormedi.com/feed/",                            "trusted": True},
    {"name": "팜뉴스",          "url": "http://www.pharmnews.com/rss/allArticle.xml",         "trusted": False},
    {"name": "뉴시스 헬스",     "url": "https://www.newsis.com/RSS/health.xml",               "trusted": False},
    {"name": "메디소비자뉴스",  "url": "https://www.medisobizanews.com/rss/allArticle.xml",   "trusted": False},
    {"name": "식품저널",        "url": "https://www.foodnews.co.kr/rss/allArticle.xml",       "trusted": False},
    {"name": "뉴스1 생활",      "url": "https://www.news1.kr/rss/life.xml",                   "trusted": False},
    {"name": "데일리팜",        "url": "http://www.dailypharm.com/rss/Users/dp.xml",          "trusted": False},
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


def is_relevant(title, desc="", trusted_source=False):
    combined = title + " " + desc
    if any(ex in combined for ex in EXCLUDE_KEYWORDS):
        return False
    if trusted_source:
        # 건기식 전문 매체라도 "연구/분석/발표" 같은 범용 단어만으로는 통과시키지
        # 않음 — 실제 성분/제품명 또는 규제 키워드가 있어야 함 (일반 의료·다이어트
        # 뉴스가 research로 잘못 분류되던 문제, 2026-07-22 수정)
        broad = CORE_HEALTH_KEYWORDS + REGULATORY_KEYWORDS
        return any(kw in combined for kw in broad)
    return any(kw in title for kw in CORE_HEALTH_KEYWORDS) or \
           any(kw in desc for kw in CORE_HEALTH_KEYWORDS)


def categorize(title, desc=""):
    combined = title + " " + desc
    if any(kw in combined for kw in REGULATORY_KEYWORDS):
        return "regulatory"
    # research는 "연구"류 단어 + 실제 성분/제품 키워드가 함께 있어야 인정
    if any(kw in combined for kw in RESEARCH_KEYWORDS) and any(kw in combined for kw in CORE_HEALTH_KEYWORDS):
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
        data = resp.json()
        if "errorCode" in data:
            logger.warning(f"Naver API 오류 [{query}]: {data.get('errorMessage')} (code={data.get('errorCode')})")
            return []
        items = data.get("items", [])
        if not items:
            logger.debug(f"Naver 검색 결과 없음 [{query}] — Search API 권한 확인 필요")
        return items
    except Exception as e:
        logger.error(f"뉴스 수집 실패 [{query}]: {e}")
        return []


def get_korean_rss_news():
    all_items, seen = [], set()
    for feed in KOREAN_RSS_FEEDS:
        try:
            resp = requests.get(
                feed["url"], timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; HealthBot/1.0)"}
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "lxml-xml")
            items_found = 0
            for item in soup.find_all("item")[:30]:
                title_tag = item.find("title")
                link_tag = item.find("link")
                pub_tag = item.find("pubDate")
                desc_tag = item.find("description")

                if not title_tag:
                    continue

                title = BeautifulSoup(title_tag.get_text(strip=True), "html.parser").get_text().strip()
                link = link_tag.get_text(strip=True) if link_tag else ""
                pub = pub_tag.get_text(strip=True) if pub_tag else ""
                desc = BeautifulSoup(desc_tag.get_text(strip=True), "html.parser").get_text()[:300] if desc_tag else ""

                if title in seen or len(title) < 5:
                    continue
                if not is_recent(pub, days=7):
                    continue
                if not is_relevant(title, desc, trusted_source=feed.get("trusted", False)):
                    continue

                seen.add(title)
                all_items.append({
                    "title": title,
                    "link": link,
                    "pubDate": pub,
                    "description": desc,
                    "category": categorize(title, desc),
                    "source": feed["name"],
                })
                items_found += 1
            logger.info(f"[{feed['name']}] {items_found}건 수집")
        except Exception as e:
            logger.warning(f"RSS 수집 실패 [{feed['name']}]: {e}")

    logger.info(f"국내 RSS 뉴스 합계 {len(all_items)}건")
    return all_items


def _collect_from_queries(queries, days=14):
    results, seen = [], set()
    for query in queries:
        items = get_naver_news(query, display=10)
        kept = 0
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
            kept += 1
            results.append({
                "title": title,
                "link": item.get("originallink") or item["link"],
                "pubDate": pub_date,
                "description": desc,
                "category": categorize(title, desc),
                "source": "네이버뉴스",
            })
        logger.info(f"[쿼리:{query}] API 원본 {len(items)}건 → 필터 통과 {kept}건")
    return results


def collect_all_news():
    general_items = _collect_from_queries(QUERIES_GENERAL, days=7)
    research_items = _collect_from_queries(QUERIES_RESEARCH, days=30)
    regulatory_items = _collect_from_queries(QUERIES_REGULATORY, days=30)
    rss_items = get_korean_rss_news()

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

    for item in rss_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            cat = item["category"]
            if cat == "research":
                research.append(item)
            elif cat == "regulatory":
                regulatory.append(item)
            else:
                general.append(item)

    logger.info(f"뉴스 최종 - 일반:{len(general)} 연구:{len(research)} 규제:{len(regulatory)}")
    mfds = [r for r in regulatory if "mfds.go.kr" in r.get("link", "")]

    return {
        "news": general[:8],
        "research": research[:8],
        "regulatory": regulatory[:8],
        "mfds": mfds[:5],
    }