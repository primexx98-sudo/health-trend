import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

# ─── 해외 RSS 피드 (직접 추가/수정 가능) ──────────────────────────
RSS_FEEDS = [
    # 업계 전문지
    {"name": "Nutraceuticals World",  "url": "https://www.nutraceuticalsworld.com/rss/"},
    {"name": "Food Navigator USA",    "url": "https://www.foodnavigator-usa.com/var/export/rss/"},
    # 연구·임상 기관
    {"name": "NIH News in Health",    "url": "https://newsinhealth.nih.gov/rss/news"},
    {"name": "Harvard Health Blog",   "url": "https://www.health.harvard.edu/blog/feed"},
    {"name": "Mayo Clinic News",      "url": "https://newsnetwork.mayoclinic.org/feed/"},
]

RELEVANT_KEYWORDS = [
    "supplement", "vitamin", "probiotic", "omega", "collagen",
    "nutraceutical", "functional food", "ingredient", "clinical",
    "health benefit", "antioxidant", "mineral", "herbal",
    "gut health", "immunity", "magnesium", "NAD", "NMN",
    "prebiotic", "adaptogen", "bioavailability", "extract",
    "protein", "fiber", "omega-3", "botanical", "phytochemical",
    "diet", "nutrition", "wellness", "microbiome", "inflammation",
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
            headers={"User-Agent": "Mozilla/5.0 (compatible; HealthBot/1.0)"}
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml-xml")

        # RSS 2.0 (<item>) 또는 Atom (<entry>) 모두 지원
        entries = soup.find_all("item") or soup.find_all("entry")

        for entry in entries[:25]:
            title_tag  = entry.find("title")
            link_tag   = entry.find("link")
            pub_tag    = entry.find("pubDate") or entry.find("published") or entry.find("updated")
            desc_tag   = entry.find("description") or entry.find("summary") or entry.find("content")

            if not title_tag:
                continue

            title_text = BeautifulSoup(title_tag.get_text(strip=True), "html.parser").get_text().strip()

            # Atom <link href="..."> vs RSS <link>text</link>
            if link_tag:
                link_text = link_tag.get("href") or link_tag.get_text(strip=True)
            else:
                link_text = ""

            pub_text  = pub_tag.get_text(strip=True) if pub_tag else ""
            desc_text = BeautifulSoup(
                desc_tag.get_text(strip=True), "html.parser"
            ).get_text()[:250] if desc_tag else ""

            if not is_recent(pub_text, days=14):
                continue
            if not is_relevant(title_text, desc_text):
                continue

            items.append({
                "title":       title_text,
                "link":        link_text,
                "pubDate":     pub_text,
                "source":      feed_info["name"],
                "description": desc_text,
            })

        logger.info(f"[{feed_info['name']}] {len(items)}건 수집")
    except Exception as e:
        logger.warning(f"RSS 수집 실패 [{feed_info['name']}]: {e}")
    return items


def get_overseas_news():
    all_items, seen = [], set()
    for feed in RSS_FEEDS:
        for item in parse_rss(feed):
            if item["title"] not in seen:
                seen.add(item["title"])
                all_items.append(item)
    logger.info(f"해외 업계 동향 합계 {len(all_items)}건")
    return all_items[:12]