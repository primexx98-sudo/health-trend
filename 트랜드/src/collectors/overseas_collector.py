import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

# ─── 해외 RSS 피드 목록 (직접 추가/수정 가능) ──────────────────────
RSS_FEEDS = [
    {"name": "Nutraceuticals World", "url": "https://www.nutraceuticalsworld.com/rss/"},
    {"name": "Natural Products Insider", "url": "https://www.naturalproductsinsider.com/rss"},
    {"name": "Nutritional Outlook", "url": "https://www.nutritionaloutlook.com/rss/all"},
]

RELEVANT_KEYWORDS = [
    "supplement", "vitamin", "probiotic", "omega", "collagen",
    "nutraceutical", "functional food", "ingredient", "clinical",
    "health benefit", "antioxidant", "mineral", "herbal",
    "gut health", "immunity", "magnesium", "NAD", "NMN",
    "prebiotic", "adaptogen", "bioavailability", "extract"
]
# ──────────────────────────────────────────────────────────────────


def is_recent(pub_date_str, days=14):
    try:
        dt = parsedate_to_datetime(pub_date_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return dt > cutoff
    except Exception:
        return True


def is_relevant(title, desc=""):
    combined = (title + " " + desc).lower()
    return any(kw.lower() in combined for kw in RELEVANT_KEYWORDS)


def parse_rss(feed_info):
    items = []
    try:
        resp = requests.get(
            feed_info["url"], timeout=15,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml-xml")
        for item in soup.find_all("item")[:20]:
            title_tag = item.find("title")
            link_tag = item.find("link")
            pub_tag = item.find("pubDate")
            desc_tag = item.find("description")

            if not title_tag:
                continue

            title_text = title_tag.get_text(strip=True)
            link_text = link_tag.get_text(strip=True) if link_tag else ""
            pub_text = pub_tag.get_text(strip=True) if pub_tag else ""
            desc_text = BeautifulSoup(desc_tag.get_text(strip=True), "html.parser").get_text()[:200] if desc_tag else ""

            if not is_recent(pub_text, days=14):
                continue
            if not is_relevant(title_text, desc_text):
                continue

            items.append({
                "title": title_text,
                "link": link_text,
                "pubDate": pub_text,
                "source": feed_info["name"],
                "description": desc_text,
            })
    except Exception as e:
        logger.warning(f"RSS 수집 실패 [{feed_info['name']}]: {e}")
    return items


def get_overseas_news():
    all_items, seen = [], set()
    for feed in RSS_FEEDS:
        items = parse_rss(feed)
        for item in items:
            if item["title"] not in seen:
                seen.add(item["title"])
                all_items.append(item)
    logger.info(f"해외 업계 동향 {len(all_items)}건 수집")
    return all_items[:10]