-- The mess in the source and what was done about it: row counts at each filter, how many category labels collapse into one,
-- and the problems that would have changed the answer if ignored. Counts come from the staged data, not a hand list.
create or replace table r13_funnel as
with counts as (
    select
        (select count(*) from stg_nav) as staged_rows,
        (select count(*) from fact_nav) as valid_rows,
        (
            select count(*) from nav_series as n inner join analysis_universe as u on n.scheme_code = u.scheme_code
            where not u.is_benchmark
        ) as analysis_rows,
        (select count(*) from dim_scheme) as all_schemes,
        (
            select count(*) from dim_scheme
            where plan_type <> 'Unknown' and option_type <> 'Other'
        ) as classified_schemes,
        (
            select count(*) from dim_scheme as s inner join dim_category as c on s.category_id = c.category_id
            where c.scheme_type = 'Open Ended' and c.asset_class = 'Equity Scheme'
        ) as open_ended_equity_schemes,
        (
            select count(*) from analysis_universe
            where not is_benchmark
        ) as direct_growth_equity_schemes
)

select
    step_order,
    step_name,
    nav_rows,
    schemes
from (
    select
        1 as step_order,
        'Daily NAV lines parsed from AMFI reports' as step_name,
        staged_rows as nav_rows,
        null::bigint as schemes
    from counts
    union all
    select
        2 as step_order,
        'Valid NAV (a positive number)' as step_name,
        valid_rows as nav_rows,
        all_schemes as schemes
    from counts
    union all
    select
        3 as step_order,
        'Plan and option identified' as step_name,
        null::bigint as nav_rows,
        classified_schemes as schemes
    from counts
    union all
    select
        4 as step_order,
        'Open-ended equity schemes (all plans)' as step_name,
        null::bigint as nav_rows,
        open_ended_equity_schemes as schemes
    from counts
    union all
    select
        5 as step_order,
        'Direct plan, Growth option: the analysis universe' as step_name,
        analysis_rows as nav_rows,
        direct_growth_equity_schemes as schemes
    from counts
) as steps
order by step_order;

-- The same category appears under different labels across years. Raw label, the label used in the analysis, schemes under it.
create or replace table r13_category_harmonisation as
select
    c.category_raw,
    c.sub_category,
    count(*) as schemes,
    count(*) over (partition by c.sub_category) as raw_labels_in_group
from dim_scheme as s
inner join dim_category as c on s.category_id = c.category_id
where c.asset_class = 'Equity Scheme' and c.scheme_type = 'Open Ended'
group by c.category_raw, c.sub_category, c.scheme_type
order by c.sub_category asc, c.category_raw asc;

create or replace table r13_data_mess as
with zero_examples as (
    select string_agg(scheme_name, '; ') as sample_values
    from (
        select scheme_name
        from stg_nav
        where nav <= 0
        group by scheme_name
        order by count(*) desc, scheme_name asc
        limit 2
    ) as e
)

select
    issue,
    rows_affected,
    sample_value,
    handling,
    if_ignored
from (
    select
        1 as sort_order,
        'NAV of zero' as issue,
        (
            select count(*) from stg_nav
            where nav <= 0
        ) as rows_affected,
        (select sample_values from zero_examples) as sample_value,
        'Dropped before any return is formed' as handling,
        'A zero NAV followed by a normal one is a false -100% day then an infinite gain' as if_ignored
    union all
    select
        2 as sort_order,
        'NAV not a number' as issue,
        (
            select count(*) from stg_nav
            where nav is null
        ) as rows_affected,
        'N.A. or blank in the NAV column' as sample_value,
        'Read as text, converted with try_cast, counted and dropped' as handling,
        'A strict numeric load would fail on the first one' as if_ignored
    union all
    select
        3 as sort_order,
        'Category labels that mean the same thing' as issue,
        (
            select count(*) from dim_category
            where asset_class = 'Equity Scheme' and scheme_type = 'Open Ended'
        ) as rows_affected,
        'Equity Scheme - Large Cap Fund vs Equity Schemes - Large Cap Fund' as sample_value,
        'Mapped to one harmonised sub-category with a tested rule table' as handling,
        'One category would be split in two and each half would fall under the minimum size' as if_ignored
    union all
    select
        4 as sort_order,
        'Scheme names containing a comma' as issue,
        (
            select count(*) from dim_scheme
            where scheme_name like '%,%'
        ) as rows_affected,
        (
            select min(scheme_name) from dim_scheme
            where scheme_name like '%,%'
        ) as sample_value,
        'Delimiter and quoting set explicitly when reading the files' as handling,
        'Auto-detection guessed a different delimiter and shifted every column' as if_ignored
    union all
    select
        5 as sort_order,
        'Plan or option could not be identified' as issue,
        (
            select count(*) from dim_scheme
            where plan_type = 'Unknown' or option_type = 'Other'
        ) as rows_affected,
        'Scheme names with neither Direct nor Regular, or an unusual option' as sample_value,
        'Left out of the analysis universe, counted here' as handling,
        'Dividend payouts would be read as losses against Growth NAVs' as if_ignored
    union all
    select
        6 as sort_order,
        'Schemes that closed or merged before the end' as issue,
        (
            select schemes_that_stop_before_as_of from r03_schemes_by_year
            where nav_year = 2018
        ) as rows_affected,
        (
            select 'Of ' || format('{:,}', schemes_with_nav) || ' schemes with a NAV in 2018, ' || format('{:,}', schemes_that_stop_before_as_of) || ' have none by the end of 2025' from r03_schemes_by_year
            where nav_year = 2018
        ) as sample_value,
        'Kept in the history; vanished schemes are reported, not dropped' as handling,
        'A list of today''s funds would hide the funds that failed' as if_ignored
) as issues
order by sort_order;
