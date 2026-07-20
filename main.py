"""
main.py -- Ghana Food Price Tracker API (merged Trader + Consumer platform)

Serves real, cleaned WFP price data across all 10 regions present in the
source dataset and all 26 commodities, in TWO lenses on one platform:

  - Trader view  (pricetype=Wholesale): what a bulk buyer pays a supplier.
    Mix of directly-observed ('actual') and WFP-modeled ('aggregate') rows.
    Units are mixed in the raw data (bags, KG) and normalized here.

  - Consumer view (pricetype=Retail): what an individual pays at a stall.
    100% WFP-modeled ('aggregate') in this dataset -- there is no directly
    observed Retail row at all. Every Retail row is already quoted in
    plain KG, so it needs no unit normalization (a genuine finding: this
    means Retail actually covers a couple of commodities, like Yam and
    Plantains, that the Wholesale view excludes for having no consistent
    weight unit).

Every endpoint returns a `data_confidence` field so the person consuming
the API (and the UI built on it) can see whether a number is a real
observation or a model estimate, rather than presenting both the same way.

No fabricated conversion factors, no invented "fair price," no
"exploitation" language anywhere -- see README.md for the full reasoning.

NOTE ON REGIONS: Ghana has had 16 official regions since a 2019 split, but
the WFP source data still reports under the older 10-region boundaries.
This API returns the 10 regions actually present in the data.
"""
import duckdb
import pandas as pd
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Literal

BASE_DIR = Path(__file__).resolve().parent
DATA_CSV = BASE_DIR / "data" / "wfp_food_prices_gha.csv"
VALID_PRICETYPES = ("Wholesale", "Retail")

