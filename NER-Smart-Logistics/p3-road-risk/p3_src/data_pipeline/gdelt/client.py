from __future__ import annotations

import json
from typing import Any, Dict, List

import requests

GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def fetch_gdelt_articles(
    queries: List[Dict[str, str]],
    max_records: int = 25,
    start_date: str | None = None,
    end_date: str | None = None,
) -> List[Dict[str, Any]]:
    """Fetch public GDELT news records for configured queries.

    This intentionally stays within public API access and does not require GDELT Cloud.
    """
    articles: List[Dict[str, Any]] = []
    for query_config in queries:
        query = query_config.get("query", "")
        if not query:
            continue

        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(max_records),
            "sort": "pubtimedesc",
            "timespan": "1M",
        }
        if start_date:
            params["startdatetime"] = start_date
        if end_date:
            params["enddatetime"] = end_date

        try:
            response = requests.get(GDELT_API_URL, params=params, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue

        docs = payload.get("articles") or []
        for article in docs:
            article["gdelt_query_state"] = query_config.get("state")
            article["gdelt_query_purpose"] = query_config.get("purpose")
            article["gdelt_query"] = query
            articles.append(article)

    return articles
