# Decisions

Short records of choices that change results, and why they were made.

1. **Direct/Growth only.** IDCW NAVs fall on every payout and Regular NAVs carry commission, so mixing plans would
   compare cost structures instead of managers. Regular plans are used only in the Direct-vs-Regular pairing.
2. **DuckDB and plain SQL.** The warehouse is a single local file, reproducible without a server; the analysis logic lives
   in numbered `.sql` files that read top to bottom and are linted with SQLFluff.
3. **No primary key on `fact_nav`.** A primary key index on about 16M rows slows the load a lot; uniqueness is checked
   in `r03_data_quality` (`duplicate_keys_in_fact` must be 0) and the test suite asserts it.
4. **ASOF joins, never carry-forward.** A look-back NAV more than `stale_gap_days` from its target date is treated as
   missing. Gaps are never filled, so a data gap cannot become a fake return.
5. **Latest attributes per scheme.** A renamed or re-categorised scheme keeps its latest name and category for its whole
   history. Category moves are therefore not modelled.
6. **Benchmark from the data.** A Nifty 50 index-fund median avoids loading a second source with its own licence. It is
   net of fund costs, so "beats the benchmark" is slightly easier than beating the index.
7. **Small categories are not reported.** Categories with fewer than `min_schemes_per_category` schemes are dropped from
   summary tables because medians and quartiles on a handful of funds mislead.
8. **Harmonised category labels.** AMFI uses "Equity Scheme" and "Equity Schemes" for the same group, and splits or renames
   some categories over time. The raw heading is kept in `dim_category.category_raw`; `asset_class` and `sub_category` are
   harmonised ("Sectoral Fund" and "Thematic Fund" fold into "Sectoral/ Thematic", "ELSS- Tax Saver Fund" into "ELSS").
   Older headings with no separator (for example "Growth", "ELSS" on closed-ended or pre-2020 labels) are left whole and
   stay outside the equity universe, because they cannot be mapped to a current category with confidence.
9. **Option type from the option column first, then the name.** The option column is empty for more than half of schemes.
   "Dividend" alone is not treated as an IDCW marker, because Dividend Yield funds are an equity category with Growth options.
10. **Attrition is measured, not assumed away.** Schemes ranked in the first window but without a NAV at the end date stay
   in the first ranking and are reported in `r08_attrition`. The repeat rate itself is conditional on surviving.
11. **Explicit CSV quoting.** DuckDB's auto-detection chose the wrong quote setting on one file where a scheme name contains a
    comma, so delimiter, quote and escape are set in the staging query.
12. **Month-end panel for the backtest and holding periods.** Daily windows would give many nearly identical, overlapping
    observations; month-end NAVs give about one per scheme and month, and a month with no NAV within `stale_gap_days` of its end
    is missing rather than filled.
13. **Vanished funds are reported, and excess is measured on survivors.** A rule that picks a fund which later closes would
    otherwise lose that fund from the average and look better. Reporting `pct_vanished` next to the result keeps this visible.
14. **Cost drag uses a scenario return.** The data's 2021 to 2025 return level should not be assumed to repeat, so the rupee
    illustration varies the gross return (8% to 15%) and takes only the Direct-minus-Regular gap from the data.
