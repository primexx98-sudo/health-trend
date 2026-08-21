import re
import requests
import logging
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
    # 채용공고/입시홍보 — 본문에 "개별인정"·"건강기능식품" 등 핵심어가 우연히
    # 섞여 있어도 뉴스가 아니라 광고성 게시물이라 규제/연구 동향에서 걸러냄
    "채용", "모집공고", "구인", "수시", "정시", "입시",
    # 기업 CSR/사회공헌 기사 — 회사 소개 문구에 "건강기능식품 연구" 같은
    # 핵심어가 섞여 research로 오분류되던 사례
    "자립준비청년", "사회공헌",
]

# ─── 분류 키워드 (직접 수정 가능) ─────────────────────────────────
# 2026-08-22: "발표"·"분석"이 너무 범용적이라(실적발표/시장분석 등) 특허소송·공시 같은
# 기업 법률·재무 뉴스가 핵심 성분 키워드를 우연히 언급하면 "연구"로 오분류되던 문제
# (예: "SK바이오팜 특허소송" 기사) — 두 단어를 단독 트리거에서 빼고 더 구체적인
# 복합어로 교체, 남을 수 있는 오탐은 아래 _RESEARCH_EXCLUDE_KEYWORDS로 추가 차단.
RESEARCH_KEYWORDS = [
    "연구", "임상", "논문", "학회", "메타분석", "실험", "임상시험",
    "연구 결과 발표", "학회 발표", "학술대회 발표", "성분 분석 결과", "효능 분석 결과",
    "효능 확인", "성분 연구",
]

_RESEARCH_EXCLUDE_KEYWORDS = [
    "특허소송", "특허침해", "손해배상", "실적발표", "공시", "주가", "인수합병",
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
    # 기업 법률/재무 뉴스는 핵심 성분 키워드를 우연히 언급해도 연구·임상 동향으로 보지 않음
    if any(kw in combined for kw in _RESEARCH_EXCLUDE_KEYWORDS):
        return "general"
    # research는 "연구"류 단어 + 실제 성분/제품 키워드가 함께 있어야 인정
    if any(kw in combined for kw in RESEARCH_KEYWORDS) and any(kw in combined for kw in CORE_HEALTH_KEYWORDS):
        return "research"
    return "general"


# 근접 중복 판정 임계값 — 실제 중복 사례(같은 제품 출시를 매체별로 다르게 보도)의
# 문자 2-gram Jaccard 유사도가 0.19~0.37에서 형성되고, 무관한 기사끼리는 0.05 이하로
# 뚜렷이 갈리는 걸 실측 확인해 0.28로 설정. "식약처 개별인정형 원료 3종/5종 인정"처럼
# 정형화된 규제 헤드라인은 서로 다른 발표인데도 유사도가 0.5+까지 올라가므로, 두 제목에
# 모두 숫자가 있고 그 숫자 집합이 겹치지 않으면(3종 vs 5종) 중복 판정에서 제외한다.
_DUP_SIMILARITY_THRESHOLD = 0.28


def _normalize_for_dedup(title):
    t = re.sub(r"\[[^\]]*\]", "", title)  # "[7월 올영픽]" 같은 접두 태그 제거
    t = re.sub(r"[\"'“”‘’()「」『』…·,.!?]", "", t)
    return re.sub(r"\s+", "", t)


def _char_bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def _title_similarity(norm_a, norm_b):
    bg_a, bg_b = _char_bigrams(norm_a), _char_bigrams(norm_b)
    if not bg_a or not bg_b:
        return 0.0
    return len(bg_a & bg_b) / len(bg_a | bg_b)


def is_near_duplicate(title, kept_norms):
    """이미 채택된 기사 제목들(정규화된 문자열 리스트) 대비 근접 중복인지 판정.
    제목 완전일치만 걸러내던 기존 dedup으로는 매체마다 표현이 다른 동일 사건
    보도(예: 같은 제품 출시 소식 3건)를 못 걸렀던 문제를 보완한다."""
    norm = _normalize_for_dedup(title)
    norm_digits = set(re.findall(r"\d+", norm))
    for kn in kept_norms:
        kn_digits = set(re.findall(r"\d+", kn))
        if norm_digits and kn_digits and norm_digits.isdisjoint(kn_digits):
            continue
        if _title_similarity(norm, kn) >= _DUP_SIMILARITY_THRESHOLD:
            return True
    return False


def get_naver_news(query, display=10):
    url = "https://openapi.naver.com/v1/search/news.json"
    # requests가 params 값을 자동으로 URL 인코딩하므로 quote()를 또 적용하면 이중 인코딩되어
    # 쿼리가 깨짐 (Naver가 의도한 검색어를 못 읽고 무관한 결과를 반환하던 원인, 2026-07-22 발견)
    params = {"query": query, "display": display, "start": 1, "sort": "date"}
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

    kept_norms = []
    research, regulatory, general = [], [], []

    for item in research_items:
        if not is_near_duplicate(item["title"], kept_norms):
            kept_norms.append(_normalize_for_dedup(item["title"]))
            research.append(item)

    for item in regulatory_items:
        if not is_near_duplicate(item["title"], kept_norms):
            kept_norms.append(_normalize_for_dedup(item["title"]))
            regulatory.append(item)

    for item in general_items:
        if not is_near_duplicate(item["title"], kept_norms):
            kept_norms.append(_normalize_for_dedup(item["title"]))
            general.append(item)

    for item in rss_items:
        if not is_near_duplicate(item["title"], kept_norms):
            kept_norms.append(_normalize_for_dedup(item["title"]))
            cat = item["category"]
            if cat == "research":
                research.append(item)
            elif cat == "regulatory":
                regulatory.append(item)
            else:
                general.append(item)

    # 2026-08-20: QUERIES_RESEARCH 여러 검색어를 순서대로 이어붙이기만 해서 쿼리
    # 순서에 따라 정렬됐음(쿼리 내부는 sort=date로 정렬되지만 쿼리 간 병합은
    # 안 됐음) — "최신 연구 소식"이라는 이름과 달리 실제로는 최신순이 아니었던
    # 문제(오늘 기사가 5번째로 밀려 요약 카드 상위 2건에 안 뜨던 사례)를 발견해
    # 병합 후 발행일 기준으로 다시 정렬.
    def _pubdate_key(item):
        try:
            return parsedate_to_datetime(item.get("pubDate", ""))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    research.sort(key=_pubdate_key, reverse=True)

    logger.info(f"뉴스 최종 - 일반:{len(general)} 연구:{len(research)} 규제:{len(regulatory)}")
    mfds = [r for r in regulatory if "mfds.go.kr" in r.get("link", "")]

    return {
        "news": general[:8],
        "research": research[:8],
        "regulatory": regulatory[:8],
        "mfds": mfds[:5],
    }