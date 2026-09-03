#!/usr/bin/env python3
"""Dedup proxy for the eFinancialCareers RSS feed.

The upstream feed (https://www.efinancialcareers.com/feed/syndication/rss.xml)
frequently publishes the same article multiple times under different URLs
(e.g. .../managing-gfs-uk-and-leading-the-uk-apprenticeship-program vs
.../managing-gfs-uk-and-leading-the-uk-apprenticeship-program-sc, old date
paths like /news/2014/09/..., /finance/ variants, slug rewrites, ...).

Miniflux deduplicates entries by URL hash, so every URL alias becomes a
separate story in the reader. This service fetches the upstream feed, removes
duplicate items (same normalized title), preferring the most canonical-looking
URL, and serves the cleaned feed to Miniflux.

Endpoints:
  GET /rss.xml   cleaned feed (application/rss+xml)
  GET /healthz   health check
"""

import html
import http.server
import re
import threading
import time
import urllib.request

UPSTREAM = "https://www.efinancialcareers.com/feed/syndication/rss.xml"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CACHE_TTL = 180  # seconds between upstream fetches
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8090

ITEM_RE = re.compile(r"<item(?:\s[^>]*)?>.*?</item>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

_cache = {"data": None, "ts": 0.0}
_lock = threading.Lock()


def normalize_title(title: str) -> str:
    t = html.unescape(TAG_RE.sub("", title or ""))
    return re.sub(r"\s+", " ", t).strip().lower()


def canonical_score(url: str) -> tuple:
    """Lower is more canonical. Penalizes obvious alias patterns."""
    s = 0
    if re.search(r"/20\d{2}/", url):
        s += 100  # old-style dated path, e.g. /news/2014/09/
    if re.search(r"-\d{4}$", url):
        s += 50  # slug suffix like -2025
    if url.endswith("-sc"):
        s += 40
    if "/finance/" in url:
        s += 30
    return (s, len(url))


def extract(item: str, field: str) -> str:
    m = re.search(rf"<{field}[^>]*>(.*?)</{field}>", item, re.S)
    return m.group(1) if m else ""


def fetch_upstream() -> str:
    req = urllib.request.Request(
        UPSTREAM,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def build_clean_feed() -> str:
    raw = fetch_upstream()

    # First pass: group items by normalized title, pick best URL per group.
    groups = {}
    for m in ITEM_RE.finditer(raw):
        item = m.group(0)
        title = normalize_title(extract(item, "title"))
        link = html.unescape(extract(item, "link")).strip()
        if not title or not link:
            continue
        cur = groups.get(title)
        if cur is None or canonical_score(link) < canonical_score(cur[0]):
            groups[title] = (link, item)

    chosen = {g[1] for g in groups.values()}

    # Second pass: keep only chosen items in their original position.
    parts = []
    pos = 0
    for m in ITEM_RE.finditer(raw):
        item = m.group(0)
        if item in chosen:
            parts.append(raw[pos:m.start()])
            parts.append(item)
        pos = m.end()
    parts.append(raw[pos:])
    return "".join(parts)


def fetch() -> str:
    now = time.time()
    with _lock:
        if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
            return _cache["data"]
        try:
            data = build_clean_feed()
        except Exception:
            if _cache["data"] is not None:
                return _cache["data"]  # serve stale cache on upstream failure
            raise
        _cache["data"] = data
        _cache["ts"] = now
        return data


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if self.path != "/rss.xml":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = fetch()
        except Exception:
            self.send_response(502)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):  # keep stdout quiet
        pass


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"feed-dedup listening on {LISTEN_HOST}:{LISTEN_PORT}")
    srv.serve_forever()
