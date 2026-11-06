-- Data quality profile. Every exclusion made in staging and the dimension build is counted here.
create or replace table r03_data_quality as
with profile as (
    select
        (select count(*) from stg_nav) as staged_rows,
        (
            select count(*) from stg_nav
            where scheme_code is null
        ) as bad_scheme_code,
        (
            select count(*) from stg_nav
            where nav_date is null
        ) as bad_date,
        (
            select count(*) from stg_nav
            where nav is null
        ) as nav_not_numeric,
        (
            select count(*) from stg_nav
            where nav <= 0
        ) as nav_not_positive,
        (select count(*) from fact_nav) as fact_rows,
        (select count(
            *) from (
            select 1 from fact_nav
            group by scheme_code, nav_date
            having count(*) > 1
        )) as duplicate_keys_in_fact,
        (
            select count(*) from fact_nav
            where scheme_code not in (select scheme_code from dim_scheme)
        ) as orphan_fact_rows,
        (select count(*) from dim_scheme) as schemes,
        (
            select count(*) from dim_scheme
            where plan_type = 'Unknown'
        ) as plan_unknown,
        (
            select count(*) from dim_scheme
            where option_type = 'Other'
        ) as option_other,
        (
            select count(*) from fact_nav
            where dayofweek(nav_date) in (0, 6)
        ) as weekend_navs
)

select
    check_name,
    n,
    round(100.0 * n / nullif(max(n) filter (where check_name = 'staged_rows') over (), 0), 3) as pct_of_staged_rows
from profile
unpivot (n for check_name in (
    staged_rows, bad_scheme_code, bad_date, nav_not_numeric, nav_not_positive, fact_rows, duplicate_keys_in_fact,
    orphan_fact_rows, schemes, plan_unknown, option_other, weekend_navs
));

-- Schemes with at least one NAV in each calendar year. The sharp year-on-year change tells you whether schemes that
-- were merged or closed are still in the file (survivorship).
create or replace table r03_schemes_by_year as
select
    year(f.nav_date) as nav_year,
    count(distinct f.scheme_code) as schemes_with_nav,
    count(distinct f.scheme_code) filter (where s.last_nav_date < p.as_of_date - to_days(30)) as schemes_that_stop_before_as_of
from fact_nav as f
inner join dim_scheme as s on f.scheme_code = s.scheme_code
cross join params as p
group by 1
order by 1;
