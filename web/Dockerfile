# syntax=docker/dockerfile:1

FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
# Avoid WORKDIR /app — it breaks Next.js typedRoutes (conflicts with route /app).
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /srv/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
# Next omits `public/` when the repo has no static assets; standalone still expects to COPY it.
RUN mkdir -p public
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /srv/web
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder /srv/web/public ./public
# Standalone trace does not ship arbitrary project files; proto is loaded at runtime via readFileSync.
COPY --from=builder --chown=nextjs:nodejs /srv/web/protos ./protos
COPY --from=builder --chown=nextjs:nodejs /srv/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /srv/web/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
