"""Command line entry point: ``clinical-lakehouse ingest`` and ``clinical-lakehouse verify``."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from clinical_lakehouse.deid import Mode, Policy, latest_date
from clinical_lakehouse.fhir import FlattenResult
from clinical_lakehouse.raw_zone import Provenance, ingest, verify

SALT_ENV = "CLINICAL_LAKEHOUSE_SALT"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clinical-lakehouse", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("ingest", help="flatten FHIR bundles into a Parquet raw zone")
    i.add_argument("bundles", type=Path, help="folder of FHIR R4 patient bundles")
    i.add_argument("--out", type=Path, default=Path("data/raw"))
    i.add_argument("--generator", default="synthea")
    i.add_argument("--generator-version", default="unknown")
    i.add_argument("--seed", type=int)
    i.add_argument("--population", type=int)
    i.add_argument(
        "--deid",
        choices=[m.value for m in Mode] + ["none"],
        default=Mode.SAFE_HARBOR.value,
        help=f"de-identification mode; the salt comes from ${SALT_ENV}",
    )
    v = sub.add_parser("verify", help="check a raw zone against its manifest and sources")
    v.add_argument("bundles", type=Path)
    v.add_argument("--out", type=Path, default=Path("data/raw"))
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.command == "ingest":
        prov = Provenance(args.generator, args.generator_version, args.seed, args.population)
        deid = None
        if args.deid != "none":
            salt = os.environ.get(SALT_ENV, "")
            if len(salt) < 16:
                print(f"set {SALT_ENV} to a secret of at least 16 characters, or pass --deid none")
                return 2
            mode = Mode(args.deid)

            def deid(rows: FlattenResult) -> Policy:
                return Policy(mode=mode, salt=salt.encode(), as_of=latest_date(rows))

        manifest = ingest(args.bundles, args.out, prov, deid)
        print(json.dumps({"tables": manifest["tables"], "skipped": manifest["skipped"]}))
        return 0
    problems = verify(args.out, args.bundles)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
