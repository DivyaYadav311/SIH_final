from __future__ import annotations

from typing import Dict, Iterable, List

ROAD_TERMS = [
    "road",
    "highway",
    "national highway",
    "NH",
    "NH-",
    "PWD road",
    "bridge",
    "culvert",
    "connectivity",
]

IMPACT_TERMS = [
    "blocked",
    "blockade",
    "closed",
    "closure",
    "cut off",
    "cut-off",
    "washed away",
    "washed out",
    "damaged",
    "collapsed",
    "destroyed",
    "inaccessible",
    "impassable",
    "traffic disrupted",
    "connectivity disrupted",
    "stranded",
    "road connectivity",
]

HAZARD_TERMS = [
    "flood",
    "flash flood",
    "heavy rain",
    "landslide",
    "mudslide",
    "erosion",
    "river",
    "cloudburst",
]

DEFAULT_STATES = [
    "Assam",
    "Arunachal Pradesh",
    "Meghalaya",
    "Manipur",
    "Mizoram",
    "Nagaland",
    "Tripura",
    "Sikkim",
]


def build_gdelt_queries(
    states: Iterable[str] | None = None,
    road_terms: Iterable[str] | None = None,
    impact_terms: Iterable[str] | None = None,
    hazard_terms: Iterable[str] | None = None,
) -> List[Dict[str, str]]:
    states = list(states or DEFAULT_STATES)
    road_terms = list(road_terms or ROAD_TERMS)
    impact_terms = list(impact_terms or IMPACT_TERMS)
    hazard_terms = list(hazard_terms or HAZARD_TERMS)

    queries: List[Dict[str, str]] = []
    for state in states:
        # The public GDELT API rejects short, generic phrases. Build explicit, multi-word
        # road-disruption queries that are more likely to match real reporting and satisfy
        # the API's minimum phrase-length requirements.
        explicit_phrases = [
            f'"{state}" "road blocked" "flood" "bridge damaged" "traffic disrupted"',
            f'"{state}" "road blocked" "landslide" "connectivity disrupted" "highway cut off"',
            f'"{state}" "road closure" "flood" "culvert washed away" "bridge closed"',
            f'"{state}" "road cut off" "landslide" "highway damaged" "villages stranded"',
            f'"{state}" "bridge washed away" "flash flood" "road damaged" "traffic halted"',
            f'"{state}" "highway damaged" "heavy rain" "road inaccessible" "bridge closure"',
        ]

        # Keep the original configurable keyword sets as a fallback when the caller passes
        # a custom state list or overrides, but prefer explicit phrase queries for public API
        # compatibility and evidence quality.
        for phrase in explicit_phrases:
            queries.append({
                "state": state,
                "query": phrase,
                "purpose": "road_disruption_evidence",
            })

        if road_terms and impact_terms and hazard_terms:
            query_parts = [
                f'"{state}"',
                '"' + '" OR "'.join(road_terms[:3]) + '"',
                '"' + '" OR "'.join(impact_terms[:3]) + '"',
                '"' + '" OR "'.join(hazard_terms[:3]) + '"',
            ]
            queries.append({
                "state": state,
                "query": " ".join(query_parts),
                "purpose": "road_disruption_evidence",
            })
    return queries
