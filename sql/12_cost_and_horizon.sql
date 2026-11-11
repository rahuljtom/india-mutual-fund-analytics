-- Two decision tables.
-- r11_cost_drag: what the Direct versus Regular gap measured in r09 costs a saver in rupees. The gap (median across all
--   equity pairs) is taken from the data; the gross Direct return is a scenario input, since the 2021-2025 return level should
--   not be assumed to repeat. A monthly SIP of 10,000 rupees (annuity due) and a one-off 10 lakh investment are shown.
-- r12_holding_period: how often an equity fund lost money, and how wide the range of outcomes was, over holding periods of
--   1, 3 and 5 years (every month-end start with a month-end finish), by category.
create or replace table r11_cost_drag as
with gap as (
    select median_gap_pp as gap_pp
    from r09_direct_vs_regular
    where sub_category = 'ALL EQUITY CATEGORIES'
),

scenarios as (
    select
        g.gap_pp,
        d.direct_cagr_pct,
        d.direct_cagr_pct - g.gap_pp as regular_cagr_pct,
        h.horizon_years
    from gap as g
    cross join (select unnest([8.0, 10.0, 12.0, 15.0]) as direct_cagr_pct) as d
    cross join (select unnest([10, 20]) as horizon_years) as h
),

values_at_end as (
    select
        *,
        power(1 + direct_cagr_pct / 100, 1.0 / 12) - 1 as mi_d,
        power(1 + regular_cagr_pct / 100, 1.0 / 12) - 1 as mi_r
    from scenarios
)

select
    horizon_years,
    direct_cagr_pct,
    round(regular_cagr_pct, 2) as regular_cagr_pct,
    round(10000 * (power(1 + mi_d, 12 * horizon_years) - 1) / mi_d * (1 + mi_d), 0) as sip_direct_inr,
    round(10000 * (power(1 + mi_r, 12 * horizon_years) - 1) / mi_r * (1 + mi_r), 0) as sip_regular_inr,
    round(
        10000 * (power(1 + mi_d, 12 * horizon_years) - 1) / mi_d * (1 + mi_d)
        - 10000 * (power(1 + mi_r, 12 * horizon_years) - 1) / mi_r * (1 + mi_r), 0
    ) as sip_cost_inr,
    round(100 * (
        1 - (power(1 + mi_r, 12 * horizon_years) - 1) / mi_r * (1 + mi_r)
        / ((power(1 + mi_d, 12 * horizon_years) - 1) / mi_d * (1 + mi_d))
    ), 1) as sip_cost_pct,
    round(1000000 * power(1 + direct_cagr_pct / 100, horizon_years), 0) as lump_direct_inr,
    round(1000000 * power(1 + regular_cagr_pct / 100, horizon_years), 0) as lump_regular_inr,
    round(1000000 * (power(1 + direct_cagr_pct / 100, horizon_years) - power(1 + regular_cagr_pct / 100, horizon_years)), 0)
        as lump_cost_inr
from values_at_end
order by horizon_years asc, direct_cagr_pct asc;

create or replace table holding_windows as
select
    h.horizon_months,
    u.sub_category,
    e.scheme_code,
    e.month_idx,
    power(e.nav / s.nav, 12.0 / h.horizon_months) - 1 as annualised_return,
    e.nav / s.nav - 1 as total_return
from (select unnest([12, 36, 60]) as horizon_months) as h
inner join monthly_nav as e on true
inner join monthly_nav as s on e.scheme_code = s.scheme_code and s.month_idx = e.month_idx - h.horizon_months
inner join analysis_universe as u on e.scheme_code = u.scheme_code;

create or replace table r12_holding_period as
with by_category as (
    select
        horizon_months,
        sub_category,
        count(*) as windows,
        count(distinct scheme_code) as schemes,
        quantile_cont(annualised_return, 0.10) as p10,
        quantile_cont(annualised_return, 0.50) as p50,
        quantile_cont(annualised_return, 0.90) as p90,
        avg((total_return < 0)::integer) as pct_loss
    from holding_windows
    group by horizon_months, sub_category
    having count(distinct scheme_code) >= (select min_schemes_per_category from params)
),

overall as (
    select
        horizon_months,
        'ALL EQUITY CATEGORIES' as sub_category,
        count(*) as windows,
        count(distinct scheme_code) as schemes,
        quantile_cont(annualised_return, 0.10) as p10,
        quantile_cont(annualised_return, 0.50) as p50,
        quantile_cont(annualised_return, 0.90) as p90,
        avg((total_return < 0)::integer) as pct_loss
    from holding_windows
    group by horizon_months
)

select
    horizon_months / 12 as horizon_years,
    sub_category,
    windows,
    schemes,
    round(100 * p10, 1) as p10_annual_pct,
    round(100 * p50, 1) as median_annual_pct,
    round(100 * p90, 1) as p90_annual_pct,
    round(100 * pct_loss, 2) as pct_windows_with_loss
from (
    select * from by_category
    union all
    select * from overall
) as all_rows
order by horizon_years asc, (sub_category = 'ALL EQUITY CATEGORIES') desc, median_annual_pct desc, sub_category asc;
