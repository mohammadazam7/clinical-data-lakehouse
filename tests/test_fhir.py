import json
from pathlib import Path

import pytest

from clinical_lakehouse.fhir import (
    BundleError,
    first_coding,
    flatten_bundle,
    iter_bundles,
    ref_id,
)

PATIENT = {
    "resourceType": "Patient",
    "id": "p1",
    "gender": "female",
    "birthDate": "1961-04-02",
    "name": [{"family": "Rivera12", "given": ["Ana3", "Luz7"]}],
    "address": [{"line": ["12 Elm St"], "city": "Salem", "state": "MA", "postalCode": "01970"}],
    "telecom": [{"system": "phone", "value": "555-0100"}],
    "extension": [
        {
            "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
            "extension": [{"url": "ombCategory", "valueCoding": {"code": "2106-3"}}],
        }
    ],
}
HBA1C = {
    "resourceType": "Observation",
    "id": "o1",
    "subject": {"reference": "urn:uuid:p1"},
    "encounter": {"reference": "urn:uuid:e1"},
    "category": [{"coding": [{"code": "laboratory"}]}],
    "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "HbA1c"}]},
    "effectiveDateTime": "2020-01-05T10:00:00-05:00",
    "valueQuantity": {"value": 7.9, "unit": "%"},
}


def bundle(*resources: dict[str, object]) -> dict[str, object]:
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{"fullUrl": f"urn:uuid:{r['id']}", "resource": r} for r in resources],
    }


def test_patient_columns_and_race() -> None:
    [row] = flatten_bundle(bundle(PATIENT)).rows["Patient"]
    assert row["gender"] == "female"
    assert row["race_code"] == "2106-3"
    assert row["ethnicity_code"] is None
    assert row["given_name"] == "Ana3 Luz7"
    assert row["postal_code"] == "01970"
    assert row["phone"] == "555-0100"


def test_observation_resolves_references_and_value() -> None:
    [row] = flatten_bundle(bundle(PATIENT, HBA1C)).rows["Observation"]
    assert (row["patient_id"], row["encounter_id"]) == ("p1", "e1")
    assert (row["code_code"], row["value_number"], row["value_unit"]) == ("4548-4", 7.9, "%")
    assert row["category"] == "laboratory"


def test_unmodelled_resources_are_counted_not_dropped_silently() -> None:
    claim = {"resourceType": "Claim", "id": "c1"}
    result = flatten_bundle(bundle(PATIENT, claim, {**claim, "id": "c2"}))
    assert result.skipped == {"Claim": 2}
    assert "Claim" not in result.rows


@pytest.mark.parametrize(
    "bad",
    [
        {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient"}}]},
        {"entry": []},
    ],
)
def test_malformed_input_is_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(BundleError):
        flatten_bundle(bad)


def test_reference_and_coding_helpers() -> None:
    assert ref_id({"reference": "urn:uuid:abc"}) == "abc"
    assert ref_id({"reference": "Patient/abc"}) == "abc"
    assert ref_id(None) is None
    assert first_coding(None) == (None, None, None)


def test_iter_bundles_skips_organisation_files(tmp_path: Path) -> None:
    (tmp_path / "b_patient.json").write_text(json.dumps(bundle(PATIENT)))
    (tmp_path / "hospitalInformation123.json").write_text("{}")
    assert [p.name for p, _ in iter_bundles(tmp_path)] == ["b_patient.json"]


def test_procedure_medication_and_immunization() -> None:
    proc = {
        "resourceType": "Procedure",
        "id": "x1",
        "subject": {"reference": "urn:uuid:p1"},
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "103697008"}]},
        "performedPeriod": {
            "start": "2019-02-09T02:26:05-05:00",
            "end": "2019-02-09T02:38:36-05:00",
        },
    }
    med = {
        "resourceType": "MedicationRequest",
        "id": "m1",
        "status": "completed",
        "subject": {"reference": "urn:uuid:p1"},
        "authoredOn": "2019-02-09T02:26:05-05:00",
        "medicationReference": {"reference": "urn:uuid:med9"},
    }
    imm = {
        "resourceType": "Immunization",
        "id": "i1",
        "patient": {"reference": "urn:uuid:p1"},
        "vaccineCode": {"coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": "140"}]},
        "occurrenceDateTime": "2017-01-28T02:26:05-05:00",
    }
    rows = flatten_bundle(bundle(PATIENT, proc, med, imm)).rows
    assert rows["Procedure"][0]["performed_end"] == "2019-02-09T02:38:36-05:00"
    assert rows["MedicationRequest"][0]["medication_ref"] == "med9"
    assert rows["MedicationRequest"][0]["medication_code"] is None
    assert (rows["Immunization"][0]["patient_id"], rows["Immunization"][0]["vaccine_code"]) == (
        "p1",
        "140",
    )
