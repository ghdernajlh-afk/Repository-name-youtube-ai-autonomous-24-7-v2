import os
import re
import time

import feedparser
import requests
from bs4 import BeautifulSoup


# ============================================================
# RSS SOURCES
# ============================================================

FEEDS = [
    # Google News
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=science+space&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=interesting+facts&hl=en-US&gl=US&ceid=US:en",

    # Backup sources
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
]


# ============================================================
# HTTP SETTINGS
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 "
    "(Linux; Android 10; Mobile) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36 "
    "YouTubeAI/2.0"
)


def http_get(url, timeout=20, retries=2):

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            response = requests.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "application/rss+xml, "
                        "application/xml, "
                        "text/xml, "
                        "text/html, "
                        "*/*"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
                allow_redirects=True,
            )

            response.raise_for_status()

            return response

        except Exception as e:

            last_error = e

            log(
                f"HTTP attempt "
                f"{attempt}/{retries} failed: "
                f"{repr(e)}"
            )

            if attempt < retries:
                time.sleep(1.5)

    if last_error:
        raise last_error

    return None


# ============================================================
# LOGGING
# ============================================================

def log(message):

    print(
        f"[DISCOVERY] {message}",
        flush=True
    )


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(value):

    if not value:
        return ""

    # Remove HTML
    value = BeautifulSoup(
        str(value),
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


# ============================================================
# DISCOVER
# ============================================================

def discover():

    out = []

    try:

        per_feed = int(
            os.getenv(
                "SEARCH_RESULTS_PER_FEED",
                "8"
            )
        )

    except Exception:

        per_feed = 8

    try:

        max_feeds = int(
            os.getenv(
                "MAX_DISCOVERY_FEEDS",
                str(len(FEEDS))
            )
        )

    except Exception:

        max_feeds = len(FEEDS)

    feeds = FEEDS[:max_feeds]

    log(
        f"Starting discovery from "
        f"{len(feeds)} RSS feeds"
    )

    successful_feeds = 0

    for index, url in enumerate(
        feeds,
        start=1
    ):

        try:

            log(
                f"Feed {index}/{len(feeds)}: "
                f"requesting {url}"
            )

            response = http_get(
                url,
                timeout=20,
                retries=2
            )

            log(
                f"Feed {index}: HTTP "
                f"{response.status_code}"
            )

            feed = feedparser.parse(
                response.content
            )

            entries = getattr(
                feed,
                "entries",
                []
            )

            log(
                f"Feed {index}: "
                f"{len(entries)} entries"
            )

            if entries:
                successful_feeds += 1

            for entry in entries[:per_feed]:

                title = clean_text(
                    entry.get(
                        "title",
                        ""
                    )
                )

                link = (
                    entry.get("link")
                    or entry.get("id")
                    or ""
                ).strip()

                summary = clean_text(
                    entry.get(
                        "summary",
                        ""
                    )
                )

                published = clean_text(
                    entry.get(
                        "published",
                        ""
                    )
                )

                if not title or not link:
                    continue

                out.append(
                    {
                        "title": title,
                        "link": link,
                        "summary": summary[:1500],
                        "published": published,
                    }
                )

        except Exception as e:

            log(
                f"Feed {index} ERROR: "
                f"{repr(e)}"
            )

        time.sleep(0.5)

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique = []
    seen_links = set()
    seen_titles = set()

    for item in out:

        link = (
            item.get("link")
            or ""
        ).strip()

        title = (
            item.get("title")
            or ""
        ).strip()

        link_key = link.lower()
        title_key = title.lower()

        if (
            not link_key
            and not title_key
        ):
            continue

        if link_key in seen_links:
            continue

        if title_key in seen_titles:
            continue

        seen_links.add(link_key)
        seen_titles.add(title_key)

        unique.append(item)

    log(
        f"Discovery completed: "
        f"{len(unique)} unique sources "
        f"from {successful_feeds} successful feeds"
    )

    # --------------------------------------------------------
    # IMPORTANT FALLBACK
    # --------------------------------------------------------

    if not unique:

        log(
            "WARNING: All RSS feeds returned "
            "zero usable sources."
        )

        # لا نخفي المشكلة، بل نعيد قائمة فارغة
        # حتى يستطيع worker.py تسجيل الخطأ بوضوح.
        return []

    return unique


# ============================================================
# SOURCE TEXT
# ============================================================

def source_text(url):

    if not url:
        return ""

    try:

        log(
            f"Fetching source: {url[:150]}"
        )

        response = http_get(
            url,
            timeout=15,
            retries=2
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # ----------------------------------------------------
        # REMOVE UNWANTED ELEMENTS
        # ----------------------------------------------------

        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
                "nav",
                "footer",
                "header",
                "form",
                "iframe",
                "aside",
            ]
        ):

            element.decompose()

        # ----------------------------------------------------
        # TRY ARTICLE FIRST
        # ----------------------------------------------------

        article = soup.find(
            "article"
        )

        if article:

            text = " ".join(
                article.stripped_strings
            )

        else:

            text = " ".join(
                soup.stripped_strings
            )

        text = clean_text(
            text
        )

        log(
            f"Source fetched: "
            f"{len(text)} characters"
        )

        return text[:7000]

    except Exception as e:

        log(
            f"Source ERROR: "
            f"{repr(e)}"
        )

        return ""
