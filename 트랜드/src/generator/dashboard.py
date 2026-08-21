from datetime import datetime, timezone, timedelta
import hashlib
import os

_KST = timezone(timedelta(hours=9))

LAW_MONITOR_URL = "https://primexx98-sudo.github.io/food-monitor-hub/law/"


def _law_item_anchor_id(item):
    """FOODLAW-MONITORING(build_site.py)의 item_anchor_id()와 동일한 알고리즘
    (url 또는 title을 md5 해시해 앞 10자) — "오늘의 요약"의 법령 항목을 클릭하면
    법령 모니터의 해당 항목으로 바로 이동하는 딥링크를 만들기 위함. 두 프로젝트가
    서로 다른 저장소라 한쪽만 바뀌면 링크가 깨지니, 바꿀 때는 반드시 같이 수정."""
    key = item.get("url") or item.get("title", "")
    return "law-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:10]

_ECOM_PLATFORMS = [
    ("카카오선물하기", "🎁 카카오 선물하기"),
    ("다이소몰", "🏪 다이소몰"),
    ("올리브영", "💚 올리브영"),
]
_BAR_COLORS = ["#fcd535", "#f0b90b", "#eaecef", "#929aa5", "#707a8a"]

_NAV_JS = """\
<script>
(function(){
  var sel = document.getElementById('date-select');
  if (!sel) return;
  sel.onchange = function(){ location.href = this.value; };
  fetch('./history.json?v=' + Date.now())
    .then(function(r){ return r.json(); })
    .then(function(dates){
      var cur = (location.pathname.match(/dashboard_(\\d{8})\\.html/) || [])[1];
      var archiveList = document.getElementById('archive-daily-list');
      if (archiveList) archiveList.innerHTML = '';
      dates.forEach(function(d, i){
        var label = d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8);
        var href = i === 0 ? './index.html' : ('./dashboard_'+d+'.html');
        var opt = document.createElement('option');
        opt.value = href;
        opt.text  = i === 0 ? label+' (오늘)' : label;
        sel.appendChild(opt);
        if (archiveList) {
          var a = document.createElement('a');
          a.href = href;
          a.className = 'archive-list-link';
          a.textContent = i === 0 ? label+' (오늘)' : label;
          archiveList.appendChild(a);
        }
      });
      sel.value = cur ? ('./dashboard_'+cur+'.html') : './index.html';
    })
    .catch(function(){});
})();
loadPeriodArchive('weekly');
loadPeriodArchive('monthly');
function applyThemeIcon(){
  var isLight = document.documentElement.getAttribute('data-theme') === 'light';
  var icon = document.getElementById('themeToggleIcon');
  var label = document.getElementById('themeToggleLabel');
  if (icon) icon.textContent = isLight ? '☀️' : '🌙';
  if (label) label.textContent = isLight ? '다크 모드' : '라이트 모드';
}
function toggleTheme(){
  var cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  var next = cur === 'light' ? 'dark' : 'light';
  localStorage.setItem('theme', next);
  location.reload();
}
applyThemeIcon();
function switchTab(name){
  ['daily','weekly','monthly','rising','archive'].forEach(function(n){
    var panel = document.getElementById('tab-' + n);
    if (panel) panel.hidden = (n !== name);
    var btn = document.querySelector('.tab-btn[data-tab="' + n + '"]');
    if (btn) btn.classList.toggle('active', n === name);
  });
  history.replaceState(null, '', '#' + name);
}
function switchArchiveSub(name){
  ['daily','weekly','monthly'].forEach(function(n){
    var panel = document.getElementById('archive-' + n);
    if (panel) panel.hidden = (n !== name);
    var btn = document.querySelector('.archive-sub-btn[data-sub="' + n + '"]');
    if (btn) btn.classList.toggle('active', n === name);
  });
}
function switchRisingSub(name){
  ['daily','weekly','monthly'].forEach(function(n){
    var panel = document.getElementById('rising-' + n);
    if (panel) panel.hidden = (n !== name);
    var btn = document.querySelector('.rising-sub-btn[data-sub="' + n + '"]');
    if (btn) btn.classList.toggle('active', n === name);
  });
}
var _periodArchiveCache = {};
function loadPeriodArchive(kind){
  var listEl = document.getElementById('archive-' + kind + '-list');
  if (!listEl || listEl.dataset.loaded) return;
  listEl.dataset.loaded = '1';
  fetch('./data/' + kind + '/index.json?v=' + Date.now())
    .then(function(r){ return r.json(); })
    .then(function(items){
      if (!items || !items.length) {
        listEl.innerHTML = '<span class="text-muted small">아직 축적된 회차가 없습니다.</span>';
        return;
      }
      listEl.innerHTML = '';
      items.forEach(function(it, i){
        var div = document.createElement('div');
        div.className = 'archive-list-item' + (i === 0 ? ' active' : '');
        div.textContent = it.label;
        div.onclick = function(){ selectPeriodArchive(kind, it.id, div); };
        listEl.appendChild(div);
      });
      selectPeriodArchive(kind, items[0].id, listEl.firstChild);
    })
    .catch(function(){ listEl.innerHTML = '<span class="text-muted small">불러오기 실패</span>'; });
}
function selectPeriodArchive(kind, id, itemEl){
  var listEl = document.getElementById('archive-' + kind + '-list');
  if (listEl) {
    Array.prototype.forEach.call(listEl.children, function(el){
      el.classList.toggle('active', el === itemEl);
    });
  }
  var contentEl = document.getElementById('archive-' + kind + '-content');
  if (!contentEl) return;
  var cacheKey = kind + ':' + id;
  if (_periodArchiveCache[cacheKey]) { contentEl.innerHTML = _periodArchiveCache[cacheKey]; return; }
  contentEl.innerHTML = '<span class="text-muted small">불러오는 중...</span>';
  fetch('./data/' + kind + '/fragments/' + id + '.html?v=' + Date.now())
    .then(function(r){ return r.text(); })
    .then(function(html){ _periodArchiveCache[cacheKey] = html; contentEl.innerHTML = html; })
    .catch(function(){ contentEl.innerHTML = '<span class="text-muted small">불러오기 실패</span>'; });
}
(function(){
  var initial = (location.hash || '#daily').slice(1);
  if (['daily','weekly','monthly','rising','archive'].indexOf(initial) === -1) initial = 'daily';
  switchTab(initial);
})();
</script>"""


def _badge_html(badge):
    """공용 순위 변동 배지 — 국내 인기순위/이커머스 모두 동일 규칙 사용.
    badge: None | "new" | "same" | "up:N" | "down:N" """
    if not badge:
        return ""
    if badge == "new":
        return '<span class="rank-badge badge-new">NEW</span>'
    if badge == "same":
        return '<span class="rank-badge badge-same">―</span>'
    if badge.startswith("up:"):
        return f'<span class="rank-badge badge-up">▲{badge.split(":")[1]}</span>'
    if badge.startswith("down:"):
        return f'<span class="rank-badge badge-down">▼{badge.split(":")[1]}</span>'
    return ""


