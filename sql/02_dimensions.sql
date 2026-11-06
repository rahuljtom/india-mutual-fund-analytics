-- Star schema. Dimensions carry primary and foreign keys; fact_nav carries a CHECK and is verified for
-- duplicate keys in the quality step (a primary key on ~16M rows slows the load far more than it helps).
-- Scheme attributes can change over time (renames, category moves); each scheme keeps its latest values.
drop table if exists fact_nav;
drop table if exists dim_scheme;
drop table if exists dim_category;
drop table if exists dim_amc;

create table dim_amc (
    amc_id integer primary key,
    amc_name varchar not null unique
);

create table dim_category (
    category_id integer primary key,
    scheme_type varchar not null,
    category_raw varchar not null,
    asset_class varchar not null,
    sub_category varchar not null,
    unique (scheme_type, category_raw)
);

create table dim_scheme (
    scheme_code integer primary key,
    scheme_name varchar not null,
    amc_id integer not null references dim_amc (amc_id),
    category_id integer not null references dim_category (category_id),
    plan_type varchar not null check (plan_type in ('Direct', 'Regular', 'Unknown')),
    option_type varchar not null check (option_type in ('Growth', 'IDCW', 'Other')),
    isin_primary varchar,
    first_nav_date date not null,
    last_nav_date date not null
);

create table fact_nav (
    scheme_code integer not null,
    nav_date date not null,
    nav double not null check (nav > 0)
);

insert into dim_amc
select
    row_number() over (order by amc) as amc_id,
    amc
from (
    select distinct amc from stg_nav
    where amc is not null
);

insert into dim_category
select
    row_number() over (order by scheme_type, category_raw) as category_id,
    scheme_type,
    category_raw,
    trim(split_part(category_raw, ' - ', 1)) as asset_class,
    coalesce(nullif(trim(substr(category_raw, strpos(category_raw, ' - ') + 3)), ''), category_raw) as sub_category
from (select distinct
    scheme_type,
    category_raw
from stg_nav
where category_raw is not null);

insert into dim_scheme
with latest as (
    select
        scheme_code,
        arg_max(scheme_name, nav_date) as scheme_name,
        arg_max(plan, nav_date) as plan,
        arg_max(option_raw, nav_date) as option_raw,
        arg_max(isin_primary, nav_date) as isin_primary,
        arg_max(amc, nav_date) as amc,
        arg_max(scheme_type, nav_date) as scheme_type,
        arg_max(category_raw, nav_date) as category_raw,
        min(nav_date) as first_nav_date,
        max(nav_date) as last_nav_date
    from stg_nav
    where scheme_code is not null and nav_date is not null and nav > 0
    group by scheme_code
)

select
    l.scheme_code,
    l.scheme_name,
    a.amc_id,
    c.category_id,
    case
        when l.plan ilike 'direct%' or l.scheme_name ilike '%direct%' then 'Direct'
        when l.plan ilike 'regular%' or l.scheme_name ilike '%regular%' then 'Regular'
        else 'Unknown'
    end as plan_type,
    case
        when
            l.option_raw ilike '%idcw%' or l.option_raw ilike '%dividend%' or l.scheme_name ilike '%idcw%'
            or l.scheme_name ilike '%dividend%' or l.scheme_name ilike '%payout%' then 'IDCW'
        when l.option_raw ilike '%growth%' or l.scheme_name ilike '%growth%' then 'Growth'
        else 'Other'
    end as option_type,
    l.isin_primary,
    l.first_nav_date,
    l.last_nav_date
from latest as l
inner join dim_amc as a on l.amc = a.amc_name
inner join dim_category as c on l.scheme_type = c.scheme_type and l.category_raw = c.category_raw;

-- One row per scheme and date. Duplicates (windows overlap at their edges) keep the first row.
insert into fact_nav
select
    scheme_code,
    nav_date,
    nav
from stg_nav
where scheme_code is not null and nav_date is not null and nav > 0
qualify row_number() over (partition by scheme_code, nav_date order by nav) = 1;
