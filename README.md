# Renewable Trade Monitor

A Trade-Data-Monitor-style dashboard for **renewable feedstocks and biofuels**
(UCO, tallow, POME, PFAD, tall oil, TOFA, technical corn oil, crop oils,
biodiesel, ethanol), built on free public trade data instead of a paid feed.

It exists to answer three questions a commercial terminal charges for:
who exports/imports how much of a given feedstock, who are the biggest
counterparties for a given country, and — the hard part — **which of several
cohabiting feedstocks is actually inside a shared HS code** for a given
corridor.

## Quick start

```bash
pip install -r requirements.txt
python -m app            # http://127.0.0.1:8000
```

No API key, no network access required — the app auto-falls back to a
bundled **synthetic sample dataset** (clearly labeled in the UI) if live
sources are unreachable. To pull real UN Comtrade data, set:

```bash
cp .env.example .env     # then edit
export DATA_MODE=live               # or "auto" (default) to fall back gracefully
export COMTRADE_API_KEY=...         # optional — raises rate limits; free at
                                     # https://comtradedeveloper.un.org
```

## What it covers

**Feedstocks** (waste/residue): used cooking oil (HS 1518), tallow (1502),
POME & fatty residues (1522), PFAD/soapstock acid oils (3823.19), tall oil
(3803), TOFA (3823.13), technical/distillers corn oil (1515.21/.29).
**Crop oils**: palm, soy, rapeseed, sunflower. **Fuels**: FAME biodiesel
(3826), ethanol split by undenatured/denatured (2207.10/.20).

**HVO and SAF have no dedicated HS6 code** — as pure hydrocarbons they clear
customs mixed into HS 2710 with fossil diesel/jet fuel. This is documented
(not faked) on the Methodology page; HS 3826 is used as the nearest proxy.

**The differentiator — feedstock disaggregation.** Several of the above share
an HS heading with a lookalike product (POME/soapstock in 1522, PFAD/acid oil
in 3823.19, technical/food corn oil in 1515.29, UCO/modified oils in 1518,
inedible/edible tallow in 1502). The Signals view splits these using a
transparent, always-labeled-heuristic composite score:

| Signal | Weight | Idea |
|---|---|---|
| Unit-value band | 45% | $/tonne vs an indicative price band per candidate |
| Origin prior | 25% | e.g. PFAD skews Indonesia/Malaysia, soy acid oil skews Argentina |
| Destination hub share | 20% | fuel-bound candidates cluster into RD/SAF refinery hubs (Rotterdam, Singapore, etc.) |
| Mirror consistency | 10% | exporter-vs-importer reporting agreement |

Every result ships with plain-language explanations and a confidence level —
this is estimation, not measurement, until a national tariff line confirms it.

**Priority coverage**: Asia (Indonesia, Malaysia, China, Thailand, Singapore,
Japan, Korea, India) and South America (Argentina, Brazil, Uruguay, Paraguay,
Colombia, Peru) watchlists, since those are the feedstock-export regions that
matter most for this use case.

## Architecture

```
app/
  pipelines/     data sources: comtrade.py (live, global HS6), sample.py
                 (offline fallback). One shared protocol (base.py) so new
                 national sources slot in without touching the API layer.
  registry/      commodities.py (HS codes + caveats), countries.py (ISO3/M49,
                 watchlists, RD/SAF hubs), national_codes.py (8-10 digit
                 tariff-line targets for future national pipelines).
  signals/       unit_value.py, corridors.py, origins.py (candidates.py),
                 mirror.py, origination.py, engine.py (composite scorer).
  api/           FastAPI routers: meta, trade (rankings/trend/partners/
                 watchlist), signals.
static/          vanilla JS + hand-rolled SVG charts, hash-router, dark mode.
data/sample/     committed, deterministic synthetic dataset (see below).
```

**Why a sample dataset is committed**: the app needs to run and demo without
network access. `scripts/generate_sample_data.py` is a seeded, deterministic
generator (no RNG state, no wall clock) with hand-curated realistic 2024
magnitudes and corridor unit-values engineered so the disaggregation signals
produce meaningful output offline. It is never presented as real data — the
UI shows a persistent banner whenever it's active, and every value carries
`estimated=True` in the underlying store.

**Comtrade request budgeting**: the free API caps responses at ~500 records.
`app/pipelines/comtrade.py::build_requests()` splits any query (by year, then
by code) so every live call stays under budget — e.g. a 7-year world trend
becomes 7 per-year calls rather than one call that silently truncates.

## Pipeline roadmap (progressive, one source at a time)

| Phase | Source | Adds |
|---|---|---|
| P0 (live) | UN Comtrade | global HS6 baseline, all countries |
| P1 | Eurostat Comext (CN8) | EU mirror data — the single biggest signal upgrade, splits POME/PFAD explicitly |
| P2 | Indonesia BPS + Malaysia DOSM (AHTN8) | origin-side confirmation for the palm-belt feedstocks |
| P3 | China (GACC releases + mirrors) | the #1 UCO exporter has no open customs API — mirror-only initially |
| quick win | Brazil Comex Stat (NCM8) | fully open API, no key |
| quick win | US Census (HTS10) | free key |
| deferred | Paid shipment/vessel data (ImportGenius vs Kpler-class) | revisit once specific corridors need company-level or vessel-level confirmation |

Each national pipeline implements the same `TradeDataPipeline` protocol and
overrides heuristic signals with `confidence="high", basis="national_tariff_line"`
where it has data — see `app/registry/national_codes.py` for the indicative
tariff lines already documented for the next few phases.

## Testing

```bash
pip install -r requirements-dev.txt
pytest                                    # 42 tests: determinism, signals
                                           # math, Comtrade budget splitting,
                                           # full API smoke (sample mode)
python scripts/screenshot.py              # Playwright screenshots of every
                                           # route + dark mode (needs the
                                           # server running separately)
```

## Known limitations / next review items

- Unit-value bands and origin priors (`app/signals/candidates.py`) are
  indicative 2022–2024 estimates — a domain-expert review pass before
  trusting the Signals view in decisions would materially improve it.
- Annual frequency only; monthly data (Comtrade `C/M/HS`, Comex Stat monthly)
  is a natural Phase-4 addition.
- No auth/rate-limiting — assumes local/trusted deployment.
