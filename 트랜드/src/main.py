import glob
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_DIR, LOG_DIR, NAVER_CLIENT_ID
from collectors.naver_trends import get_top_keywords
from collectors.google_trends import get_global_trends, get_rising_keywords
from collectors.sns_collector import get_sns_keywords
from collectors.news_collector import collect_all_news
from collectors.overseas_collector import get_overseas_news
from generator.dashboard import generate_html

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()]
    )

def cleanup_old_dashboards(output_dir, keep_days=30):
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for fpath in glob.glob(os.path.join(output_dir, "dashboard_????????.html")):
        try:
            date_str = os.path.basename(fpath)[len("dashboard_"):-len(".html")]
            if datetime.strptime(date_str, "%Y%m%d") < cutoff:
                os.remove(fpath)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.getLogger("main").info(f"오래된 대시보드 {removed}개 삭제")

def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("트랜드 수집 시작")

    print("[1/5] 국내 키워드 순위 수집 중...")
    naver_data = get_top_keywords() or [{"keyword": "데이터 없음", "ratio": 0}]

    print("[2/5] 글로벌 트랜드 수집 중...")
    google_data = get_global_trends()
    rising_data = get_rising_keywords()

    print("[3/5] SNS 키워드 수집 중...")
    sns_data = get_sns_keywords()

    print("[4/5] 뉴스/연구 동향 수집 중...")
    news_data = collect_all_news()

    print("[5/5] 해외 업계 동향 수집 중...")
    overseas_data = get_overseas_news()

    print("대시보드 생성 중...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    available_dates = sorted(
        [
            (os.path.basename(f)[len("dashboard_"):-len(".html")],)
            for f in glob.glob(os.path.join(OUTPUT_DIR, "dashboard_????????.html"))
            if len(os.path.basename(f)) == len("dashboard_YYYYMMDD.html")
        ],
        reverse=True,
    )
    html, date_str = generate_html(naver_data, google_data, sns_data, news_data, rising_data, overseas_data, available_dates)

    # 날짜별 백업 (최근 30일 보관)
    archive_path = os.path.join(OUTPUT_DIR, f"dashboard_{date_str}.html")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 고정 URL — index.html에 오늘 대시보드 직접 덮어쓰기
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    cleanup_old_dashboards(OUTPUT_DIR)

    logger.info(f"완료: {index_path}")
    print(f"완료! index.html 업데이트됨 (백업: dashboard_{date_str}.html)")

if __name__ == "__main__":
    main()
