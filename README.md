# 🌿 건강기능식품 트랜드 대시보드

건강기능식품 시장의 국내외 트랜드를 매일 자동 수집해 GitHub Pages로 제공하는 대시보드입니다.

**대시보드 바로가기 →** [GitHub Pages](https://primexx98-sudo.github.io/health-trend/)

---

## 주요 기능

| 섹션 | 내용 |
|------|------|
| 📊 국내 인기 순위 | 네이버 데이터랩 건강식품 검색 Top 20 |
| 🌍 글로벌 트랜드 | Google Trends 해외 검색 동향 |
| 💬 SNS 화제 키워드 | 네이버 블로그·카페 언급 키워드 |
| 📰 국내 뉴스 | 건강기능식품 관련 최신 뉴스 (RSS 7개 피드) |
| 🔬 연구·임상 동향 | 학회·논문·임상 관련 뉴스 자동 분류 |
| 🏛 식약처·규제 동향 | 개별인정형·고시·허가·행정처분 등 규제 뉴스 |
| 🌐 해외 업계 동향 | ScienceDaily 등 해외 RSS → 한국어 자동 번역 |

---

## 자동화

- **GitHub Actions** 매일 오전 9시(KST) 자동 실행
- **keepalive 워크플로** 매주 월요일 스케줄러 재활성화 (중단 방지)
- 결과는 **GitHub Pages**에 자동 배포

---

## 구조

```
트랜드/src/
├── main.py                  # 실행 진입점
├── translator.py            # 해외뉴스 한국어 번역 (deep-translator)
├── collectors/
│   ├── news_collector.py    # 국내 뉴스 RSS + 키워드 필터
│   └── overseas_collector.py # 해외 RSS 수집
└── generator/
    └── dashboard.py         # HTML 대시보드 생성
```

---

## 키워드 커스터마이징

`트랜드/src/collectors/news_collector.py` 상단에서 직접 수정 가능합니다.

```python
HEALTH_KEYWORDS    # 수집 대상 키워드 (건강기능식품 성분명·규제용어)
EXCLUDE_KEYWORDS   # 제외 키워드 (병원뉴스·무관주제 차단)
REGULATORY_KEYWORDS # 규제 뉴스 분류 기준
KOREAN_RSS_FEEDS   # RSS 피드 목록 (추가/제거 가능)
```

---

*매일 자동 업데이트 | 설계서: `트랜드/설계서.md`*