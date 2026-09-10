"""
과거 dashboard_YYYYMMDD.html 백업 페이지를 최신 코드(보관함 탭 동적 로딩 포함)로 재생성.
naver_/digest_/ecommerce_ 일별 스냅샷이 남아있는 날짜(현재 07-01~오늘)만 대상 — 스냅샷 자체가
없는 06-28~06-30(UI 개편 이전, 원본 데이터 소재 없음)은 제외.

일회성 로컬 스크립트 — generate_html()이 datetime.now()에 의존해 과거 날짜를 파라미터로
못 받기 때문에 dashboard 모듈의 datetime을 그 날짜 09:00 KST로 몽키패치해서 호출한다.
weekly_data/monthly_data(상단 주간/월간 탭)는 이 사이트의 기존 설계대로 전 페이지 공용
"현재 최신값"을 그대로 사용 — 보관함 탭만 이번에 동적 로딩으로 바뀌어 날짜별 재현이 필요없다.

regenerate_one()은 main.py의 급상승 리포트 재시도 경로(2026-09-10)에서도 단일 날짜(전일)
재생성에 재사용한다 — Gemini 할당량 초과로 비어있던 이슈요약이 다음날 복구되면, 그 하루치
아카이브 페이지도 복구된 내용으로 다시 써야 실제로 화면에 반영되기 때문.
"""
import sys
import os
import glob
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


def _load_latest(period_dir, prefix):
    files = sorted(glob.glob(os.path.join(period_dir, f"{prefix}_*.json")))
    return _load(files[-1]) if files else None


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


def regenerate_one(date_str, weekly_data=None, monthly_data=None, rising_report=None):
    """단일 날짜의 dashboard_{date_str}.html을 그날 저장된 원본 스냅샷으로 재생성해 덮어쓴다.
    weekly_data/monthly_data/rising_report를 안 넘기면 각각 현재 최신 회차·해당 날짜의
    rising_{date_str}.json 스냅샷을 사용. 성공하면 True, naver 스냅샷 자체가 없으면 False."""
    naver_data = _load(os.path.join(DATA_DIR, f"naver_{date_str}.json"))
    if not naver_data:
        return False
    digest = _load(os.path.join(DATA_DIR, f"digest_{date_str}.json")) or {}
    sns_data = digest.get("sns_data", [])
    news_data = _normalize_news_data(digest.get("news_data", {}))
    rising_data = digest.get("rising_data", [])
    law_summary = digest.get("law_summary")

    ecommerce_data = _load(os.path.join(DATA_DIR, f"ecommerce_{date_str}.json")) or {}
    dates = sorted(
        f[len("naver_"):-len(".json")]
        for f in os.listdir(DATA_DIR)
        if f.startswith("naver_") and f.endswith(".json")
    )
    prev_date = next((d for d in reversed(dates) if d < date_str), None)
    naver_prev_data = _load(os.path.join(DATA_DIR, f"naver_{prev_date}.json")) if prev_date else None
    ecommerce_prev_data = _load(os.path.join(DATA_DIR, f"ecommerce_{prev_date}.json")) if prev_date else None
    ecommerce_data = attach_rank_changes(ecommerce_data, ecommerce_prev_data)

    if weekly_data is None:
        weekly_data = _load_latest(os.path.join(DATA_DIR, "weekly"), "weekly")
    if monthly_data is None:
        monthly_data = _load_latest(os.path.join(DATA_DIR, "monthly"), "monthly")
    if rising_report is None:
        rising_report = _load(os.path.join(DATA_DIR, f"rising_{date_str}.json"))

    _FakeDatetime._fixed = datetime.strptime(date_str, "%Y%m%d").replace(hour=9, minute=0, tzinfo=_KST)

    with mock.patch.object(dashboard, "datetime", _FakeDatetime):
        html, date_str_out = dashboard.generate_html(
            naver_data, sns_data, news_data, rising_data,
            ecommerce_data=ecommerce_data, naver_prev_data=naver_prev_data,
            law_summary=law_summary, weekly_data=weekly_data, monthly_data=monthly_data,
            rising_report=rising_report,
        )
    assert date_str_out == date_str, f"{date_str_out} != {date_str}"

    out_path = os.path.join(DOCS_DIR, f"dashboard_{date_str}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return True


def main(only_dates=None):
    # 이 CLI의 원래 용도(07-01~07 구버전 라이트테마 아카이브 일괄 재생성)는 그 시점 기준
    # "현재 최신" 주간/월간 회차를 전 날짜에 공통 적용했음 — 이후 회차가 계속 쌓여도 이
    # 배치용 기본값은 그대로 고정해 기존 재생성 결과와 동일하게 유지한다.
    weekly_data = _load(os.path.join(DATA_DIR, "weekly", "weekly_2026-W31.json"))
    monthly_data = _load(os.path.join(DATA_DIR, "monthly", "monthly_202607.json"))

    dates = sorted(
        f[len("naver_"):-len(".json")]
        for f in os.listdir(DATA_DIR)
        if f.startswith("naver_") and f.endswith(".json")
    )
    if only_dates:
        dates = [d for d in dates if d in only_dates]

    written = [d for d in dates if regenerate_one(d, weekly_data=weekly_data, monthly_data=monthly_data)]

    print(f"재생성 완료: {len(written)}개 ({written[0]}~{written[-1]})" if written else "재생성 대상 없음")


if __name__ == "__main__":
    main()
