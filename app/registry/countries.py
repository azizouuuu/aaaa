"""Country registry: ISO3 <-> UN M49 numeric codes (what Comtrade speaks),
display names, renewable-diesel/SAF hub flags and the priority watchlists.

Curated to the countries that matter for renewable feedstock & fuel trade;
extend as pipelines grow. "WLD" (0) is Comtrade's World aggregate partner.
"""

# iso3: (m49, name)
COUNTRIES: dict[str, tuple[int, str]] = {
    "WLD": (0, "World"),
    # Asia
    "CHN": (156, "China"),
    "IDN": (360, "Indonesia"),
    "MYS": (458, "Malaysia"),
    "THA": (764, "Thailand"),
    "SGP": (702, "Singapore"),
    "JPN": (392, "Japan"),
    "KOR": (410, "Rep. of Korea"),
    "IND": (356, "India"),
    "VNM": (704, "Viet Nam"),
    "PHL": (608, "Philippines"),
    "PAK": (586, "Pakistan"),
    "TWN": (490, "Other Asia, nes (Taiwan)"),
    "HKG": (344, "Hong Kong SAR"),
    "PNG": (598, "Papua New Guinea"),
    "ARE": (784, "United Arab Emirates"),
    "SAU": (682, "Saudi Arabia"),
    "TUR": (792, "Türkiye"),
    # South America
    "ARG": (32, "Argentina"),
    "BRA": (76, "Brazil"),
    "URY": (858, "Uruguay"),
    "PRY": (600, "Paraguay"),
    "COL": (170, "Colombia"),
    "PER": (604, "Peru"),
    "CHL": (152, "Chile"),
    "BOL": (68, "Bolivia"),
    "ECU": (218, "Ecuador"),
    # North & Central America
    "USA": (842, "USA"),
    "CAN": (124, "Canada"),
    "MEX": (484, "Mexico"),
    "GTM": (320, "Guatemala"),
    "HND": (340, "Honduras"),
    # Europe
    "NLD": (528, "Netherlands"),
    "DEU": (276, "Germany"),
    "BEL": (56, "Belgium"),
    "FRA": (251, "France"),
    "ESP": (724, "Spain"),
    "ITA": (380, "Italy"),
    "GBR": (826, "United Kingdom"),
    "IRL": (372, "Ireland"),
    "PRT": (620, "Portugal"),
    "SWE": (752, "Sweden"),
    "FIN": (246, "Finland"),
    "DNK": (208, "Denmark"),
    "NOR": (579, "Norway"),
    "POL": (616, "Poland"),
    "AUT": (40, "Austria"),
    "CZE": (203, "Czechia"),
    "HUN": (348, "Hungary"),
    "ROU": (642, "Romania"),
    "BGR": (100, "Bulgaria"),
    "GRC": (300, "Greece"),
    "LTU": (440, "Lithuania"),
    "LVA": (428, "Latvia"),
    "EST": (233, "Estonia"),
    "CHE": (757, "Switzerland"),
    "UKR": (804, "Ukraine"),
    "RUS": (643, "Russian Federation"),
    # Oceania & Africa
    "AUS": (36, "Australia"),
    "NZL": (554, "New Zealand"),
    "ZAF": (710, "South Africa"),
    "EGY": (818, "Egypt"),
    "MAR": (504, "Morocco"),
    "NGA": (566, "Nigeria"),
    "KEN": (404, "Kenya"),
}

M49_TO_ISO3: dict[int, str] = {m49: iso for iso, (m49, _) in COUNTRIES.items()}

# Pseudo-country codes for bloc aggregates — not real M49-codeable reporters,
# so they're deliberately excluded from COUNTRIES/m49_of. See
# app/signals/eu_bloc.py for how the EU27 figure itself is computed.
EU_BLOC_ISO = "EU27"
_SPECIAL_NAMES = {EU_BLOC_ISO: "European Union (27)"}


def name_of(iso3: str) -> str:
    if iso3 in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[iso3]
    entry = COUNTRIES.get(iso3)
    return entry[1] if entry else iso3


def m49_of(iso3: str) -> int | None:
    entry = COUNTRIES.get(iso3)
    return entry[0] if entry else None


