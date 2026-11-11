-- How much return does the Regular plan give up against the Direct plan of the same scheme? Both plans hold the same
-- portfolio, so the NAV gap is mostly the extra distribution cost charged to Regular. Plans are paired by fund house and a
-- normalised name stem; stems that do not map to exactly one Direct and one Regular Growth scheme are not paired.
create or replace table plan_pairs as
with growth as (
    select
        s.scheme_code,
        s.amc_id,
        s.plan_type,
        c.sub_category,
        trim(regexp_replace(
            regexp_replace(lower(s.scheme_name), '\b(direct|regular|plan|growth|option|scheme)\b', ' ', 'g'),
            '[^a-z0-9]+', ' ', 'g'
        )) as stem
    from dim_scheme as s
    inner join dim_category as c on s.category_id = c.category_id
    where
        s.option_type = 'Growth'
        and s.plan_type in ('Direct', 'Regular')
        and c.scheme_type = 'Open Ended'
        and c.asset_class = 'Equity Scheme'
),

stems as (
    select
        amc_id,
        stem,
        any_value(sub_category) as sub_category,
        count(*) filter (where plan_type = 'Direct') as direct_count,
        count(*) filter (where plan_type = 'Regular') as regular_count,
        min(scheme_code) filter (where plan_type = 'Direct') as direct_code,
        min(scheme_code) filter (where plan_type = 'Regular') as regular_code
    from growth
    group by amc_id, stem
)

select
    sub_category,
    stem,
    direct_code,
    regular_code
from stems
where direct_count = 1 and regular_count = 1;

create or replace table plan_pair_returns as
select
    pp.sub_category,
    pp.direct_code,
    pp.regular_code,
    power(d.nav_end / d.nav_start, 1.0 / w.window_years) - 1 as direct_cagr,
    power(r.nav_end / r.nav_start, 1.0 / w.window_years) - 1 as regular_cagr
from plan_pairs as pp
inner join scheme_points as d on pp.direct_code = d.scheme_code
inner join scheme_points as r on pp.regular_code = r.scheme_code
cross join params as w
where d.nav_start is not null and d.nav_end is not null and r.nav_start is not null and r.nav_end is not null;

create or replace table r09_direct_vs_regular as
select
    sub_category,
    count(*) as pairs,
    round(100 * median(direct_cagr), 2) as median_direct_cagr_pct,
    round(100 * median(regular_cagr), 2) as median_regular_cagr_pct,
    round(100 * median(direct_cagr - regular_cagr), 2) as median_gap_pp,
    round(100 * min(direct_cagr - regular_cagr), 2) as min_gap_pp,
    round(100 * max(direct_cagr - regular_cagr), 2) as max_gap_pp
from plan_pair_returns
group by sub_category
having count(*) >= (select min_schemes_per_category from params)
union all
select
    'ALL EQUITY CATEGORIES' as sub_category,
    count(*) as pairs,
    round(100 * median(direct_cagr), 2) as median_direct_cagr_pct,
    round(100 * median(regular_cagr), 2) as median_regular_cagr_pct,
    round(100 * median(direct_cagr - regular_cagr), 2) as median_gap_pp,
    round(100 * min(direct_cagr - regular_cagr), 2) as min_gap_pp,
    round(100 * max(direct_cagr - regular_cagr), 2) as max_gap_pp
from plan_pair_returns
order by median_gap_pp desc, sub_category asc;
