import requests
import logging
from urllib.parse import quote
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

# 건강기능식품 관련 핵심 키워드 — 이 중 하나라도 포함되면 수집 대상
HEALTH_KEYWORDS = [
    # 제품 카테고리
    "건강기능식품", "영양제", "보충제", "기능성식품", "서플리먼트",
    # 성분명
    "비타민", "유산균", "오메가3", "콜라겐", "홍삼", "마그네슘",
    "프로바이오틱스", "글루타치온", "코엔자임Q10", "루테인",
    "아연", "칼슘", "철분", "크레아틴", "밀크시슬", "엽산",
    "비오틴", "NMN", "NAD", "레스베라트롤", "커큐민",
    "베타글루칸", "아스타잔틴",
    # 효능/목적
    "면역력", "항산화", "장건강", "피로회복",
    "혈당 조절", "콜레스테롤", "체지방", "수면 개선",
    # 규제/인정 체계 (필터용)
    "개별인정", "개별인정형", "고시형", "기능성 원료", "개정고시", "GMP",
    # 기관
    "식품의약품안전처",
]

# 명백히 건강기능식품과 무관한 주제 — 병원뉴스 타겟
EXCLUDE_KEYWORDS = [
    # 병원/의료
    "수술", "입원", "응급", "처방", "진료", "병원", "건강보험", "건강검진",
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
REGULATORY_KEYWORDS = [
    # 기관/행정
    "식약처", "식품의약품안전처", "허가", "승인", "행정처분",
    # 고시/기준
    "고시", "개정고시", "기준", "규정", "안전성 평가",
    # 인정 체계
    "개별인정", "개별인정형", "고시형", "기능성 원료", "원료 인정", "기능성 심사",
    # 사후관리/광고
    "GMP", "우수건강기능식품", "부작용 보고", "리콜", "판매 중지",
    "허위광고", "과대광고", "부당광고", "기능성 표시",
]

# ─── 국내 건강 뉴스 RSS (직접 추가/수정 가능) ────────────────────
# trusted=True 피드는 건강 전문 매체로 키워드 필터 완화 적용
KOREAN_RSS_FEEDS = [
    {"name": "연합뉴스 건강", "url": "https://www.yna.co.kr/rss/health.xml", "trusted": True},
    {"name": "헬스조선", "url": "https://health.chosun.com/site/data/rss/rss.xml", "trusted": True},
    {"name": "팜뉴스",         "url": "http://www.pharmnews.com/rss/allArticle.xml",        "trusted": False},
    {"name": "메디소비자뉴스", "url": "https://www.medisobizanews.com/rss/allArticle.xml", "trusted": False},
    {"name": "식품음료신문", "url": "http://www.thinkfood.co.kr/rss/allArticle.xml", "trusted": True},
    {"name": "뉴스1 생활", "url": "https://www.news1.kr/rss/life.xml", "trusted": False},
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
        # 건강 전문 매체도 건강기능식품 키워드 최소 1개 요구 (병원뉴스 차단)
        return any(kw in combined for kw in HEALTH_KEYWORDS)
    return any(kw in title for kw in HEALTH_KEYWORDS) or \
           any(kw in desc for kw in HEALTH_KEYWORDS)


def categorize(title, desc=""):
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