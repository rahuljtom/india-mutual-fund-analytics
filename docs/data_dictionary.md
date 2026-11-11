# Data dictionary

All tables live in the DuckDB file `data/mf.duckdb` (built by `make build`, not committed).

## Source

AMFI (Association of Mutual Funds in India) historical NAV report, downloaded from the public portal
`portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx` in windows of at most 90 days. NAV is the net asset value
per unit, published for each scheme and date. The raw file is semi-structured text; `src/mfa/parse.py` turns it into
rows. The raw files are not committed (110 MB compressed, 2.3 GB as text); `make download` recreates them.

## Warehouse tables

| Table | Grain | Key | Notes |
|---|---|---|---|
| `dim_amc` | one fund house | `amc_id` | Name as printed in the report heading. |
| `dim_category` | one category heading | `category_id`; unique `(scheme_type, category_raw)` | `asset_class` is the text before the first ` - `, `sub_category` the text after it. |
| `dim_scheme` | one scheme code | `scheme_code`; FKs to `dim_amc`, `dim_category` | Latest name, category and fund house seen for the code. `plan_type` is Direct, Regular or Unknown; `option_type` is Growth, IDCW or Other. |
| `fact_nav` | scheme and date | `(scheme_code, nav_date)`, verified in `r03_data_quality` | `nav > 0` is a CHECK constraint. |

## Working tables

| Table | Purpose |
|---|---|
| `params` | All analysis parameters in one row: `as_of_date`, `window_years`, `risk_years`, `dd_start`, `stale_gap_days`, `min_schemes_per_category`, `min_benchmark_funds`. |
| `analysis_universe` | Open-ended equity schemes, Direct plan, Growth option, plus Nifty 50 index funds flagged `is_benchmark`. |
| `nav_series`, `daily_returns` | NAV series of the universe, with daily returns formed only across gaps of up to `stale_gap_days`. |
| `point_navs`, `scheme_points` | NAV at the reference dates each windowed query needs, found with an ASOF join. |
| `rolling_returns` | Annualised return (CAGR) of every window of `window_years` ending on every date. |
| `scheme_drawdowns` | Maximum drawdown, peak, trough and recovery dates per scheme. |
| `scheme_quartiles` | Category quartile of each scheme in two consecutive windows. |
| `plan_pairs`, `plan_pair_returns` | Direct and Regular plans of the same scheme, and their returns. |

## Result tables (exported to `outputs/tables/`)

| Table | Columns that need explaining |
|---|---|
| `r03_data_quality` | `n` rows or schemes per check; `pct_of_staged_rows` where it makes sense. |
| `r03_schemes_by_year` | Schemes with a NAV in each year, and how many of them stop before `as_of_date`. |
| `r05_rolling_by_category` | `p10/median/p90_cagr_pct` across all windows; `pct_windows_negative`; `pct_windows_below_7pct`. |
| `r05_vs_benchmark` | Date by date, does the category median rolling return beat the median Nifty 50 index fund? |
| `r06_drawdown_by_category` | Median and worst maximum drawdown; days peak to trough; share recovered by `as_of_date`; days trough to recovery. |
| `r07_scheme_risk_return`, `r07_risk_return_by_category` | `return_per_vol` = CAGR / annualised volatility, no risk-free rate. |
| `r08_quartile_transitions`, `r08_top_quartile_repeat` | Movement between category quartiles across two consecutive windows. |
| `r09_direct_vs_regular` | Median CAGR gap, in percentage points, between paired Direct and Regular plans. |
| `r10_backtest_by_year`, `r10_backtest_summary` | Walk-forward test on 31 December 2020 to 2024: schemes picked inside each category from the trailing 24 months, measured over the next 12 months against the category average. `pct_vanished` = picks with no NAV at the end of the forward year; excess is measured on survivors. |
| `r11_cost_drag` | Rupees lost to the Regular plan for a monthly SIP of 10,000 and a one-off 10 lakh. The gap is the data's median Direct-minus-Regular gap; the gross Direct return is a scenario input. |
| `r12_holding_period` | Annualised return percentiles and share of windows with a loss for every month-end start and finish, by holding period (1, 3, 5 years) and category. |
| `r13_funnel`, `r13_data_mess`, `r13_category_harmonisation` | Rows and schemes surviving each filter; each source problem with count, handling and effect if ignored; raw category labels and the harmonised category they map to. |
| `r03_parse_summary` | Totals over every parsed report file: lines of each kind seen by the parser, and how many were unclassified. |
