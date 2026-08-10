# Love Journal 一起听 upstream — self-built image of the MAINTAINED
# NeteaseCloudMusicApiEnhanced fork (npm @neteasecloudmusicapienhanced/api).
#
# Replaces the archived (2024-04) prebuilt binaryify/netease_cloud_music_api
# image so (a) we own the supply chain — no third-party Docker Hub account in
# the prod path — and (b) we get the guest-token-refresh login fix. Listens on
# 3000; backend-only, never published to the host.
#
# node:22-alpine: the fork pulls express@5 / yargs@18, which require Node
# >=20.19. All deps are pure JS, so no build toolchain is needed.
FROM node:22.14.0-alpine3.21

WORKDIR /app

# Install deps in their own layer so app code edits don't bust the npm cache.
# npm ci against the committed lockfile = reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

COPY server.js ./
COPY LICENSE NOTICE THIRD_PARTY_LICENSES.md ./

EXPOSE 3000

# Quietly probe the running API. wget ships in the alpine base image.
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1 || exit 1

CMD ["node", "server.js"]
