from __future__ import annotations

import re
from typing import Any, Dict, List


def normalize_gdelt_articles(raw_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for article in raw_articles:
        if not article:
            continue

        title = (article.get("title") or "").strip()
        snippet = (article.get("snippet") or "").strip()
        # Keep the original raw evidence; do not invent details.
        normalized_article = {
            "article_id": article.get("article_id") or article.get("source_url") or title or "unknown",
            "source": article.get("source") or "GDELT",
            "source_url": article.get("source_url") or "",
            "publication_datetime": article.get("publication_datetime") or "",
            "retrieved_datetime": article.get("retrieved_datetime") or "",
            "title": title,
            "snippet": snippet,
            "full_text_available": bool(article.get("full_text_available")),
            "country": article.get("country") or "IN",
            "state": article.get("state") or "",
            "district": article.get("district") or "",
            "location_text": article.get("location_text") or "",
            "road_name": article.get("road_name") or "",
            "road_reference": article.get("road_reference") or "",
            "hazard_type": article.get("hazard_type") or "",
            "impact_type": article.get("impact_type") or "",
            "keyword_match": article.get("keyword_match") or "",
            "raw_record_path": article.get("raw_record_path") or "",
        }
        normalized.append(normalized_article)
    return normalized
