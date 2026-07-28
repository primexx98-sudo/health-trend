import logging
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://www.foodnews.co.kr/"

# S2N3=건강기능식품, S2N6=신상품 (사이트 상단 메뉴 data-code 기준)
SECTIONS = {"S2N3": "건강기능식품", "S2N6": "신상품"}

# 이 사이트는 articleList.html?sc_sub_section_code=... URL에 직접 접속하면(curl/헤드리스
# 브라우저 무관) 항상 "전체기사" 목록을 반환하는 버그가 있음(2026-07-28 확인, 원인 불명 —
# 캐시 문제 아님, 쿠키/Referer 헤더로도 우회 안 됨). 홈페이지 접속 후 실제 메뉴를
# hover→click 하는 네비게이션을 그대로 재현해야만 서버가 올바르게 필터링한다.


def _extract_articles(page):
    items = page.eval_on_selector_all(
        "li:has(h4.titles > a[href*='articleView.html?idxno='])",
        """els => els.map(el => {
            const titleA = el.querySelector('h4.titles a');
            const desc = el.querySelector('p.lead');
            const bylineEms = el.querySelectorAll('span.byline em');
            const emTexts = Array.from(bylineEms).map(e => e.textContent.trim());
            return {
                title: titleA ? titleA.textContent.trim() : '',
                link: titleA ? titleA.href : '',
                desc: desc ? desc.textContent.trim() : '',
                date: emTexts.length ? emTexts[emTexts.length - 1] : '',
            };
        })""",
    )
    return items


def _in_target_month(date_str, year, month):
    # date_str 예: "2026.07.28 10:08"
    try:
        dt = datetime.strptime(date_str.split(" ")[0], "%Y.%m.%d")
        return dt.year == year and dt.month == month
    except Exception:
        return False


def get_foodnews_monthly(year, month):
    """S2N3(건강기능식품)/S2N6(신상품) 두 섹션에서 지정한 연/월에 해당하는 기사만 수집.
    반환: {"건강기능식품": [{"title","link","desc","date"}, ...], "신상품": [...]}"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright 미설치 — foodnews 월간 수집 건너뜀 (pip install playwright && playwright install chromium)")
        return {label: [] for label in SECTIONS.values()}

    result = {label: [] for label in SECTIONS.values()}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            for code, label in SECTIONS.items():
                try:
                    page.hover('a[data-code="S1N1"]')
                    page.wait_for_timeout(400)
                    page.click(f'a[data-code="{code}"]', force=True)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    items = _extract_articles(page)
                    in_month = [it for it in items if _in_target_month(it["date"], year, month)]
                    result[label] = in_month
                    logger.info(f"[foodnews:{label}] {year}-{month:02d} 기사 {len(in_month)}건 (페이지 내 총 {len(items)}건 중)")
                except Exception as e:
                    logger.error(f"[foodnews:{label}] 수집 실패: {e}")
            browser.close()
    except Exception as e:
        logger.error(f"foodnews 월간 수집 실패: {e}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    now = datetime.now()
    data = get_foodnews_monthly(now.year, now.month)
    for label, items in data.items():
        print(f"=== {label} ({len(items)}건) ===")
        for it in items[:5]:
            print(f"- [{it['date']}] {it['title']}")
