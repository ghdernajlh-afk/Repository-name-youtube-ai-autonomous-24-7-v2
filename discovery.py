import os, feedparser, requests, re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

FEEDS=[
 "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
 "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en",
 "https://news.google.com/rss/search?q=science+space&hl=en-US&gl=US&ceid=US:en",
 "https://news.google.com/rss/search?q=business&hl=en-US&gl=US&ceid=US:en",
 "https://news.google.com/rss/search?q=interesting+facts&hl=en-US&gl=US&ceid=US:en"
]

def discover():
    out=[]
    n=int(os.getenv("SEARCH_RESULTS_PER_FEED","8"))
    for url in FEEDS:
        try:
            f=feedparser.parse(url)
            for e in f.entries[:n]:
                title=re.sub(r"\s+"," ",e.get("title","")).strip()
                link=e.get("link","")
                if title and link:
                    out.append({"title":title,"link":link,"summary":e.get("summary","")[:500]})
        except Exception:
            pass
    return out

def source_text(url):
    try:
        r=requests.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        for x in soup(["script","style","noscript"]): x.decompose()
        return " ".join(soup.stripped_strings)[:7000]
    except Exception:
        return ""
