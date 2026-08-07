"""
과거 dashboard_YYYYMMDD.html 백업 페이지를 최신 코드(보관함 탭 동적 로딩 포함)로 재생성.
naver_/digest_/ecommerce_ 일별 스냅샷이 남아있는 날짜(현재 07-01~오늘)만 대상 — 스냅샷 자체가
없는 06-28~06-30(UI 개편 이전, 원본 데이터 소재 없음)은 제외.

일회성 로컬 스크립트 — generate_html()이 datetime.now()에 의존해 과거 날짜를 파라미터로
못 받기 때문에 dashboard 모듈의 datetime을 그 날짜 09:00 KST로 몽키패치해서 호출한다.
weekly_data/monthly_data(상단 주간/월간 탭)는 이 사이트의 기존 설계대로 전 페이지 공용
"현재 최신값"을 그대로 사용 — 보관함 탭만 이번에 동적 로딩으로 바뀌어 날짜별 재현이 필요없다.
"""
import sys
import os
import json
from unittest import mock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")

from generator import dashboard
from collectors.ecommerce_collector import attach_rank_changes

_KST = timezone(timedelta(hours=9))
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
DOCS_DIR = os.path.join(_REPO_ROOT, "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")


def _load(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_news_data(news_data):
    """일부 과거 digest 스냅샷(특히 07-22, UI 개편 첫날)은 news_data 항목에 pubDate가
    아예 없는 경우가 있다 — 현재 collector는 항상 빈 문자열이라도 채워 넣지만, 그 이전
    데이터는 그렇지 않았음. generate_html은 이 필드가 항상 존재한다고 가정하므로,
    과거 데이터를 재생성 입력으로 쓸 때만 여기서 기본값을 채워준다."""
    if not isinstance(news_data, dict):
        return news_data
    for items in news_data.values():
        for it in items:
            it.setdefault("pubDate", "")
            it.setdefault("source", "네이버뉴스")
    return news_data


class _FakeDatetime(datetime):
    _fixed = None

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls._fixed.astimezone(tz)
        return cls._fixed.replace(tzinfo=None)


def main(only_dates=None):
    weekly_data = _load(os.path.join(DATA_DIR, "weekly", "weekly_2026-W31.json"))
    monthly_data = _load(os.path.join(DATA_DIR, "monthly", "monthly_202607.json"))

    dates = sorted(
        f[len("naver_"):-len(".json")]
        for f in os.listdir(DATA_DIR)
        if f.startswith("naver_") and f.endswith(".json")
    )
    if only_dates:
        dates = [d for d in dates if d in only_dates]

    written = []
    for i, date_str in enumerate(dates):
        naver_data = _load(os.path.join(DATA_DIR, f"naver_{date_str}.json"))
        if not naver_data:
            continue
        digest = _load(os.path.join(DATA_DIR, f"digest_{date_str}.json")) or {}
        sns_data = digest.get("sns_data", [])
        news_data = _normalize_news_data(digest.get("news_data", {}))
        rising_data = digest.get("rising_data", [])
        law_summary = digest.get("law_summary")

        ecommerce_data = _load(os.path.join(DATA_DIR, f"ecommerce_{date_str}.json")) or {}
        prev_date = None
        for j in range(i - 1, -1, -1):
            prev_date = dates[j]
            break
        naver_prev_data = _load(os.path.join(DATA_DIR, f"naver_{prev_date}.json")) if prev_date else None
        ecommerce_prev_data = _load(os.path.join(DATA_DIR, f"ecommerce_{prev_date}.json")) if prev_date else None
        ecommerce_data = attach_rank_changes(ecommerce_data, ecommerce_prev_data)

        _FakeDatetime._fixed = datetime.strptime(date_str, "%Y%m%d").replace(hour=9, minute=0, tzinfo=_KST)

        with mock.patch.object(dashboard, "datetime", _FakeDatetime):
            html, date_str_out = dashboard.generate_html(
                naver_data, sns_data, news_data, rising_data,
                ecommerce_data=ecommerce_data, naver_prev_data=naver_prev_data,
                law_summary=law_summary, weekly_data=weekly_data, monthly_data=monthly_data,
            )
        assert date_str_out == date_str, f"{date_str_out} != {date_str}"

        out_path = os.path.join(DOCS_DIR, f"dashboard_{date_str}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        written.append(date_str)

    print(f"재생성 완료: {len(written)}개 ({written[0]}~{written[-1]})" if written else "재생성 대상 없음")


if __name__ == "__main__":
    main()
