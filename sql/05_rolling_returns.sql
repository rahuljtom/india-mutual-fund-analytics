-- Rolling returns. For every scheme and date, find the NAV window_years earlier with an ASOF join (the latest NAV on
-- or before the target date) and reject matches more than stale_gap_days away. Annualised as a CAGR.
create or replace table rolling_returns as
with targets as (
    select
        n.scheme_code,
        n.nav_date,
        n.nav,
        n.nav_date - to_years(p.window_years) as target_date,
        p.window_years,
        p.stale_gap_days
    from nav_series as n
    cross join params as p
)

select
    t.scheme_code,
    t.nav_date,
    power(t.nav / s.nav, 1.0 / t.window_years) - 1 as cagr
from targets as t
asof join nav_series as s on t.scheme_code = s.scheme_code and t.target_date >= s.nav_date
where date_diff('day', s.nav_date, t.target_date) <= t.stale_gap_days;

-- Distribution of rolling returns per category, over every window ending on every date.
create or replace table r05_rolling_by_category as
select
    u.sub_category,
    count(distinct r.scheme_code) as schemes,
    count(*) as windows,
    round(100 * quantile_cont(r.cagr, 0.10), 2) as p10_cagr_pct,
    round(100 * quantile_cont(r.cagr, 0.50), 2) as median_cagr_pct,
    round(100 * quantile_cont(r.cagr, 0.90), 2) as p90_cagr_pct,
    round(100.0 * avg((r.cagr < 0)::int), 1) as pct_windows_negative,
    round(100.0 * avg((r.cagr < 0.07)::int), 1) as pct_windows_below_7pct
from rolling_returns as r
inner join analysis_universe as u on r.scheme_code = u.scheme_code
where not u.is_benchmark
group by u.sub_category
having count(distinct r.scheme_code) >= (select min_schemes_per_category from params)
order by median_cagr_pct desc;

-- How often does the typical scheme in a category beat the Nifty 50 index-fund benchmark? Compared date by date:
-- the category median rolling return against the median across benchmark index funds on that date.
create or replace table r05_vs_benchmark as
with bench as (
    select
        r.nav_date,
        median(r.cagr) as bench_cagr,
        count(*) as bench_funds
    from rolling_returns as r
    inner join analysis_universe as u on r.scheme_code = u.scheme_code
    where u.is_benchmark
    group by r.nav_date
    having count(*) >= (select min_benchmark_funds from params)
),

category_day as (
    select
        u.sub_category,
        r.nav_date,
        median(r.cagr) as category_cagr,
        count(*) as category_schemes
    from rolling_returns as r
    inner join analysis_universe as u on r.scheme_code = u.scheme_code
    where not u.is_benchmark
    group by u.sub_category, r.nav_date
    having count(*) >= (select min_schemes_per_category from params)
)

select
    c.sub_category,
    count(*) as dates_compared,
    round(100.0 * avg((c.category_cagr > b.bench_cagr)::int), 1) as pct_dates_category_median_beats_benchmark,
    round(100 * median(c.category_cagr - b.bench_cagr), 2) as median_excess_cagr_pp
from category_day as c
inner join bench as b on c.nav_date = b.nav_date
group by c.sub_category
order by median_excess_cagr_pp desc;
