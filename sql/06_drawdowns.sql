-- Maximum drawdown per scheme between dd_start and as_of_date, and how long recovery took.
-- Only schemes that existed at both ends are compared, so every scheme lives through the same market episodes.
create or replace table scheme_drawdowns as
with matured as (
    select u.scheme_code
    from analysis_universe as u
    cross join params as p
    where
        not u.is_benchmark
        and u.first_nav_date <= p.dd_start + to_days(p.stale_gap_days)
        and u.last_nav_date >= p.as_of_date - to_days(p.stale_gap_days)
),

running as (
    select
        n.scheme_code,
        n.nav_date,
        n.nav,
        max(n.nav) over (partition by n.scheme_code order by n.nav_date rows between unbounded preceding and current row) as peak_nav
    from nav_series as n
    cross join params as p
    where n.scheme_code in (select scheme_code from matured) and n.nav_date between p.dd_start and p.as_of_date
),

depth as (
    select
        *,
        nav / peak_nav - 1 as drawdown
    from running
),

worst as (
    select
        scheme_code,
        min(drawdown) as max_drawdown,
        arg_min(nav_date, drawdown) as trough_date,
        arg_min(peak_nav, drawdown) as peak_nav_at_trough
    from depth
    group by scheme_code
)

select
    w.scheme_code,
    w.max_drawdown,
    w.trough_date,
    case when w.max_drawdown < 0 then (
        select min(d.nav_date) from depth as d
        where d.scheme_code = w.scheme_code and d.nav = w.peak_nav_at_trough
    ) end as peak_date,
    case when w.max_drawdown < 0 then (
        select min(d.nav_date) from depth as d
        where d.scheme_code = w.scheme_code and d.nav_date > w.trough_date and d.nav >= w.peak_nav_at_trough
    ) end as recovery_date
from worst as w;

create or replace table r06_drawdown_by_category as
select
    u.sub_category,
    count(*) as schemes,
    round(100 * median(d.max_drawdown), 1) as median_max_drawdown_pct,
    round(100 * min(d.max_drawdown), 1) as worst_max_drawdown_pct,
    round(median(date_diff('day', d.peak_date, d.trough_date)), 0) as median_days_peak_to_trough,
    round(100.0 * avg((d.recovery_date is not null)::int) filter (where d.max_drawdown < 0), 1) as pct_recovered,
    round(median(date_diff('day', d.trough_date, d.recovery_date)), 0) as median_days_trough_to_recovery
from scheme_drawdowns as d
inner join analysis_universe as u on d.scheme_code = u.scheme_code
group by u.sub_category
having count(*) >= (select min_schemes_per_category from params)
order by median_max_drawdown_pct desc, u.sub_category asc;
