import logging
from datetime import datetime
import json, os

logger = logging.getLogger(__name__)

MONTHLY_LIMIT = 490_000

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USAGE_FILE = os.path.join(_BASE, "data", "translate_usage.json")


def _load_usage():
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("month") != datetime.now().strftime("%Y-%m"):
            return {"month": datetime.now().strftime("%Y-%m"), "chars_used": 0}
        return data
    except Exception:
        return {"month": datetime.now().strftime("%Y-%m"), "chars_used": 0}


def _save_usage(usage):
    os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False)


def _is_korean(text):
    return any('가' <= c <= '힣' for c in (text or ''))


def translate_text(text):
    if not text:
        return None
    usage = _load_usage()
    if usage["chars_used"] + len(text) > MONTHLY_LIMIT:
        logger.warning(f"번역 월 한도 초과 ({usage['chars_used']:,}/{MONTHLY_LIMIT:,}자) — 영문 표시")
        return None
    import translators as ts
    for engine in ("bing", "google"):
        try:
            result = ts.translate_text(text, from_language="en", to_language="ko", translator=engine)
            if _is_korean(result):
                usage["chars_used"] += len(text)
                _save_usage(usage)
                logger.debug(f"번역 성공 [{engine}]: {text[:30]}...")
                return result
            logger.warning(f"[{engine}] 한글 없는 번역 결과 — 다음 엔진 시도")
        except Exception as e:
            logger.warning(f"[{engine}] 번역 실패: {e}")
    return None


def translate_overseas_items(items):
    usage = _load_usage()
    logger.info(f"번역 잔여 한도: {MONTHLY_LIMIT - usage['chars_used']:,}자")
    success = 0
    for item in items:
        translated = translate_text(item["title"])
        if translated:
            item["title_ko"] = translated
            success += 1
        else:
            item["title_ko"] = item["title"]
    logger.info(f"번역 완료: {success}/{len(items)}건")
    return items
