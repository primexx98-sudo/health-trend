import glob
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_DIR, LOG_DIR, NAVER_CLIENT_ID
from collectors.naver_trends import get_top_keywords, get_rising_from_previous
from collectors.sns_collector import get_sns_keywords
from collectors.news_collector import collect_all_news
from collectors.overseas_collector import get_overseas_news
from collectors.ecommerce_collector import get_ecommerce_rankings, attach_rank_changes
from collectors.law_summary_collector import get_law_weekly_summary
from generator.dashboard import generate_html, write_archive_files

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

def cleanup_old_dashboards(output_dir, keep_days=90):
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

def cleanup_old_snapshots(data_dir, keep_days=90):
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

def save_digest_snapshot(data_dir, date_str, sns_data, news_data, rising_data, law_summary):
    """뉴스/SNS/급상승 키워드/법령요약은 그동안 그날 HTML에만 반영되고 사라졌음 —
    주간/월간 집계의 원본 재료로 쓰기 위해 구조화된 형태로 보존한다."""
    import json as _json
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"digest_{date_str}.json")
    payload = {
        "date": date_str,
        "sns_data": sns_data,
        "news_data": news_data,
        "rising_data": rising_data,
        "law_summary": law_summary,
    }
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, ensure_ascii=False)


def cleanup_old_digests(data_dir, keep_days=90):
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for fpath in glob.glob(os.path.join(data_dir, "digest_????????.json")):
        try:
            date_str = os.path.basename(fpath)[len("digest_"):-len(".json")]
            if datetime.strptime(date_str, "%Y%m%d") < cutoff:
                os.remove(fpath)
                removed += 1
        except Exception:
            pass
    if removed:
        logging.getLogger("main").info(f"오래된 digest 스냅샷 {removed}개 삭제")


def load_latest_period_snapshot(period_dir, prefix):
    """docs/data/weekly 또는 docs/data/monthly에서 파일명 기준 최신 집계 파일을 읽는다.
    아직 한 번도 집계가 안 돌았으면 폴더/파일이 없을 수 있음 — None 반환."""
    if not os.path.isdir(period_dir):
        return None
    files = sorted(glob.glob(os.path.join(period_dir, f"{prefix}_*.json")))
    if not files:
        return None
    try:
        import json as _json
        with open(files[-1], "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return None


def load_period_archive(period_dir, prefix, keep_n):
    """docs/data/weekly 또는 docs/data/monthly의 전체 회차를 최신순으로 로드 — 보관함 탭용.
    weekly/monthly json은 별도 삭제 로직이 없어 계속 쌓이므로, 페이지에 무한정 끼워넣지 않게
    UI 표시 개수만 keep_n으로 제한한다(파일 자체는 그대로 유지됨)."""
    if not os.path.isdir(period_dir):
        return []
    files = sorted(glob.glob(os.path.join(period_dir, f"{prefix}_*.json")), reverse=True)[:keep_n]
    import json as _json
    out = []
    for fpath in files:
        period_id = os.path.basename(fpath)[len(prefix) + 1:-len(".json")]
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                out.append((period_id, _json.load(f)))
        except Exception:
            pass
    return out


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

def cleanup_old_ecommerce_snapshots(data_dir, keep_days=90):
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

    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _committed_docs = os.path.join(_repo_root, "docs")
    _committed_data_dir = os.path.join(_committed_docs, "data")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    naver_prev_data = load_naver_snapshot(_committed_data_dir, yesterday_str)

    print("[1/5] 국내 키워드 순위 수집 중...")
    naver_data = get_top_keywords() or [{"keyword": "데이터 없음", "ratio": 0}]

    print("[2/5] 급상승 키워드 계산 중...")
    rising_data = get_rising_from_previous(naver_data, naver_prev_data)

    print("[3/5] SNS 키워드 수집 중...")
    sns_data = get_sns_keywords()

    print("[4/5] 뉴스/연구/해외 동향 수집 중...")
    news_data = collect_all_news()
    overseas_data = get_overseas_news()

    print("[5/5] 이커머스 판매순위·법령 요약 수집 중...")
    ecommerce_data = get_ecommerce_rankings()
    law_summary = get_law_weekly_summary()

    print("대시보드 생성 중...")

    # history.json: 커밋된 docs/ 백업 파일 + 오늘 날짜
    existing = sorted(
        [os.path.basename(f)[len("dashboard_"):-len(".html")]
         for f in glob.glob(os.path.join(_committed_docs, "dashboard_????????.html"))],
        reverse=True,
    )

    # 이커머스 순위 변동/신규진입 배지 — 전일 스냅샷과 비교
    ecommerce_prev_data = load_ecommerce_snapshot(_committed_data_dir, yesterday_str)
    ecommerce_data = attach_rank_changes(ecommerce_data, ecommerce_prev_data)

    # 주간/월간 탭 — weekly.yml/monthly.yml이 각자 커밋해둔 최신 집계를 읽어 반영.
    # 아직 한 번도 안 돌았으면 None → dashboard.py가 "축적 중" 빈 상태로 표시.
    weekly_data = load_latest_period_snapshot(os.path.join(_committed_data_dir, "weekly"), "weekly")
    monthly_data = load_latest_period_snapshot(os.path.join(_committed_data_dir, "monthly"), "monthly")

    # 보관함 탭 — 주간은 최근 104회(약 2년), 월간은 최근 36회(3년)까지 화면에 노출.
    # 그 이전 회차도 파일은 삭제되지 않고 docs/data/weekly·monthly에 그대로 남아있음.
    weekly_archive = load_period_archive(os.path.join(_committed_data_dir, "weekly"), "weekly", keep_n=104)
    monthly_archive = load_period_archive(os.path.join(_committed_data_dir, "monthly"), "monthly", keep_n=36)

    html, date_str = generate_html(
        naver_data, sns_data, news_data, rising_data, overseas_data,
        ecommerce_data=ecommerce_data, naver_prev_data=naver_prev_data,
        law_summary=law_summary, weekly_data=weekly_data, monthly_data=monthly_data,
    )

    # 보관함 탭의 주간/월간 회차는 대시보드 HTML에 직접 심지 않고, JS가 열람 시점에
    # fetch로 불러올 정적 데이터 파일(index.json + fragments/*.html)로 별도 기록한다.
    # OUTPUT_DIR(트랜드/docs)에 쓰면 기존 워크플로가 "cp -r 트랜드/docs/. docs/"로
    # 그대로 커밋 대상 docs/에 옮겨준다 — naver/ecommerce 스냅샷과 동일한 경로 패턴.
    write_archive_files(os.path.join(OUTPUT_DIR, "data", "weekly"), weekly_archive, "weekly")
    write_archive_files(os.path.join(OUTPUT_DIR, "data", "monthly"), monthly_archive, "monthly")

    # 일별 대시보드 백업은 cleanup_old_dashboards가 90일로 보관 기간을 관리하므로
    # 여기서는 별도 개수 제한을 두지 않고 실제 존재하는 파일 전부를 노출한다.
    all_dates = [date_str] + [d for d in existing if d != date_str]

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

    # digest 스냅샷 저장 (주간/월간 집계 원본 재료 — 뉴스/SNS/급상승/법령요약)
    _snapshot_dir = os.path.join(OUTPUT_DIR, "data")
    save_digest_snapshot(_snapshot_dir, date_str, sns_data, news_data, rising_data, law_summary)
    cleanup_old_digests(_snapshot_dir)

    logger.info(f"완료: {index_path}")
    print(f"완료! index.html 업데이트됨 (백업: dashboard_{date_str}.html)")

if __name__ == "__main__":
    main()
