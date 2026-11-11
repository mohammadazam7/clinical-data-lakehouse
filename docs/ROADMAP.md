# Roadmap

Target: v1.0 on **Dec 13, 2026**. Each milestone ends in a merge to main, a tagged
release and a changelog entry.

- [x] **M0 (Nov 10): foundation.** Repository, CI, design doc, roadmap.
- [ ] **M1 (Nov 11 to 17): synthetic patients in, raw zone out.** Synthea pinned to one
  release, seed and population; FHIR R4 bundles flattened into a Parquet raw zone with a
  manifest; schema and reference checks on every resource; the de-identification step
  with tests for each Safe Harbor identifier.
- [ ] **M2 (Nov 18 to 25): OMOP CDM 5.4 in dbt.** person, observation_period,
  visit_occurrence, condition_occurrence, drug_exposure, measurement,
  procedure_occurrence, observation and death, with enforced contracts and incremental
  loads. Vocabulary mapping from SNOMED, LOINC and RxNorm codes through a pinned
  concept subset, or a full vocabulary download if the user has one. Row counts and
  concept coverage compared against the OHDSI Eunomia Synthea reference.
- [ ] **M3 (Nov 26 to Dec 3): quality and measures.** Data quality checks in the style
  of the OHDSI Data Quality Dashboard (conformance, completeness, plausibility) with a
  report; care gap and quality measure marts (HbA1c control in diabetes, 30-day
  all-cause readmission, colorectal and breast cancer screening) behind a governed
  metric layer and a LookML model.
- [ ] **M4 (Dec 4 to 10): scale and the app.** One command from nothing to a
  populated warehouse, the BigQuery target, a throughput benchmark at 1,000, 10,000 and
  100,000 patients with hardware stated, and the Patient Journey 3D web app.
- [ ] **M5 (Dec 11 to 13): v1.0.** Runbook, final design doc and ADRs, demo video,
  release.
