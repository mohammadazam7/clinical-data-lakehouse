-- Rows returned are failures.
select visit_occurrence_id, visit_start_date, visit_end_date
from {{ ref('visit_occurrence') }}
where visit_end_date < visit_start_date