# Renewable-diesel / SAF demand hubs: destinations whose imports of waste
# feedstocks are overwhelmingly fuel-driven. Used by the corridor signal.
RD_SAF_HUBS: dict[str, str] = {
    "NLD": "Rotterdam hub — Neste, Shell HEFA, storage & blending",
    "SGP": "Neste Singapore RD/SAF platform",
    "FIN": "Neste Porvoo",
    "ESP": "Repsol Cartagena, Cepsa La Rábida",
    "ITA": "Eni Gela & Venice bio-refineries",
    "USA": "US renewable diesel boom (California LCFS, IRA credits)",
    "SWE": "Preem, St1",
    "PRT": "Galp Sines (co-processing/HVO)",
    "FRA": "TotalEnergies La Mède, Grandpuits",
    "GBR": "Phillips 66 Humber co-processing, blending demand",
    "BEL": "Ghent bioport, blending & storage",
    "DEU": "FAME industry & blending demand",
}

WATCHLIST_ASIA = ("IDN", "MYS", "CHN", "THA", "SGP", "JPN", "KOR", "IND")
WATCHLIST_SOUTH_AMERICA = ("ARG", "BRA", "URY", "PRY", "COL", "PER")

WATCHLISTS = {
    "asia": {"name": "Asia", "countries": WATCHLIST_ASIA},
    "sam": {"name": "South America", "countries": WATCHLIST_SOUTH_AMERICA},
}

# Standard ISO 3166-1 alpha-2 for every country in COUNTRIES (except WLD) —
# needed for Eurostat/Comext, which addresses ALL countries (reporters and
# partners alike) by ISO2, not just EU members. Eurostat uses two documented
# exceptions to the standard: Greece is "EL" (not "GR") and the United
# Kingdom is "UK" (not "GB") — both applied via ISO2_OVERRIDES below.
# UNVERIFIED against a live Comext call in this environment (outbound access
# is sandboxed) — confirm before trusting P1 output; see
# app/pipelines/eurostat_comext.py.
ISO3_TO_ISO2: dict[str, str] = {
    "CHN": "CN", "IDN": "ID", "MYS": "MY", "THA": "TH", "SGP": "SG", "JPN": "JP",
    "KOR": "KR", "IND": "IN", "VNM": "VN", "PHL": "PH", "PAK": "PK", "TWN": "TW",
    "HKG": "HK", "PNG": "PG", "ARE": "AE", "SAU": "SA", "TUR": "TR",
    "ARG": "AR", "BRA": "BR", "URY": "UY", "PRY": "PY", "COL": "CO", "PER": "PE",
    "CHL": "CL", "BOL": "BO", "ECU": "EC",
    "USA": "US", "CAN": "CA", "MEX": "MX", "GTM": "GT", "HND": "HN",
    "NLD": "NL", "DEU": "DE", "BEL": "BE", "FRA": "FR", "ESP": "ES", "ITA": "IT",
    "GBR": "GB", "IRL": "IE", "PRT": "PT", "SWE": "SE", "FIN": "FI", "DNK": "DK",
    "NOR": "NO", "POL": "PL", "AUT": "AT", "CZE": "CZ", "HUN": "HU", "ROU": "RO",
    "BGR": "BG", "GRC": "GR", "LTU": "LT", "LVA": "LV", "EST": "EE", "CHE": "CH",
    "UKR": "UA", "RUS": "RU",
    "AUS": "AU", "NZL": "NZ", "ZAF": "ZA", "EGY": "EG", "MAR": "MA", "NGA": "NG",
    "KEN": "KE",
}
ISO2_OVERRIDES = {"GRC": "EL", "GBR": "UK"}  # Eurostat-specific exceptions

# EU-27 members this app currently tracks (extend as more are added to
# COUNTRIES). Used to decide when Comext can answer a query directly
# (reporter is EU) vs. via mirror (partner is EU) — see eurostat_comext.py.
EU_MEMBERS = frozenset({
    "NLD", "DEU", "BEL", "FRA", "ESP", "ITA", "IRL", "PRT", "SWE", "FIN",
    "DNK", "POL", "AUT", "CZE", "HUN", "ROU", "BGR", "GRC", "LTU", "LVA", "EST",
})


def to_eurostat(iso3: str) -> str:
    """ISO3 -> the code Comext uses for this country (any country, not just
    EU members — Comext addresses non-EU partners by ISO2 too)."""
    return ISO2_OVERRIDES.get(iso3, ISO3_TO_ISO2.get(iso3, iso3))


ISO3_TO_EUROSTAT: dict[str, str] = {iso3: to_eurostat(iso3) for iso3 in EU_MEMBERS}
