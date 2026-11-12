from datetime import date

import pytest

from clinical_lakehouse.deid import Mode, Policy, age_on, deidentify, leaked, pseudonym, zip3
from clinical_lakehouse.fhir import FlattenResult

SALT = b"0123456789abcdef-test-salt"
AS_OF = date(2026, 11, 1)


def sample() -> FlattenResult:
    result = FlattenResult()
    result.rows["Patient"] = [
        {
            "id": "p-young",
            "gender": "female",
            "birth_date": "1961-04-02",
            "deceased_datetime": None,
            "race_code": "2106-3",
            "ethnicity_code": None,
            "family_name": "Rivera12",
            "given_name": "Ana3",
            "address_line": "12 Elm St",
            "city": "Salem",
            "state": "MA",
            "postal_code": "01970",
            "phone": "555-0100",
        },
        {
            "id": "p-old",
            "gender": "male",
            "birth_date": "1930-06-30",
            "deceased_datetime": None,
            "race_code": None,
            "ethnicity_code": None,
            "family_name": "Okafor9",
            "given_name": "Ben2",
            "address_line": "4 Pine Rd",
            "city": "Rawlins",
            "state": "WY",
            "postal_code": "82301",
            "phone": None,
        },
    ]
    result.rows["Encounter"] = [
        {
            "id": "e1",
            "patient_id": "p-young",
            "class_code": "IMP",
            "start": "2020-03-01T08:00:00-05:00",
            "end": "2020-03-05T10:00:00-05:00",
        },
        {
            "id": "e2",
            "patient_id": "p-old",
            "class_code": "AMB",
            "start": "2021-07-09T09:00:00-04:00",
            "end": "2021-07-09T09:30:00-04:00",
        },
    ]
    return result


def policy(mode: Mode) -> Policy:
    return Policy(mode=mode, salt=SALT, as_of=AS_OF)


def test_names_address_city_and_phone_are_removed() -> None:
    out = deidentify(sample(), policy(Mode.SAFE_HARBOR))
    for row in out.rows["Patient"]:
        for col in ("family_name", "given_name", "address_line", "city", "phone"):
            assert col not in row
    originals = {"names": ["Rivera12", "Ana3", "Okafor9", "Ben2"], "places": ["12 Elm St", "Salem"]}
    assert leaked(out.rows["Patient"], originals) == []


def test_zip_is_cut_to_three_digits_and_small_areas_become_000() -> None:
    assert zip3("01970") == "019"
    assert zip3("82001") == "820"
    assert zip3("82301") == "000"  # 823 has 20,000 people or fewer
    assert zip3(None) is None


def test_safe_harbor_keeps_only_the_year_of_every_date() -> None:
    out = deidentify(sample(), policy(Mode.SAFE_HARBOR))
    young = next(r for r in out.rows["Patient"] if r["state"] == "MA")
    assert young["birth_date"] == "1961"
    enc = out.rows["Encounter"][0]
    assert (enc["start"], enc["end"]) == ("2020", "2020")


def test_patients_over_89_lose_every_date_that_would_reveal_their_age() -> None:
    assert age_on("1930-06-30", AS_OF) == 96
    out = deidentify(sample(), policy(Mode.SAFE_HARBOR))
    old = next(r for r in out.rows["Patient"] if r["state"] == "WY")
    assert old["age_over_89"] is True and old["birth_date"] is None
    their_visit = out.rows["Encounter"][1]
    assert their_visit["start"] is None and their_visit["end"] is None


def test_ids_are_keyed_pseudonyms_consistent_across_tables() -> None:
    out = deidentify(sample(), policy(Mode.SAFE_HARBOR))
    young_id = pseudonym("p-young", SALT)
    assert young_id in {r["id"] for r in out.rows["Patient"]}
    assert out.rows["Encounter"][0]["patient_id"] == young_id
    assert young_id != pseudonym("p-young", b"another-salt-of-16+bytes")
    assert leaked(out.rows["Encounter"], {"ids": ["p-young", "p-old", "e1", "e2"]}) == []


def test_date_shift_keeps_intervals_within_a_patient() -> None:
    out = deidentify(sample(), policy(Mode.DATE_SHIFT))
    enc = out.rows["Encounter"][0]
    assert enc["start"] != "2020-03-01T08:00:00-05:00"
    from datetime import datetime

    stay = datetime.fromisoformat(enc["end"]) - datetime.fromisoformat(enc["start"])
    assert stay.days == 4 and stay.seconds == 2 * 3600
    patient = next(r for r in out.rows["Patient"] if r["state"] == "MA")
    assert len(patient["birth_date"]) == 10  # a full, shifted date


def test_input_is_not_modified_and_short_salts_are_refused() -> None:
    original = sample()
    deidentify(original, policy(Mode.SAFE_HARBOR))
    assert original.rows["Patient"][0]["family_name"] == "Rivera12"
    with pytest.raises(ValueError):
        Policy(mode=Mode.SAFE_HARBOR, salt=b"short", as_of=AS_OF)
