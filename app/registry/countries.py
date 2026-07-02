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


def name_of(iso3: str) -> str:
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
