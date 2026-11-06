-- Return and volatility over the last risk_years before as_of_date, for schemes with data across the whole period.
-- Return per unit of volatility has no risk-free rate in it, so it ranks schemes inside a category but is not a Sharpe ratio.
create or replace table r07_scheme_risk_return as
with bounds as (
    select
        as_of_date,
        as_of_date - to_years(risk_years) as start_date,
        risk_years
    from params
),

vol as (
    select
        r.scheme_code,
        stddev_samp(r.daily_return) * sqrt(252) as annual_vol,
        count(*) as return_days
    from daily_returns as r
    cross join bounds as b
    where r.nav_date > b.start_date and r.nav_date <= b.as_of_date
    group by r.scheme_code
),

metrics as (
    select
        p.scheme_code,
        power(p.nav_end / p.nav_risk_start, 1.0 / b.risk_years) - 1 as cagr,
        v.annual_vol,
        v.return_days
    from scheme_points as p
    cross join bounds as b
    inner join vol as v on p.scheme_code = v.scheme_code
    where p.nav_end is not null and p.nav_risk_start is not null
)

select
    u.sub_category,
    u.scheme_code,
    u.scheme_name,
    u.amc_name,
    round(100 * m.cagr, 2) as cagr_pct,
    round(100 * m.annual_vol, 2) as annual_vol_pct,
    round(m.cagr / nullif(m.annual_vol, 0), 3) as return_per_vol,
    rank() over (partition by u.sub_category order by m.cagr / nullif(m.annual_vol, 0) desc) as rank_in_category,
    count(*) over (partition by u.sub_category) as schemes_in_category
from metrics as m
inner join analysis_universe as u on m.scheme_code = u.scheme_code
where not u.is_benchmark
order by u.sub_category, rank_in_category;

create or replace table r07_risk_return_by_category as
select
    sub_category,
    count(*) as schemes,
    round(median(cagr_pct), 2) as median_cagr_pct,
    round(median(annual_vol_pct), 2) as median_annual_vol_pct,
    round(median(return_per_vol), 3) as median_return_per_vol
from r07_scheme_risk_return
group by sub_category
having count(*) >= (select min_schemes_per_category from params)
order by median_return_per_vol desc;
