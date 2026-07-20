# Ghana Food Price Tracker — Merged Trader & Consumer Platform

A real-data food price transparency tool for Ghana, covering all 10 regions
and 26 commodities present in the WFP price dataset — built on the same
proven data-cleaning pipeline as the food-security capstone project.

## Two views, one platform

- **Trader · Wholesale** — what a bulk buyer pays a supplier. A mix of
  directly-observed and WFP-modeled prices; units are mixed in the raw
  data (bags, KG) and normalized here.
- **Consumer · Retail** — closer to what an individual pays at a market
  stall. Every Retail row in this dataset is WFP's own modeled estimate,
  not a directly observed price — labeled "estimated" everywhere it
  appears, never presented the same way as an observed number.

A real finding from merging the two: Retail happens to be quoted in plain
KG for every single row, with none of Wholesale's mixed-unit problem — so
the Consumer view actually covers a couple of commodities (Yam, Plantains)
that the Trader view excludes for lacking a consistent weight unit. The
`/api/v1/coverage-diff` endpoint surfaces exactly which commodities differ
between the two views, rather than hiding the mismatch.

## What this is (and isn't)

- **Every price traces to a real WFP-reported number.** No fabricated
  conversion factors — an earlier draft of this idea used invented
  olonka/margarine-tin-to-kg ratios with no source. Gone.
- **No "fair price" or "exploitation" claims.** Framing is neutral:
  "11.8% above the 10-region average," not an accusation against a vendor.
- **A visible confidence label on every price** — "directly observed,"
  "estimated," or "mixed" — so the person using it can judge how much
  weight to put on a given number.
- **10 regions, not 16.** Ghana has had 16 official regions since 2019, but
  the WFP source data still reports under the older 10-region boundaries.
  This tool shows exactly those 10 rather than fabricating figures for the
  six newer regions.

## What this still doesn't solve

Merging Wholesale and Retail closes the biggest gap for a consumer, but
these remain open and would need more than a code change:
- **Internet-dependent, English-only** — no offline mode, no local-language
  support, no USSD/SMS fallback. That would need a telco or NGO partner,
  not just more frontend work.
- **Monthly, not real-time** — WFP updates this data periodically, not daily.
- **44 surveyed markets, not every market** — coverage is WFP's survey
  footprint, not exhaustive.

## Running locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Open http://localhost:8000 — the app builds its in-memory database from
`data/wfp_food_prices_gha.csv` on first request.

## Running with Docker

```bash
docker build -t ghana-food-tracker .
docker run -p 8080:8080 ghana-food-tracker
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/regions?pricetype=` | Regions available for that view |
| `GET /api/v1/commodities?pricetype=&region=` | Commodities available for that view |
| `GET /api/v1/summary?region=&commodity=&pricetype=` | Latest price, MoM change, vs. national average, confidence label |
| `GET /api/v1/trend?region=&commodity=&pricetype=` | Full monthly price history + rolling average |
| `GET /api/v1/compare?commodity=&pricetype=` | Same commodity's latest price across every region |
| `GET /api/v1/volatility?limit=&pricetype=` | Most volatile region × commodity pairs |
| `GET /api/v1/coverage-diff` | Which commodities differ between the two views |

`pricetype` accepts `Wholesale` (default) or `Retail` on every endpoint that takes it.

## Two real bugs found and fixed during testing

1. **Thread-safety crash**: the frontend fires 4 API calls in parallel;
   sharing one DuckDB connection across FastAPI's worker threads produced a
   real, reproducible `500` error the moment two requests overlapped. Fixed
   with per-request cursors, then verified by re-running the exact
   interaction that broke it.
2. **Stale selection on view switch**: if the selected commodity doesn't
   exist in the other pricetype's view (e.g. "Cowpeas (white)" is
   Wholesale-only), switching views could have left a broken selection.
   Verified this falls back gracefully to a commodity that exists in both.

## Data source & caveats

World Food Programme price reports for Ghana (via HDX), 2006–2023, 39,038
rows. Weight-quoted commodities only; count-quoted items with no valid
weight conversion in a given view are excluded from that view's
price-per-KG comparisons.

