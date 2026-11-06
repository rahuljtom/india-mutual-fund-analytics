-- Does past outperformance repeat? Rank schemes inside their category on the three years up to the midpoint, then on the
-- three years after it, and count how many move between quartiles. A top-quartile scheme that repeats at random would
-- land in the top quartile again 25% of the time. Only schemes alive across both periods are included, so this
-- understates how often leaders disappear (survivorship).
create or replace table scheme_period_returns as
select
    u.scheme_code,
    u.sub_category,
    power(p.nav_start / p.nav_start_2x, 1.0 / w.window_years) - 1 as cagr_first,
    power(p.nav_end / p.nav_start, 1.0 / w.window_years) - 1 as cagr_second
from analysis_universe as u
inner join scheme_points as p on u.scheme_code = p.scheme_code
cross join params as w
where
    not u.is_benchmark
    and p.nav_start_2x is not null and p.nav_start is not null and p.nav_end is not null;

create or replace table scheme_quartiles as
select
    *,
    ntile(4) over (partition by sub_category order by cagr_first desc, scheme_code asc) as quartile_first,
    ntile(4) over (partition by sub_category order by cagr_second desc, scheme_code asc) as quartile_second,
    count(*) over (partition by sub_category) as schemes_in_category
from scheme_period_returns;

create or replace table r08_quartile_transitions as
select
    quartile_first,
    quartile_second,
    count(*) as schemes,
    round(100.0 * count(*) / sum(count(*)) over (partition by quartile_first), 1) as pct_of_first_quartile
from scheme_quartiles
where schemes_in_category >= (select min_schemes_per_category from params)
group by quartile_first, quartile_second
order by quartile_first, quartile_second;

create or replace table r08_top_quartile_repeat as
select
    sub_category,
    count(*) filter (where quartile_first = 1) as top_quartile_schemes,
    count(*) filter (where quartile_first = 1 and quartile_second = 1) as stayed_top_quartile,
    round(
        100.0 * count(*) filter (where quartile_first = 1 and quartile_second = 1)
        / nullif(count(*) filter (where quartile_first = 1), 0), 1
    ) as repeat_rate_pct
from scheme_quartiles
where schemes_in_category >= (select min_schemes_per_category from params)
group by sub_category
order by repeat_rate_pct desc;
