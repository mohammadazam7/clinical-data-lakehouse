{#
  OMOP requires year_of_birth, but Safe Harbor removes the birth date of anyone over 89
  because the year alone would reveal the age. Those people get the latest year in the
  data minus 90, HIPAA's single "90 or older" category, so they stay in the table without
  their real birth year coming back.
#}
with latest as (
    select max(coalesce(end_year, start_year)) as data_year from {{ ref('stg_encounter') }}
),

concepts as (
    select * from {{ ref('demographic_concepts') }}
)

select
    p.person_id,
    coalesce(g.concept_id, 0) as gender_concept_id,
    case
        when p.age_over_89 then coalesce(p.birth_year, latest.data_year - 90)
        else p.birth_year
    end as year_of_birth,
    cast(extract(month from p.birth_date) as integer) as month_of_birth,
    cast(extract(day from p.birth_date) as integer) as day_of_birth,
    cast(p.birth_date as timestamp) as birth_datetime,
    coalesce(r.concept_id, 0) as race_concept_id,
    coalesce(e.concept_id, 0) as ethnicity_concept_id,
    cast(null as bigint) as location_id,
    cast(null as bigint) as provider_id,
    cast(null as bigint) as care_site_id,
    p.patient_key as person_source_value,
    p.gender as gender_source_value,
    0 as gender_source_concept_id,
    p.race_code as race_source_value,
    0 as race_source_concept_id,
    p.ethnicity_code as ethnicity_source_value,
    0 as ethnicity_source_concept_id
from {{ ref('stg_patient') }} as p
cross join latest
left join concepts as g on g.source_vocabulary = 'gender' and g.source_code = p.gender
left join concepts as r on r.source_vocabulary = 'race' and r.source_code = p.race_code
left join concepts as e on e.source_vocabulary = 'ethnicity' and e.source_code = p.ethnicity_code
