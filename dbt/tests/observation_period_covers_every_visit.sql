-- Rows returned are failures: a visit outside its person's observation period.
select v.visit_occurrence_id
from {{ ref('visit_occurrence') }} as v
join {{ ref('observation_period') }} as o using (person_id)
where v.visit_start_date < o.observation_period_start_date
   or v.visit_end_date > o.observation_period_end_date
