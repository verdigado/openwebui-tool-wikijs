"""
title: Wiki.js Fetch
description: Fetch the rendered content of a Wiki.js page from the Netzbegrünung Wiki (doku.netzbegruenung.de) by path or URL.
"""

import html
import re
from urllib.parse import urlsplit, unquote
import requests
from pydantic import Field

# Hard-coded Wiki.js base URL (no trailing slash) and content locale.
WIKIJS_URL = "https://doku.netzbegruenung.de"
WIKIJS_LOCALE = "de"


def _resolve_path(page: str) -> str:
    """
    Accept either a Wiki.js page path (e.g. 'wolke/gruppenordner') or a full
    page URL and return a normalised slash-separated path without the locale
    prefix.
    """
    page = (page or "").strip()
    if not page:
        return ""

    if "://" in page:
        path = urlsplit(page).path
    else:
        path = page

    path = unquote(path).strip().strip("/")
    # Strip leading locale segment (e.g. 'de/').
    path = re.sub(rf"^{re.escape(WIKIJS_LOCALE)}/", "", path)
    return path.strip("/")


def _html_to_text(content_html: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", content_html, flags=re.S | re.I)
    s = re.sub(r'<template\s+slot="comments">.*?</template>', "", s, flags=re.S | re.I)
    for level in range(6, 0, -1):
        s = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lvl=level: "\n\n" + "#" * lvl + " " + m.group(1) + "\n\n",
            s,
            flags=re.S | re.I,
        )
    s = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", s, flags=re.S | re.I)
    s = re.sub(r"<li[^>]*>", "- ", s, flags=re.I)
    s = re.sub(r"</li>", "\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p>", "\n\n", s, flags=re.I)
    s = re.sub(r"</(div|ul|ol|tr|table|h[1-6])>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


class Tools:
    def __init__(self):
        pass

    def fetch_wikijs_page(
        self,
        page: str = Field(
            ...,
            description=(
                "Wiki.js page to fetch. Accepts either a slash-separated page path "
                "(e.g. 'wolke/gruppenordner') or a full page URL."
            ),
        ),
    ) -> str:
        """
        Fetch the rendered HTML of the given Wiki.js page and return its title,
        description, and body converted to Markdown-like plain text.
        """
        path = _resolve_path(page)
        if not path:
            return "Error: no page path or URL provided."

        url = f"{WIKIJS_URL}/{WIKIJS_LOCALE}/{path}"

        try:
            resp = requests.get(url, timeout=15)
        except requests.RequestException as e:
            return f"Error contacting Wiki.js: {e}"

        if resp.status_code == 404:
            return f"Page not found: {path}"
        if resp.status_code in (401, 403):
            return f"Access denied for page: {path}"
        if not resp.ok:
            return f"Error fetching page {path}: HTTP {resp.status_code}"

        page_html = resp.text

        title_match = re.search(
            r'<meta\s+property="og:title"\s+content="([^"]*)"', page_html
        ) or re.search(r"<title>([^<]+)</title>", page_html)
        desc_match = re.search(
            r'<meta\s+name="description"\s+content="([^"]*)"', page_html
        )
        title = html.unescape(title_match.group(1)) if title_match else path
        description = html.unescape(desc_match.group(1)) if desc_match else ""

        body_match = re.search(r"<page\b[^>]*>(.*?)</page>", page_html, re.S)
        if not body_match:
            return f"Could not extract content from page: {path}"
        body = _html_to_text(body_match.group(1))
        if not body:
            return f"Page {path} has no extractable content."

        header = [f"# {title}", f"Source: {url}"]
        if description:
            header.append(f"Description: {description}")
        header.append("")
        header.append(body)
        return "\n".join(header)
