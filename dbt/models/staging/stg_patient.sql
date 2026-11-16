select
    id as patient_key,
    {{ surrogate_id('id') }} as person_id,
    lower(gender) as gender,
    {{ raw_year('birth_date') }} as birth_year,
    {{ raw_date('birth_date') }} as birth_date,
    race_code,
    ethnicity_code,
    state,
    postal_code as zip3,
    age_over_89
from {{ source('raw', 'patient') }}
