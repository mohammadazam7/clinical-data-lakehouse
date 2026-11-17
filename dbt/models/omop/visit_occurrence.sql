{# 32827 is the OMOP type concept "EHR encounter record". #}
select
    e.visit_occurrence_id,
    e.person_id,
    coalesce(v.concept_id, 0) as visit_concept_id,
    {{ event_date('e.start_date', 'e.start_year') }} as visit_start_date,
    e.start_datetime as visit_start_datetime,
    {{ event_date('e.end_date', 'coalesce(e.end_year, e.start_year)') }} as visit_end_date,
    e.end_datetime as visit_end_datetime,
    32827 as visit_type_concept_id,
    cast(null as bigint) as provider_id,
    cast(null as bigint) as care_site_id,
    e.class_code as visit_source_value,
    0 as visit_source_concept_id,
    0 as admitted_from_concept_id,
    cast(null as varchar) as admitted_from_source_value,
    0 as discharged_to_concept_id,
    cast(null as varchar) as discharged_to_source_value,
    cast(null as bigint) as preceding_visit_occurrence_id
from {{ ref('stg_encounter') }} as e
left join {{ ref('visit_concepts') }} as v on v.class_code = e.class_code
-- Safe Harbor removes every date of a person over 89, so their encounters have no year
-- and cannot be placed in time; they are left out, not given an invented date.
where e.start_year is not null
