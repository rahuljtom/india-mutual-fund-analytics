-- Staging: read the parsed CSV files as text, then type them. Bad values become NULL (try_cast) so they can be
-- counted in the quality report instead of stopping the load.
-- __INTERIM_GLOB__ is replaced by src/mfa/pipeline.py.
create or replace table stg_nav as
select
    try_cast(scheme_code as integer) as scheme_code,
    trim(scheme_name) as scheme_name,
    nullif(trim(plan), '') as plan,
    nullif(trim(option), '') as option_raw,
    nullif(trim(isin_payout_growth), '') as isin_primary,
    try_cast(nav as double) as nav,
    try_strptime(nav_date, '%d-%b-%Y')::date as nav_date,
    amc,
    scheme_type,
    category_raw
from read_csv('__INTERIM_GLOB__', header = true, all_varchar = true);
