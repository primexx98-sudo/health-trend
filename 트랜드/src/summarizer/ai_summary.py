import json
import logging
import os
import re

logger = logging.getLogger(__name__)

MODEL = "gemini-flash-latest"  # Google이 유지하는 최신 flash 별칭 — 특정 버전을 박아두면 구버전처럼 신규 사용자 접근이 막힐 수 있어 별칭 사용

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
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=_PROMPT.format(period_label=period_label, material=formatted),
        )
        text = resp.text
    except Exception as e:
        logger.error(f"AI 요약 생성 실패 [{period_label}]: {e}")
        return None

    return _parse_response(text)
