#!/bin/sh
# Alembic is the schema source of truth outside development (see app.main lifespan).
# Running it here — before uvicorn binds — means a container never serves traffic
# against a schema it has not migrated.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "entrypoint: applying database migrations"
    if ! uv run alembic upgrade head; then
        echo "entrypoint: alembic upgrade failed." >&2
        echo "  If this database predates the migration wiring its tables may have been" >&2
        echo "  created by metadata.create_all and have no alembic_version row." >&2
        echo "  For a disposable dev database:  docker compose -f docker/docker-compose.yml down -v" >&2
        echo "  For a database with real data:  uv run alembic stamp head   (verify the schema first)" >&2
        exit 1
    fi

    # Knowledge base needs its table, so it runs under the same flag as migrations.
    # Smoke tests use RUN_MIGRATIONS=0 with a scratch DB that has no knowledge_chunk.
    echo "entrypoint: syncing knowledge base"
    if ! uv run python -m app.content.sync_kb; then
        echo "entrypoint: sync_kb failed." >&2
        exit 1
    fi
else
    echo "entrypoint: RUN_MIGRATIONS=0, skipping migrations and knowledge sync"
fi

exec "$@"
