{#
  One period per person, from their first visit to their last. Synthea records a life
  as a single continuous history, so there are no gaps to split on. 32827 is the type
  concept "EHR encounter record".
#}
select
    person_id as observation_period_id,
    person_id,
    min(visit_start_date) as observation_period_start_date,
    max(visit_end_date) as observation_period_end_date,
    32827 as period_type_concept_id
from {{ ref('visit_occurrence') }}
group by person_id
