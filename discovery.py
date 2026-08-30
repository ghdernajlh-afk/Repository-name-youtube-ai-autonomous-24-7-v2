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
    "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=science+space&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=interesting+facts&hl=en-US&gl=US&ceid=US:en",
]


# ============================================================
# LOGGING
# ============================================================

def log(message):
    print(
        f"[DISCOVERY] {message}",
        flush=True
    )


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

    log(
        f"Starting discovery from "
        f"{len(FEEDS)} RSS feeds"
    )

    for index, url in enumerate(
        FEEDS,
        start=1
    ):

        try:

            log(
                f"Feed {index}/{len(FEEDS)}: "
                f"requesting"
            )

            response = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(compatible; "
                        "YouTubeAI/1.0)"
                    )
                }
            )

            response.raise_for_status()

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

            for entry in entries[:per_feed]:

                title = re.sub(
                    r"\s+",
                    " ",
                    entry.get(
                        "title",
                        ""
                    )
                ).strip()

                link = entry.get(
                    "link",
                    ""
                )

                summary = re.sub(
                    r"\s+",
                    " ",
                    entry.get(
                        "summary",
                        ""
                    )
                ).strip()

                if not title or not link:
                    continue

                out.append(
                    {
                        "title": title,
                        "link": link,
                        "summary": summary[:1000],
                    }
                )

        except Exception as e:

            log(
                f"Feed {index} ERROR: "
                f"{repr(e)}"
            )

        # إعطاء الخادم فترة قصيرة بين المصادر
        time.sleep(0.5)

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique = []
    seen = set()

    for item in out:

        key = (
            item.get("link")
            or item.get("title")
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    log(
        f"Discovery completed: "
        f"{len(unique)} unique sources"
    )

    return unique


# ============================================================
# SOURCE TEXT
# ============================================================

def source_text(url):

    if not url:
        return ""

    try:

        log(
            f"Fetching source: {url[:120]}"
        )

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; "
                    "YouTubeAI/1.0)"
                )
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # إزالة العناصر غير المفيدة
        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
                "nav",
                "footer",
                "header",
            ]
        ):
            element.decompose()

        text = " ".join(
            soup.stripped_strings
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()

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
