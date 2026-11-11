-- Would a simple selection selection_rule have beaten the category average? Walk-forward test: on 31 December of each formation year
-- (2020 to 2024), use only what was known then (the trailing 24 months) to pick schemes inside each category, then measure
-- what the picks returned over the next 12 months relative to the average scheme in the same category. No later information is
-- used to choose. Schemes with no NAV at the end of the forward year (closed, merged) are counted as vanished, and the
-- excess return is measured on the schemes that survived, so the results can only be flattered, never hurt, by survivorship.
create or replace table backtest_panel as
with formation as (
    select
        y as formation_year,
        y * 12 + 12 as m0
    from (select unnest([2020, 2021, 2022, 2023, 2024]) as y) as years
),

v as (
    select
        r.scheme_code,
        f2.formation_year,
        stddev_samp(r.monthly_return) as vol,
        count(*) as months
    from formation as f2
    inner join monthly_returns as r on r.month_idx between f2.m0 - 23 and f2.m0
    group by r.scheme_code, f2.formation_year
    having count(*) = 24
),

lookback as (
    select
        f.formation_year,
        u.sub_category,
        e.scheme_code,
        power(e.nav / s.nav, 0.5) - 1 as trailing_cagr,
        v.vol,
        fwd.nav / e.nav - 1 as forward_return
    from formation as f
    inner join monthly_nav as e on f.m0 = e.month_idx
    inner join monthly_nav as s on e.scheme_code = s.scheme_code and s.month_idx = f.m0 - 24
    inner join analysis_universe as u on e.scheme_code = u.scheme_code
    inner join v on e.scheme_code = v.scheme_code and f.formation_year = v.formation_year
    left join monthly_nav as fwd on e.scheme_code = fwd.scheme_code and fwd.month_idx = f.m0 + 12
),

sized as (
    select
        *,
        count(*) over (partition by formation_year, sub_category) as schemes_in_category
    from lookback
)

select
    formation_year,
    sub_category,
    scheme_code,
    trailing_cagr,
    vol,
    forward_return,
    ntile(4) over (partition by formation_year, sub_category order by trailing_cagr desc, scheme_code asc) as trailing_quartile,
    ntile(3) over (partition by formation_year, sub_category order by vol asc, scheme_code asc) as vol_tercile,
    avg(forward_return) over (partition by formation_year, sub_category) as category_forward_avg
from sized
where schemes_in_category >= (select min_schemes_per_category from params);

create or replace table backtest_picks as
select
    'Top quartile of trailing 2-year return' as selection_rule,
    1 as sort_order,
    formation_year,
    scheme_code,
    forward_return,
    forward_return - category_forward_avg as excess
from backtest_panel
where trailing_quartile = 1
union all
select
    'Everything except the bottom quartile' as selection_rule,
    2 as sort_order,
    formation_year,
    scheme_code,
    forward_return,
    forward_return - category_forward_avg as excess
from backtest_panel
where trailing_quartile < 4
union all
select
    'Bottom quartile (the avoid list)' as selection_rule,
    3 as sort_order,
    formation_year,
    scheme_code,
    forward_return,
    forward_return - category_forward_avg as excess
from backtest_panel
where trailing_quartile = 4
union all
select
    'Lowest-volatility third' as selection_rule,
    4 as sort_order,
    formation_year,
    scheme_code,
    forward_return,
    forward_return - category_forward_avg as excess
from backtest_panel
where vol_tercile = 1;

create or replace table r10_backtest_by_year as
select
    selection_rule,
    formation_year,
    count(*) as picks,
    count(excess) as survivors,
    round(100 * avg(excess), 2) as avg_excess_pp,
    round(100 * avg(forward_return), 2) as avg_forward_return_pct
from backtest_picks
group by selection_rule, sort_order, formation_year
order by sort_order asc, formation_year asc;

create or replace table r10_backtest_summary as
with yearly as (
    select
        selection_rule,
        sort_order,
        formation_year,
        avg(excess) as year_excess
    from backtest_picks
    group by selection_rule, sort_order, formation_year
)

select
    p.selection_rule,
    count(*) as picks,
    count(p.excess) as survivors,
    round(100.0 * (1 - count(p.excess)::double / count(*)), 1) as pct_vanished,
    round(100 * avg(p.excess), 2) as avg_excess_pp,
    round(100 * median(p.excess), 2) as median_excess_pp,
    round(100.0 * avg((p.excess > 0)::integer), 1) as pct_picks_beating_category,
    (
        select count(*) from yearly as y
        where y.selection_rule = p.selection_rule and y.year_excess > 0
    ) as years_positive,
    (
        select count(*) from yearly as y
        where y.selection_rule = p.selection_rule
    ) as years_tested
from backtest_picks as p
group by p.selection_rule, p.sort_order
order by p.sort_order asc;
