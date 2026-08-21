import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)

MODEL = "gemini-flash-latest"  # Google이 유지하는 최신 flash 별칭 — 특정 버전을 박아두면 구버전처럼 신규 사용자 접근이 막힐 수 있어 별칭 사용

# 2026-08-21: Gemini가 "503 UNAVAILABLE (high demand)"를 자주 반환하는 걸 실배포에서
# 확인(급상승 리포트 6개 카드 중 5개가 한 번의 시도로 이 오류를 맞음) — 일시적 과부하라
# 짧은 대기 후 재시도하면 회복되는 경우가 많아 재시도 로직을 공용 헬퍼로 둔다.
_MAX_RETRIES = 2
_RETRY_DELAYS = [2, 5]  # 재시도 사이 대기(초), 마지막 시도까지 실패하면 포기


def _generate_with_retry(client, contents, label):
    """일시적 API 실패(503 등)에 짧게 재시도. 최종 실패 시 None."""
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(model=MODEL, contents=contents)
            return resp.text
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(f"AI 생성 실패 [{label}], {delay}초 후 재시도({attempt + 1}/{_MAX_RETRIES}): {e}")
                time.sleep(delay)
    logger.error(f"AI 생성 최종 실패 [{label}]: {last_error}")
    return None

_PROMPT = """당신은 건강기능식품 산업 동향을 정리하는 애널리스트입니다.
아래는 "{period_label}" 기간 동안 수집된 원본 데이터입니다. 이를 바탕으로 간결한 한국어 요약을 작성하세요.

{material}

주의사항:
- "이커머스 동향"의 "신규진입"은 그 몰에 상시적으로 발생하는 신규 상품 등록일 뿐, 그 자체로 산업 트렌드나 의미 있는 변화를 뜻하지 않습니다. 특정 유통채널(예: 다이소몰)에 신규진입이 몰려있다고 해서 "그 채널 중심으로 신규 입점이 확대되고 있다" 같은 트렌드성 주장을 하지 마세요.
- 실제로 근거 있는 신호는 순위 상승(예: "▲4")처럼 기존 순위에서 올라간 경우입니다. 신규진입은 트렌드 주장 없이 사실만 나열하는 정도로만 언급하세요.

다음 JSON 형식으로만 답하세요(다른 텍스트 없이):
{{"summary": "2~3문장의 전체 요약", "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"]}}
"""


def _client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai
    return genai.Client(api_key=api_key)


def _format_material(material):
    """material: {section_label: [line, line, ...]} 형태의 dict — 호출부(weekly.py/monthly.py)가
    자기 도메인(검색순위/뉴스/이커머스/foodnews 등)에 맞게 이미 골라 넣은 텍스트 줄들을 받아
    프롬프트용 텍스트로만 조립한다. 원본 데이터 구조는 이 모듈이 알 필요 없음."""
    parts = []
    for label, lines in material.items():
        if not lines:
            continue
        parts.append(f"[{label}]")
        parts.extend(f"- {line}" for line in lines)
    return "\n".join(parts)


def _parse_response(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        logger.warning("AI 요약 응답에서 JSON을 찾지 못함")
        return None
    try:
        parsed = json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"AI 요약 응답 JSON 파싱 실패: {e}")
        return None
    if not isinstance(parsed.get("summary"), str) or not isinstance(parsed.get("key_points"), list):
        return None
    return {"summary": parsed["summary"], "key_points": [str(p) for p in parsed["key_points"]]}


def summarize(period_label, material):
    """period_label: "2026년 7월 1주차" 등 표시용 문구.
    material: {섹션명: [줄, ...]} — 호출부가 준비한 요약 재료.
    반환: {"summary": str, "key_points": [str, ...]} | None (키 미설정·재료 없음·API 실패 시)"""
    client = _client()
    if client is None:
        logger.warning("GEMINI_API_KEY 미설정 — AI 요약 건너뜀")
        return None
    if not any(material.values()):
        logger.info(f"[{period_label}] AI 요약 재료 없음 — 건너뜀")
        return None

    formatted = _format_material(material)
    text = _generate_with_retry(
        client, _PROMPT.format(period_label=period_label, material=formatted), period_label
    )
    if text is None:
        return None

    return _parse_response(text)


_KEYWORD_PROMPT = """당신은 건강기능식품 마케팅 동향을 분석하는 애널리스트입니다.
아래는 "{name}"({kind_label})에 대해 최근 수집된 뉴스 제목입니다. 이 자료만 근거로
왜 이 키워드의 검색량이 늘고 있는지 짧게 분석하세요.

[뉴스 제목]
{news_lines}

주의사항:
- 자료에 없는 내용(구체적인 방송 편성, 인플루언서 이름, 광고 캠페인 등)은 추측해서
  지어내지 마세요 — 자료에 실제로 나온 내용만 근거로 쓰세요.
- 근거가 부족하면 억지로 만들지 말고 있는 그대로("최근 언급이 늘어난 배경은 자료만으로는
  확인되지 않음" 등)를 짧게 쓰세요.

다음 JSON 형식으로만 답하세요(다른 텍스트 없이):
{{"bullets": ["핵심 포인트 1", "핵심 포인트 2"]}}
"""


def summarize_keyword_issue(name, kind_label, news_titles):
    """급상승 원료/브랜드 카드의 '이슈 및 현황' 텍스트를 생성한다.
    name: 원료명 또는 브랜드/제품명. kind_label: "원료" | "브랜드/제품".
    news_titles: 그 키워드로 검색한 최근 뉴스 제목 리스트.
    반환: [str, ...] | None (키 미설정·자료 없음·API 실패 시)"""
    client = _client()
    if client is None:
        return None
    if not news_titles:
        return None

    news_lines = "\n".join(f"- {t}" for t in news_titles[:8])
    text = _generate_with_retry(
        client, _KEYWORD_PROMPT.format(name=name, kind_label=kind_label, news_lines=news_lines), name
    )
    if text is None:
        return None

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return None
    bullets = parsed.get("bullets")
    if not isinstance(bullets, list):
        return None
    return [str(b) for b in bullets]
