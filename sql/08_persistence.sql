-- Does past outperformance repeat? Within each category, schemes are ranked into quartiles on the return of one window,
-- then again on the next window, and we count how many stay in the top quartile. A top-quartile scheme that repeats at
-- random would land in the top quartile again 25% of the time.
-- Schemes that existed in the first window but have no NAV at as_of_date (closed, merged or re-coded) are kept in the first
-- ranking and reported as attrition. Only survivors can be ranked in the second window, so the repeat rate is conditional
-- on surviving; the attrition table shows what that condition hides.
create or replace table scheme_period_returns as
select
    u.scheme_code,
    u.sub_category,
    power(p.nav_start / p.nav_start_2x, 1.0 / w.window_years) - 1 as cagr_first,
    power(p.nav_end / p.nav_start, 1.0 / w.window_years) - 1 as cagr_second -- NULL when there is no NAV at as_of_date
from analysis_universe as u
inner join scheme_points as p on u.scheme_code = p.scheme_code
cross join params as w
where
    not u.is_benchmark
    and p.nav_start_2x is not null and p.nav_start is not null;

create or replace table scheme_quartiles as
with first_period as (
    select
        *,
        ntile(4) over (partition by sub_category order by cagr_first desc, scheme_code asc) as quartile_first,
        count(*) over (partition by sub_category) as schemes_in_category
    from scheme_period_returns
),

second_period as (
    select
        scheme_code,
        ntile(4) over (partition by sub_category order by cagr_second desc, scheme_code asc) as quartile_second
    from scheme_period_returns
    where cagr_second is not null
)

select
    f.*,
    s.quartile_second
from first_period as f
left join second_period as s on f.scheme_code = s.scheme_code;

create or replace table r08_quartile_transitions as
select
    quartile_first,
    quartile_second,
    count(*) as schemes,
    round(100.0 * count(*) / sum(count(*)) over (partition by quartile_first), 1) as pct_of_surviving_first_quartile
from scheme_quartiles
where
    quartile_second is not null
    and schemes_in_category >= (select min_schemes_per_category from params)
group by quartile_first, quartile_second
order by quartile_first, quartile_second;

create or replace table r08_top_quartile_repeat as
select
    sub_category,
    count(*) filter (where quartile_first = 1) as top_quartile_schemes,
    count(*) filter (where quartile_first = 1 and quartile_second is not null) as survivors,
    count(*) filter (where quartile_first = 1 and quartile_second = 1) as stayed_top_quartile,
    round(
        100.0 * count(*) filter (where quartile_first = 1 and quartile_second = 1)
        / nullif(count(*) filter (where quartile_first = 1 and quartile_second is not null), 0), 1
    ) as repeat_rate_pct
from scheme_quartiles
where schemes_in_category >= (select min_schemes_per_category from params)
group by sub_category
order by repeat_rate_pct desc;

create or replace table r08_attrition as
select
    quartile_first,
    count(*) as schemes,
    count(*) filter (where quartile_second is null) as no_nav_at_as_of,
    round(100.0 * count(*) filter (where quartile_second is null) / count(*), 1) as pct_not_surviving
from scheme_quartiles
where schemes_in_category >= (select min_schemes_per_category from params)
group by quartile_first
order by quartile_first;
