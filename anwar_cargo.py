#!/usr/bin/env python3
"""
Anwar Group of Industries cargo relevance mapping.

Maps CPA cargo codes to Anwar Group SBU supply categories. Cargoes outside
Anwar Group's scope (food, edible oil, fertiliser, ballast, demolition,
vehicles, paper pulp, etc.) map to None and are excluded from briefings.
"""

CATEGORY_PATTERNS = [
    ("Containerized Cargo", ["CONT"]),
    ("Coal", ["COAL"]),
    ("Cement Clinker", ["C.CLINK", "CLINKER"]),
    ("Limestone", ["LIMESTONE"]),
    ("Gypsum & Slag", ["GYPSUM", "SLAG"]),
    ("Iron & Steel Scrap", ["GI(SCRAP)", "SCRAP"]),
    ("Galvanized Iron", ["GI"]),
    ("Iron Ore / Steel", ["IRON ORE", "ORE", "PELLET", "BILLET", "STEEL ROD", "M.S ROD", "TMT"]),
    ("Gas & Energy", ["GAS", "LPG", "LNG", "PROPANE", "BUTANE", "HSFO", "CRUDE", "CONDENSATE", "FUEL OIL"]),
    ("Polymer / PP Resin", ["PP", "POLYPROPYLENE", "RESIN", "POLYMER", "YARN"]),
    ("Cement", ["CEMENT"]),
    ("Construction Materials", ["AGGREGATE", "STONE"]),
]

CATEGORY_SBU = {
    "Containerized Cargo": "All SBUs — raw materials, packaging, machinery, exports",
    "Coal": "Anwar Ispat & Anwar Cement — furnace and kiln fuel",
    "Cement Clinker": "Anwar Cement & Anwar Cement Sheet — core raw material",
    "Limestone": "Anwar Cement — cement-grade raw material",
    "Gypsum & Slag": "Anwar Cement — grinding additives",
    "Iron & Steel Scrap": "Anwar Ispat — melting feedstock; Anwar Galvanizing — base metal",
    "Galvanized Iron": "Anwar Galvanizing — GI coils and sheets",
    "Iron Ore / Steel": "Anwar Ispat — billets, rods and rebar",
    "Gas & Energy": "Group energy — furnace fuel and ocean-freight cost signal",
    "Polymer / PP Resin": "A1 Polymer — PP yarn, woven bags",
    "Cement": "Anwar Cement — finished-product market signal",
    "Construction Materials": "Construction demand proxy — Anwar Cement & Cement Sheet",
}


def categorize_cargo(cargo_type):
    """Return the Anwar supply category for a cargo code, or None if out of scope."""
    if cargo_type is None:
        return None
    c = str(cargo_type).upper().strip()
    for category, tokens in CATEGORY_PATTERNS:
        for token in tokens:
            if token == c or token in c:
                return category
    return None


def is_anwar_relevant(cargo_type):
    """True when the cargo falls inside Anwar Group's supply scope."""
    return categorize_cargo(cargo_type) is not None
