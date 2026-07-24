from datetime import datetime
import os

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
      dates.forEach(function(d, i){
        var opt = document.createElement('option');
        var label = d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8);
        opt.value = i === 0 ? './index.html' : ('./dashboard_'+d+'.html');
        opt.text  = i === 0 ? label+' (오늘)' : label;
        sel.appendChild(opt);
      });
      sel.value = cur ? ('./dashboard_'+cur+'.html') : './index.html';
    })
    .catch(function(){});
})();
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


def generate_html(naver_data, sns_data, news_data, rising_data, overseas_data=None, available_dates=None, ecommerce_data=None, naver_prev_data=None, law_summary=None):
    if overseas_data is None:
        overseas_data = []
    if ecommerce_data is None:
        ecommerce_data = {}
    today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    today_file = datetime.now().strftime("%Y%m%d")

    _medals = ["🥇", "🥈", "🥉"]
    _bar_colors = ["#fcd535", "#f0b90b", "#eaecef", "#929aa5", "#707a8a"]
    no_data = '<span class="text-muted small">데이터 수집 중...</span>'

    # 전일 스냅샷에서 키워드별 순위(1-base)를 미리 뽑아 둠 — 없으면 배지 생략
    _prev_rank = {d["keyword"]: idx + 1 for idx, d in enumerate(naver_prev_data or [])}

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
    rising_tags = "".join(
        f'<span class="rising-tag">🔥 {r["keyword"]}</span>'
        for r in rising_data[:8]
    )
    _ecommerce_platforms = [
        ("카카오선물하기", "🎁 카카오 선물하기"),
        ("다이소몰", "🏪 다이소몰"),
        ("올리브영", "💚 올리브영"),
    ]

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
        lines = []
        for key, label in _ecommerce_platforms:
            platform = label.split()[-1]
            for it in ecommerce_data.get(key, []):
                badge = it.get("badge")
                if badge == "new":
                    lines.append((0, f'<div class="summary-line">🆕 {platform}에 <b>{it["name"]}</b> 신규 진입</div>'))
                elif badge and badge.startswith("up:") and int(badge.split(":")[1]) >= 3:
                    diff = int(badge.split(":")[1])
                    lines.append((diff, f'<div class="summary-line">▲ {platform} <b>{it["name"]}</b> 순위 {diff}단계 상승</div>'))
        lines.sort(key=lambda x: -x[0])
        return "".join(html for _, html in lines[:5])

    def _naver_top_movers():
        # 2026-07-23: "▲5 키워드"처럼 기호+숫자만 있던 표기를 문장으로 풀어서 표시
        movers = []
        for i, d in enumerate(naver_data[:15]):
            prev = _prev_rank.get(d["keyword"])
            if prev is None:
                continue
            diff = prev - (i + 1)
            if diff > 0:
                movers.append((diff, d["keyword"]))
        movers.sort(key=lambda x: -x[0])
        if not movers:
            return no_data
        return "".join(
            f'<div class="summary-line">▲ <b>{kw}</b> 검색 순위 {diff}단계 상승</div>' for diff, kw in movers[:3]
        )

    ecommerce_highlights_html = _ecommerce_highlights() or no_data
    naver_movers_html = _naver_top_movers()
    latest_research_html = "".join(
        f'<div class="summary-line">🔬 {n["title"]}</div>'
        for n in news_data.get("research", [])[:2]
    ) or no_data

    law_summary = law_summary or {}
    _law_items = law_summary.get("items") or []
    _law_top_item = _law_items[0] if _law_items else {}
    _law_key_points = _law_top_item.get("key_points") or []
    if _law_key_points:
        # 2026-07-23: 주간 통합 요약(문장형) 대신, 가장 최근 법령 항목의 실제
        # 핵심내용(①②③, FOODLAW-MONITORING이 이미 생성해둔 값을 그대로 재사용 —
        # 여기서 추가 AI 호출은 하지 않음)을 그대로 보여주는 방식으로 변경
        law_summary_html = (
            f'<div class="summary-line law-item-title">{_law_top_item.get("title", "")}</div>'
            + "".join(f'<div class="summary-line law-kp-line">{pt}</div>' for pt in _law_key_points[:3])
        )
    else:
        _law_text = law_summary.get("weekly_summary") or law_summary.get("summary") or ""
        law_summary_html = f'<div class="summary-line">{_law_text}</div>' if _law_text else no_data
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

    html = f"""<!DOCTYPE html>
<html lang="ko">
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
  .law-item-title {{ font-weight: 600; font-size: 0.8rem; color: var(--muted-strong); padding-bottom: 5px; line-height: 1.4; }}
  .law-kp-line {{ font-size: 0.8rem; line-height: 1.5; padding: 2px 0; }}
  .theme-toggle {{
    background: var(--surface-elevated); border: 1px solid var(--hairline);
    color: var(--body-text); height: 28px; padding: 0 11px; border-radius: 14px;
    cursor: pointer; display: inline-flex; align-items: center; gap: 5px;
    font-size: 0.76rem; font-weight: 600; white-space: nowrap;
  }}
  .theme-toggle:hover {{ background: var(--hairline); }}
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
    <select id="date-select" class="date-select" title="과거 날짜 조회"></select>
  </div>
  <div class="date mt-1">{today} &nbsp;|&nbsp; 매일 오전 9시 자동 업데이트</div>
</div>
<div class="container-fluid px-4">
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
{_NAV_JS}
</body>
</html>"""
    return html, today_file
