from datetime import datetime
import os
import json

def generate_html(naver_data, google_data, sns_data, news_data, rising_data):
    today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    today_file = datetime.now().strftime("%Y%m%d")

    naver_rows = "".join(
        f'<tr><td class="rank">{i+1}</td><td>{d["keyword"]}</td>'
        f'<td><div class="bar" style="width:{min(d["ratio"],100)}%">{d["ratio"]:.0f}</div></td></tr>'
        for i, d in enumerate(naver_data[:15])
    )

    google_rows = "".join(
        f'<tr><td class="rank">{i+1}</td><td>{d["keyword"]}</td>'
        f'<td><div class="bar bar-green" style="width:{min(d["ratio"],100)}%">{d["ratio"]}</div></td></tr>'
        for i, d in enumerate(google_data[:10])
    )

    sns_tags = "".join(
        f'<span class="tag" style="font-size:{min(14+d["count"],22)}px">{d["tag"]} <small>{d["count"]}</small></span>'
        for d in sns_data[:20]
    )

    news_items = "".join(
        f'<div class="news-item"><a href="{n["link"]}" target="_blank">{n["title"]}</a>'
        f'<span class="news-date">{n["pubDate"][:16]}</span></div>'
        for n in news_data.get("news", [])
    )

    mfds_items = "".join(
        f'<div class="news-item mfds"><a href="{m["link"]}" target="_blank">🏛 {m["title"]}</a></div>'
        for m in news_data.get("mfds", [])
    )

    rising_tags = "".join(
        f'<span class="rising-tag">🔥 {r["keyword"]}</span>'
        for r in rising_data[:8]
    )

    chart_labels = json.dumps([d["keyword"] for d in naver_data[:7]])
    chart_values = json.dumps([d["ratio"] for d in naver_data[:7]])

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>건강기능식품 트랜드 - {today}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body {{ background: #f0f4f8; font-family: 'Malgun Gothic', sans-serif; }}
  .header {{ background: linear-gradient(135deg, #2d6a4f, #52b788); color: white; padding: 20px 30px; border-radius: 0 0 16px 16px; }}
  .header h1 {{ font-size: 1.6rem; margin: 0; }}
  .header .date {{ opacity: 0.85; font-size: 0.95rem; }}
  .card {{ border: none; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.07); margin-bottom: 20px; }}
  .card-header {{ background: #fff; border-bottom: 2px solid #e9ecef; border-radius: 12px 12px 0 0 !important; font-weight: 700; font-size: 1rem; padding: 14px 18px; }}
  .rank {{ width: 32px; color: #adb5bd; font-weight: 700; }}
  .bar {{ background: #52b788; height: 18px; border-radius: 4px; min-width: 4px; color: white; font-size: 11px; padding: 1px 4px; }}
  .bar-green {{ background: #74c69d; }}
  table {{ width: 100%; }}
  td {{ padding: 6px 8px; vertical-align: middle; font-size: 0.9rem; }}
  tr:hover {{ background: #f8f9fa; }}
  .tag {{ display: inline-block; background: #d8f3dc; color: #1b4332; border-radius: 20px; padding: 4px 12px; margin: 4px; cursor: default; }}
  .rising-tag {{ display: inline-block; background: #fff3cd; color: #856404; border-radius: 8px; padding: 6px 14px; margin: 4px; font-weight: 600; font-size: 0.9rem; }}
  .news-item {{ padding: 8px 0; border-bottom: 1px solid #f1f3f5; }}
  .news-item a {{ color: #2d6a4f; text-decoration: none; font-size: 0.88rem; }}
  .news-item a:hover {{ text-decoration: underline; }}
  .news-date {{ display: block; color: #adb5bd; font-size: 0.78rem; }}
  .mfds {{ background: #f8f9fa; padding: 6px 10px; border-radius: 6px; margin: 4px 0; }}
  .section-icon {{ margin-right: 6px; }}
</style>
</head>
<body>
<div class="header mb-4">
  <h1>🌿 건강기능식품 트랜드 대시보드</h1>
  <div class="date">{today} &nbsp;|&nbsp; 매일 오전 9시 자동 업데이트</div>
</div>

<div class="container-fluid px-4">

  <!-- 급상승 키워드 배너 -->
  <div class="card mb-3">
    <div class="card-header">⚡ 오늘의 급상승 키워드</div>
    <div class="card-body py-2">{rising_tags if rising_tags else '<span class="text-muted">데이터 수집 중...</span>'}</div>
  </div>

  <div class="row">
    <!-- 국내 순위 -->
    <div class="col-md-6 col-xl-3">
      <div class="card">
        <div class="card-header"><span class="section-icon">📊</span>국내 인기 순위</div>
        <div class="card-body p-2">
          <table><tbody>{naver_rows}</tbody></table>
        </div>
      </div>
    </div>

    <!-- 글로벌 트랜드 -->
    <div class="col-md-6 col-xl-3">
      <div class="card">
        <div class="card-header"><span class="section-icon">🌍</span>글로벌 트랜드</div>
        <div class="card-body p-2">
          <table><tbody>{google_rows}</tbody></table>
        </div>
      </div>
    </div>

    <!-- SNS 키워드 -->
    <div class="col-md-6 col-xl-3">
      <div class="card">
        <div class="card-header"><span class="section-icon">💬</span>SNS 화제 키워드</div>
        <div class="card-body">{sns_tags if sns_tags else '<span class="text-muted">데이터 수집 중...</span>'}</div>
      </div>
    </div>

    <!-- 뉴스/연구 -->
    <div class="col-md-6 col-xl-3">
      <div class="card">
        <div class="card-header"><span class="section-icon">📰</span>뉴스 / 연구 동향</div>
        <div class="card-body p-2">{news_items}{mfds_items}</div>
      </div>
    </div>
  </div>

  <!-- 주간 트랜드 차트 -->
  <div class="card">
    <div class="card-header"><span class="section-icon">📈</span>국내 Top 7 키워드 검색량 비교</div>
    <div class="card-body">
      <canvas id="trendChart" height="80"></canvas>
    </div>
  </div>

</div>

<script>
const ctx = document.getElementById('trendChart').getContext('2d');
new Chart(ctx, {{
  type: 'bar',
  data: {{
    labels: {chart_labels},
    datasets: [{{
      label: '검색 지수',
      data: {chart_values},
      backgroundColor: 'rgba(82, 183, 136, 0.7)',
      borderColor: '#2d6a4f',
      borderWidth: 1,
      borderRadius: 6
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true }} }}
  }}
}});
</script>
</body>
</html>"""

    return html, today_file
