"""Registry/metadata endpoints — no upstream calls."""

from fastapi import APIRouter

from .. import config
from ..registry.commodities import COMMODITIES, GROUPS, HVO_SAF_NOTE
from ..registry.countries import COUNTRIES, EU_BLOC_ISO, EU_MEMBERS, RD_SAF_HUBS, WATCHLISTS, name_of
from ..registry.national_codes import NATIONAL_LINES
from ..signals.candidates import CANDIDATES
from ..signals.unit_value import BAND_VINTAGE
from ..services import get_registry, get_store, sample_disclaimer
from .helpers import envelope

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    registry = get_registry()
    return {
        "status": "ok",
        "data_mode": registry.data_mode,
        "flows_stored": get_store().count_flows(),
    }


@router.get("/meta")
def meta():
    commodities = [
        {
            "slug": c.slug,
            "name": c.name,
            "group": c.group,
            "codes": list(c.codes),
            "hs_label": c.hs_label,
            "shared_heading": c.shared_heading,
            "cohabitants": list(c.cohabitants),
            "caveat": c.caveat,
        }
        for c in COMMODITIES
    ]
    return envelope(
        {
            "commodities": commodities,
            "groups": GROUPS,
            "years": config.YEARS,
            "countries": {iso: name for iso, (_, name) in COUNTRIES.items()},
            "blocs": {
                EU_BLOC_ISO: {
                    "name": name_of(EU_BLOC_ISO),
                    "members": sorted(EU_MEMBERS),
                    "note": "Consolidated extra-EU trade only — intra-EU legs "
                            "excluded to avoid double-counting re-exports "
                            "(the Rotterdam effect). The UK left the customs "
                            "union in 2021 and is tracked as its own country, "
                            "not part of this bloc.",
                },
            },
            "hubs": RD_SAF_HUBS,
            "watchlists": {
                key: {"name": w["name"], "countries": list(w["countries"])}
                for key, w in WATCHLISTS.items()
            },
            "hvo_saf_note": HVO_SAF_NOTE,
            "sample_disclaimer": sample_disclaimer(),
        },
        "registry",
    )


