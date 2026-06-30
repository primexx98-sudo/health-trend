import logging
import re
import time
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

# 급상승 키워드에서 제외할 건기식 무관 카테고리
RISING_BLACKLIST = [
    # 뷰티/미용
    "속눈썹", "화장", "파운데이션", "립스틱", "아이섀도", "블러셔",
    "헤어", "샴푸", "트리트먼트", "에센스", "세럼", "스킨케어", "네일",
    # 패션
    "코디", "패션", "신발", "가방", "의류", "원피스", "청바지",
    # 일반 식품
    "레시피", "맛집", "배달", "음식점", "요리", "식당", "편의점", "카페",
    # 연예/문화
    "아이돌", "드라마", "영화", "연예인", "유튜버", "웹툰",
    # 교육/기관
    "교육", "센터", "학원", "대학", "강의", "수업",
    # 의료 (건기식 아님)
    "병원", "약국", "처방", "수술", "치료",
    # 기타
    "부동산", "주식", "펀드", "코인", "게임",
]

# 급상승 키워드가 건기식 관련임을 판단하는 최소 포함 조건
RISING_RELEVANT_TERMS = {
    "영양제", "비타민", "유산균", "오메가", "마그네슘", "콜라겐", "홍삼",
    "프로바이오틱스", "글루타치온", "루테인", "아연", "칼슘", "철분",
    "크레아틴", "밀크시슬", "엽산", "NMN", "NAD", "건강기능식품",
    "건강보조제", "보충제", "서플리먼트", "면역", "항산화",
    "피로", "혈당", "혈압", "관절", "수면", "단백질", "체지방",
}

_PARTICLES = sorted([
    "에서", "에게서", "에게", "으로부터", "으로", "에",
    "이나", "이고", "이며", "이라도", "이라", "이란", "이든",
    "이", "가", "을", "를", "의", "은", "는",
    "로부터", "로", "와", "과", "도", "만", "부터", "까지",
], key=len, reverse=True)

def _normalize_spacing(text):
    """Google Trends가 분리한 조사를 앞 단어에 다시 붙임 ('눈 에' → '눈에')"""
    result = text
    for p in _PARTICLES:
        result = re.sub(r'(?<=[가-힣A-Za-z0-9]) ' + re.escape(p) + r'(?=\s|$)', p, result)
    return result


GLOBAL_KEYWORDS = [
    "vitamin supplement", "probiotic", "collagen", "omega 3",
    "magnesium", "protein powder", "NAD supplement", "ashwagandha",
    "turmeric", "zinc supplement"
]

def get_global_trends():
    """Google Trends - 글로벌 건강보조제 트랜드"""
    try:
        pytrends = TrendReq(hl="ko", tz=540, timeout=(10, 25))
        pytrends.build_payload(GLOBAL_KEYWORDS[:5], timeframe="now 7-d", geo="")
        interest_df = pytrends.interest_over_time()

        if interest_df.empty:
            logger.warning("Google Trends 데이터 없음")
            return []

        latest = interest_df.iloc[-1].drop("isPartial", errors="ignore")
        results = [{"keyword": kw, "ratio": int(val)} for kw, val in latest.items()]
        results.sort(key=lambda x: x["ratio"], reverse=True)
        logger.info(f"Google Trends {len(results)}개 수집 완료")
        return results
    except Exception as e:
        logger.error(f"Google Trends 수집 실패: {e}")
        return []

def get_rising_keywords():
    """Google Trends - 급상승 키워드"""
    try:
        pytrends = TrendReq(hl="ko", tz=540, timeout=(10, 25))
        pytrends.build_payload(["건강기능식품", "영양제", "비타민", "유산균", "오메가3"], timeframe="now 1-d", geo="KR")
        time.sleep(1)
        related = pytrends.related_queries()

        rising = []
        for kw, data in related.items():
            if data and data.get("rising") is not None:
                df = data["rising"]
                if not df.empty:
                    for _, row in df.head(5).iterrows():
                        rising.append({"keyword": _normalize_spacing(row["query"]), "value": row["value"]})

        # 블랙리스트 필터
        filtered = [
            r for r in rising
            if not any(bl in r["keyword"] for bl in RISING_BLACKLIST)
        ]
        # 건기식 관련 키워드만 허용 (최소 1개 관련 용어 포함)
        relevant = [
            r for r in filtered
            if any(term in r["keyword"] for term in RISING_RELEVANT_TERMS)
        ]
        logger.info(f"급상승 키워드 수집 {len(rising)}개 → 블랙리스트 {len(filtered)}개 → 관련성 {len(relevant)}개")
        return relevant[:10]
    except Exception as e:
        logger.error(f"급상승 키워드 수집 실패: {e}")
        return []
