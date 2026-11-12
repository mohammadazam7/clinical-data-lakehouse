# clinical-data-lakehouse

[![CI](https://github.com/mohammadazam7/clinical-data-lakehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammadazam7/clinical-data-lakehouse/actions/workflows/ci.yml)

Turn FHIR R4 patient records into a tested OMOP CDM 5.4 warehouse with one command, on
DuckDB or BigQuery.

> **Status:** in development. Ingestion and de-identification work (milestone 1); the
> OMOP models are next. No benchmark numbers yet; they appear here once measured. See
> the [roadmap](docs/ROADMAP.md).

## Why

If your data is in OMOP, every OHDSI study, tool and package runs on it. Getting FHIR
into OMOP is where teams lose months: nested resources, code mapping, visit and
observation period rules, and no good way to prove the result is complete. I want this
to be the pipeline you can run on Monday and trust on Tuesday.

## What it will do

- Generate synthetic patients with a pinned Synthea release, or take your own FHIR R4
  bundles.
- Flatten and check every resource, then de-identify before anything is modelled
  (HIPAA Safe Harbor, or per-patient date shifting for research).
- Build the OMOP CDM 5.4 clinical tables in dbt, with contracts, tests and incremental
  loads, on DuckDB or BigQuery.
- Map SNOMED, LOINC and RxNorm codes to standard concepts and report what did not map.
- Run data quality checks in the style of the OHDSI Data Quality Dashboard.
- Publish care gap and quality measures (diabetes control, 30-day readmissions, cancer
  screening) through one metric layer and a LookML model.

The full reasoning is in the [design doc](docs/design.md).

## Quick start

Everything below runs on synthetic patients. You need Python 3.11+ and Java 17+.

```bash
pip install -e ".[dev]"
scripts/generate_synthea.sh 100 7 Massachusetts data/synthea   # pinned Synthea v4.0.0

export CLINICAL_LAKEHOUSE_SALT="$(openssl rand -hex 32)"         # keep this secret
clinical-lakehouse ingest data/synthea/fhir --out data/raw \
  --generator-version v4.0.0 --seed 7 --population 100
clinical-lakehouse verify data/synthea/fhir --out data/raw
```

`ingest` flattens the FHIR bundles, de-identifies them (Safe Harbor by default,
`--deid date_shift` to keep intervals) and writes one Parquet file per resource type
plus `manifest.json`. The manifest records the generator, seed, a checksum per source
file, row counts and the resource types that were skipped, but never the salt.
`verify` rechecks all of that and fails if a de-identified table still has a name,
address or phone column. The OMOP models come next; see the [roadmap](docs/ROADMAP.md).

## Data and privacy

Everything here is built and tested on synthetic patients from
[Synthea](https://github.com/synthetichealth/synthea). No real patient data goes in this
repository, its issues or its CI. Vocabulary files are not redistributed here; see the
design doc for how concepts are sourced. [SECURITY.md](SECURITY.md) explains what the
de-identification step does and does not promise.

## License

MIT for the code in this repository. Synthea and the OHDSI vocabularies keep their own
licences.
