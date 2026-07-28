"""
2026-07-28 일회성 백필 스크립트.

과거 dashboard_YYYYMMDD.html 아카이브는 그날 실행된 구버전 dashboard.py로
이미 렌더링돼 저장된 정적 파일이라, 최신 코드(일간/주간/월간 탭)를 추가해도
소급 적용되지 않는다. 이 스크립트는 아카이브를 다시 생성하는 대신, 이미 저장된
HTML에 탭 UI를 직접 주입한다(정규식 치환) — main.py의 patch_legacy_dashboards()와
같은 발상이지만 탭은 카드 스타일까지 필요해서 별도 스크립트로 분리했다.

과거 버전마다 헤더 구조·CSS 클래스가 상당히 달라서(2026-07-22 다크테마 전면개편 등),
어떤 버전이든 항상 존재하는 세 앵커만 사용한다: `<body>`, `</body>`, `id="date-select"`.
주입하는 CSS는 그 페이지의 기존 스타일에 의존하지 않도록 색상을 하드코딩한 완전
독립 블록이다(다크 테마 고정 — 옛 페이지는 라이트/다크 토글이 아예 없거나 있어도
이 패치가 그 토글과 연동되지는 않음, 절충).

주간/월간 내용은 "그 날짜 기준 회차"가 아니라 항상 최신 1건을 보여준다 — 과거
주/월별 이력을 보관하는 기능은 없기 때문(사용자 확인 후 진행, 2026-07-28).

실행: python scripts/backfill_tabs.py
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(_repo_root, "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")

_STYLE = """
<style>
/* 2026-07-28 일간/주간/월간 탭 소급 패치 — 이 페이지의 기존 스타일과 무관한 독립 블록 */
.patched-tab-bar { display:flex; gap:6px; align-items:center; }
.patched-tab-btn { background:transparent; border:none; border-bottom:2px solid transparent; color:#929aa5; padding:8px 4px; font-size:0.92rem; font-weight:600; cursor:pointer; font-family:inherit; }
.patched-tab-btn.active { color:#fcd535; border-bottom-color:#fcd535; }
.patched-tab-btn:hover { color:#eaecef; }
.patched-panel[hidden] { display:none; }
.patched-container { padding:0 30px; }
.patched-card { background:#1e2329; border-radius:12px; margin-bottom:20px; padding:14px 18px; }
.patched-card-header { font-weight:600; font-size:1rem; margin-bottom:10px; color:#eaecef; }
.patched-summary-line { font-size:0.85rem; padding:3px 0; color:#eaecef; }
.patched-news-item { padding:7px 0; border-bottom:1px solid #2b3139; font-size:0.87rem; }
.patched-news-item a { color:#eaecef; text-decoration:none; }
.patched-news-item a:hover { color:#fcd535; }
.patched-muted { color:#707a8a; font-size:0.85rem; }
@media (max-width:576px){ .patched-container{padding:0 16px;} }
</style>
"""

_TAB_BAR = """<div class="patched-tab-bar" style="background:#0b0e11;padding:10px 30px;">
<button class="patched-tab-btn" data-tab="daily" onclick="patchedSwitchTab('daily')">일간</button>
<button class="patched-tab-btn" data-tab="weekly" onclick="patchedSwitchTab('weekly')">주간</button>
<button class="patched-tab-btn" data-tab="monthly" onclick="patchedSwitchTab('monthly')">월간</button>
</div>
"""

_TAB_JS = """
<script>
function patchedSwitchTab(name){
  ['daily','weekly','monthly'].forEach(function(n){
    var panel = document.getElementById('patched-tab-' + n);
    if (panel) panel.hidden = (n !== name);
    var btn = document.querySelector('.patched-tab-btn[data-tab="' + n + '"]');
    if (btn) btn.classList.toggle('active', n === name);
  });
}
patchedSwitchTab('daily');
</script>
"""


def _no_data():
    return '<span class="patched-muted">데이터 수집 중...</span>'


def _render_legacy_period_section(data, kind):
    empty_label = "주간" if kind == "weekly" else "월간"
    if not data:
        return (
            f'<div class="patched-card"><div class="patched-card-header">📅 {empty_label} 요약</div>'
            f'<span class="patched-muted">{empty_label} 집계 데이터를 아직 축적 중입니다.</span></div>'
        )

    label = data.get("period_label", "")
    ai = data.get("ai_summary")
    if ai and ai.get("summary"):
        ai_html = f'<div class="patched-summary-line">{ai["summary"]}</div>' + "".join(
            f'<div class="patched-summary-line">・ {pt}</div>' for pt in ai.get("key_points", [])
        )
    else:
        ai_html = '<span class="patched-muted">AI 요약을 생성하지 못했습니다.</span>'

    keyword_rows = "".join(
        f'<div class="patched-summary-line">{i+1}. <b>{k["keyword"]}</b> (평균 {k["avg_ratio"]:.0f})</div>'
        for i, k in enumerate(data.get("top_keywords", [])[:10])
    ) or _no_data()

    news_rows = "".join(
        f'<div class="patched-news-item"><a href="{n.get("link","")}" target="_blank">[{n["category"]}] {n["title"]}</a></div>'
        for n in data.get("news_highlights", [])[:10]
    ) or _no_data()

    ecom_rows = "".join(
        f'<div class="patched-summary-line">{e["platform"]} '
        + ("🆕 신규진입: " if e["kind"] == "new" else "▲ 순위상승: ")
        + f'<b>{e["name"]}</b></div>'
        for e in data.get("ecommerce_highlights", [])[:10]
    ) or _no_data()

    foodnews_html = ""
    if kind == "monthly":
        foodnews = data.get("foodnews") or {}
        cols = ""
        for section_label in ("건강기능식품", "신상품"):
            items = foodnews.get(section_label, [])
            rows = "".join(
                f'<div class="patched-news-item"><a href="{it.get("link","")}" target="_blank">{it["title"]}</a></div>'
                for it in items[:8]
            ) or _no_data()
            cols += f'<div class="col-md-6"><div class="patched-card"><div class="patched-card-header">📰 식품저널 {section_label} ({len(items)}건)</div>{rows}</div></div>'
        foodnews_html = f'<div class="row">{cols}</div>'

    return f"""
<div class="patched-card">
  <div class="patched-card-header">📅 {label} 요약</div>
  {ai_html}
</div>
<div class="row">
  <div class="col-md-4"><div class="patched-card"><div class="patched-card-header">📊 {empty_label} 검색 상위 키워드</div>{keyword_rows}</div></div>
  <div class="col-md-4"><div class="patched-card"><div class="patched-card-header">📰 {empty_label} 주요 뉴스</div>{news_rows}</div></div>
  <div class="col-md-4"><div class="patched-card"><div class="patched-card-header">🛒 {empty_label} 이커머스 동향</div>{ecom_rows}</div></div>
</div>
{foodnews_html}"""


def _load_latest(period_dir, prefix):
    if not os.path.isdir(period_dir):
        return None
    files = sorted(glob.glob(os.path.join(period_dir, f"{prefix}_*.json")))
    if not files:
        return None
    with open(files[-1], "r", encoding="utf-8") as f:
        return json.load(f)


def patch_file(path, weekly_html, monthly_html):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    if "patched-tab-bar" in html or 'class="tab-bar"' in html:
        return False  # 이미 패치됨

    html = html.replace("</style>", "</style>\n" + _STYLE, 1)
    # 과거 템플릿마다 헤더 구조·date-select 존재 방식이 달라(일부는 JS로 런타임에 동적
    # 생성되어 정적 HTML에 앵커가 아예 없음, 2026-07-28 실제로 겪음) 어떤 버전이든
    # 항상 존재하는 <body> 바로 뒤에 탭바+래퍼를 함께 주입한다.
    html = html.replace(
        "<body>",
        "<body>\n" + _TAB_BAR + '<div id="patched-tab-daily" class="patched-panel">',
        1,
    )
    injected_tail = (
        f'</div>\n'
        f'<div id="patched-tab-weekly" class="patched-panel patched-container" hidden>{weekly_html}</div>\n'
        f'<div id="patched-tab-monthly" class="patched-panel patched-container" hidden>{monthly_html}</div>\n'
        f'{_TAB_JS}\n</body>'
    )
    html = html.replace("</body>", injected_tail, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return True


def main():
    weekly_data = _load_latest(os.path.join(DATA_DIR, "weekly"), "weekly")
    monthly_data = _load_latest(os.path.join(DATA_DIR, "monthly"), "monthly")
    weekly_html = _render_legacy_period_section(weekly_data, "weekly")
    monthly_html = _render_legacy_period_section(monthly_data, "monthly")

    patched, skipped = 0, 0
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "dashboard_????????.html"))):
        if patch_file(path, weekly_html, monthly_html):
            patched += 1
        else:
            skipped += 1
    print(f"패치 완료: {patched}개, 건너뜀(이미 패치됨): {skipped}개")


if __name__ == "__main__":
    main()
