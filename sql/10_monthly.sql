-- Month-end NAVs for the Direct/Growth equity schemes, used by the backtest and the holding-period analysis. A month's
-- NAV is the last one in the month and only counts if it falls within stale_gap_days of the month end, so a scheme that
-- stopped reporting mid-month has no NAV for that month rather than a stale one.
create or replace table monthly_nav as
select
    n.scheme_code,
    (extract(year from n.nav_date) * 12 + extract(month from n.nav_date))::integer as month_idx,
    max(n.nav_date) as nav_date,
    arg_max(n.nav, n.nav_date) as nav
from nav_series as n
inner join analysis_universe as u on n.scheme_code = u.scheme_code
where not u.is_benchmark
group by n.scheme_code, (extract(year from n.nav_date) * 12 + extract(month from n.nav_date))::integer
having date_diff('day', max(n.nav_date), last_day(max(n.nav_date))) <= (select stale_gap_days from params);

-- One-month returns between consecutive month-end NAVs.
create or replace table monthly_returns as
select
    b.scheme_code,
    b.month_idx,
    b.nav / a.nav - 1 as monthly_return
from monthly_nav as b
inner join monthly_nav as a on b.scheme_code = a.scheme_code and b.month_idx = a.month_idx + 1;
