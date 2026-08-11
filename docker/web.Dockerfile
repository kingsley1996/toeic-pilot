FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared/package.json ./packages/shared/
# KHÔNG có `|| pnpm install` dự phòng (P2-7). Nhánh dự phòng đó biến một lỗi ồn
# ào — package.json và lockfile lệch nhau — thành một lần build im lặng thành
# công với cây phụ thuộc do máy build tự đoán. Ảnh chạy được, phiên bản khác với
# lockfile, và không ai biết cho tới khi một thư viện hành xử khác ở production.
# `web-entrypoint.sh` đã theo đúng luật này từ trước; chỗ này là chỗ sót.
RUN pnpm install --frozen-lockfile

FROM base AS runner
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=deps /app/packages/shared/node_modules ./packages/shared/node_modules
COPY . .
# packages/shared/dist is .dockerignore'd (host build artifacts must not leak in),
# so the image builds it itself — apps/web imports the compiled output, not src.
RUN pnpm --filter @toeic-pilot/shared build
COPY docker/web-entrypoint.sh /usr/local/bin/web-entrypoint.sh
RUN chmod +x /usr/local/bin/web-entrypoint.sh

WORKDIR /app/apps/web
EXPOSE 3000
ENV NODE_ENV=development
# The entrypoint reconciles node_modules with the lockfile before handing over —
# without it, a dependency added after the volumes were created is invisible to
# the container no matter how many times the image is rebuilt.
ENTRYPOINT ["/usr/local/bin/web-entrypoint.sh"]
CMD ["pnpm", "dev"]