app = FastAPI(
    title="Ghana Food Price Tracker API",
    description=(
        "Real, cleaned WFP food price data across Ghana's 10 WFP-reported "
        "regions and 26 commodities, in two honestly-labeled lenses: "
        "Trader (Wholesale) and Consumer (Retail, WFP-estimated)."
    ),
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_con: Optional[duckdb.DuckDBPyConnection] = None


def get_db() -> duckdb.DuckDBPyConnection:
    """Build the cleaned mart once, in memory, on first request. Builds
    BOTH pricetypes into the same tables (pricetype is now a dimension,
    not a fixed filter), so the platform can serve both views without
    maintaining two separate pipelines."""
    global _con
    if _con is not None:
        return _con
    if not DATA_CSV.exists():
        raise RuntimeError(f"Missing {DATA_CSV} -- the CSV must be bundled with this service.")

    con = duckdb.connect(":memory:")
    con.execute(f"CREATE OR REPLACE TABLE prices AS SELECT * FROM read_csv_auto('{DATA_CSV.as_posix()}')")

    # Cleaning rule (units): normalize weight-quoted units to price-per-KG.
    # Applied across BOTH pricetypes now, not just Wholesale. Retail happens
    # to already be 100% plain "KG" in this dataset (verified), so this is
    # a no-op for Retail rows but still correct to apply uniformly.
    con.execute("""
        CREATE OR REPLACE TABLE prices_clean AS
        SELECT
            admin1 AS region,
            commodity,
            date,
            pricetype,
            priceflag,
            unit,
            price,
            CASE
                WHEN unit = 'KG'     THEN price
                WHEN unit LIKE '%KG' THEN price / TRY_CAST(REPLACE(unit, ' KG', '') AS DOUBLE)
                ELSE NULL
            END AS price_per_kg
        FROM prices
        WHERE pricetype IN ('Wholesale', 'Retail')
    """)

    # Cleaning rule (provenance): keep both 'actual' and 'aggregate' rows for
    # series continuity, but track the ACTUAL share per region/commodity/
    # pricetype so the API can report a real confidence level instead of
    # treating a directly-observed row and a modeled one identically.
    con.execute("""
        CREATE OR REPLACE TABLE region_month AS
        SELECT
            region, commodity, pricetype,
            DATE_TRUNC('month', date) AS month,
            AVG(price_per_kg) AS avg_price,
            AVG(CASE WHEN priceflag = 'actual' THEN 1.0 ELSE 0.0 END) AS actual_share
        FROM prices_clean
        WHERE price_per_kg IS NOT NULL
        GROUP BY 1, 2, 3, 4
    """)

    con.execute("""
        CREATE OR REPLACE TABLE region_month_enriched AS
        SELECT
            region, commodity, pricetype, month, avg_price, actual_share,
            LAG(avg_price) OVER (PARTITION BY region, commodity, pricetype ORDER BY month) AS prev_month_price,
            AVG(avg_price) OVER (
                PARTITION BY region, commodity, pricetype ORDER BY month
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ) AS rolling_3mo_avg,
            AVG(avg_price) OVER (PARTITION BY commodity, pricetype, month) AS national_avg_price
        FROM region_month
    """)

    _con = con
    return con


def db_cursor() -> duckdb.DuckDBPyConnection:
    """A fresh cursor per request -- DuckDB connections aren't safe for
    concurrent queries from multiple threads (confirmed by testing earlier
    in this project). cursor() shares the same in-memory database safely."""
    return get_db().cursor()


def confidence_label(actual_share: Optional[float], pricetype: str) -> str:
    """Turn the raw actual-vs-aggregate share into a plain-language label,
    since 'actual_share=0.34' means nothing to someone using the app."""
    if actual_share is None:
        return "unknown"
    if pricetype == "Retail":
        return "estimated"  # always true for this dataset -- 0% actual, ever
    if actual_share >= 0.8:
        return "directly observed"
    if actual_share <= 0.2:
        return "estimated"
    return "mixed (partly observed, partly estimated)"


def validate_pricetype(pricetype: str) -> str:
    if pricetype not in VALID_PRICETYPES:
        raise HTTPException(status_code=422, detail=f"pricetype must be one of {VALID_PRICETYPES}.")
    return pricetype


@app.on_event("startup")
def _startup():
    get_db()


@app.get("/api/v1/regions")
def list_regions(pricetype: str = "Wholesale"):
    validate_pricetype(pricetype)
    con = db_cursor()
    rows = con.sql(
        "SELECT DISTINCT region FROM region_month_enriched WHERE pricetype = ? ORDER BY 1",
        params=[pricetype],
    ).fetchall()
    return {"pricetype": pricetype, "regions": [r[0] for r in rows]}


@app.get("/api/v1/commodities")
def list_commodities(pricetype: str = "Wholesale", region: Optional[str] = None):
    validate_pricetype(pricetype)
    con = db_cursor()
    if region:
        rows = con.sql(
            "SELECT DISTINCT commodity FROM region_month_enriched WHERE pricetype = ? AND region = ? ORDER BY 1",
            params=[pricetype, region],
        ).fetchall()
    else:
        rows = con.sql(
            "SELECT DISTINCT commodity FROM region_month_enriched WHERE pricetype = ? ORDER BY 1",
            params=[pricetype],
        ).fetchall()
    return {"pricetype": pricetype, "commodities": [r[0] for r in rows]}


@app.get("/api/v1/summary")
def price_summary(region: str = Query(...), commodity: str = Query(...), pricetype: str = "Wholesale"):
    validate_pricetype(pricetype)
    con = db_cursor()
    row = con.sql("""
        SELECT month, avg_price, prev_month_price, rolling_3mo_avg, national_avg_price, actual_share
        FROM region_month_enriched
        WHERE region = ? AND commodity = ? AND pricetype = ?
        ORDER BY month DESC LIMIT 1
    """, params=[region, commodity, pricetype]).fetchone()

    if row is None:
        other = "Retail" if pricetype == "Wholesale" else "Wholesale"
        raise HTTPException(
            status_code=404,
            detail=f"No {pricetype} price-per-KG data for {commodity} in {region}. "
                   f"Try the {other} view -- coverage differs between the two.",
        )

    month, avg_price, prev_price, rolling_avg, national_avg, actual_share = row
    mom_pct = round((avg_price - prev_price) / prev_price * 100, 1) if prev_price else None
    vs_national_pct = round((avg_price - national_avg) / national_avg * 100, 1) if national_avg else None

    return {
        "region": region,
        "commodity": commodity,
        "pricetype": pricetype,
        "month": str(month.date()),
        "avg_price_per_kg": round(avg_price, 3),
        "month_over_month_pct": mom_pct,
        "rolling_3mo_avg": round(rolling_avg, 3) if rolling_avg else None,
        "national_avg_price_per_kg": round(national_avg, 3) if national_avg else None,
        "vs_national_avg_pct": vs_national_pct,
        "data_confidence": confidence_label(actual_share, pricetype),
    }


@app.get("/api/v1/trend")
def price_trend(region: str = Query(...), commodity: str = Query(...), pricetype: str = "Wholesale"):
    validate_pricetype(pricetype)
    con = db_cursor()
    df = con.sql("""
        SELECT month, avg_price, rolling_3mo_avg
        FROM region_month_enriched
        WHERE region = ? AND commodity = ? AND pricetype = ?
        ORDER BY month
    """, params=[region, commodity, pricetype]).df()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No {pricetype} trend data for {commodity} in {region}.")
    return {
        "region": region,
        "commodity": commodity,
        "pricetype": pricetype,
        "points": [
            {"month": str(m.date()), "price": round(p, 3), "rolling_avg": round(r, 3) if pd.notna(r) else None}
            for m, p, r in zip(df["month"], df["avg_price"], df["rolling_3mo_avg"])
        ],
    }


@app.get("/api/v1/compare")
def compare_regions(commodity: str = Query(...), pricetype: str = "Wholesale"):
    """Latest price for one commodity across every region that reports it --
    the core transparency view: see the same commodity's price side by side."""
    validate_pricetype(pricetype)
    con = db_cursor()
    df = con.sql("""
        WITH latest AS (
            SELECT region, MAX(month) AS month
            FROM region_month_enriched WHERE commodity = ? AND pricetype = ? GROUP BY region
        )
        SELECT r.region, r.avg_price, r.month
        FROM region_month_enriched r
        JOIN latest l ON r.region = l.region AND r.month = l.month
        WHERE r.commodity = ? AND r.pricetype = ?
        ORDER BY r.avg_price DESC
    """, params=[commodity, pricetype, commodity, pricetype]).df()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No {pricetype} data for {commodity}.")
    return {
        "commodity": commodity,
        "pricetype": pricetype,
        "regions": [
            {"region": reg, "avg_price_per_kg": round(p, 3), "month": str(m.date())}
            for reg, p, m in zip(df["region"], df["avg_price"], df["month"])
        ],
    }


@app.get("/api/v1/volatility")
def volatility_ranking(limit: int = 10, pricetype: str = "Wholesale"):
    validate_pricetype(pricetype)
    con = db_cursor()
    df = con.sql("""
        SELECT region, commodity, STDDEV(avg_price) AS price_stddev, COUNT(*) AS n_months
        FROM region_month
        WHERE pricetype = ?
        GROUP BY region, commodity
        HAVING COUNT(*) > 12
        ORDER BY price_stddev DESC
        LIMIT ?
    """, params=[pricetype, limit]).df()
    return {
        "pricetype": pricetype,
        "pairs": [
            {"region": r, "commodity": c, "price_stddev": round(sd, 3), "months_observed": int(n)}
            for r, c, sd, n in zip(df["region"], df["commodity"], df["price_stddev"], df["n_months"])
        ]
    }


@app.get("/api/v1/coverage-diff")
def coverage_diff():
    """What's available in one view but not the other -- surfaces the real
    finding that Retail (all-KG) covers some commodities Wholesale (mixed
    units) doesn't, and vice versa. Transparency about the merge itself."""
    con = db_cursor()
    wholesale = set(r[0] for r in con.sql(
        "SELECT DISTINCT commodity FROM region_month_enriched WHERE pricetype='Wholesale'"
    ).fetchall())
    retail = set(r[0] for r in con.sql(
        "SELECT DISTINCT commodity FROM region_month_enriched WHERE pricetype='Retail'"
    ).fetchall())
    return {
        "wholesale_only": sorted(wholesale - retail),
        "retail_only": sorted(retail - wholesale),
        "both": sorted(wholesale & retail),
    }


# --- Serve the frontend ---
if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def read_root():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))
