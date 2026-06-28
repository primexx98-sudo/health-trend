import logging
import time
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

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

        logger.info(f"급상승 키워드 {len(rising)}개 수집 완료")
        return rising[:10]
    except Exception as e:
        logger.error(f"급상승 키워드 수집 실패: {e}")
        return []
