-- Analysis universe: open-ended equity schemes, Direct plan, Growth option, plus Nifty 50 index funds as the
-- benchmark. Direct/Growth is used because it is the only combination whose NAV is not distorted by distributions
-- or distribution commissions, so schemes can be compared on NAV alone.
create or replace table analysis_universe as
select
    s.scheme_code,
    s.scheme_name,
    a.amc_name,
    c.sub_category,
    c.asset_class,
    s.first_nav_date,
    s.last_nav_date,
    c.sub_category = 'Index Funds' and regexp_matches(s.scheme_name, '(?i)\bnifty 50\b') as is_benchmark
from dim_scheme as s
inner join dim_amc as a on s.amc_id = a.amc_id
inner join dim_category as c on s.category_id = c.category_id
where
    s.plan_type = 'Direct'
    and s.option_type = 'Growth'
    and c.scheme_type = 'Open Ended'
    and (c.asset_class = 'Equity Scheme' or c.sub_category = 'Index Funds')
    and not (c.sub_category = 'Index Funds' and not regexp_matches(s.scheme_name, '(?i)\bnifty 50\b'));

-- Daily series with the previous NAV. A return is only formed across gaps of up to stale_gap_days so that
-- missing data is not turned into one large fake return.
create or replace table nav_series as
select
    f.scheme_code,
    f.nav_date,
    f.nav,
    lag(f.nav) over w as prev_nav,
    lag(f.nav_date) over w as prev_date
from fact_nav as f
inner join analysis_universe as u on f.scheme_code = u.scheme_code
window w as (partition by f.scheme_code order by f.nav_date);

create or replace table daily_returns as
select
    n.scheme_code,
    n.nav_date,
    n.nav / n.prev_nav - 1 as daily_return
from nav_series as n
cross join params as p
where n.prev_nav is not null and date_diff('day', n.prev_date, n.nav_date) <= p.stale_gap_days;

-- Reference NAVs at the dates every windowed analysis needs, found once with an ASOF join (latest NAV on or before the
-- target date). A NAV further than stale_gap_days from its target date is treated as missing, never carried forward.
-- Labels: end = as_of_date, start = one window earlier, start_2x = two windows earlier, risk_start = risk_years earlier.
create or replace table point_navs as
with points as (
    select
        'end' as point_name,
        as_of_date as target_date
    from params
    union all
    select
        'start' as point_name,
        as_of_date - to_years(window_years) as target_date
    from params
    union all
    select
        'start_2x' as point_name,
        as_of_date - to_years(2 * window_years) as target_date
    from params
    union all
    select
        'risk_start' as point_name,
        as_of_date - to_years(risk_years) as target_date
    from params
),

wanted as (
    select
        s.scheme_code,
        p.point_name,
        p.target_date
    from dim_scheme as s
    cross join points as p
)

select
    w.scheme_code,
    w.point_name,
    f.nav_date,
    f.nav
from wanted as w
asof join fact_nav as f on w.scheme_code = f.scheme_code and w.target_date >= f.nav_date
where date_diff('day', f.nav_date, w.target_date) <= (select stale_gap_days from params);

create or replace table scheme_points as
select
    scheme_code,
    max(nav) filter (where point_name = 'end') as nav_end,
    max(nav) filter (where point_name = 'start') as nav_start,
    max(nav) filter (where point_name = 'start_2x') as nav_start_2x,
    max(nav) filter (where point_name = 'risk_start') as nav_risk_start
from point_navs
group by scheme_code;
