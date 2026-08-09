#!/bin/sh
# Reconcile node_modules with the lockfile before the dev server starts.
#
# This exists for the same reason api-entrypoint.sh runs Alembic before uvicorn:
# a container must not serve against a state it has not reconciled. For the web
# side that state is node_modules, and it goes stale in a way that is easy to
# misread as a broken package.
#
# `node_modules` are mounted as **named volumes**, and Docker seeds a named
# volume from the image only when the volume is *empty*. So adding a dependency
# and running `up --build` installs it into the fresh image and then mounts the
# old volume straight over it. The container then fails with
#
#     Module not found: Can't resolve 'lucide-react'
#
# for a package that is plainly in package.json — which sends you looking at the
# package, the import, and the bundler, none of which are wrong.
#
# Installing here fixes it at the one moment that always happens: start-up. With
# a warm volume and an unchanged lockfile this is a no-op that costs a second.
set -e

cd /app

echo "entrypoint: reconciling node_modules with the lockfile"
if ! pnpm install --frozen-lockfile; then
    echo "entrypoint: pnpm install --frozen-lockfile failed." >&2
    echo "  The lockfile and the package.json files disagree, so the container" >&2
    echo "  refuses to guess which one is right. On the host, run:" >&2
    echo "    pnpm install" >&2
    echo "  and commit the updated pnpm-lock.yaml." >&2
    exit 1
fi

# packages/shared is bind-mounted, which hides the dist/ the image built — and
# apps/web imports the compiled output, not src. On a fresh clone the host has no
# dist at all, so without this the web container cannot resolve the shared
# package even though the image built it correctly.
echo "entrypoint: building @toeic-pilot/shared"
pnpm --filter @toeic-pilot/shared build

cd /app/apps/web
exec "$@"
