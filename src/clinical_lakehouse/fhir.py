"""Flatten FHIR R4 bundles into one row per resource.

Each supported resource type has a flattener that pulls out the columns the OMOP
mapping needs and nothing else. Anything the pipeline does not model is counted, not
dropped silently, so the raw zone manifest can say what was left behind.

References inside a Synthea transaction bundle use ``urn:uuid:<id>`` full URLs, so a
reference is reduced to the bare id of the resource it points at.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Row = dict[str, Any]
Resource = Mapping[str, Any]

RACE_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
ETHNICITY_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"


class BundleError(ValueError):
    pass


def ref_id(reference: Mapping[str, Any] | None) -> str | None:
    """``{"reference": "urn:uuid:abc"}`` or ``"Patient/abc"`` to ``"abc"``."""
    if not reference or "reference" not in reference:
        return None
    value = str(reference["reference"])
    return value.rsplit(":", 1)[-1].rsplit("/", 1)[-1]


def first_coding(concept: Mapping[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    """(system, code, display) of the first coding, or Nones."""
    codings = (concept or {}).get("coding") or []
    if not codings:
        return None, None, None
    c = codings[0]
    return c.get("system"), c.get("code"), c.get("display")


def _omb_category(resource: Resource, url: str) -> str | None:
    for ext in resource.get("extension", []):
        if ext.get("url") == url:
            for part in ext.get("extension", []):
                if part.get("url") == "ombCategory":
                    return str(part["valueCoding"]["code"])
    return None


def _coded(prefix: str, concept: Mapping[str, Any] | None) -> Row:
    system, code, display = first_coding(concept)
    return {f"{prefix}_system": system, f"{prefix}_code": code, f"{prefix}_display": display}


def patient(r: Resource) -> Row:
    name = (r.get("name") or [{}])[0]
    address = (r.get("address") or [{}])[0]
    return {
        "id": r["id"],
        "gender": r.get("gender"),
        "birth_date": r.get("birthDate"),
        "deceased_datetime": r.get("deceasedDateTime"),
        "race_code": _omb_category(r, RACE_URL),
        "ethnicity_code": _omb_category(r, ETHNICITY_URL),
        # Identifiers are kept in the raw zone only so de-identification has something
        # to remove and tests can prove it did; nothing downstream reads them.
        "family_name": name.get("family"),
        "given_name": " ".join(name.get("given", [])) or None,
        "address_line": " ".join(address.get("line", [])) or None,
        "city": address.get("city"),
        "state": address.get("state"),
        "postal_code": address.get("postalCode"),
        "phone": next(
            (t.get("value") for t in r.get("telecom", []) if t.get("system") == "phone"), None
        ),
    }


def encounter(r: Resource) -> Row:
    period = r.get("period") or {}
    return {
        "id": r["id"],
        "patient_id": ref_id(r.get("subject")),
        "class_code": (r.get("class") or {}).get("code"),
        **_coded("type", (r.get("type") or [None])[0]),
        "start": period.get("start"),
        "end": period.get("end"),
    }


def condition(r: Resource) -> Row:
    return {
        "id": r["id"],
        "patient_id": ref_id(r.get("subject")),
        "encounter_id": ref_id(r.get("encounter")),
        **_coded("code", r.get("code")),
        "onset": r.get("onsetDateTime"),
        "abatement": r.get("abatementDateTime"),
    }


def observation(r: Resource) -> Row:
    quantity = r.get("valueQuantity") or {}
    return {
        "id": r["id"],
        "patient_id": ref_id(r.get("subject")),
        "encounter_id": ref_id(r.get("encounter")),
        "category": first_coding((r.get("category") or [None])[0])[1],
        **_coded("code", r.get("code")),
        "effective": r.get("effectiveDateTime"),
        "value_number": quantity.get("value"),
        "value_unit": quantity.get("unit"),
        **_coded("value", r.get("valueCodeableConcept")),
    }


def procedure(r: Resource) -> Row:
    period = r.get("performedPeriod") or {}
    return {
        "id": r["id"],
        "patient_id": ref_id(r.get("subject")),
        "encounter_id": ref_id(r.get("encounter")),
        **_coded("code", r.get("code")),
        "performed_start": period.get("start") or r.get("performedDateTime"),
        "performed_end": period.get("end"),
    }


def medication_request(r: Resource) -> Row:
    # Most Synthea requests carry the drug code inline; some point at a separate
    # Medication resource instead, so the reference is kept for the mapping step.
    return {
        "id": r["id"],
        "patient_id": ref_id(r.get("subject")),
        "encounter_id": ref_id(r.get("encounter")),
        "status": r.get("status"),
        **_coded("medication", r.get("medicationCodeableConcept")),
        "medication_ref": ref_id(r.get("medicationReference")),
        "authored_on": r.get("authoredOn"),
    }


def immunization(r: Resource) -> Row:
    return {
        "id": r["id"],
        "patient_id": ref_id(r.get("patient")),
        "encounter_id": ref_id(r.get("encounter")),
        **_coded("vaccine", r.get("vaccineCode")),
        "occurred": r.get("occurrenceDateTime"),
    }


FLATTENERS: dict[str, Callable[[Resource], Row]] = {
    "Patient": patient,
    "Encounter": encounter,
    "Condition": condition,
    "Observation": observation,
    "Procedure": procedure,
    "MedicationRequest": medication_request,
    "Immunization": immunization,
}


@dataclass
class FlattenResult:
    rows: dict[str, list[Row]] = field(default_factory=dict)
    skipped: Counter[str] = field(default_factory=Counter)

    def add(self, other: FlattenResult) -> None:
        for kind, rows in other.rows.items():
            self.rows.setdefault(kind, []).extend(rows)
        self.skipped.update(other.skipped)


def flatten_bundle(bundle: Mapping[str, Any]) -> FlattenResult:
    if bundle.get("resourceType") != "Bundle":
        raise BundleError("not a FHIR Bundle")
    result = FlattenResult()
    for entry in bundle.get("entry", []):
        resource = entry.get("resource") or {}
        kind = resource.get("resourceType")
        if not kind or "id" not in resource:
            raise BundleError("bundle entry without resourceType or id")
        flatten = FLATTENERS.get(kind)
        if flatten is None:
            result.skipped[kind] += 1
            continue
        result.rows.setdefault(kind, []).append(flatten(resource))
    return result


def iter_bundles(directory: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Patient bundles in name order. Synthea's hospital and practitioner files are
    exported separately and skipped here because they carry no patients."""
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith(("hospitalInformation", "practitionerInformation")):
            continue
        yield path, json.loads(path.read_text(encoding="utf-8"))
