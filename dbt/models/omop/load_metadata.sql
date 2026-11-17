{# Not a CDM table: one row describing how to read this build. #}
select
    case when count(start_date) = 0 then 'year' else 'day' end as date_precision,
    count(*) as encounters,
    max(coalesce(end_year, start_year)) as latest_data_year
from {{ ref('stg_encounter') }}
