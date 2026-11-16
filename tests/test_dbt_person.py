"""Build the dbt project on a small raw zone and check the OMOP person table.

These run dbt for real on DuckDB, once per de-identification mode, because the two modes
hand the models different date precision.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from clinical_lakehouse.deid import Mode, Policy, latest_date
from clinical_lakehouse.fhir import ETHNICITY_URL, RACE_URL
from clinical_lakehouse.raw_zone import Provenance, ingest

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"
SALT = b"test-salt-of-sixteen-bytes"
PEOPLE = {
    # id: (gender, birth date, race, ethnicity)
    "p-old": ("female", "1930-03-04", "2106-3", "2186-5"),
    "p-mid": ("male", "1970-06-15", "2054-5", "2135-2"),
    "p-unknown": ("unknown", "1990-12-31", None, None),
}


Built = tuple[Mode, dict[str, tuple[object, ...]]]


def _omb(url: str, code: str) -> dict[str, object]:
    return {"url": url, "extension": [{"url": "ombCategory", "valueCoding": {"code": code}}]}


def _bundle(pid: str) -> dict[str, object]:
    gender, birth, race, ethnicity = PEOPLE[pid]
    patient: dict[str, object] = {
        "resourceType": "Patient",
        "id": pid,
        "gender": gender,
        "birthDate": birth,
        "name": [{"family": "Doe", "given": ["Jo"]}],
        "address": [
            {"line": ["1 Main St"], "city": "Boston", "state": "MA", "postalCode": "02118"}
        ],
        "extension": [
            *([_omb(RACE_URL, race)] if race else []),
            *([_omb(ETHNICITY_URL, ethnicity)] if ethnicity else []),
        ],
    }
    encounter = {
        "resourceType": "Encounter",
        "id": f"{pid}-e1",
        "class": {"code": "AMB"},
        "subject": {"reference": f"urn:uuid:{pid}"},
        "period": {"start": "2024-05-01T09:00:00-04:00", "end": "2024-05-01T09:40:00-04:00"},
    }
    return {"resourceType": "Bundle", "entry": [{"resource": patient}, {"resource": encounter}]}


def _build(tmp_path: Path, mode: Mode) -> duckdb.DuckDBPyConnection:
    src = tmp_path / "fhir"
    src.mkdir()
    for pid in PEOPLE:
        (src / f"{pid}.json").write_text(json.dumps(_bundle(pid)), encoding="utf-8")
    raw = tmp_path / "raw"
    ingest(
        src,
        raw,
        Provenance("synthea", "test", seed=1, population=len(PEOPLE)),
        deid=lambda result: Policy(mode, SALT, latest_date(result)),
    )
    warehouse = tmp_path / "warehouse.duckdb"
    env = {**os.environ, "CLINICAL_RAW": str(raw), "CLINICAL_DUCKDB": str(warehouse)}
    dbt = Path(sys.executable).parent / "dbt"
    run = subprocess.run(
        [str(dbt), "build", "--profiles-dir", ".", "--target-path", str(tmp_path / "target")],
        cwd=DBT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-3000:]
    return duckdb.connect(str(warehouse), read_only=True)


def _people(con: duckdb.DuckDBPyConnection) -> dict[str, tuple[object, ...]]:
    rows = con.execute(
        "select gender_source_value, year_of_birth, month_of_birth, gender_concept_id, "
        "race_concept_id, ethnicity_concept_id, person_source_value from omop.person"
    ).fetchall()
    return {str(r[0]): r[1:] for r in rows}


@pytest.fixture(scope="module", params=list(Mode), ids=lambda m: m.value)
def built(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Built:
    mode: Mode = request.param
    return mode, _people(_build(tmp_path_factory.mktemp(mode.value), mode))


def test_person_has_one_row_per_patient_with_mapped_concepts(built: Built) -> None:
    _, people = built
    assert len(people) == 3
    assert people["male"][2:5] == (8507, 8516, 38003563)
    assert people["female"][2:5] == (8532, 8527, 38003564)
    # Codes with no standard concept map to 0, the OMOP convention, and are not dropped.
    assert people["unknown"][2:5] == (0, 0, 0)


def test_birth_date_precision_follows_the_deidentification_mode(built: Built) -> None:
    mode, people = built
    if mode is Mode.SAFE_HARBOR:
        assert people["male"][:2] == (1970, None)
        # Born in 1930 and 94 at the last encounter: reported as 90 in the latest data year.
        assert people["female"][:2] == (2024 - 90, None)
    else:
        year, month = people["male"][:2]
        assert year in {1969, 1970, 1971} and month is not None


def test_no_original_identifier_reaches_the_warehouse(built: Built) -> None:
    _, people = built
    assert not {str(p[5]) for p in people.values()} & set(PEOPLE)
