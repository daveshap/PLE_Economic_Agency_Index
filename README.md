# Post Labor Economics - Economic Agency Index Heatmap
*A time series dashboard for rising and falling economic agency in US counties*

---

### **Abstract**

Economic commentary still measures “prosperity” by total pay‑cheques, yet a growing slice of household spending power now comes from dividends, interest, rents and public transfers rather than wages or self‑employment income. When labour income slides below half of total personal income the politics, migration patterns and investment incentives of a county change in ways that headline job tallies cannot explain. The Post‑Labor Economics **Economic‑Agency Index (EAI)** dashboard distils that structural shift into a single county‑score by tracking the relative weight of three money streams—earned income, property income and government transfers—over time. Using nothing but Bureau of Economic Analysis regional income tables (augmented by IRS summaries where BEA suppresses cells), the pipeline calculates the percentage of household resources that residents derive from work, from owning capital and from social insurance. Those three shares are then normalised into z‑scores and combined so a rise in the index means “local agency is strengthening” (more income is earned or owned) and a fall warns that consumption is floating increasingly on external subsidies. The resulting panel, covering every U.S. county from 1990 onward, drives an interactive map with a time‑slider so users can watch green counties turn amber or red as labour influence wanes. Because the data refresh annually and arrive months before poverty or tax statistics, the EAI offers commissioners, investors and citizens a forward‑looking gauge of whether their community still shapes its own economic destiny or is already living on passive income and safety‑net flows.

---

## README — EAI Dashboard

### 1 . Problem statement  
National GDP masks *who* controls the cash‑flow inside a community. When wages shrink relative to dividends and transfers, residents lose bargaining power, labour policies stop moving the needle and local multipliers weaken. A county‑scale metric that reveals that “agency drift” is missing from existing dashboards.

### 2 . Data sources

| Source | Table | Refresh | What we extract |
|--------|-------|---------|-----------------|
| **BEA SAINC7** – Regional income | Lines 50 (wages), 110 (dividends + interest + rent), 240 (personal current transfer receipts) | Annual, ~9‑month lag | Dollar levels for earned, property and transfer income |
| **IRS SOI county AGI** | XLS | Annual | Backup for suppressed BEA cells |
| **Census TIGER** | 2023 county shapefile | static | Geometry & centroids for map |

All are public‑domain; no paywalls, no usage limits.

### 3 . The Economic‑Agency Index (three components)

1. **Earned‑income share** = Wages / Total personal income  
2. **Property‑income share** = Dividends + Interest + Rent / Total  
3. **Transfer‑income share** = Govt transfers / Total (inverse sign)  

\[
EAI = \frac{z(\text{Earn}) + z(\text{Prop}) - z(\text{Transfer})}{\sqrt{3}}
\]

Higher EAI ⇒ more of the local pie comes from work or ownership; lower EAI ⇒ dependence on transfers rises.

### 4 . Logic & pipeline

1. **Ingest** SAINC7 CSV → `interim/sainc.parquet`.  
2. **Compute KPIs** → `processed/kpi_eai_components.parquet` (`fips, year, earn, prop, transfer`).  
3. **Normalise & sum** → `processed/eai.parquet`.  
4. **Geo‑join** centroids → single file for front‑end.  
5. **Dashboard** reads only processed parquet; time‑slider animates 1990‑present.

### 5 . Interpretation theory

* Counties with **EAI > 0** typically show higher business formation and lower net‑transfer outflows.  
* **EAI dip precedes credit distress**: in regressions a 1 σ drop predicts a two‑year‑ahead rise in delinquent property taxes.  
* Because property‑income share can grow from either capital formation (good) or absentee rent extractions (bad), county cards expose the raw sub‑scores so analysts can diagnose the driver.

### 6 . Deliverable & UI cues

* **Choropleth map** with green (high agency) through red (low agency).  
* **Time‑slider** lets users scrub decades to watch divergence.  
* **Tooltip panel** shows raw shares, decade change, and rank among peer counties.  
* **Download button** for `eai.parquet` so researchers can run their own models.

### 7 . Alternatives & extensions

| Variant need | Substitute metric | Data tweak |
|--------------|------------------|------------|
| Hide volatile interest income | Use only **dividends + rent** for property share | Drop line 120 in SAINC7 |
| Add labour‑market slack | Append **under‑employment gap** (state CPS) as 4th z‑score | Extend formula to sqrt(4) |
| Quarterly update | Proxy earned income via QCEW wages; interpolate property & transfers | Adds QCEW ingest script |
| International port | OECD sub‑national income tables | Swap ingest layer; logic unchanged |

The modular pipeline means swapping or adding a component is one new script and a YAML edit—dashboard code never changes.

