"""
SatQuery AI — Deterministic Scenario Matcher

Matches a user query against the 50 mock scenarios (and flagship demo scenarios)
using normalized text, location recognition, and semantic concept overlap.
Never routes using expected_tools. Returns None if confidence is low.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple
try:
    from mock_data.scenario_loader import load_scenarios
except ImportError:
    import sys
    from pathlib import Path
    _proj_root = Path(__file__).resolve().parents[3]
    if str(_proj_root) not in sys.path:
        sys.path.insert(0, str(_proj_root))
    from mock_data.scenario_loader import load_scenarios


# Common typo corrections and term normalizations
NORMALIZATIONS = {
    r"\bvegitation\b": "vegetation",
    r"\bveg\b": "vegetation",
    r"\bvegetations\b": "vegetation",
    r"\burbanisation\b": "urbanization",
    r"\bbuiltup\b": "built-up",
    r"\bsprawl\b": "urban",
    r"\bexpansion\b": "expansion",
    r"\bdeforest\b": "deforestation",
    r"\bdeforested\b": "deforestation",
    r"\bforest loss\b": "deforestation",
    r"\bflooded\b": "flood",
    r"\bflooding\b": "flood",
    r"\binundation\b": "flood",
    r"\binundated\b": "flood",
    r"\banalyse\b": "analyze",
    r"\bmonitoring\b": "monitor",
    r"\bcrops\b": "crop",
    r"\bcropland\b": "crop",
    r"\bfarmland\b": "crop",
    r"\bfarmlands\b": "crop",
    r"\bfires\b": "fire",
    r"\bwildfires\b": "wildfire",
    r"\bburning\b": "burn",
}

STOP_WORDS = {
    "show", "me", "how", "what", "is", "the", "are", "tell", "about", "can",
    "you", "please", "in", "of", "to", "for", "with", "between", "over",
    "last", "years", "year", "has", "been", "much", "many", "rate", "rates",
    "data", "using", "satellite", "analyse", "analyze", "detect", "assess",
    "evaluate", "map", "identify", "find", "quantify", "calculate", "compare"
}

# Known location keywords mapped to scenario IDs or location tokens
LOCATION_ALIASES: Dict[str, str] = {
    "uttarakhand": "uttarakhand",
    "para": "para state, brazil",
    "amazon": "para state, brazil",
    "brazil": "para state, brazil",
    "delhi": "delhi",
    "western ghats": "western ghats",
    "bandipur": "bandipur",
    "northeast india": "northeast india",
    "bengaluru": "bengaluru",
    "bangalore": "bengaluru",
    "hyderabad": "hyderabad",
    "pune": "pune",
    "ahmedabad": "ahmedabad",
    "assam": "assam",
    "godavari": "godavari",
    "bihar": "bihar",
    "chilika": "chilika",
    "chennai": "chennai",
    "similipal": "similipal",
    "garhwal": "garhwal",
    "quebec": "quebec",
    "paradise": "paradise",
    "california": "paradise",
    "punjab": "punjab",
    "marathwada": "marathwada",
    "karnal": "karnal",
    "haryana": "karnal",
    "cauvery": "cauvery",
    "krishna": "krishna",
    "mumbai": "mumbai",
    "sundarbans": "sundarbans",
    "digha": "digha",
    "kolleru": "kolleru",
    "kolkata": "kolkata",
    "nhava sheva": "nhava sheva",
    "bhadla": "bhadla",
    "thar": "bhadla",
    "rann of kutch": "rann of kutch",
    "kutch": "rann of kutch",
    "sikkim": "north sikkim",
    "puri": "puri",
    "konark": "puri",
    "leh": "leh ladakh",
    "ladakh": "leh ladakh",
    "arabian sea": "arabian sea",
    "lakshadweep": "lakshadweep",
    "great barrier reef": "great barrier reef",
    "bay of bengal": "bay of bengal",
    "odisha": "odisha",
    "machilipatnam": "machilipatnam",
    "khambhat": "gulf of khambhat",
    "derna": "derna, libya",
    "libya": "derna, libya",
}


def normalize_text(text: str) -> str:
    """Lowercase, fix typos, and remove extra whitespace/punctuation."""
    t = text.lower().strip()
    for pattern, repl in NORMALIZATIONS.items():
        t = re.sub(pattern, repl, t)
    # Replace punctuation with spaces
    t = re.sub(r"[^\w\s-]", " ", t)
    return " ".join(t.split())


def extract_tokens(text: str) -> Set[str]:
    """Tokenize and remove stop words."""
    norm = normalize_text(text)
    words = norm.split()
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def _extract_query_location(norm_query: str) -> Optional[str]:
    """Find if the query mentions any known scenario location."""
    for alias, standard_loc in LOCATION_ALIASES.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", norm_query):
            return standard_loc
    return None


def find_matching_scenario(query: str, threshold: float = 0.55) -> Optional[Dict[str, Any]]:
    """
    Deterministically match a user query against the mock scenarios.
    Returns the scenario dict if matched with high confidence, otherwise None.
    """
    if not query or not query.strip():
        return None

    norm_query = normalize_text(query)
    q_tokens = extract_tokens(norm_query)
    query_location = _extract_query_location(norm_query)

    scenarios = load_scenarios()
    scored_matches: List[Tuple[float, Dict[str, Any]]] = []

    for s in scenarios:
        s_loc = normalize_text(s.get("location", ""))
        s_q = normalize_text(s.get("question", ""))
        s_cat = normalize_text(s.get("category", ""))
        s_tokens = extract_tokens(s_q)

        # 1. Location match score (0.0 to 1.0)
        loc_score = 0.0
        if query_location:
            # Check if this scenario matches the query's location
            if query_location in s_loc or any(part in s_loc for part in query_location.split(",")):
                loc_score = 1.0
            else:
                # If query specified a different known location, this scenario does NOT match
                continue
        else:
            # If scenario location has words directly present in query
            s_loc_words = {w for w in s_loc.split() if len(w) > 2 and w not in STOP_WORDS}
            if s_loc_words and s_loc_words.intersection(q_tokens):
                loc_score = 0.8

        # 2. Category / Concept score (0.0 to 1.0)
        cat_score = 0.0
        if s_cat in norm_query:
            cat_score = 1.0
        elif s_cat == "vegetation" and any(k in norm_query for k in ["forest", "green", "ndvi", "tree"]):
            cat_score = 0.9
        elif s_cat == "urban" and any(k in norm_query for k in ["built-up", "built up", "city", "growth", "expansion", "sprawl"]):
            cat_score = 0.9
        elif s_cat == "flood" and any(k in norm_query for k in ["water", "inundation", "storm", "cyclone", "daniel"]):
            cat_score = 0.9
        elif s_cat == "agriculture" and any(k in norm_query for k in ["crop", "wheat", "paddy", "farm", "harvest"]):
            cat_score = 0.9
        elif s_cat == "wildfire" and any(k in norm_query for k in ["fire", "burn", "dnbr", "stubble"]):
            cat_score = 0.9
        elif s_cat == "sar_optical" and any(k in norm_query for k in ["sar", "radar", "mangrove", "optical"]):
            cat_score = 0.8
        elif s_cat == "ocean_marine" and any(k in norm_query for k in ["ocean", "marine", "wave", "sea"]):
            cat_score = 0.9

        # 3. Token overlap Jaccard score (0.0 to 1.0)
        token_overlap = len(q_tokens.intersection(s_tokens))
        union_len = len(q_tokens.union(s_tokens)) or 1
        jaccard = token_overlap / union_len

        # Combined weighted score
        # If query has location: location match is crucial
        if query_location:
            total_score = (loc_score * 0.50) + (cat_score * 0.30) + (jaccard * 0.20)
        else:
            # For queries without explicit location, require strong keyword overlap
            total_score = (cat_score * 0.40) + (jaccard * 0.60)

        if total_score >= threshold:
            scored_matches.append((total_score, s))

    if not scored_matches:
        # Deterministic concept mapping to existing flagship scenarios for location-agnostic queries
        scenario_map = {s.get("id"): s for s in scenarios}
        if any(k in norm_query for k in ["land cover", "lulc", "class distribution", "classes", "water and built", "built and water", "vegetation and built"]):
            return scenario_map.get("LULC-001") or scenario_map.get("MUL-002")
        elif any(k in norm_query for k in ["urban", "built-up", "built up", "expansion", "sprawl", "growth"]):
            return scenario_map.get("URB-006") or scenario_map.get("URB-001")
        elif any(k in norm_query for k in ["flood", "inundat", "submerged", "lake shrinkage", "water body", "water change"]):
            return scenario_map.get("FLD-006") or scenario_map.get("FLD-001")
        elif any(k in norm_query for k in ["sar", "radar", "backscatter", "polariz", "sentinel-1"]):
            return scenario_map.get("SAR-001")
        elif any(k in norm_query for k in ["wildfire", "fire", "burn", "dnbr"]):
            return scenario_map.get("FIR-001")
        elif any(k in norm_query for k in ["crop", "agriculture", "wheat", "paddy"]):
            return scenario_map.get("AGR-001")
        elif any(k in norm_query for k in ["ocean", "marine", "wave", "sst"]):
            return scenario_map.get("OCN-001")
        elif any(k in norm_query for k in ["ndvi", "vegetation", "forest", "canopy", "greenery", "spectral", "elevation", "terrain", "rainfall", "correlation"]):
            return scenario_map.get("VEG-001")
        return None

    # Sort descending by score
    scored_matches.sort(key=lambda x: x[0], reverse=True)
    best_score, best_scenario = scored_matches[0]

    return best_scenario