def _render_period_section(data, kind):
    """주간/월간 탭 공용 렌더러. kind: "weekly" | "monthly" — 라벨/foodnews 블록 유무만 다름.
    data는 aggregator/weekly.py, aggregator/monthly.py가 만든 JSON 그대로(없으면 None)."""
    no_data = '<span class="text-muted small">데이터 수집 중...</span>'
    empty_period = "주간" if kind == "weekly" else "월간"

    if not data:
        return f"""
  <div class="card mb-3 summary-card">
    <div class="card-header">📅 {empty_period}</div>
    <div class="card-body"><span class="text-muted small">{empty_period} 집계 데이터를 아직 축적 중입니다 — 매{"주" if kind == "weekly" else "월"} 자동 집계되며 시간이 지나면 채워집니다.</span></div>
  </div>"""

    label = data.get("period_label", "")
    ai = data.get("ai_summary")
    if ai and ai.get("summary"):
        ai_html = (
            f'<div class="summary-line">{ai["summary"]}</div>'
            + "".join(f'<div class="summary-line law-kp-line">・ {pt}</div>' for pt in ai.get("key_points", []))
        )
    else:
        ai_html = f'<span class="text-muted small">AI 요약을 생성하지 못했습니다(데이터 부족 또는 API 미설정) — 아래 집계 데이터는 정상 표시됩니다.</span>'

    top_keywords = data.get("top_keywords", [])
    keyword_rows = "".join(
        f'<div class="summary-line">{i+1}. <b>{k["keyword"]}</b> <span class="text-muted small">(평균 {k["avg_ratio"]:.0f})</span></div>'
        for i, k in enumerate(top_keywords[:10])
    ) or no_data

    news_highlights = data.get("news_highlights", [])
    news_rows = "".join(
        f'<div class="news-item"><a href="{n.get("link", "")}" target="_blank">[{n["category"]}] {n["title"]}</a></div>'
        for n in news_highlights[:10]
    ) or no_data

    ecommerce_highlights = data.get("ecommerce_highlights", [])
    ecommerce_rows = "".join(
        f'<div class="summary-line">{e["platform"]} '
        + ("🆕 신규진입: " if e["kind"] == "new" else "▲ 순위상승: ")
        + f'<b>{e["name"]}</b></div>'
        for e in ecommerce_highlights[:10]
    ) or no_data

    _ecom_platforms = _ECOM_PLATFORMS

    def _ranking_col(key, label, items):
        rows = "".join(
            f'<div class="ecom-item">'
            + (
                f'<img class="ecom-thumb" src="{it["image"]}" alt="" loading="lazy" onerror="this.style.visibility=\'hidden\'">'
                if it.get("image") else '<div class="ecom-thumb"></div>'
            )
            + f'<div class="ecom-info">'
            f'<div class="ecom-top"><span class="rank">{i+1}</span>'
            f'<span class="ecom-cat">{it.get("category") or ""}</span>'
            f'<span class="rank-badge badge-same">평균 {it["avg_rank"]:.1f}위 · {it["days_seen"]}일</span></div>'
            f'<a class="ecom-name" href="{it.get("url","")}" target="_blank">{it["name"]}</a>'
            f'<div class="ecom-price">{it.get("price","")}</div>'
            f'</div></div>'
            for i, it in enumerate(items)
        )
        body = rows if rows else no_data
        return f'<div class="col-md-4"><div class="fw-bold mb-1 ecom-platform-label">{label}</div>{body}</div>'

    ecommerce_rankings = data.get("ecommerce_rankings") or {}
    ranking_cols = "".join(
        _ranking_col(key, label, ecommerce_rankings.get(key, [])) for key, label in _ecom_platforms
    )
    ranking_row = f"""
  <div class="card mb-3">
    <div class="card-header"><span class="section-icon">🛒</span>{empty_period} 판매순위 TOP10 (기간 평균)</div>
    <div class="card-body p-2"><div class="row">{ranking_cols}</div></div>
  </div>""" if any(ecommerce_rankings.values()) else ""

    # ── 2026-07-29: 검색↔판매 갭 / 브랜드 트렌드 / 카테고리 트렌드 (일간에서 이전) ──
    # 일간 스냅샷(플랫폼당 최대 10개)은 표본이 작고 하루 단위로 들쭉날쭉해서,
    # 기간 집계(꾸준히 팔린 상품 위주로 필터링된 ecommerce_rankings)를 쓰는
    # 주간/월간 탭이 더 안정적이라는 판단으로 여기로 옮김.
    _period_items = [it for key, _ in _ecom_platforms for it in ecommerce_rankings.get(key, [])]

    def _period_search_sales_gap(top_n=15, show_n=6):
        product_names = " ".join(it.get("name", "") for it in _period_items)
        gaps = [
            (i + 1, k["keyword"]) for i, k in enumerate(top_keywords[:top_n])
            if k["keyword"] not in product_names
        ]
        if not gaps:
            return '<span class="text-muted small">검색 상위 키워드가 모두 판매순위 상품명에서 확인됨</span>'
        return "".join(
            f'<div class="summary-line">🔍 검색 <b>{rank}위</b> <b>{kw}</b> — 판매순위 TOP10 상품명에 미노출</div>'
            for rank, kw in gaps[:show_n]
        )

    def _period_brand_trend(top_n=6):
        counts = {}
        for it in _period_items:
            brand = (it.get("brand") or "").strip()
            if brand:
                counts[brand] = counts.get(brand, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
        if not ranked:
            return no_data
        return "".join(f'<span class="tag">{brand} <small>{n}건</small></span>' for brand, n in ranked)

    def _period_category_trend(top_n=6):
        counts = {}
        for it in _period_items:
            cat = (it.get("category") or "").strip()
            if cat:
                counts[cat] = counts.get(cat, 0) + 1
        total = sum(counts.values())
        if not total:
            return no_data
        ranked = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
        rows = "".join(
            f'<tr><td class="rank">{i + 1}</td>'
            f'<td style="font-weight:{"700" if i < 3 else "400"}">{cat}</td>'
            f'<td><div class="bar" style="width:{n / total * 100:.0f}%;background:{_BAR_COLORS[min(i, 4)]}">'
            f'{n}건 ({n / total * 100:.0f}%)</div></td></tr>'
            for i, (cat, n) in enumerate(ranked)
        )
        return f'<table><tbody>{rows}</tbody></table>'

    insight_row = f"""
  <div class="card mb-3">
    <div class="card-header"><span class="section-icon">🔍</span>{empty_period} 검색↔판매 갭 분석</div>
    <div class="card-body p-2">
      {_period_search_sales_gap()}
      <div class="card-source">{empty_period} 검색 상위 15개 키워드 중 {empty_period} 판매순위 TOP10 상품명에 등장하지 않는 키워드 — 관심은 있는데 아직 대표 히트상품이 없는 성분 후보(신제품 기획 참고용, 상품명 텍스트 매칭 기반 참고 지표)</div>
    </div>
  </div>
  <div class="row">
    <div class="col-md-6">
      <div class="card">
        <div class="card-header"><span class="section-icon">🏷</span>{empty_period} 브랜드 트렌드</div>
        <div class="card-body">
          {_period_brand_trend()}
          <div class="card-source">{empty_period} 판매순위 TOP10 합산 내 브랜드 노출 빈도</div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header"><span class="section-icon">🗂</span>{empty_period} 카테고리 트렌드</div>
        <div class="card-body p-2">
          {_period_category_trend()}
          <div class="card-source">{empty_period} 판매순위 TOP10 합산 내 카테고리 비중</div>
        </div>
      </div>
    </div>
  </div>""" if any(ecommerce_rankings.values()) else ""

    foodnews_block = ""
    if kind == "monthly":
        foodnews = data.get("foodnews") or {}
        for section_label in ("건강기능식품", "신상품"):
            items = foodnews.get(section_label, [])
            rows = "".join(
                f'<div class="news-item"><a href="{it.get("link", "")}" target="_blank">{it["title"]}</a>'
                f'<span class="news-date">{it.get("date", "")}</span></div>'
                for it in items[:8]
            ) or no_data
            foodnews_block += f"""
    <div class="col-md-6">
      <div class="card">
        <div class="card-header"><span class="section-icon">📰</span>식품저널 {section_label} ({len(items)}건)</div>
        <div class="card-body p-2">{rows}</div>
      </div>
    </div>"""

    days_collected = data.get("days_collected", 0)

    foodnews_row = f'<div class="row">{foodnews_block}</div>' if foodnews_block else ""

    return f"""
  <div class="card mb-3 summary-card">
    <div class="card-header">📅 {label}</div>
    <div class="card-body">
      {ai_html}
      <div class="card-source">집계 대상: {days_collected}일치 원본 데이터 · AI 요약: Gemini API</div>
    </div>
  </div>
  <div class="row">
    <div class="col-md-4">
      <div class="card">
        <div class="card-header"><span class="section-icon">📊</span>{empty_period} 검색 상위 키워드</div>
        <div class="card-body p-2">{keyword_rows}</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card">
        <div class="card-header"><span class="section-icon">📰</span>{empty_period} 주요 뉴스</div>
        <div class="card-body p-2">{news_rows}</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card">
        <div class="card-header"><span class="section-icon">🛒</span>{empty_period} 이커머스 동향</div>
        <div class="card-body p-2">{ecommerce_rows}</div>
      </div>
    </div>
  </div>
  {ranking_row}
  {insight_row}
  {foodnews_row}"""


def _rising_trend_svg(trend):
    """1년 쿼리 그래프 — 외부 차트 라이브러리 없이 인라인 SVG 폴리라인으로 그린다."""
    if not trend or len(trend) < 2:
        return ""
    w, h, pad = 220, 46, 4
    values = [p["ratio"] for p in trend]
    vmin, vmax = min(values), max(values)
    span = (vmax - vmin) or 1
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = pad + (w - 2 * pad) * i / (n - 1)
        y = h - pad - (h - 2 * pad) * (v - vmin) / span
        points.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(points)
    return (
        f'<svg viewBox="0 0 {w} {h}" class="rising-trend-svg" preserveAspectRatio="none">'
        f'<polyline points="{poly}" fill="none" stroke="var(--up)" stroke-width="2"/>'
        f'</svg>'
    )


def _rising_demo_bars(demo_bars):
    """연령대x성별 검색 비중 막대 — 남성(파랑)/여성(청록) 2색."""
    if not demo_bars:
        return ""
    max_v = max((max(row.get("m", 0), row.get("f", 0)) for row in demo_bars), default=0) or 1
    rows = []
    for row in demo_bars:
        m_pct = row.get("m", 0) / max_v * 100
        f_pct = row.get("f", 0) / max_v * 100
        rows.append(
            f'<div class="rising-demo-row">'
            f'<span class="rising-demo-age">{row["age"]}</span>'
            f'<div class="rising-demo-bar-wrap">'
            f'<div class="rising-demo-bar rising-demo-m" style="width:{m_pct:.0f}%" title="남성"></div>'
            f'<div class="rising-demo-bar rising-demo-f" style="width:{f_pct:.0f}%" title="여성"></div>'
            f'</div></div>'
        )
    return "".join(rows)


def _rising_card_html(card, rank):
    issue_html = "".join(
        f'<div class="summary-line">・ {b}</div>' for b in (card.get("issue_bullets") or [])
    ) or '<span class="text-muted small">근거 자료 부족으로 이슈 요약 생략</span>'

    brands = card.get("top_brands") or []
    brands_html = " / ".join(brands) if brands else '<span class="text-muted small">매칭 상품 없음</span>'

    trend_svg = _rising_trend_svg(card.get("trend"))
    chart_block = (
        f'<div class="rising-card-chart">{trend_svg}<div class="rising-chart-label">최근 1년 검색 추이</div></div>'
        if trend_svg else ""
    )

    demo_bars_html = _rising_demo_bars(card.get("demo_bars"))
    demo_label = card.get("demo_top_label")
    demo_highlight = f'<div class="rising-demo-highlight">{demo_label}</div>' if demo_label else ""
    demo_block = f'<div class="rising-card-demo">{demo_bars_html}{demo_highlight}</div>' if demo_bars_html else ""

    return f"""
  <div class="rising-card">
    <div class="rising-card-head"><span class="rank">{rank}</span><span class="rising-card-name">{card["name"]}</span></div>
    <div class="rising-card-volume">{card["total"]:,.0f}<small>월간 검색량(PC {card.get("pc", 0):,.0f} · 모바일 {card.get("mobile", 0):,.0f})</small></div>
    <div class="rising-card-row"><span class="rising-row-label">상위 브랜드</span>{brands_html}</div>
    <div class="rising-card-issue"><div class="rising-row-label">이슈 및 현황</div>{issue_html}</div>
    {chart_block}
    {demo_block}
  </div>"""


def _render_rising_report_section(report):
    """급상승 원료/브랜드·제품 리포트 — 일간/주간/월간 공용 렌더러."""
    no_data = '<span class="text-muted small">아직 축적된 데이터가 없습니다 — 검색량 스냅샷이 쌓이면 표시됩니다.</span>'

    ingredients = (report or {}).get("ingredients") or []
    brands = (report or {}).get("brands") or []

    ing_cards = "".join(_rising_card_html(c, i + 1) for i, c in enumerate(ingredients)) or no_data
    brand_cards = "".join(_rising_card_html(c, i + 1) for i, c in enumerate(brands)) or no_data

    return f"""
  <div class="card mb-3">
    <div class="card-header"><span class="section-icon">🔥</span>급상승 원료</div>
    <div class="card-body p-2"><div class="rising-grid">{ing_cards}</div></div>
  </div>
  <div class="card mb-3">
    <div class="card-header"><span class="section-icon">🔥</span>급상승 브랜드/제품</div>
    <div class="card-body p-2"><div class="rising-grid">{brand_cards}</div></div>
  </div>
  <div class="card-source px-2 pb-3">검색량: 네이버 검색광고 키워드도구(월간 PC+모바일 검색수) · 성별/연령: 네이버 데이터랩(최근 3개월 평균 상대지수) · 이슈 요약: Gemini AI(수집된 뉴스 기반, 자료에 없는 내용은 생성하지 않음)</div>"""


def write_archive_files(period_dir, archive, kind):
    """보관함 탭의 주간/월간 회차를 정적 파일로 미리 렌더링해 디스크에 쓴다.
    index.json(회차 목록)과 fragments/{period_id}.html(회차별 본문)을 매 실행마다 새로 씀 —
    이 파일들은 JS가 보관함 탭을 열 때 fetch로 그때그때 불러온다(대시보드 HTML에 박아넣지 않음).
    dashboard_YYYYMMDD.html 백업 페이지는 생성된 뒤 다시 빌드되지 않으므로, 회차 목록을 HTML에
    직접 심으면 그 페이지를 나중에 열람할 때 빌드 시점의 낡은 목록이 영구히 고정되는 문제가 있었다
    (예: 재생성된 과거 페이지만 최신 회차를 보여주고, 그렇지 않은 페이지는 오래된 회차에 멈춰있음).
    정적 데이터 파일로 분리해두면 페이지가 언제 만들어졌든 열람 시점 기준 최신 목록을 항상 보여준다.
    _render_period_section을 그대로 재사용해 렌더링 로직이 두 곳에서 갈라지지 않게 한다."""
    import json as _json
    fragments_dir = os.path.join(period_dir, "fragments")
    os.makedirs(fragments_dir, exist_ok=True)
    index = []
    for period_id, data in archive:
        label = (data.get("period_label") if data else None) or period_id
        index.append({"id": period_id, "label": label})
        with open(os.path.join(fragments_dir, f"{period_id}.html"), "w", encoding="utf-8") as f:
            f.write(_render_period_section(data, kind))
    with open(os.path.join(period_dir, "index.json"), "w", encoding="utf-8") as f:
        _json.dump(index, f, ensure_ascii=False)


def generate_html(naver_data, sns_data, news_data, rising_data, overseas_data=None, available_dates=None, ecommerce_data=None, naver_prev_data=None, law_summary=None, weekly_data=None, monthly_data=None, rising_report=None):
    if overseas_data is None:
        overseas_data = []
    if ecommerce_data is None:
        ecommerce_data = {}
    today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    today_file = datetime.now().strftime("%Y%m%d")
    # GitHub Actions 러너는 UTC, 로컬 실행은 KST라 시스템 시각을 그대로 쓰면 표시가
    # 오락가락함 — datetime.now(timezone.utc)로 절대 시각을 구해 KST로 변환해 항상
    # 올바른 실제 생성 시각을 보여준다 (날짜/파일명용 today/today_file은 기존 로직
    # 유지, 표시용 update_time만 별도 계산이라 스냅샷 파일명과 무관).
    update_time = datetime.now(timezone.utc).astimezone(_KST).strftime("%H:%M")

    _medals = ["🥇", "🥈", "🥉"]
    _bar_colors = _BAR_COLORS
    no_data = '<span class="text-muted small">데이터 수집 중...</span>'

    # 전일 스냅샷에서 키워드별 순위(1-base)·검색지수를 미리 뽑아 둠 — 없으면 배지 생략
    _prev_rank = {d["keyword"]: idx + 1 for idx, d in enumerate(naver_prev_data or [])}
    _prev_ratio = {d["keyword"]: d.get("ratio") for d in (naver_prev_data or [])}

    def _naver_badge_str(keyword, cur_rank):
        if not _prev_rank:
            return None
        prev = _prev_rank.get(keyword)
        if prev is None:
            return "new"
        diff = prev - cur_rank
        if diff > 0:
            return f"up:{diff}"
        if diff < 0:
            return f"down:{abs(diff)}"
        return "same"

    def _naver_row(i, d):
        rank = _medals[i] if i < 3 else str(i + 1)
        weight = "700" if i < 3 else "400"
        color = _bar_colors[min(i, 4)]
        badge = _naver_badge_str(d["keyword"], i + 1)
        return (f'<tr>'
                f'<td class="rank">{rank}</td>'
                f'<td style="font-weight:{weight}">{d["keyword"]} {_badge_html(badge)}</td>'
                f'<td><div class="bar" style="width:{min(d["ratio"],100)}%;background:{color}">'
                f'{d["ratio"]:.0f}</div></td>'
                f'</tr>')

    naver_rows = "".join(_naver_row(i, d) for i, d in enumerate(naver_data[:15]))

    sns_tags = "".join(
        f'<span class="tag" style="font-size:{min(14+d["count"],22)}px">{d["tag"]} <small>{d["count"]}</small></span>'
        for d in sns_data[:20]
    )
    news_items = "".join(
        f'<div class="news-item"><a href="{n["link"]}" target="_blank">{n["title"]}</a>'
        f'<span class="news-date">{n.get("source", "네이버뉴스")} · {n["pubDate"][:16]}</span></div>'
        for n in news_data.get("news", [])
    )
    domestic_research = "".join(
        f'<div class="news-item"><a href="{n["link"]}" target="_blank">🔬 {n["title"]}</a>'
        f'<span class="news-date">{n.get("source", "네이버뉴스")} · {n["pubDate"][:16]}</span></div>'
        for n in news_data.get("research", [])
    )
    overseas_research = "".join(
        f'<div class="news-item">'
        f'<a href="{n["link"]}" target="_blank">🌐 {n.get("title_ko", n["title"])}</a>'
        f'<span class="news-date news-source">[{n["source"]}] {n["pubDate"][:16]}</span>'
        f'</div>'
        for n in overseas_data
    )
    research_items = domestic_research + overseas_research
    regulatory_items = "".join(
        f'<div class="news-item"><a href="{n["link"]}" target="_blank">🏛 {n["title"]}</a>'
        f'<span class="news-date">{n.get("source", "네이버뉴스")} · {n["pubDate"][:16]}</span></div>'
        for n in news_data.get("regulatory", [])
    )
    # 2026-08-20: 키워드만 나열하면 왜 "급상승"인지 근거가 안 보이고 8개는 너무
    # 많다는 피드백 — 전일 대비 검색지수 증가폭을 숫자로 함께 보여주고 5개로 축소
    rising_tags = "".join(
        f'<span class="rising-tag">🔥 {r["keyword"]} <small>+{r["value"]:.1f}</small></span>'
        for r in rising_data[:5]
    )
    _ecommerce_platforms = _ECOM_PLATFORMS

    def _ecommerce_col(key, label):
        items = ecommerce_data.get(key, [])
        rows = "".join(
            f'<div class="ecom-item">'
            + (
                f'<img class="ecom-thumb" src="{it["image"]}" alt="" loading="lazy" onerror="this.style.visibility=\'hidden\'">'
                if it.get("image") else '<div class="ecom-thumb"></div>'
            )
            + f'<div class="ecom-info">'
            f'<div class="ecom-top"><span class="rank">{it["rank"]}</span>'
            f'<span class="ecom-cat">{it.get("category") or ""}</span>'
            f'{_badge_html(it.get("badge"))}</div>'
            f'<a class="ecom-name" href="{it["url"]}" target="_blank">{it["name"]}</a>'
            f'<div class="ecom-price">{it["price"]}</div>'
            f'</div></div>'
            for it in items
        )
        body = rows if rows else no_data
        return f'<div class="col-md-4"><div class="fw-bold mb-1 ecom-platform-label">{label}</div>{body}</div>'

    ecommerce_cols = "".join(_ecommerce_col(key, label) for key, label in _ecommerce_platforms)
    ecommerce_date = ecommerce_data.get("date", "")
    ecommerce_is_stale = bool(ecommerce_date) and ecommerce_date != datetime.now().strftime("%Y-%m-%d")

    # ── 오늘의 요약 박스 (2026-07-22 신설 — 기존 "오늘의 급상승 키워드" 배너 대체) ──
    def _ecommerce_highlights():
        # 2026-07-23: "🆕 [올리브영] 상품명"처럼 기호 위주로 압축된 표기 대신,
        # 무슨 일이 있었는지 문장으로 풀어서 한눈에 읽히게 함
        # 2026-08-20: 상품명을 클릭하면 실제 판매 페이지로 바로 이동하도록 링크화
        # (이커머스 신규·급등 본문 카드의 .ecom-name과 동일하게 it["url"] 재사용)
        lines = []
        for key, label in _ecommerce_platforms:
            platform = label.split()[-1]
            for it in ecommerce_data.get(key, []):
                badge = it.get("badge")
                url = it.get("url") or ""
                tag = "a" if url else "div"
                attrs = f' href="{url}" target="_blank" rel="noopener"' if url else ""
                if badge == "new":
                    lines.append((0, f'<{tag} class="summary-line summary-line-link"{attrs}>🆕 {platform}에 <b>{it["name"]}</b> 신규 진입</{tag}>'))
                elif badge and badge.startswith("up:") and int(badge.split(":")[1]) >= 3:
                    diff = int(badge.split(":")[1])
                    lines.append((diff, f'<{tag} class="summary-line summary-line-link"{attrs}>▲ {platform} <b>{it["name"]}</b> 순위 {diff}단계 상승</{tag}>'))
        lines.sort(key=lambda x: -x[0])
        return "".join(html for _, html in lines[:5])

    def _naver_top_movers():
        # 2026-08-20: "N단계 상승"만으로는 몇 위에서 몇 위로 올랐는지, 실제 검색량이
        # 얼마나 늘었는지 알 수 없다는 피드백 — 순위 변화(prev위→cur위)와 검색지수
        # 변화(전일→오늘)를 함께 보여줘 근거를 보강
        movers = []
        for i, d in enumerate(naver_data[:15]):
            prev_r = _prev_rank.get(d["keyword"])
            if prev_r is None:
                continue
            diff = prev_r - (i + 1)
            if diff > 0:
                movers.append((diff, d["keyword"], prev_r, i + 1, _prev_ratio.get(d["keyword"]), d.get("ratio")))
        movers.sort(key=lambda x: -x[0])
        if not movers:
            return no_data
        lines = []
        for diff, kw, prev_r, cur_r, prev_ratio, cur_ratio in movers[:3]:
            ratio_txt = (
                f' <small>(지수 {prev_ratio:.0f}→{cur_ratio:.0f})</small>'
                if prev_ratio is not None and cur_ratio is not None else ''
            )
            lines.append(f'<div class="summary-line">▲ <b>{kw}</b> 검색 순위 {prev_r}위→{cur_r}위{ratio_txt}</div>')
        return "".join(lines)

    ecommerce_highlights_html = _ecommerce_highlights() or no_data
    naver_movers_html = _naver_top_movers()
    # 2026-08-20: 제목만 있으면 언제·어디서 나온 소식인지 알 수 없다는 피드백 —
    # 다른 뉴스 섹션(news-item)과 동일하게 출처·날짜를 함께 표시
    latest_research_html = "".join(
        f'<div class="summary-line">🔬 {n["title"]}'
        f'<span class="summary-meta"> · {n.get("source", "네이버뉴스")} · {n.get("pubDate", "")[:16]}</span></div>'
        for n in news_data.get("research", [])[:2]
    ) or no_data

    _LAW_BADGE_CLASS = {
        "시행": "law-badge-enforce", "공포": "law-badge-enforce", "공고": "law-badge-enforce",
        "예고": "law-badge-notice",
    }

    law_summary = law_summary or {}
    _law_items = law_summary.get("items") or []
    if _law_items:
        # 2026-08-20: 주간 통합 요약(AI가 쓴 긴 문단)을 그대로 늘어놓으면 안 읽힌다는
        # 피드백 — 문단 대신 이번 주 법령 항목을 상태 배지+제목+핵심내용 한 줄로 된
        # 짧은 목록으로 항상 보여줌(항목별 key_points가 아직 없으면 제목까지만).
        # FOODLAW-MONITORING이 이미 만들어둔 값을 재사용, 여기서 추가 AI 호출 없음.
        rows = []
        for it in _law_items[:3]:
            status = it.get("status", "")
            badge_cls = _LAW_BADGE_CLASS.get(status, "law-badge-other")
            kp = (it.get("key_points") or [None])[0]
            # 2026-08-20: 클릭하면 법령 모니터의 해당 항목으로 바로 이동하도록
            # #law-xxxxx 딥링크 부여(build_site.py의 item_anchor_id()와 동일 알고리즘)
            anchor = _law_item_anchor_id(it)
            rows.append(
                f'<a class="law-item-row" href="{LAW_MONITOR_URL}#{anchor}" target="_blank" rel="noopener">'
                f'<span class="law-badge {badge_cls}">{status}</span>'
                f'<span class="law-item-title">{it.get("title", "")}</span>'
                + (f'<div class="law-kp-line">{kp}</div>' if kp else '')
                + '</a>'
            )
        law_summary_html = "".join(rows)
    else:
        law_summary_html = no_data
    law_label = law_summary.get("label", "")

    summary_box = f"""
  <div class="card mb-3 summary-card">
    <div class="card-header">📋 오늘의 요약</div>
    <div class="card-body">
      <div class="summary-grid">
        <div class="summary-block">
          <div class="summary-label">🔥 급상승 키워드</div>
          {rising_tags if rising_tags else no_data}
        </div>
        <div class="summary-block">
          <div class="summary-label">🏛 식약처 법령 요약{f" ({law_label})" if law_label else ""}</div>
          {law_summary_html}
        </div>
        <div class="summary-block">
          <div class="summary-label">🛒 이커머스 신규·급등</div>
          {ecommerce_highlights_html}
        </div>
        <div class="summary-block">
          <div class="summary-label">📊 국내 검색 급상승 TOP3</div>
          {naver_movers_html}
        </div>
        <div class="summary-block">
          <div class="summary-label">🔬 최신 연구 소식</div>
          {latest_research_html}
        </div>
      </div>
      <div class="card-source">급상승: 네이버 데이터랩(전일 대비 증가폭) · 법령: 식품법령모니터 연동(주간) · 이커머스: 전일 대비 · 검색급상승/연구: 네이버 데이터랩·뉴스 API</div>
    </div>
  </div>"""

    weekly_html = _render_period_section(weekly_data, "weekly")
    monthly_html = _render_period_section(monthly_data, "monthly")

    rising_daily_html = _render_rising_report_section(rising_report)
    rising_weekly_html = _render_rising_report_section((weekly_data or {}).get("rising_report"))
    rising_monthly_html = _render_rising_report_section((monthly_data or {}).get("rising_report"))

    html = f"""<!DOCTYPE html>
<html lang="ko" data-bs-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>건강기능식품 트랜드 - {today}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<script>
  // 저장된 테마를 CSS 적용 전에 먼저 읽어 첫 렌더 깜빡임 방지
  (function() {{
    var saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') {{
      document.documentElement.setAttribute('data-theme', saved);
      document.documentElement.setAttribute('data-bs-theme', saved);
    }}
  }})();
</script>
<style>
  :root {{
    --canvas: #0b0e11;
    --surface: #1e2329;
    --surface-elevated: #2b3139;
    --hairline: #2b3139;
    --body-text: #eaecef;
    --muted: #707a8a;
    --muted-strong: #929aa5;
    --primary: #fcd535;
    --primary-text: #fcd535;
    --primary-active: #f0b90b;
    --up: #0ecb81;
    --down: #f6465d;
    --info: #3b82f6;
    --turquoise: #2dbdb6;
    --rising-bg: #3a3a1f;
  }}
  :root[data-theme="light"] {{
    --canvas: #f7f8fa;
    --surface: #ffffff;
    --surface-elevated: #f0f2f5;
    --hairline: #e6e8eb;
    --body-text: #1e2329;
    --muted: #76808f;
    --muted-strong: #4b5563;
    --primary: #fcd535;
    --primary-text: #9a7300;
    --primary-active: #b8860b;
    --up: #0a9f68;
    --down: #d63447;
    --info: #2563eb;
    --turquoise: #0f8f88;
    --rising-bg: #fff3cd;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--canvas); color: var(--body-text); font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; }}
  .header {{ background: var(--canvas); border-bottom: 1px solid var(--hairline); color: var(--body-text); padding: 20px 30px; }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; margin: 0; }}
  .header h1 .brand-accent {{ color: var(--primary-text); }}
  .header .date {{ opacity: 0.7; font-size: 0.9rem; color: var(--muted-strong); }}
  .card {{ background: var(--surface); border: none; border-radius: 12px; box-shadow: none; margin-bottom: 20px; }}
  .card-header {{ background: transparent; color: var(--body-text); border-bottom: 1px solid var(--hairline); border-radius: 12px 12px 0 0 !important; font-weight: 600; font-size: 1rem; padding: 14px 18px; }}
  .card-header.research {{ border-bottom-color: var(--info); }}
  .card-header.regulatory {{ border-bottom-color: var(--turquoise); }}
  .rank {{ width: 32px; color: var(--muted); font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
  .rank-badge {{ font-size: 0.72rem; font-weight: 700; margin-left: 4px; font-family: 'JetBrains Mono', monospace; }}
  .badge-new {{ color: var(--primary-text); }}
  .badge-up {{ color: var(--up); }}
  .badge-down {{ color: var(--down); }}
  .badge-same {{ color: var(--muted); }}
  .bar {{ background: var(--up); height: 18px; border-radius: 4px; min-width: 28px; white-space: nowrap; color: #0b0e11; font-size: 11px; font-weight: 700; padding: 1px 4px; font-family: 'JetBrains Mono', monospace; box-sizing: border-box; }}
  table {{ width: 100%; }}
  td {{ padding: 6px 8px; vertical-align: middle; font-size: 0.9rem; color: var(--body-text); }}
  tr:hover {{ background: var(--surface-elevated); }}
  .tag {{ display: inline-block; background: var(--surface-elevated); color: var(--body-text); border-radius: 20px; padding: 4px 12px; margin: 4px; cursor: default; }}
  .tag small {{ color: var(--muted-strong); font-family: 'JetBrains Mono', monospace; }}
  .rising-tag {{ display: inline-block; background: var(--rising-bg); color: var(--primary-text); border-radius: 8px; padding: 6px 14px; margin: 4px; font-weight: 600; font-size: 0.9rem; }}
  .news-item {{ padding: 7px 0; border-bottom: 1px solid var(--hairline); }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-item a {{ color: var(--body-text); text-decoration: none; font-size: 0.87rem; line-height: 1.4; }}
  .news-item a:hover {{ color: var(--primary-text); text-decoration: underline; }}
  .news-date {{ display: block; color: var(--muted); font-size: 0.76rem; margin-top: 2px; }}
  .news-source {{ color: var(--muted); }}
  .section-icon {{ margin-right: 6px; }}
  .section-label {{ font-size: 0.7rem; font-weight: 600; padding: 2px 7px; border-radius: 10px; margin-left: 6px; vertical-align: middle; }}
  .label-research {{ background: rgba(59,130,246,0.15); color: var(--info); }}
  .label-regulatory {{ background: rgba(45,189,182,0.15); color: var(--turquoise); }}
  .card-source {{ font-size: 0.7rem; color: var(--muted); border-top: 1px solid var(--hairline); margin-top: 8px; padding-top: 5px; }}
  .date-select {{ background: var(--surface-elevated); color: var(--body-text); border: 1px solid var(--hairline); border-radius: 6px; padding: 4px 8px; font-size: 0.85rem; cursor: pointer; }}
  .date-select option {{ background: var(--surface); color: var(--body-text); }}
  .ecom-item {{ display: flex; align-items: center; gap: 10px; padding: 8px 4px; border-bottom: 1px solid var(--hairline); }}
  .ecom-item:last-child {{ border-bottom: none; }}
  .ecom-thumb {{ width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; background: var(--surface-elevated); }}
  .ecom-info {{ min-width: 0; flex: 1; }}
  .ecom-top {{ display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }}
  .ecom-cat {{ font-size: 0.68rem; background: rgba(45,189,182,0.15); color: var(--turquoise); border-radius: 8px; padding: 1px 7px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 130px; }}
  .ecom-name {{ display: block; color: var(--body-text); text-decoration: none; font-size: 0.85rem; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
  .ecom-name:hover {{ color: var(--primary-text); }}
  .ecom-price {{ font-size: 0.85rem; color: var(--primary-text); font-weight: 700; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }}
  .ecom-platform-label {{ color: var(--body-text); }}
  .summary-card {{ border: 1px solid var(--primary); }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }}
  .summary-label {{ font-size: 0.78rem; font-weight: 600; color: var(--muted-strong); margin-bottom: 6px; }}
  .summary-line {{ font-size: 0.85rem; padding: 3px 0; color: var(--body-text); }}
  .law-item-row {{ display: block; padding: 6px 4px; margin: 0 -4px; border-bottom: 1px dashed var(--hairline); border-radius: 4px; text-decoration: none; color: inherit; }}
  .law-item-row:last-child {{ border-bottom: none; }}
  .law-item-row:hover {{ background: var(--surface-elevated); }}
  .law-item-row:hover .law-item-title {{ color: var(--primary-text); }}
  .law-badge {{ display: inline-block; font-size: 0.68rem; font-weight: 700; padding: 1px 7px; border-radius: 3px; margin-right: 6px; vertical-align: middle; }}
  .law-badge-enforce {{ background: rgba(14,203,129,.15); color: var(--up); }}
  .law-badge-notice {{ background: rgba(252,213,53,.18); color: var(--primary-text); }}
  .law-badge-other {{ background: var(--surface-elevated); color: var(--muted); }}
  .law-item-title {{ font-weight: 600; font-size: 0.82rem; color: var(--body-text); line-height: 1.4; }}
  .law-kp-line {{ font-size: 0.8rem; line-height: 1.5; padding: 3px 0 0; color: var(--muted-strong); }}
  .rising-tag small {{ margin-left: 4px; font-weight: 700; color: var(--up); font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }}
  .summary-meta {{ color: var(--muted); font-size: 0.72rem; }}
  .summary-line-link {{ display: block; text-decoration: none; color: inherit; border-radius: 4px; margin: 0 -4px; padding: 3px 4px; }}
  .summary-line-link:hover {{ background: var(--surface-elevated); }}
  .summary-line-link:hover b {{ color: var(--primary-text); }}
  .theme-toggle {{
    background: var(--surface-elevated); border: 1px solid var(--hairline);
    color: var(--body-text); height: 28px; padding: 0 11px; border-radius: 14px;
    cursor: pointer; display: inline-flex; align-items: center; gap: 5px;
    font-size: 0.76rem; font-weight: 600; white-space: nowrap;
  }}
  .theme-toggle:hover {{ background: var(--hairline); }}
  .tab-bar {{ display: flex; gap: 6px; }}
  .tab-btn {{
    background: transparent; border: none; border-bottom: 2px solid transparent;
    color: var(--muted-strong); padding: 8px 4px; font-size: 0.92rem; font-weight: 600;
    cursor: pointer;
  }}
  .tab-btn.active {{ color: var(--primary-text); border-bottom-color: var(--primary); }}
  .tab-btn:hover {{ color: var(--body-text); }}
  .tab-panel[hidden] {{ display: none; }}
  .archive-subnav {{ display: flex; gap: 6px; margin-bottom: 14px; }}
  .archive-sub[hidden] {{ display: none; }}
  .archive-list {{ display: flex; flex-direction: column; gap: 2px; max-height: 520px; overflow-y: auto; }}
  .archive-list-item {{ padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: var(--body-text); }}
  .archive-list-item:hover {{ background: var(--surface-elevated); }}
  .archive-list-item.active {{ background: var(--primary); color: #1e2329; font-weight: 700; }}
  .archive-list-link {{ display: block; padding: 6px 10px; border-radius: 6px; color: var(--body-text); text-decoration: none; font-size: 0.85rem; }}
  .archive-list-link:hover {{ background: var(--surface-elevated); color: var(--primary-text); }}
  .rising-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
  .rising-card {{ background: var(--surface-elevated); border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 8px; }}
  .rising-card-head {{ display: flex; align-items: center; gap: 8px; }}
  .rising-card-name {{ font-weight: 700; font-size: 1rem; color: var(--body-text); }}
  .rising-card-volume {{ font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 700; color: var(--primary-text); }}
  .rising-card-volume small {{ display: block; font-weight: 400; font-size: 0.68rem; color: var(--muted); font-family: 'Inter', sans-serif; margin-top: 2px; }}
  .rising-row-label {{ display: block; font-size: 0.72rem; font-weight: 600; color: var(--muted-strong); margin-bottom: 2px; }}
  .rising-card-row {{ font-size: 0.85rem; }}
  .rising-card-issue {{ border-top: 1px dashed var(--hairline); padding-top: 6px; }}
  .rising-card-chart {{ border-top: 1px dashed var(--hairline); padding-top: 6px; }}
  .rising-trend-svg {{ width: 100%; height: 46px; display: block; }}
  .rising-chart-label {{ font-size: 0.68rem; color: var(--muted); margin-top: 2px; }}
  .rising-card-demo {{ border-top: 1px dashed var(--hairline); padding-top: 6px; }}
  .rising-demo-row {{ display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }}
  .rising-demo-age {{ width: 42px; font-size: 0.72rem; color: var(--muted-strong); flex-shrink: 0; }}
  .rising-demo-bar-wrap {{ flex: 1; display: flex; gap: 2px; height: 10px; }}
  .rising-demo-bar {{ height: 10px; border-radius: 2px; }}
  .rising-demo-m {{ background: var(--info); }}
  .rising-demo-f {{ background: var(--turquoise); }}
  .rising-demo-highlight {{ margin-top: 4px; font-size: 0.76rem; font-weight: 600; color: var(--up); }}
  @media (max-width: 576px) {{
    .header {{ padding: 14px 16px; }}
    .header h1 {{ font-size: 1.2rem; }}
    .date-select {{ max-width: 140px; font-size: 0.78rem; }}
    .rising-tag {{ font-size: 0.78rem; padding: 4px 10px; }}
    .card-header {{ font-size: 0.9rem; padding: 10px 14px; }}
    td {{ font-size: 0.82rem; padding: 5px 6px; }}
    .ecom-thumb {{ width: 40px; height: 40px; }}
    .ecom-name {{ font-size: 0.8rem; }}
    .summary-grid {{ grid-template-columns: 1fr; }}
    .rising-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="header mb-4">
  <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
    <div class="d-flex align-items-center gap-2">
      <h1 class="mb-0"><span class="brand-accent">●</span> 건강기능식품 트랜드 대시보드</h1>
      <button class="theme-toggle" onclick="toggleTheme()" title="라이트/다크 모드 전환"><span id="themeToggleIcon">🌙</span><span id="themeToggleLabel">라이트 모드</span></button>
    </div>
    <div class="d-flex align-items-center gap-3">
      <div class="tab-bar">
        <button class="tab-btn" data-tab="daily" onclick="switchTab('daily')">일간</button>
        <button class="tab-btn" data-tab="weekly" onclick="switchTab('weekly')">주간</button>
        <button class="tab-btn" data-tab="monthly" onclick="switchTab('monthly')">월간</button>
        <button class="tab-btn" data-tab="rising" onclick="switchTab('rising')">🔥급상승</button>
        <button class="tab-btn" data-tab="archive" onclick="switchTab('archive')">보관함</button>
      </div>
      <select id="date-select" class="date-select" title="과거 날짜 조회"></select>
    </div>
  </div>
  <div class="date mt-1">{today} &nbsp;|&nbsp; {update_time} 업데이트 (KST, 매일 자동 수집)</div>
</div>
<div id="tab-daily" class="tab-panel container-fluid px-4">
  {summary_box}
  <div class="row">
    <div class="col-md-6 col-xl-4">
      <div class="card">
        <div class="card-header"><span class="section-icon">📊</span>국내 인기 순위</div>
        <div class="card-body p-2">
          <table><tbody>{naver_rows}</tbody></table>
          <div class="card-source">산출기준: 네이버 데이터랩 검색량 지수 (최근 7일, 건강기능식품 주요 키워드 비교)</div>
        </div>
      </div>
    </div>
    <div class="col-md-6 col-xl-4">
      <div class="card">
        <div class="card-header"><span class="section-icon">💬</span>SNS 화제 키워드</div>
        <div class="card-body">
          {sns_tags if sns_tags else no_data}
          <div class="card-source">출처: 네이버 블로그 검색 · 숫자 = 해당 키워드 직접 검색 결과 수 + 다른 키워드 검색 결과에 함께 언급된 횟수 (실제 게시글 총량이 아닌 언급 빈도 지수)</div>
        </div>
      </div>
    </div>
    <div class="col-md-6 col-xl-4">
      <div class="card">
        <div class="card-header"><span class="section-icon">📰</span>국내 뉴스</div>
        <div class="card-body p-2">
          {news_items if news_items else no_data}
          <div class="card-source">출처: 연합뉴스·헬스조선·식품음료신문·히트뉴스 RSS · 네이버 뉴스 API</div>
        </div>
      </div>
    </div>
  </div>
  <div class="card mb-3">
    <div class="card-header"><span class="section-icon">🛒</span>이커머스 판매순위 TOP10{' (전일 기준)' if ecommerce_is_stale else ''}</div>
    <div class="card-body p-2">
      <div class="row">
        {ecommerce_cols if ecommerce_cols else no_data}
      </div>
      <div class="card-source">출처: 올리브영·다이소몰·카카오 선물하기 판매순위 크롤러 (별도 시장조사 프로젝트, 자동 수집){f" · {ecommerce_date} 기준(전일자 랭킹 — 각 몰의 당일 랭킹은 오전 10시경 갱신되어 반영 못 함)" if ecommerce_is_stale else f" · {ecommerce_date} 기준" if ecommerce_date else ""} · NEW=신규 진입, ▲▼=전일 대비 순위 변동</div>
    </div>
  </div>
  <div class="row">
    <div class="col-md-6">
      <div class="card">
        <div class="card-header research">
          <span class="section-icon">🔬</span>연구·임상 동향
          <span class="section-label label-research">Research</span>
        </div>
        <div class="card-body p-2">
          {research_items if research_items else no_data}
          <div class="card-source">출처: 네이버 뉴스 API (연구·임상 키워드 검색) · ScienceDaily RSS(🌐, 자동 번역)</div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header regulatory">
          <span class="section-icon">🏛</span>식약처·규제 동향
          <span class="section-label label-regulatory">Regulatory</span>
        </div>
        <div class="card-body p-2">
          {regulatory_items if regulatory_items else no_data}
          <div class="card-source">출처: 네이버 뉴스 API (식약처·규제·고시 키워드 검색)</div>
        </div>
      </div>
    </div>
  </div>
</div>
<div id="tab-weekly" class="tab-panel container-fluid px-4" hidden>
  {weekly_html}
</div>
<div id="tab-monthly" class="tab-panel container-fluid px-4" hidden>
  {monthly_html}
</div>
<div id="tab-rising" class="tab-panel container-fluid px-4" hidden>
  <div class="archive-subnav">
    <button class="tab-btn rising-sub-btn active" data-sub="daily" onclick="switchRisingSub('daily')">일간</button>
    <button class="tab-btn rising-sub-btn" data-sub="weekly" onclick="switchRisingSub('weekly')">주간</button>
    <button class="tab-btn rising-sub-btn" data-sub="monthly" onclick="switchRisingSub('monthly')">월간</button>
  </div>
  <div id="rising-daily" class="archive-sub">{rising_daily_html}</div>
  <div id="rising-weekly" class="archive-sub" hidden>{rising_weekly_html}</div>
  <div id="rising-monthly" class="archive-sub" hidden>{rising_monthly_html}</div>
</div>
<div id="tab-archive" class="tab-panel container-fluid px-4" hidden>
  <div class="archive-subnav">
    <button class="tab-btn archive-sub-btn active" data-sub="daily" onclick="switchArchiveSub('daily')">일간</button>
    <button class="tab-btn archive-sub-btn" data-sub="weekly" onclick="switchArchiveSub('weekly')">주간</button>
    <button class="tab-btn archive-sub-btn" data-sub="monthly" onclick="switchArchiveSub('monthly')">월간</button>
  </div>
  <div id="archive-daily" class="archive-sub">
    <div class="card">
      <div class="card-header"><span class="section-icon">📅</span>일간 대시보드 보관함</div>
      <div class="card-body p-2"><div id="archive-daily-list" class="archive-list"><span class="text-muted small">불러오는 중...</span></div></div>
    </div>
  </div>
  <div id="archive-weekly" class="archive-sub" hidden>
    <div class="row">
      <div class="col-md-4 col-xl-3">
        <div class="card">
          <div class="card-header"><span class="section-icon">📅</span>주간 회차</div>
          <div class="card-body p-2"><div id="archive-weekly-list" class="archive-list"><span class="text-muted small">불러오는 중...</span></div></div>
        </div>
      </div>
      <div class="col-md-8 col-xl-9"><div id="archive-weekly-content"><span class="text-muted small">불러오는 중...</span></div></div>
    </div>
  </div>
  <div id="archive-monthly" class="archive-sub" hidden>
    <div class="row">
      <div class="col-md-4 col-xl-3">
        <div class="card">
          <div class="card-header"><span class="section-icon">📅</span>월간 회차</div>
          <div class="card-body p-2"><div id="archive-monthly-list" class="archive-list"><span class="text-muted small">불러오는 중...</span></div></div>
        </div>
      </div>
      <div class="col-md-8 col-xl-9"><div id="archive-monthly-content"><span class="text-muted small">불러오는 중...</span></div></div>
    </div>
  </div>
</div>
{_NAV_JS}
</body>
</html>"""
    return html, today_file
