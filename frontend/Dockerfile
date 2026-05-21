# syntax=docker/dockerfile:1
FROM docker.1panel.live/library/node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM docker.1panel.live/library/node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
