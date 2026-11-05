"""Fetch the daily news digest from GNews and save it as site/digest.json."""

import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

API_KEY = os.environ["GNEWS_API_KEY"]
ARTICLES_PER_TOPIC = 5
LANGUAGES = ["en", "de"]
OUTPUT_FILE = os.path.join("site", "digest.json")

RSS_ARTICLES_PER_SITE = 10

# Add new sites here: one line each (name, feed link).
RSS_SITES = [
    {"id": "mit-tech-review", "lang": "en", "name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"id": "towards-data-science", "lang": "en", "name": "Towards Data Science", "url": "https://towardsdatascience.com/feed"},
    {"id": "olive-press", "lang": "en", "name": "The Olive Press", "url": "https://www.theolivepress.es/feed/"},
    {"id": "heise", "lang": "de", "name": "Heise", "url": "https://www.heise.de/rss/heise-atom.xml"},
    {"id": "tagesschau", "lang": "de", "name": "Tagesschau", "url": "https://www.tagesschau.de/xml/rss2/"},
]

TOPICS = [
    {
        "id": "ai",
        "label": {"en": "AI", "de": "KI"},
        "query": {"en": '"artificial intelligence"', "de": '"Künstliche Intelligenz"'},
    },
    {
        "id": "data-science",
        "label": {"en": "Data science", "de": "Data Science"},
        "query": {"en": '"data science"', "de": '"Data Science"'},
    },
    {
        "id": "spain",
        "label": {"en": "Spain", "de": "Spanien"},
        "query": {"en": "Spain", "de": "Spanien"},
    },
]


def fetch_articles(query, lang):
    params = urllib.parse.urlencode({
        "q": query,
        "lang": lang,
        "max": ARTICLES_PER_TOPIC,
        "sortby": "publishedAt",
        "apikey": API_KEY,
    })
    url = "https://gnews.io/api/v4/search?" + params
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", ""),
            "published_at": item.get("publishedAt", ""),
        })
    return articles


def strip_html(text):
    import re
    import html
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return " ".join(text.split())[:300]


def fetch_rss(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DailyDigest)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    atom = "{http://www.w3.org/2005/Atom}"
    articles = []

    # RSS 2.0 format
    for item in root.iter("item"):
        articles.append({
            "title": strip_html(item.findtext("title")),
            "description": strip_html(item.findtext("description")),
            "url": (item.findtext("link") or "").strip(),
            "published_at": (item.findtext("pubDate") or "").strip(),
        })

    # Atom format (used by Heise)
    if len(articles) == 0:
        for entry in root.iter(atom + "entry"):
            link = ""
            link_element = entry.find(atom + "link")
            if link_element is not None:
                link = link_element.get("href", "")
            summary = entry.findtext(atom + "summary") or entry.findtext(atom + "content")
            published = entry.findtext(atom + "updated") or entry.findtext(atom + "published")
            articles.append({
                "title": strip_html(entry.findtext(atom + "title")),
                "description": strip_html(summary),
                "url": link,
                "published_at": (published or "").strip(),
            })

    return articles[:RSS_ARTICLES_PER_SITE]


def main():
    digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "languages": {},
    }

    for lang in LANGUAGES:
        sections = []
        for topic in TOPICS:
            error = None
            try:
                articles = fetch_articles(topic["query"][lang], lang)
            except Exception as exc:
                articles = []
                error = str(exc)
                print(f"Failed: {topic['id']} ({lang}): {error}")
            sections.append({
                "id": topic["id"],
                "label": topic["label"][lang],
                "articles": articles,
                "error": error,
            })
            time.sleep(2)  # stay well under the API rate limit
        digest["languages"][lang] = sections

    sites = []
    for site in RSS_SITES:
        error = None
        try:
            articles = fetch_rss(site["url"])
        except Exception as exc:
            articles = []
            error = str(exc)
            print(f"Failed RSS: {site['name']}: {error}")
        sites.append({"id": site["id"], "lang": site["lang"], "name": site["name"], "articles": articles, "error": error})
    digest["sites"] = sites

    os.makedirs("site", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(digest, file, ensure_ascii=False, indent=2)
    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
