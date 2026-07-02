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

**Tonnage by default.** Rankings, Partners, and Watchlist rank and display
by physical volume (tonnes), not USD value — a country's dollar value moves
with price as much as with quantity, so comparing tonnage is the more direct
read of actual trade flow. A Value ($) toggle is available everywhere the
Volume (t) one is; switching genuinely re-ranks the list (e.g. China leads
UCO exports by value but not by volume — see `app/api/helpers.py::rank_rows`)
rather than just relabeling the same order. Countries with no reported
weight for a given flow/year are omitted from the tonnage ranking, with a
count shown, rather than silently plotted as zero.

## Architecture

```
app/
  pipelines/     data sources: comtrade.py (live, global HS6), eurostat_comext.py
                 (live, EU CN8 + non-EU mirror), us_census.py (live, HTS10 +
                 China mirror), brazil_comexstat.py (live, NCM8, feeds
                 origin-check), national_csv.py + indonesia_bps.py +
                 malaysia_dosm.py + china_gacc.py (local-file ingestion, see
                 P2/P3 below), sample.py (offline fallback). One shared
                 protocol (base.py) so new national sources slot in without
                 touching the API layer.
  registry/      commodities.py (HS codes + caveats), countries.py (ISO3/M49,
                 EU/Eurostat codes, watchlists, RD/SAF hubs), national_codes.py
                 (8-10 digit tariff-line targets for the national pipelines).
  signals/       unit_value.py, corridors.py, candidates.py (origin priors +
                 bands), mirror.py, origination.py, national_override.py
                 (CN8/HTS10 line -> candidate map), origin_confirmation.py
                 (national CSV vs global-mirror cross-check), china_mirror.py
                 (demand-side triangulation), engine.py (composite scorer +
                 national-line short-circuit).
  api/           FastAPI routers: meta, trade (rankings/trend/partners/
                 watchlist), signals (incl. origin-check, china-mirror).
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
| P1 (implemented, unverified live) | Eurostat Comext (CN8) | EU mirror data — splits POME/soapstock, PFAD/acid oil, UCO/modified oils directly at CN8, and picks up non-EU exporters' flows via the EU side even though they aren't reporters themselves |
| P2 (implemented, local-file) | Indonesia BPS + Malaysia DOSM (AHTN8) | origin-side confirmation for the palm-belt feedstocks — see `GET /api/origin-check` |
| P3 (implemented) | China — mirror triangulation + GACC local-file slot | the #1 UCO exporter, covered from the demand side — see `GET /api/china-mirror` and the China tab |
| quick win (implemented, unverified live) | Brazil Comex Stat (NCM8) | fully open API, no key — feeds `GET /api/origin-check?reporter=BRA` live |
| quick win (implemented, unverified live) | US Census (HTS10) | HTS10 detail incl. the UCO import line; also the biggest China mirror |
| deferred | Paid shipment/vessel data (ImportGenius vs Kpler-class) | revisit once specific corridors need company-level or vessel-level confirmation |

Each national pipeline implements the same `TradeDataPipeline` protocol and
overrides heuristic signals with `confidence="high"/"medium", basis="national_tariff_line"`
where it has data — see `app/registry/national_codes.py` for the indicative
tariff lines already documented for the next few phases.

### P1 in detail: Eurostat Comext

`app/pipelines/eurostat_comext.py` queries Comext (dataset `DS-045409`) at
CN8 detail and does two things Comtrade can't:

1. **Splits shared HS6 headings directly** — CN8 has separate lines for POME
   vs soapstock (1522), PFAD vs acid oils (3823.19), UCO vs modified oils
   (1518). `app/signals/national_override.py` maps known CN8 lines to a
   feedstock candidate; when a corridor's data includes these lines, the
   signals engine (`_national_line_split` in `app/signals/engine.py`)
   returns a **measured** split instead of a heuristic guess.
2. **Mirrors non-EU exporters** — Indonesia and Malaysia don't report to
   Eurostat, but their exports *to* an EU country show up in that EU
   country's own import declarations. The pipeline detects this case
   (`covers()` matches on the *partner* being an EU member, not just the
   reporter) and transparently flips reporter/partner and flow direction to
   fetch the EU side, then flips the labels back — callers never need to
   know which side of the corridor the data actually came from.

**This has not been exercised against the live Comext endpoint** — this
sandbox's outbound network only reaches pypi/npm/github, so the dataset id,
dimension names, flow codes (`FLOW_CODE`), and world-partner code
(`PARTNER_WORLD`) are built from documented Comext conventions but are
unverified. `parse_jsonstat()` is a generic JSON-stat 2.0 decoder, so a live
field-name mismatch should only need a constant tweak, not a rewrite. Also
note: Comext reports values in EUR; they're converted to USD with a fixed
indicative rate (`EUR_TO_USD` in the same file) as a stopgap — a per-year FX
rate would be the correct fix. **Before trusting P1 output, run one live
call and check both.**

### P2 in detail: Indonesia BPS + Malaysia DOSM (local-file ingestion, not a live API)

Unlike Comtrade and Eurostat — both long-standing services with documented,
stable APIs — neither Indonesia's BPS nor Malaysia's DOSM has a publicly
documented API for bilateral HS-code trade at the confidence level needed to
write against it sight-unseen. Rather than guess endpoint details for two
more national offices, P2 reads from a **local CSV file** you provide:

```bash
export INDONESIA_BPS_CSV=/path/to/indonesia.csv   # default: data/local/indonesia_bps.csv
export MALAYSIA_DOSM_CSV=/path/to/malaysia.csv    # default: data/local/malaysia_dosm.csv
```

Download the relevant export/import-by-HS-code table — Indonesia BPS at
<https://www.bps.go.id/exim/>, Malaysia via OpenDOSM's trade catalogue at
<https://open.dosm.gov.my/data-catalogue> — and normalize it into:

```
hs_code,partner,flow,year,value_usd,net_wgt_kg
15220090,Netherlands,X,2024,180000000,290000000
```

(`partner` accepts ISO2/ISO3 or the common English name; `net_wgt_kg` is
optional. Full schema and column rules in `app/pipelines/national_csv.py`.)

This deliberately does **not** replace Comtrade in rankings/partners/trend:
the catalogued AHTN8 lines for Indonesia/Malaysia are single "other/residual"
lines, and whether they fully partition the HS6 heading is unverified — using
them as a drop-in total could silently understate a country's trade. Instead,
`GET /api/origin-check?cmd=pome&reporter=IDN&year=2024` compares the
country's own declared value against the global HS6 total and reports the
gap plainly (e.g. "covers only 43% of the global total — likely other AHTN8
sub-lines aren't catalogued yet") rather than picking a side. With no file
present it returns `available: false`, not an error — that's the expected
state until you provide data.

### P3 in detail: China (mirror triangulation)

China is the #1 UCO exporter and there is **no free automated route to its
own customs data**: GACC's query portal (stats.customs.gov.cn) requires
mainland-China real-name registration and blocks overseas fetches (verified
403 during this build), and China's direct reporting to UN Comtrade has been
sparse in recent years. So P3 works from the demand side:

- `app/signals/china_mirror.py` + `GET /api/china-mirror?cmd=uco&year=2024`
  (and the **China** tab in the UI) sum what a 20-country mirror panel —
  the RD/SAF hubs plus the big Asian buyers — reports importing *from*
  China, show the per-country breakdown, and compare it against China's own
  declared exports where available. The result always carries its caveats:
  mirror imports are CIF (~5–10% above FOB) and destinations outside the
  panel are invisible, so the own-vs-mirror ratio is a coverage indicator,
  not a fraud verdict by itself.
- `app/pipelines/us_census.py` sharpens the biggest single mirror: US
  imports at HTS10 detail (the 1518.00.4000 UCO line), with the same
  reporter/partner flip logic as the Eurostat pipeline so `China → USA`
  queries route through it automatically. Same caveat as Eurostat: written
  from documented API conventions, **not yet exercised against the live
  endpoint** (this sandbox can't reach api.census.gov). Optional free
  `CENSUS_API_KEY` raises rate limits.
- `app/pipelines/china_gacc.py` is a ready ingestion slot: the moment
  Chinese data is obtained by any route below, drop it in as a CSV
  (schema in `national_csv.py`, env `CHINA_GACC_CSV`) and
  `/api/origin-check?reporter=CHN` starts cross-checking it.

**Getting Chinese data directly — options priced, deliberately not built
until one is chosen:**

| Route | Price (sourced) | Notes |
|---|---|---|
| Manual export from stats.customs.gov.cn via a mainland contact | free + labor | Registration needs a mainland phone. Feeds `china_gacc.py` as-is. |
| HKTDC China Customs Statistics | **free** | Hong Kong trade-promotion council, not a vendor. Likely aggregate totals only — too coarse for HS 1518 detail; a spot-check, not a pipeline source. |
| ExportGenius | from **$278/mo** (Starter, 2 users; Essential/Expert tiers cost more, annual billing discounted) | [pricing](https://www.exportgenius.com/pricing) |
| ImportGenius | **$125–899/user/mo** (Essentials $125 annual / $199 month-to-month, Business $399, Enterprise $899); extra countries beyond its US core **+$99–399/mo each** | [pricing](https://www.importgenius.com/pricing). Core strength is US import BoL data — confirm China coverage specifically before buying. |
| Tendata / Volza | Tendata: no public pricing (sales quote, credit-based). Volza: online access **from $1,500** (pay-per-point model, unclear if monthly/annual) | [Volza pricing](https://www.volza.com/pricing/) |
| Panjiva (S&P Global) | No public pricing — enterprise sales quote | Typically priced for large-corporate budgets. |
| Kpler/MarineTraffic-class vessel tracking | **tens of thousands to low-hundreds of thousands $/year**, modular by commodity | [Kpler enterprise](https://www.kpler.com/product/maritime/enterprise-plan). Best for bulk-liquid UCO/UCOME cargo flows near-real-time; also the priciest. |

**Before paying any of these — a finding that changes the calculus:** China
does not publish granular export declarations to third parties at all.
Every commercial "China export data" provider reconstructs it from partner
countries' import statistics (mirror data — the same technique
`china_mirror.py` already does for free), shipping-manifest scraping, or
older archived/resold sources. Industry reporting describes coverage as
solid through ~2017, patchier from 2018, and **materially degraded for the
most recent 12–24 months** since China's 2021 Personal Information
Protection Law and Data Security Law took effect. **Before subscribing to
any paid option, ask the vendor directly: is this sourced from China's own
customs declarations, or reconstructed from partner-country mirrors? If
it's mirror-based, verify it isn't just a worse (or same) version of what
`/api/china-mirror` already gives for free**, and check current-year
coverage specifically rather than assuming historical depth carries forward.

The mirror triangulation stays valuable regardless — it's the independent
cross-check any purchased Chinese dataset should be validated against.

### Quick win in detail: Brazil Comex Stat

Unlike Indonesia/Malaysia, Brazil's Comex Stat (comexstat.mdic.gov.br) is a
genuinely open, documented public API — no key, no registration. Brazil is
always the implicit reporter (there's no country selector; it's Brazil's own
declarations), so `app/pipelines/brazil_comexstat.py` is a live pipeline,
not a file drop like `national_csv.py`.

Same scope caution as Indonesia/Malaysia, though: the catalogued NCM8 lines
(tallow, soy) aren't confirmed to fully partition their HS6 heading, so this
isn't wired into rankings/partners as a Comtrade replacement — it feeds
`GET /api/origin-check?cmd=tallow&reporter=BRA&year=2024` live instead,
sharing the same `available()` / `load(slug, year)` interface as the CSV
sources (`available()` returns `false` whenever `DATA_MODE=sample`, matching
this sandbox). Country resolution is by Portuguese name match
(`PT_COUNTRY_NAMES`), not numeric SISCOMEX codes — the same "skip and warn
rather than silently miscode" rule as the CSV loader. **Unverified against
the live endpoint**, same flag as Eurostat/Census.

## Testing

```bash
pip install -r requirements-dev.txt
pytest                                    # 110 tests: determinism, signals math,
                                           # Comtrade/Eurostat/Census/Comex Stat
                                           # request building, national CSV
                                           # ingestion, origin confirmation,
                                           # China mirror triangulation,
                                           # tonnage/value metric ranking,
                                           # full API smoke (sample mode)
