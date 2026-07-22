import glob
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_DIR, LOG_DIR, NAVER_CLIENT_ID
from collectors.naver_trends import get_top_keywords
from collectors.google_trends import get_rising_keywords
from collectors.sns_collector import get_sns_keywords
from collectors.news_collector import collect_all_news
from collectors.overseas_collector import get_overseas_news
from collectors.ecommerce_collector import get_ecommerce_rankings, attach_rank_changes
from collectors.law_summary_collector import get_law_weekly_summary
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
    '<script>(function(){'
    'if(document.getElementById("date-select"))return;'
    'var s=document.createElement("select");'
    's.id="date-select";'
    's.style.cssText="position:fixed;top:10px;right:15px;z-index:9999;'
    'background:rgba(45,106,79,0.92);color:#fff;'
    'border:1px solid rgba(255,255,255,0.4);border-radius:6px;'
    'padding:3px 8px;font-size:0.82rem;cursor:pointer";'
    'document.body.appendChild(s);'
    's.onchange=function(){location.href=this.value;};'
    'fetch("./history.json?v="+Date.now())'
    '.then(function(r){return r.json();})'
    '.then(function(a){'
    'var c=(location.pathname.match(/dashboard_(\\d{8})\\.html/)||[])[1];'
    'a.forEach(function(d,i){'
    'var o=document.createElement("option");'
    'var l=d.slice(0,4)+"-"+d.slice(4,6)+"-"+d.slice(6,8);'
    'o.value=i===0?"./index.html":"./dashboard_"+d+".html";'
    'o.text=i===0?l+" (오늘)":l;'
    's.appendChild(o);});'
    's.value=c?"./dashboard_"+c+".html":"./index.html";'
    '}).catch(function(){});'
    '})();</script>'
)

import re as _re

def patch_legacy_dashboards(docs_dir):
    for fpath in glob.glob(os.path.join(docs_dir, "dashboard_????????.html")):
        with open(fpath, "r", encoding="utf-8") as f:
            html = f.read()
        if "d-flex" in html:  # 새 템플릿 — 헤더에 select 이미 있음, 건너뜀
            continue
        if "position:fixed" in html:  # 이미 새 패치 적용됨
            continue
        # 구버전 패치 제거 후 신버전 삽입
        html = _re.sub(r'<select id="date-select"[\s\S]*?</script>', '', html, count=1)
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

def load_naver_snapshot(data_dir, date_str):
    path = os.path.join(data_dir, f"naver_{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return None

def save_naver_snapshot(data_dir, date_str, naver_data):
    import json as _json
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"naver_{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(naver_data, f, ensure_ascii=False)

def cleanup_old_snapshots(data_dir, keep_days=30):
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for fpath in glob.glob(os.path.join(data_dir, "naver_????????.json")):
        try:
            date_str = os.path.basename(fpath)[len("naver_"):-len(".json")]
            if datetime.strptime(date_str, "%Y%m%d") < cutoff:
                os.remove(fpath)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.getLogger("main").info(f"오래된 검색량 스냅샷 {removed}개 삭제")

def load_ecommerce_snapshot(data_dir, date_str):
    path = os.path.join(data_dir, f"ecommerce_{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return None

def save_ecommerce_snapshot(data_dir, date_str, ecommerce_data):
    import json as _json
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"ecommerce_{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(ecommerce_data, f, ensure_ascii=False)

def cleanup_old_ecommerce_snapshots(data_dir, keep_days=30):
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for fpath in glob.glob(os.path.join(data_dir, "ecommerce_????????.json")):
        try:
            date_str = os.path.basename(fpath)[len("ecommerce_"):-len(".json")]
            if datetime.strptime(date_str, "%Y%m%d") < cutoff:
                os.remove(fpath)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.getLogger("main").info(f"오래된 이커머스 스냅샷 {removed}개 삭제")

def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("트랜드 수집 시작")

    print("[1/5] 국내 키워드 순위 수집 중...")
    naver_data = get_top_keywords() or [{"keyword": "데이터 없음", "ratio": 0}]

    print("[2/5] 급상승 키워드 수집 중...")
    rising_data = get_rising_keywords()

    print("[3/5] SNS 키워드 수집 중...")
    sns_data = get_sns_keywords()

    print("[4/5] 뉴스/연구/해외 동향 수집 중...")
    news_data = collect_all_news()
    overseas_data = get_overseas_news()

    print("[5/5] 이커머스 판매순위·법령 요약 수집 중...")
    ecommerce_data = get_ecommerce_rankings()
    law_summary = get_law_weekly_summary()

    print("대시보드 생성 중...")
    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _committed_docs = os.path.join(_repo_root, "docs")

    # history.json: 커밋된 docs/ 백업 파일 + 오늘 날짜
    existing = sorted(
        [os.path.basename(f)[len("dashboard_"):-len(".html")]
         for f in glob.glob(os.path.join(_committed_docs, "dashboard_????????.html"))],
        reverse=True,
    )

    # 국내 인기순위 히스토리 — 커밋된 docs/data/의 스냅샷 기준 (이번 실행분 저장 전 상태)
    _committed_data_dir = os.path.join(_committed_docs, "data")
    _today_str = datetime.now().strftime("%Y%m%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    naver_prev_data = load_naver_snapshot(_committed_data_dir, yesterday_str)

    history_files = sorted(glob.glob(os.path.join(_committed_data_dir, "naver_????????.json")))[-14:]
    naver_history = []
    for fpath in history_files:
        d = os.path.basename(fpath)[len("naver_"):-len(".json")]
        if d == _today_str:
            continue
        data = load_naver_snapshot(_committed_data_dir, d)
        if data:
            naver_history.append({"date": d, "data": data})

    # 이커머스 순위 변동/신규진입 배지 — 전일 스냅샷과 비교
    ecommerce_prev_data = load_ecommerce_snapshot(_committed_data_dir, yesterday_str)
    ecommerce_data = attach_rank_changes(ecommerce_data, ecommerce_prev_data)

    html, date_str = generate_html(
        naver_data, sns_data, news_data, rising_data, overseas_data,
        ecommerce_data=ecommerce_data, naver_prev_data=naver_prev_data, naver_history=naver_history,
        law_summary=law_summary,
    )

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

    # 국내 인기순위 스냅샷 저장 (다음 실행의 순위 변동 배지·추이 차트에 사용) — 수집 실패 폴백 데이터는 저장하지 않음
    if not (len(naver_data) == 1 and naver_data[0]["keyword"] == "데이터 없음"):
        _snapshot_dir = os.path.join(OUTPUT_DIR, "data")
        save_naver_snapshot(_snapshot_dir, date_str, naver_data)
        cleanup_old_snapshots(_snapshot_dir)

    # 이커머스 스냅샷 저장 (다음 실행의 순위 변동·신규진입 배지에 사용)
    if ecommerce_data.get("date"):
        _snapshot_dir = os.path.join(OUTPUT_DIR, "data")
        save_ecommerce_snapshot(_snapshot_dir, date_str, ecommerce_data)
        cleanup_old_ecommerce_snapshots(_snapshot_dir)

    logger.info(f"완료: {index_path}")
    print(f"완료! index.html 업데이트됨 (백업: dashboard_{date_str}.html)")

if __name__ == "__main__":
    main()
