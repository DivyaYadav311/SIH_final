from __future__ import annotations

from typing import Any, Dict, Iterable, List


def parse_gdelt_articles(raw_articles: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    for article in raw_articles:
        if not article:
            continue
        parsed.append({
            "article_id": article.get("gid") or article.get("url") or article.get("title") or "",
            "source": article.get("source", ""),
            "source_url": article.get("url") or "",
            "publication_datetime": article.get("pubDate") or article.get("pubdate") or "",
            "retrieved_datetime": article.get("retrieved_datetime") or "",
            "title": article.get("title") or "",
            "snippet": article.get("seendate") or article.get("snippet") or article.get("title") or "",
            "full_text_available": False,
            "country": article.get("domain") or "",
            "state": article.get("gdelt_query_state") or "",
            "district": "",
            "location_text": article.get("location") or "",
            "road_name": "",
            "road_reference": "",
            "hazard_type": "",
            "impact_type": "",
            "keyword_match": article.get("gdelt_query") or "",
            "raw_record_path": "",
        })
    return parsed
