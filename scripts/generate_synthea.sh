#!/usr/bin/env bash
# Generate synthetic patients with a pinned Synthea release.
#
#   scripts/generate_synthea.sh [population] [seed] [state] [out_dir]
#
# Same arguments, same patients: the jar is pinned by version and checksum, both the
# patient seed and the clinician seed are fixed, and so is the reference date (without
# it Synthea simulates up to the current time and every run differs). Needs Java 17+.
set -euo pipefail

VERSION=v4.0.0
SHA256=ed43c20ad40ba5c3bc724503a5af032715fe3c491620b766148e7c2361e6ecc1
URL="https://github.com/synthetichealth/synthea/releases/download/${VERSION}/synthea-with-dependencies.jar"

POPULATION=${1:-100}
SEED=${2:-7}
STATE=${3:-Massachusetts}
OUT=${4:-data/synthea}
REFERENCE_DATE=${SYNTHEA_REFERENCE_DATE:-20261101}
CACHE=${SYNTHEA_CACHE:-.cache/synthea}
JAR="${CACHE}/synthea-${VERSION}.jar"

mkdir -p "$CACHE"
if [[ ! -f "$JAR" ]]; then
  echo "downloading Synthea ${VERSION}"
  curl -fsSL -o "$JAR.part" "$URL"
  mv "$JAR.part" "$JAR"
fi
echo "${SHA256}  ${JAR}" | sha256sum --check --quiet

rm -rf "$OUT"
java -jar "$JAR" \
  -s "$SEED" -cs "$SEED" -r "$REFERENCE_DATE" -p "$POPULATION" \
  --exporter.baseDirectory "$OUT" \
  --exporter.fhir.export true \
  --exporter.csv.export false \
  --exporter.hospital.fhir.export false \
  --exporter.practitioner.fhir.export false \
  "$STATE" > "${OUT%/}.log"

echo "$(ls "$OUT/fhir" | wc -l) patient bundles in $OUT/fhir (Synthea ${VERSION}, seed ${SEED}, ${STATE})"
