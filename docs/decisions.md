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
