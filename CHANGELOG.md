# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-11-13

### Added
- `scripts/generate_synthea.sh`: Synthea v4.0.0 pinned by checksum, with fixed patient
  seed, clinician seed and reference date so the same arguments give the same patients.
- FHIR R4 flattening for Patient, Encounter, Condition, Observation, Procedure,
  MedicationRequest and Immunization; other resource types are counted, not dropped
  silently.
- De-identification before anything is written: HIPAA Safe Harbor (year-only dates,
  three-digit ZIPs with the small-area rule, ages over 89, keyed pseudonyms for ids) or
  per-patient date shifting.
- A Parquet raw zone with a deterministic manifest, and `clinical-lakehouse ingest` and
  `verify`.

[Unreleased]: https://github.com/mohammadazam7/clinical-data-lakehouse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mohammadazam7/clinical-data-lakehouse/releases/tag/v0.1.0
