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
    """일시적 API 실패(503 등)에 짧게 재시도. 단, 429(RESOURCE_EXHAUSTED)는 하루 총
    호출한도 자체를 넘긴 것이라 몇 초 기다려도 풀리지 않으므로 즉시 포기한다
    (재시도하면 남은 할당량만 더 빨리 소진됨). 최종 실패 시 None."""
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(model=MODEL, contents=contents)
            return resp.text
        except Exception as e:
            last_error = e
            if "RESOURCE_EXHAUSTED" in str(e):
                logger.error(f"AI 생성 실패 [{label}]: 일일 호출 한도 초과 — 재시도하지 않음: {e}")
                return None
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

추가로, 아래 자료 중 "급상승 원료"·"급상승 브랜드/제품"·"검색은 늘었지만 대표 판매상품이 없는
키워드" 항목을 근거로 이 기간에 검토해볼 만한 신제품 콘셉트를 최대 3개 제안하세요.
- 반드시 위 자료에 실제로 있는 신호(급상승 원료명, 검색-판매 갭 키워드 등)를 근거로 삼으세요.
- 근거로 삼을 만한 신호가 부족하면 억지로 개수를 채우지 말고 0~1개만 제안해도 됩니다.
- rationale에는 어떤 자료의 어떤 신호를 근거로 했는지 구체적으로 쓰세요(예: "젖산마그네슘 검색량
  급상승 + 검색-판매 갭에 해당 원료 미노출").

다음 JSON 형식으로만 답하세요(다른 텍스트 없이):
{{"summary": "2~3문장의 전체 요약", "key_points": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
"product_ideas": [{{"name": "제품 콘셉트명", "concept": "1~2문장 제품 설명", "rationale": "근거가 된 구체적 데이터 신호"}}]}}
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

    product_ideas = []
    for idea in parsed.get("product_ideas") or []:
        if isinstance(idea, dict) and idea.get("name") and idea.get("concept"):
            product_ideas.append({
                "name": str(idea["name"]),
                "concept": str(idea["concept"]),
                "rationale": str(idea.get("rationale", "")),
            })

    return {
        "summary": parsed["summary"],
        "key_points": [str(p) for p in parsed["key_points"]],
        "product_ideas": product_ideas,
    }


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


_BATCH_KEYWORD_PROMPT = """당신은 건강기능식품 마케팅 동향을 분석하는 애널리스트입니다.
아래는 여러 원료/브랜드별로 최근 수집된 뉴스 제목입니다. 각 항목마다 그 자료만 근거로
왜 검색량이 늘고 있는지 짧게 분석하세요.

{items_block}

주의사항:
- 자료에 없는 내용(구체적인 방송 편성, 인플루언서 이름, 광고 캠페인 등)은 추측해서
  지어내지 마세요 — 자료에 실제로 나온 내용만 근거로 쓰세요.
- 근거가 부족하면 억지로 만들지 말고 있는 그대로("최근 언급이 늘어난 배경은 자료만으로는
  확인되지 않음" 등)를 짧게 쓰세요.
- 항목 이름은 입력에 준 이름과 정확히 동일한 문자열을 키로 사용하세요.

다음 JSON 형식으로만 답하세요(다른 텍스트 없이):
{{"items": {{"항목명1": ["핵심 포인트 1", "핵심 포인트 2"], "항목명2": ["핵심 포인트 1"]}}}}
"""


def summarize_keyword_issues_batch(items):
    """급상승 원료/브랜드 카드 여러 개의 '이슈 및 현황'을 한 번의 API 호출로 함께 생성한다.
    카드마다 개별 호출하면(원료3+브랜드3=6회) Gemini 무료 티어의 하루 호출 한도(20회)를
    리포트 한 번 생성으로 다 써버릴 수 있어 배치 처리로 바꿈(2026-08-21).
    items: [{"name": str, "kind_label": "원료"|"브랜드/제품", "news_titles": [str, ...]}, ...]
    반환: {name: [bullet, ...]} — 뉴스가 있던 항목만 포함, 키 미설정·자료 없음·API 실패 시 {}"""
    client = _client()
    if client is None:
        return {}
    usable = [it for it in items if it.get("news_titles")]
    if not usable:
        return {}

    blocks = []
    for it in usable:
        lines = "\n".join(f"  - {t}" for t in it["news_titles"][:8])
        blocks.append(f'[{it["name"]}] ({it["kind_label"]})\n{lines}')
    items_block = "\n\n".join(blocks)

    text = _generate_with_retry(
        client, _BATCH_KEYWORD_PROMPT.format(items_block=items_block), "키워드 이슈 배치"
    )
    if text is None:
        return {}

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except Exception:
        return {}
    result = parsed.get("items")
    if not isinstance(result, dict):
        return {}
    return {k: [str(b) for b in v] for k, v in result.items() if isinstance(v, list)}