python scripts/screenshot.py              # Playwright screenshots of every
                                           # route + dark mode (needs the
                                           # server running separately)
```

## Known limitations / next review items

- Unit-value bands and origin priors (`app/signals/candidates.py`) are
  indicative 2022–2024 estimates — a domain-expert review pass before
  trusting the Signals view in decisions would materially improve it.
- **Eurostat Comext (P1) and US Census (P3) are unverified against their
  live endpoints** — see the per-phase sections above. Run one real call
  against each before trusting their output.
- The China mirror panel covers 20 destinations; flows to unlisted countries
  are invisible to `/api/china-mirror`, and mirror imports are CIF vs FOB.
- **Brazil Comex Stat is unverified against its live endpoint**, and its
  country resolution is by Portuguese name match, not numeric code — see
  "Quick win in detail" above. Not wired into rankings/partners for the same
  incomplete-catalogue reason as Indonesia/Malaysia.
- HKTDC's China Customs Statistics appears to be a free resource (no
  pricing/subscription found), but likely too coarse (aggregate totals, not
  bilateral HS8) to feed this app — see the P3 access-options table.
- CN8-to-candidate mappings (`app/signals/national_override.py`) are also a
  judgment call, same caveat as the unit-value bands.
- Comext values are converted from EUR to USD at a fixed indicative rate, not
  a per-year FX rate.
- **Indonesia BPS / Malaysia DOSM (P2) are local-file ingestion, not live
  APIs** — see "P2 in detail" above. `/api/origin-check` returns
  `available: false` until you supply a CSV; that's expected, not a bug.
- The catalogued AHTN8 lines for Indonesia/Malaysia are single "other"
  lines of unverified completeness — a large gap in `/api/origin-check`
  likely means an uncatalogued sub-line exists, not bad data.
- Annual frequency only; monthly data (Comtrade `C/M/HS`, Comex Stat monthly)
  is a natural Phase-4 addition.
- No auth/rate-limiting — assumes local/trusted deployment.