@router.get("/methodology")
def methodology():
    shared = []
    for slug, cands in CANDIDATES.items():
        shared.append(
            {
                "slug": slug,
                "candidates": [
                    {
                        "key": c.key,
                        "label": c.label,
                        "fuel_bound": c.fuel_bound,
                        "band_usd_per_t": [c.band_lo, c.band_hi],
                        "band_note": c.band_note,
                        "top_origins": sorted(
                            c.origin_priors.items(), key=lambda kv: -kv[1]
                        )[:5],
                    }
                    for c in cands
                ],
            }
        )
    national = [
        {
            "jurisdiction": jur,
            "commodity": slug,
            "lines": [
                {"code": line.code, "system": line.system, "label": line.label}
                for line in lines
            ],
        }
        for (jur, slug), lines in sorted(NATIONAL_LINES.items())
    ]
    roadmap = [
        {"phase": "P0", "pipeline": "UN Comtrade global (HS6)", "status": "live"},
        {
            "phase": "P1",
            "pipeline": "EU mirror — Eurostat Comext (CN8)",
            "status": "implemented, unverified against live endpoint",
        },
        {
            "phase": "P2",
            "pipeline": "Indonesia BPS + Malaysia DOSM (AHTN8)",
            "status": "implemented as local-file ingestion, not a live API — "
                     "see GET /api/origin-check",
        },
        {
            "phase": "P3",
            "pipeline": "China — mirror triangulation (see GET /api/china-mirror) "
                       "+ GACC local-file slot",
            "status": "implemented; GACC portal itself is not freely automatable "
                     "(mainland real-name registration, overseas fetch blocked)",
        },
        {
            "phase": "quick win",
            "pipeline": "Brazil Comex Stat (NCM8)",
            "status": "implemented (live, no key needed), unverified against "
                     "live endpoint — see GET /api/origin-check?reporter=BRA",
        },
        {
            "phase": "quick win",
            "pipeline": "US Census (HTS10)",
            "status": "implemented, unverified against live endpoint",
        },
        {"phase": "deferred", "pipeline": "Paid shipment/vessel data (ImportGenius vs Kpler-class)", "status": "deferred"},
    ]
    return envelope(
        {
            "hvo_saf_note": HVO_SAF_NOTE,
            "band_vintage": BAND_VINTAGE,
            "signal_weights": {
                "unit_value": 0.45, "origin": 0.25, "destination": 0.20, "mirror": 0.10,
            },
            "eu_bloc": {
                "problem": (
                    "If Indonesia ships POME to the Netherlands, and the Netherlands "
                    "re-ships part of it to Germany, that's one physical shipment. "
                    "Naively summing every country's own \"exports to world\" figure "
                    "counts it twice, because an EU member's own reported total "
                    "legitimately includes its intra-EU trade — the 'Rotterdam effect'."
                ),
                "fix": (
                    "Every world/bloc total in this app (World trend, Rankings' world "
                    "total and per-row shares) excludes intra-EU27 legs. See "
                    "app/signals/eu_bloc.py."
                ),
                "uk_note": (
                    "EU_MEMBERS is EU27, not EU28 — the UK left the customs union in "
                    "2021, so UK<->EU flows count in full as real international trade, "
                    "never netted out as internal. Slightly imprecise for 2018-2020 "
                    "data (the UK genuinely was in the bloc then)."
                ),
                "features": (
                    "Rankings: 'Show EU27 as one bloc' collapses the 21 tracked member "
                    "states into one consolidated row. Partners: reporter=EU27 shows "
                    "which non-EU countries the bloc trades with. The two EU27 figures "
                    "can differ slightly (different calculation methods) the same way "
                    "real customs statistics carry an unattributed-partner residual."
                ),
            },
            "shared_headings": shared,
            "national_lines": national,
            "pipeline_roadmap": roadmap,
            "sources": [
                {
                    "name": "UN Comtrade",
                    "url": "https://comtradeplus.un.org",
                    "notes": "Annual HS6 goods trade; free preview API (~500 records/call) "
                             "or free registered key with higher limits.",
                },
                {
                    "name": "Eurostat Comext",
                    "url": "https://ec.europa.eu/eurostat/web/international-trade-in-goods/database",
                    "notes": "EU trade at CN8 detail (dataset DS-045409). Splits several "
                             "shared HS6 headings directly and mirrors non-EU exporters' "
                             "flows into the EU. Values converted from EUR at a fixed "
                             "indicative rate — see app/pipelines/eurostat_comext.py. "
                             "Not yet exercised against the live endpoint in this build.",
                },
                {
                    "name": "US Census international trade",
                    "url": "https://www.census.gov/foreign-trade/data/index.html",
                    "notes": "US imports/exports at HTS10 detail (free API; optional key "
                             "raises limits). Mirrors China->USA corridors incl. the UCO "
                             "line 1518.00.4000. Not yet exercised against the live "
                             "endpoint in this build.",
                },
                {
                    "name": "China GACC (indirect only)",
                    "url": "http://stats.customs.gov.cn/",
                    "notes": "Official query portal requires mainland real-name "
                             "registration; overseas automated access is blocked. China "
                             "is covered via mirror triangulation (/api/china-mirror) "
                             "and a local-file slot for manually/commercially obtained "
                             "data (/api/origin-check?reporter=CHN).",
                },
                {
                    "name": "Brazil Comex Stat",
                    "url": "https://comexstat.mdic.gov.br",
                    "notes": "Brazil's own trade statistics at NCM8 detail; genuinely "
                             "open API, no key or registration. Feeds "
                             "/api/origin-check?reporter=BRA live rather than via a "
                             "manual file. Not yet exercised against the live endpoint "
                             "in this build.",
                },
            ],
        },
        "registry",
    )
