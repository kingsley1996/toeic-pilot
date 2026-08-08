FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared/package.json ./packages/shared/
RUN pnpm install --frozen-lockfile || pnpm install

FROM base AS runner
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=deps /app/packages/shared/node_modules ./packages/shared/node_modules
COPY . .
# packages/shared/dist is .dockerignore'd (host build artifacts must not leak in),
# so the image builds it itself — apps/web imports the compiled output, not src.
RUN pnpm --filter @toeic-pilot/shared build
WORKDIR /app/apps/web
EXPOSE 3000
ENV NODE_ENV=development
CMD ["pnpm", "dev"]
