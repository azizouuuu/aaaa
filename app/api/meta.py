"""Registry/metadata endpoints — no upstream calls."""

from fastapi import APIRouter

from .. import config
from ..registry.commodities import COMMODITIES, GROUPS, HVO_SAF_NOTE
from ..registry.countries import COUNTRIES, RD_SAF_HUBS, WATCHLISTS
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
        {"phase": "P3", "pipeline": "China — GACC releases + EU/US/SGP mirrors", "status": "planned"},
        {"phase": "quick win", "pipeline": "Brazil Comex Stat (NCM8)", "status": "planned"},
        {"phase": "quick win", "pipeline": "US Census (HTS10)", "status": "planned"},
        {"phase": "deferred", "pipeline": "Paid shipment/vessel data (ImportGenius vs Kpler-class)", "status": "deferred"},
    ]
    return envelope(
        {
            "hvo_saf_note": HVO_SAF_NOTE,
            "band_vintage": BAND_VINTAGE,
            "signal_weights": {
                "unit_value": 0.45, "origin": 0.25, "destination": 0.20, "mirror": 0.10,
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
            ],
        },
        "registry",
    )
