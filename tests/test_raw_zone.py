import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from clinical_lakehouse.raw_zone import MANIFEST, Provenance, ingest, verify

PROV = Provenance(generator="synthea", version="v4.0.0", seed=7, population=2)


def _bundle(pid: str, n_obs: int) -> dict[str, object]:
    resources = [
        {"resourceType": "Patient", "id": pid, "gender": "male", "birthDate": "1970-01-01"}
    ]
    resources += [
        {
            "resourceType": "Observation",
            "id": f"{pid}-o{i}",
            "subject": {"reference": f"urn:uuid:{pid}"},
        }
        for i in range(n_obs)
    ]
    resources.append(
        {
            "resourceType": "Encounter",
            "id": f"{pid}-e",
            "subject": {"reference": f"urn:uuid:{pid}"},
            "period": {"start": "2024-05-01T09:00:00-04:00", "end": "2024-05-01T09:40:00-04:00"},
        }
    )
    resources.append({"resourceType": "Claim", "id": f"{pid}-c"})
    return {"resourceType": "Bundle", "entry": [{"resource": r} for r in resources]}


@pytest.fixture
def bundles(tmp_path: Path) -> Path:
    src = tmp_path / "fhir"
    src.mkdir()
    (src / "a.json").write_text(json.dumps(_bundle("p1", 2)))
    (src / "b.json").write_text(json.dumps(_bundle("p2", 1)))
    return src


def test_ingest_writes_tables_and_manifest(bundles: Path, tmp_path: Path) -> None:
    out = tmp_path / "raw"
    manifest = ingest(bundles, out, PROV)
    assert manifest["tables"] == {"encounter": 2, "observation": 3, "patient": 2}
    assert manifest["skipped"] == {"Claim": 2}
    assert manifest["generator"]["seed"] == 7
    assert set(manifest["sources"]) == {"a.json", "b.json"}
    assert pq.read_table(out / "patient.parquet").column("id").to_pylist() == ["p1", "p2"]
    assert verify(out, bundles) == []


def test_manifest_is_deterministic(bundles: Path, tmp_path: Path) -> None:
    ingest(bundles, tmp_path / "one", PROV)
    ingest(bundles, tmp_path / "two", PROV)
    assert (tmp_path / "one" / MANIFEST).read_bytes() == (tmp_path / "two" / MANIFEST).read_bytes()


def test_verify_reports_changed_sources_and_tables(bundles: Path, tmp_path: Path) -> None:
    out = tmp_path / "raw"
    ingest(bundles, out, PROV)
    (bundles / "a.json").write_text(json.dumps(_bundle("p1", 5)))
    (out / "observation.parquet").unlink()
    (bundles / "b.json").unlink()
    assert verify(out, bundles) == [
        "source changed: a.json",
        "source missing: b.json",
        "table missing: observation",
    ]


def test_empty_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest(tmp_path, tmp_path / "raw", PROV)


def test_cli_ingest_then_verify(
    bundles: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinical_lakehouse.cli import SALT_ENV, main

    out = tmp_path / "raw"
    monkeypatch.delenv(SALT_ENV, raising=False)
    assert main(["ingest", str(bundles), "--out", str(out)]) == 2  # no salt, no load
    capsys.readouterr()

    monkeypatch.setenv(SALT_ENV, "a-test-salt-of-sixteen-plus")
    assert main(["ingest", str(bundles), "--out", str(out), "--seed", "7"]) == 0
    assert json.loads(capsys.readouterr().out)["tables"]["patient"] == 2
    manifest = json.loads((out / MANIFEST).read_text())
    assert manifest["deidentification"] == {"mode": "safe_harbor", "as_of": "2024-05-01"}
    assert "a-test-salt" not in (out / MANIFEST).read_text()
    ids = pq.read_table(out / "patient.parquet").column("id").to_pylist()
    assert "p1" not in ids and len(ids) == 2
    assert main(["verify", str(bundles), "--out", str(out)]) == 0
    (bundles / "a.json").write_text("{}")
    assert main(["verify", str(bundles), "--out", str(out)]) == 1


def test_verify_flags_identifier_columns_in_a_deidentified_zone(
    bundles: Path, tmp_path: Path
) -> None:
    out = tmp_path / "raw"
    ingest(bundles, out, PROV)  # written without de-identification
    manifest = json.loads((out / MANIFEST).read_text())
    manifest["deidentification"] = {"mode": "safe_harbor", "as_of": "2024-05-01"}
    (out / MANIFEST).write_text(json.dumps(manifest))
    assert "identifier column present: patient.family_name" in verify(out, bundles)
