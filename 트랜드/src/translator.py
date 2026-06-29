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


def translate_text(text):
    if not text:
        return None
    usage = _load_usage()
    if usage["chars_used"] + len(text) > MONTHLY_LIMIT:
        logger.warning(f"번역 월 한도 초과 ({usage['chars_used']:,}/{MONTHLY_LIMIT:,}자) — 영문 표시")
        return None
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="en", target="ko").translate(text)
        usage["chars_used"] += len(text)
        _save_usage(usage)
        return translated
    except Exception as e:
        logger.error(f"번역 실패: {e}")
        return None


def translate_overseas_items(items):
    usage = _load_usage()
    logger.info(f"번역 잔여 한도: {MONTHLY_LIMIT - usage['chars_used']:,}자")
    for item in items:
        translated = translate_text(item["title"])
        item["title_ko"] = translated if translated else item["title"]
    return items