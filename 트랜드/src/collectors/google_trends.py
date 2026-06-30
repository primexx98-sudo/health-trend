import logging
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
    # 기타
    "부동산", "주식", "펀드", "코인", "게임",
]

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
        pytrends.build_payload(["건강기능식품", "건강보조제", "영양제"], timeframe="now 1-d", geo="KR")
        time.sleep(1)
        related = pytrends.related_queries()

        rising = []
        for kw, data in related.items():
            if data and data.get("rising") is not None:
                df = data["rising"]
                if not df.empty:
                    for _, row in df.head(5).iterrows():
                        rising.append({"keyword": row["query"], "value": row["value"]})

        # 건기식 무관 키워드 블랙리스트 필터
        filtered = [
            r for r in rising
            if not any(bl in r["keyword"] for bl in RISING_BLACKLIST)
        ]
        logger.info(f"급상승 키워드 수집 {len(rising)}개 → 필터 후 {len(filtered)}개")
        return filtered[:10]
    except Exception as e:
        logger.error(f"급상승 키워드 수집 실패: {e}")
        return []
