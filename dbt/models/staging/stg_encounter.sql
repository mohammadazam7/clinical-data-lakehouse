select
    id as encounter_key,
    {{ surrogate_id('id') }} as visit_occurrence_id,
    {{ surrogate_id('patient_id') }} as person_id,
    class_code,
    type_system,
    type_code,
    type_display,
    {{ raw_year('"start"') }} as start_year,
    {{ raw_date('"start"') }} as start_date,
    {{ raw_timestamp('"start"') }} as start_datetime,
    {{ raw_year('"end"') }} as end_year,
    {{ raw_date('"end"') }} as end_date,
    {{ raw_timestamp('"end"') }} as end_datetime
from {{ source('raw', 'encounter') }}
