# BEA Data Feed for the Economic Agency Index (EAI) Dashboard

## Purpose and Context

The Economic Agency Index measures how much of a person’s livelihood is determined by **agency‑enhancing** income streams—wages, dividends, interest, rent—versus passive or contingent transfers.  Those component shares, updated every year and disaggregated down to U.S. counties, underpin all of the dashboard visualizations and composite scores.  Because the index will ultimately guide policy simulations, the data pipeline must be replicable, transparent, and aligned with a public statistical authority that is unlikely to disappear behind a paywall.  The **Bureau of Economic Analysis (BEA) Regional Economic Accounts** satisfy those criteria and have already been cited throughout the Post‑Labor Economics (PLE) archive.

## Core Table Selection

The single most information‑dense table for our purposes is **CAINC7 / SAINC7, “Personal income, population, per‑capita personal income.”**  It provides every building block of the EAI numerator—wage and salary disbursements, dividends + interest + rent, and government transfer receipts—alongside both population counts and total personal income.  Using this table alone we can construct the county‑level share of agency income as well as the per‑capita and aggregate versions displayed in the dashboard.

### Why CAINC7 instead of CAINC1 or CAINC6?

CAINC1 contains disposable personal income while CAINC6 is an income summary, but each omits at least one component needed for the EAI ratio.  CAINC7 has the advantage of collapsing all relevant line items into a single rectangular panel that never changes dimensionality when BEA revises peripheral indicators.  This means fewer joins, fewer version headaches, and a smaller change surface when we automate refresh jobs.

## Supporting Tables

Occasionally we need secondary variables.  Disposable personal income, available in **CAINC1 / SAINC1**, feeds the Current Purchasing Power (CPP) overlay.  Regional Price Parities (RPP) supply county‑level deflators when we want real‑term comparability.  These tables live in the same Regional dataset, share the same GEOID keys, and are accessed through identical query patterns, so bolting them onto the pipeline is mechanically trivial.

## Access Paths

BEA exposes three equivalent windows into the Regional data: an interactive iTable, zipped bulk CSV files, and a REST‑style JSON API.  All of them address the same canonical table names, differ only in packaging, and therefore interchange seamlessly.

* **Interactive browser** — [https://apps.bea.gov/itable/?ReqID=70\&step=1\&tableId=CAINC7](https://apps.bea.gov/itable/?ReqID=70&step=1&tableId=CAINC7)
* **Bulk download** — [https://apps.bea.gov/regional/downloadzip.cfm](https://apps.bea.gov/regional/downloadzip.cfm) (choose "Regional" → "CAINC")
* **API** — base endpoint `https://apps.bea.gov/api/data/` with query parameters shown below

```text
https://apps.bea.gov/api/data/?UserID=YOUR_KEY
  &dataset=Regional
  &TableName=CAINC7
  &GeoFIPS=05000-04999       # all counties
  &LineCode=3,4,9            # 3 = wages, 4 = div+int+rent, 9 = transfers
  &Year=ALL
  &frequency=A
```

When automating, prefer the API because it arrives pre‑typed as JSON, reducing downstream parsing time.  Reserve the bulk ZIP option for historical backfills or parity checks.

## Refresh Cadence and Version Control

BEA releases “advance” county estimates every December and fully reconciled figures the following September.  The pipeline is therefore scheduled to hit the API twice a year: once immediately after the December drop, flagged as **provisional**, and again after the September reconciliation, which overwrites the provisional tag while preserving a SHA‑hashed snapshot in the `/data/archive` folder.  Minor revisions inside the same reference year are exceedingly rare but, if they occur, the checksum comparison will trigger an incremental commit.

## Integration Workflow

1. The ingestion script queries CAINC7 for the latest year and normalizes the JSON into a tidy dataframe keyed on `GeoFIPS`, `Year`, and `LineCode`.
2. A transformation layer pivots the three selected line codes into wide columns (`wages`, `capital_income`, `transfers`) and calculates the **Agency Share** as `(wages + capital_income) / (wages + capital_income + transfers)`.
3. The resulting table feeds both the Postgres materialized view that powers the live dashboard and the static parquet snapshots used for reproducibility tests.
4. Documentation is auto‑generated via pydoc‑markdown so that every field retains lineage metadata back to its BEA source table and line code.

## Attribution

All economic series originate from the **U.S. Bureau of Economic Analysis, Regional Economic Accounts, Table CAINC7 / SAINC7 (accessed via API and bulk download, various releases 2022‑present).**  Derived metrics such as the Economic Agency Index are © Post‑Labor Economics, released under the MIT License.

## Next Steps

Future iterations of the dashboard will integrate BEA’s **County Compensation Tables** to separate employer‑paid benefits from nominal wages and the **Consumer Expenditure Survey microdata** to test how agency income correlates with consumption volatility.  Those additions, however, do not affect the CAINC7 backbone documented here.
