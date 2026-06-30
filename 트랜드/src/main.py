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

_LEGACY_NAV = (
    '<select id="date-select" class="date-select" '
    'style="background:rgba(255,255,255,0.15);color:white;border:1px solid rgba(255,255,255,0.4);'
    'border-radius:6px;padding:4px 8px;font-size:0.85rem;cursor:pointer;margin-top:6px;display:block"></select>'
    '<script>(function(){'
    'var sel=document.getElementById("date-select");if(!sel)return;'
    'sel.onchange=function(){location.href=this.value;};'
    'fetch("./history.json").then(function(r){return r.json();})'
    '.then(function(dates){'
    'var cur=(location.pathname.match(/dashboard_(\\d{8})\\.html/)||[])[1];'
    'dates.forEach(function(d,i){'
    'var opt=document.createElement("option");'
    'var label=d.slice(0,4)+"-"+d.slice(4,6)+"-"+d.slice(6,8);'
    'opt.value=i===0?"./index.html":"./dashboard_"+d+".html";'
    'opt.text=i===0?label+" (오늘)":label;'
    'if(cur===d||(!cur&&i===0))opt.selected=true;'
    'sel.appendChild(opt);});}).catch(function(){});})();</script>'
)

def patch_legacy_dashboards(docs_dir):
    for fpath in glob.glob(os.path.join(docs_dir, "dashboard_????????.html")):
        with open(fpath, "r", encoding="utf-8") as f:
            html = f.read()
        if "date-select" in html:
            continue
        patched = html.replace("</body>", _LEGACY_NAV + "</body>", 1)
        if patched != html:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(patched)

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
    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _committed_docs = os.path.join(_repo_root, "docs")

    # history.json: 커밋된 docs/ 백업 파일 + 오늘 날짜
    existing = sorted(
        [os.path.basename(f)[len("dashboard_"):-len(".html")]
         for f in glob.glob(os.path.join(_committed_docs, "dashboard_????????.html"))],
        reverse=True,
    )
    html, date_str = generate_html(naver_data, google_data, sns_data, news_data, rising_data, overseas_data)

    all_dates = ([date_str] + [d for d in existing if d != date_str])[:30]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 날짜별 백업 (최근 30일 보관)
    archive_path = os.path.join(OUTPUT_DIR, f"dashboard_{date_str}.html")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 고정 URL — index.html에 오늘 대시보드 직접 덮어쓰기
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    # history.json — 모든 HTML 파일의 JS 드롭다운이 참조
    import json as _json
    with open(os.path.join(OUTPUT_DIR, "history.json"), "w", encoding="utf-8") as f:
        _json.dump(all_dates, f, ensure_ascii=False)

    # 구형 백업 파일에 네비 스크립트 삽입 (커밋된 docs/ 직접 패치)
    patch_legacy_dashboards(_committed_docs)

    cleanup_old_dashboards(OUTPUT_DIR)

    logger.info(f"완료: {index_path}")
    print(f"완료! index.html 업데이트됨 (백업: dashboard_{date_str}.html)")

if __name__ == "__main__":
    main()
