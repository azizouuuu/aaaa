# Handover — Renewable Trade Monitor

This is a context handover for continuing the project in a fresh (local) Claude
Code session that has no memory of the original build conversation. Read this
first, then `README.md` for full technical detail. Everything below reflects
the state at commit `0a503f3`.

## What this is (one paragraph)

A "Trade Data Monitor"-style dashboard for **renewable feedstocks and biofuels**
(UCO, tallow, POME, PFAD, tall oil, TOFA, technical corn oil, crop oils,
biodiesel, ethanol), built on **free public trade data** instead of a paid feed.
Python FastAPI backend + vanilla-JS/SVG dashboard (no build step), SQLite cache.
Its distinctive feature is a **feedstock-disaggregation signals engine**: several
of these products share an HS6 code with a lookalike (POME↔soapstock in 1522,
PFAD↔acid oil in 3823.19, etc.), and the app estimates the split using
unit-value bands, origin priors, destination-hub share, and mirror-data checks.

## How to run it

```bash
pip install -r requirements.txt
python -m app                 # http://127.0.0.1:8000  (sample data, offline)
DATA_MODE=live python -m app  # hits real APIs (see "unverified" caveat below)
pytest                        # 124 tests, all passing
```

`DATA_MODE` is `auto` (default, live→sample fallback), `live`, or `sample`.
The app runs fully offline against a committed synthetic dataset
(`data/sample/sample_trade.json`) with a persistent amber "sample data" banner.

## Architecture in 30 seconds

- `app/pipelines/` — one class per data source, all implementing the same tiny
  protocol (`base.py`). `comtrade.py` is the global HS6 baseline. Others are
  per-country/region, added progressively. `sample.py` is the offline fallback.
- `app/signals/` — the analytical layer: `engine.py` (disaggregation scorer),
  `candidates.py` (**the domain-expert-review table** — price bands + origin
  priors), `eu_bloc.py` (intra-EU double-count correction), `china_mirror.py`,
  `origin_confirmation.py`, `mirror.py`, `origination.py`.
- `app/api/` — FastAPI routers (`meta`, `trade`, `signals`).
- `app/registry/` — `commodities.py` (HS codes), `countries.py` (ISO/M49,
  EU membership, hubs), `national_codes.py` (8–10 digit tariff lines).
- `static/` — hash-routed dashboard, hand-rolled SVG charts, dark mode.

## What's built (all committed & pushed on `claude/trade-data-monitor-app-0uxnmt`)

- **P0 UN Comtrade** — global HS6, the baseline pipeline. Has a record-budget
  splitter (`build_requests`) to stay under the free API's ~500-record cap.
- **P1 Eurostat Comext (CN8)** — EU mirror; splits shared HS6 headings directly
  and picks up non-EU exporters' flows via the EU import side (flip logic).
- **P2 Indonesia BPS + Malaysia DOSM** — local-CSV ingestion (no verified public
  API), feeds `/api/origin-check`.
- **P3 China** — mirror triangulation (`/api/china-mirror`) + a local-file slot
  (GACC has no open API). **US Census (HTS10)** built alongside.
- **Brazil Comex Stat (NCM8)** — live open API, feeds `/api/origin-check?reporter=BRA`.
- **Tonnage-first metrics** — Rankings/Partners/Watchlist rank by volume (tonnes)
  by default, with a Value ($) toggle that genuinely re-ranks.
- **EU27 intra-bloc correction** — world/bloc totals exclude intra-EU
  double-counting (the "Rotterdam effect"); EU27 is also a selectable bloc
  entity in Rankings (toggle) and Partners (reporter=EU27). UK correctly
  excluded (EU27, not EU28).

## ⚠️ The most important open items

1. **Four pipelines are UNVERIFIED against their live endpoints.** This is the
   #1 thing to do locally, because the original build ran in a sandbox with no
   outbound internet — the request/response shapes are built from documented
   conventions but were never exercised against a real response:
   - `comtrade.py`, `eurostat_comext.py`, `us_census.py`, `brazil_comexstat.py`
   - **Action:** run `DATA_MODE=live python -m app`, hit each source's endpoint
     once, and fix any field-name drift. Parsing is written defensively
     (generic JSON-stat for Eurostat, tolerant key-lookups for Brazil) so a
     mismatch should be a constant tweak, not a rewrite. Each file has a
     "CAVEAT — UNVERIFIED" docstring pointing at exactly what to check.

2. **Domain-expert review of `app/signals/candidates.py`.** The unit-value bands
   ($/tonne per feedstock) and origin priors are best-effort estimates, not
   verified against recent trade prints. Every Signals-view number depends on
   them. Same caveat for the CN8/HTS10→candidate mappings in
   `national_override.py`. This is the highest-value *analytical* improvement.
   (The user is the domain expert here — ask them to sanity-check the numbers.)

3. **Chinese data access is an open decision, not a build task.** China
   publishes no granular export data to third parties; every commercial
   provider reconstructs it from mirrors (which `china_mirror.py` already does
   for free). Pricing for the paid options is documented in the README's
   Chinese-data table. HKTDC was researched → free but too coarse. Don't build
   a paid integration until the user picks one and confirms it beats the free
   mirror.

## Decisions already made (don't relitigate without reason)

- **Free-sources-first**, paid data deferred (ImportGenius/Kpler-class). The
  pipeline protocol keeps a slot open for it.
- **HVO/SAF have no HS6 code** — documented as a caveat/proxy (HS 3826), not
  faked into a fake series.
- **National pipelines with single "other/residual" tariff lines are NOT wired
  into rankings/partners** as Comtrade replacements — their completeness is
  unverified, so they feed the cross-check (`/api/origin-check`) instead of
  silently understating a country's totals.
- **Stack:** Python + vanilla JS, no build step, on purpose (keep it dependency-
  light and runnable anywhere).

## Testing & conventions

- `pytest` — 124 tests, offline, fast. New behavior gets a test; the suite is
  the safety net for the live-API work (it locks the parsing/split logic so you
  can see if a live fix breaks something).
- Charts follow a validated accessible palette + spec (see the dataviz
  conventions already applied in `static/js/charts.js`).
- `scripts/screenshot.py` — Playwright smoke-shots of every route (needs the
  server running); good for eyeballing a UI change.
- Sample data is deterministic (`scripts/generate_sample_data.py`, seeded) and
  a test asserts it stays byte-stable — regenerate + commit if you change it.

## Git state

- Branch: `claude/trade-data-monitor-app-0uxnmt` (all work is here; default
  branch may be empty).
- Latest commit: `0a503f3` (EU27 intra-bloc correction).
- Working tree clean, pushed to origin.
