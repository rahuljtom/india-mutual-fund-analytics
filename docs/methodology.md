# Methodology

## Question

How have Indian equity mutual fund categories compared on rolling returns, drawdowns and cost, and does past
outperformance within a category tend to repeat? The unit of analysis is a scheme-level NAV series.

## Pipeline

1. **Download.** `mfa.download` fetches the AMFI historical NAV report in 90-day windows (the portal maximum) for
   2018-01-01 to 2025-12-31 and stores each window gzip-compressed.
2. **Parse.** `mfa.parse` reads the text report. Category and fund-house headings apply to the rows beneath them, so the
   parser keeps them as state. Every line is either parsed or counted under a named reason; counts are written to
   `data/interim/parse_report.csv`.
3. **Load.** SQL stages all rows as text, types them with `try_cast` so bad values become NULL, then builds the star
   schema and removes duplicate scheme-date rows.
4. **Check.** `r03_data_quality` counts every exclusion and verifies there are no duplicate keys or orphan rows.
5. **Analyse.** Numbered SQL files build the analysis tables; `mfa.pipeline` exports each result table to CSV.
6. **Test.** `pytest` runs the parser, then the real SQL files, against a synthetic history whose answers are worked out
   by hand (compound growth, a drawdown with known peak, trough and recovery, plan pairs with a known cost gap).

## Definitions

- **Universe.** Open-ended schemes in equity categories, Direct plan, Growth option. Direct/Growth is the only
  combination whose NAV is not shifted by payouts or by distribution commission, so schemes compare on NAV alone.
- **Rolling return.** For each scheme and date, the NAV `window_years` calendar years earlier is the latest NAV on or
  before that date, and only if it is within `stale_gap_days` of it. Return is annualised: `(NAV_end / NAV_start)^(1/years) - 1`.
- **Benchmark.** The median rolling return across Direct/Growth index funds with "Nifty 50" in the name. It is a
  proxy built from the data itself; it is not the index and is net of fund costs.
- **Maximum drawdown.** Lowest value of `NAV / running peak NAV - 1` between `dd_start` and `as_of_date`, for schemes that
  existed at both ends. Recovery is the first date after the trough with NAV at or above the peak.
- **Volatility.** Sample standard deviation of daily returns times the square root of 252.
- **Return per unit of volatility.** CAGR divided by annualised volatility. No risk-free rate, so this is a ranking device.
- **Persistence.** Within a category, schemes are split into quartiles on their return in one window, then again in the
  next window. A top-quartile scheme that repeats at random would stay in the top quartile 25% of the time.
- **Direct vs Regular.** Plans are paired by fund house and a normalised name stem. Both hold the same portfolio, so the
  return gap is mostly the extra distribution cost in the Regular plan.

## Reproducing

```
make setup
make all        # download, build, charts, lint and tests
```
