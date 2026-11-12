"""De-identify flattened rows before anything is written to the raw zone.

Two modes:

``safe_harbor``
    Removes or generalises the HIPAA Safe Harbor identifiers that appear in the
    flattened tables: names, street address, city, phone, every date element except the
    year, ZIP codes beyond their first three digits (or entirely, for the three-digit
    areas with 20,000 people or fewer), ages over 89, and record identifiers.

``date_shift``
    Same removals, but dates are moved by a per-patient offset instead of cut to the
    year, so intervals inside one patient's record (length of stay, days to
    readmission) survive. This is not Safe Harbor: it suits a limited data set or an
    expert determination, and the README says so.

Identifiers are replaced with a keyed hash (HMAC-SHA256 with a secret salt), so the
same patient keeps the same id across tables and loads, but the id cannot be traced
back without the salt.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from clinical_lakehouse.fhir import FlattenResult, Row

# Three-digit ZIP areas with 20,000 people or fewer, which Safe Harbor requires to be
# reported as 000 (HHS guidance, based on 2000 Census data).
RESTRICTED_ZIP3 = frozenset(
    {
        "036", "059", "063", "102", "203", "556", "692", "790", "821",
        "823", "830", "831", "878", "879", "884", "890", "893",
    }
)  # fmt: skip

DIRECT_IDENTIFIERS = ("family_name", "given_name", "address_line", "city", "phone")
ID_COLUMNS = ("id", "patient_id", "encounter_id")
DATE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "Patient": ("birth_date", "deceased_datetime"),
    "Encounter": ("start", "end"),
    "Condition": ("onset", "abatement"),
    "Observation": ("effective",),
}
MAX_SHIFT_DAYS = 365


class Mode(Enum):
    SAFE_HARBOR = "safe_harbor"
    DATE_SHIFT = "date_shift"


@dataclass(frozen=True)
class Policy:
    mode: Mode
    salt: bytes
    as_of: date

    def __post_init__(self) -> None:
        if len(self.salt) < 16:
            raise ValueError("salt must be at least 16 bytes")


def pseudonym(value: str, salt: bytes) -> str:
    return hmac.new(salt, value.encode(), hashlib.sha256).hexdigest()[:24]


def zip3(postal_code: str | None) -> str | None:
    if not postal_code:
        return None
    prefix = postal_code.strip()[:3]
    return "000" if prefix in RESTRICTED_ZIP3 else prefix


def _parse(value: str) -> datetime:
    if len(value) == 10:
        return datetime.fromisoformat(value + "T00:00:00")
    return datetime.fromisoformat(value)


def _year(value: str | None) -> str | None:
    return value[:4] if value else None


def _shift_days(patient_id: str, salt: bytes) -> int:
    digest = hmac.new(salt, b"shift:" + patient_id.encode(), hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") % (2 * MAX_SHIFT_DAYS + 1) - MAX_SHIFT_DAYS


def _shift(value: str | None, days: int) -> str | None:
    if not value:
        return None
    shifted = _parse(value) + timedelta(days=days)
    return shifted.date().isoformat() if len(value) == 10 else shifted.isoformat()


def age_on(birth: str, on: date) -> int:
    b = _parse(birth).date()
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


def _patient_fields(row: Row, policy: Policy) -> Row:
    out = {k: v for k, v in row.items() if k not in DIRECT_IDENTIFIERS}
    out["postal_code"] = zip3(row.get("postal_code"))
    birth = row.get("birth_date")
    end = _parse(row["deceased_datetime"]).date() if row.get("deceased_datetime") else policy.as_of
    out["age_over_89"] = birth is not None and age_on(str(birth), end) > 89
    if out["age_over_89"] and policy.mode is Mode.SAFE_HARBOR:
        # A birth year alone would reveal an age over 89, so it goes too.
        out["birth_date"] = None
    return out


def latest_date(result: FlattenResult) -> date:
    """Latest encounter end in the data: a deterministic ``as_of`` for age checks."""
    ends = [r["end"] or r["start"] for r in result.rows.get("Encounter", []) if r.get("start")]
    if not ends:
        raise ValueError("no encounters to take an as-of date from; pass one explicitly")
    return max(_parse(e).date() for e in ends)


def deidentify(result: FlattenResult, policy: Policy) -> FlattenResult:
    """A new result with identifiers removed; ``result`` is not modified."""
    patients = {r["id"]: r for r in result.rows.get("Patient", [])}
    over_89 = {pid for pid, r in patients.items() if _patient_fields(r, policy)["age_over_89"]}
    out = FlattenResult(skipped=result.skipped.copy())
    for kind, rows in result.rows.items():
        out.rows[kind] = [_row(kind, r, policy, over_89) for r in rows]
    return out


def _row(kind: str, row: Row, policy: Policy, over_89: set[str]) -> Row:
    owner = row["id"] if kind == "Patient" else row.get("patient_id")
    new: dict[str, Any] = _patient_fields(row, policy) if kind == "Patient" else dict(row)
    for col in DATE_COLUMNS.get(kind, ()):
        if policy.mode is Mode.SAFE_HARBOR:
            # Dates of someone over 89 would reveal their age, so they are dropped.
            new[col] = None if owner in over_89 else _year(new.get(col))
        elif owner:
            new[col] = _shift(new.get(col), _shift_days(owner, policy.salt))
    for col in ID_COLUMNS:
        if new.get(col):
            new[col] = pseudonym(str(new[col]), policy.salt)
    return new


def leaked(rows: Iterable[Row], originals: Mapping[str, Iterable[str]]) -> list[str]:
    """Original identifier values that still appear anywhere in ``rows``.

    Used by tests and by ``verify`` as a last check before data leaves the step.
    """
    needles = {v for values in originals.values() for v in values if v}
    found = set()
    for row in rows:
        for value in row.values():
            if isinstance(value, str) and value in needles:
                found.add(value)
    return sorted(found)
