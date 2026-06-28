import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_DIR, LOG_DIR, NAVER_CLIENT_ID
from collectors.naver_trends import get_top_keywords
from collectors.google_trends import get_global_trends, get_rising_keywords
from collectors.sns_collector import get_sns_keywords
from collectors.news_collector import collect_all_news
from generator.dashboard import generate_html

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()]
    )

def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("트랜드 수집 시작")

    print("[1/4] 국내 키워드 순위 수집 중...")
    naver_data = get_top_keywords() or [{"keyword": "데이터 없음", "ratio": 0}]

    print("[2/4] 글로벌 트랜드 수집 중...")
    google_data = get_global_trends()
    rising_data = get_rising_keywords()

    print("[3/4] SNS 키워드 수집 중...")
    sns_data = get_sns_keywords()

    print("[4/4] 뉴스/연구 동향 수집 중...")
    news_data = collect_all_news()

    print("대시보드 생성 중...")
    html, date_str = generate_html(naver_data, google_data, sns_data, news_data, rising_data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 날짜별 파일 저장
    output_path = os.path.join(OUTPUT_DIR, f"dashboard_{date_str}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # index.html 업데이트 (GitHub Pages 진입점)
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    redirect_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url=dashboard_{date_str}.html">
<title>건강기능식품 트랜드</title></head>
<body><p>대시보드로 이동 중... <a href="dashboard_{date_str}.html">클릭</a></p></body>
</html>"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(redirect_html)

    logger.info(f"완료: {output_path}")
    print(f"완료! dashboard_{date_str}.html 생성됨")

if __name__ == "__main__":
    main()
