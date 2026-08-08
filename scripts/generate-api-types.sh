#!/usr/bin/env bash
# Regenerate the TypeScript view of the API contract from FastAPI's own OpenAPI
# schema. Hand-written duplicates of the Pydantic models drift silently — see
# planning/REVIEW-OPUS.md P1-4 for the incident this replaces.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA="$ROOT/packages/shared/openapi.json"
OUT="$ROOT/packages/shared/src/api-types.ts"

echo "→ exporting OpenAPI schema from FastAPI"
(cd "$ROOT/apps/api" && uv run python -m app.openapi_export) > "$SCHEMA"

echo "→ generating $OUT"
(cd "$ROOT/packages/shared" && \
  ./node_modules/.bin/openapi-typescript "$SCHEMA" -o "$OUT")

echo "✓ done"
