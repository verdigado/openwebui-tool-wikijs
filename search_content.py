"""
title: Wiki.js Search
description: Search pages in the Netzbegrünung Wiki.js instance (doku.netzbegruenung.de) via GraphQL and return matching page paths.
"""

import os
import requests
from pydantic import Field

# Hard-coded Wiki.js base URL (no trailing slash) and content locale.
WIKIJS_URL = "https://doku.netzbegruenung.de"
WIKIJS_LOCALE = "de"


def _graphql(query: str, variables: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    token = os.getenv("WIKIJS_API_KEY")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.post(
        f"{WIKIJS_URL}/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


class Tools:
    def __init__(self):
        pass

    def search_wikijs(
        self,
        query: str = Field(
            ..., description="Full-text search query to run against the Wiki.js."
        ),
    ) -> str:
        """
        Search the configured Wiki.js for the given query and return a list of
        matching pages (title, path, and short description) from the Wiki.js
        GraphQL search API.
        """
        gql = """
        query($query: String!, $locale: String) {
          pages {
            search(query: $query, locale: $locale) {
              results { id title description path locale }
              suggestions
              totalHits
            }
          }
        }
        """

        try:
            data = _graphql(gql, {"query": query, "locale": WIKIJS_LOCALE})
        except requests.RequestException as e:
            return f"Error contacting Wiki.js: {e}"

        if data.get("errors"):
            return f"GraphQL error: {data['errors'][0].get('message', 'unknown')}"

        search = (data.get("data") or {}).get("pages", {}).get("search") or {}
        results = search.get("results") or []

        if not results:
            suggestions = search.get("suggestions") or []
            msg = f"No results found for: {query}"
            if suggestions:
                msg += f"\nSuggestions: {', '.join(suggestions)}"
            return msg

        lines = [f"Found {search.get('totalHits', len(results))} result(s) for '{query}':", ""]
        for r in results:
            path = r.get("path", "")
            title = r.get("title") or "(untitled)"
            url = f"{WIKIJS_URL}/{r.get('locale', WIKIJS_LOCALE)}/{path}"
            lines.append(f"- {title} ({path}): {url}")
            description = r.get("description") or ""
            if description:
                lines.append(f"  {description}")
        return "\n".join(lines)
