"""Write flattened FHIR rows to a Parquet raw zone with a manifest.

The manifest is what makes a load reproducible and checkable: it records the generator
and seed that produced the bundles, a checksum per source file, row counts per table and
what was skipped. It carries no timestamp, so two loads of the same input produce byte
for byte the same manifest and a diff shows real changes only.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from clinical_lakehouse.deid import DIRECT_IDENTIFIERS, Policy, deidentify
from clinical_lakehouse.fhir import FlattenResult, flatten_bundle, iter_bundles

log = logging.getLogger(__name__)

MANIFEST = "manifest.json"


@dataclass(frozen=True)
class Provenance:
    generator: str
    version: str
    seed: int | None
    population: int | None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write(
    result: FlattenResult,
    sources: Iterable[Path],
    out: Path,
    provenance: Provenance,
    deid: Policy | None = None,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    tables = {}
    for kind in sorted(result.rows):
        rows = sorted(result.rows[kind], key=lambda r: str(r["id"]))
        pq.write_table(pa.Table.from_pylist(rows), out / f"{kind.lower()}.parquet")
        tables[kind.lower()] = len(rows)
    manifest = {
        "generator": {
            "name": provenance.generator,
            "version": provenance.version,
            "seed": provenance.seed,
            "population": provenance.population,
        },
        # The salt is never recorded: with it, pseudonyms could be reversed by brute force.
        "deidentification": (
            {"mode": deid.mode.value, "as_of": deid.as_of.isoformat()} if deid else None
        ),
        "sources": {p.name: sha256(p) for p in sorted(sources)},
        "tables": tables,
        "skipped": dict(sorted(result.skipped.items())),
    }
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log.info("raw zone %s: %s", out, tables)
    return manifest


def ingest(
    bundles_dir: Path,
    out: Path,
    provenance: Provenance,
    deid: Callable[[FlattenResult], Policy] | None = None,
) -> dict[str, Any]:
    """Flatten every patient bundle in ``bundles_dir`` and write the raw zone.

    ``deid`` builds the de-identification policy from the flattened data (so the
    as-of date can come from the data itself); ``None`` writes identifiers as they
    are and is only meant for synthetic data under test.
    """
    total = FlattenResult()
    sources = []
    for path, bundle in iter_bundles(bundles_dir):
        total.add(flatten_bundle(bundle))
        sources.append(path)
    if not sources:
        raise FileNotFoundError(f"no FHIR bundles in {bundles_dir}")
    policy = deid(total) if deid else None
    if policy:
        total = deidentify(total, policy)
    return write(total, sources, out, provenance, policy)


def verify(out: Path, bundles_dir: Path) -> list[str]:
    """Problems found comparing a raw zone with its manifest; empty means consistent."""
    manifest: Mapping[str, Any] = json.loads((out / MANIFEST).read_text(encoding="utf-8"))
    problems = []
    for name, expected in manifest["sources"].items():
        path = bundles_dir / name
        if not path.exists():
            problems.append(f"source missing: {name}")
        elif sha256(path) != expected:
            problems.append(f"source changed: {name}")
    for table, count in manifest["tables"].items():
        path = out / f"{table}.parquet"
        if not path.exists():
            problems.append(f"table missing: {table}")
            continue
        if pq.read_metadata(path).num_rows != count:
            problems.append(f"row count differs: {table}")
        if manifest.get("deidentification"):
            names = set(pq.read_schema(path).names)
            problems += [
                f"identifier column present: {table}.{c}" for c in DIRECT_IDENTIFIERS if c in names
            ]
    return problems
