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
#
# 依赖安装在原生构建平台（--platform=$BUILDPLATFORM）上执行：node/npm 不经
# QEMU 模拟运行（QEMU 模拟 arm64 时 node 易触发 SIGILL 崩溃，且模拟执行极
# 慢）。依赖全部为纯 JS，node_modules 与平台无关，可直接复制进目标架构
# （amd64/arm64）的 node 运行镜像。
FROM --platform=$BUILDPLATFORM node:22.23.2-alpine3.24 AS deps

WORKDIR /app

# Install deps in their own stage so app code edits don't bust the npm cache.
# npm ci against the committed lockfile = reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

FROM node:22.23.2-alpine3.24

# 构建时刷新 Alpine 安全补丁并移除运行时不需要的 npm：
# - apk upgrade：官方镜像重建节奏跟不上 Alpine secdb（如 libssl3
#   3.5.7→3.5.8 修复 CVE-2026-14456），升级保证 OS 包为当前已修复版本
# - node 镜像捆绑的 npm 及其依赖树（/usr/local/lib/node_modules/npm）含
#   已修复的 HIGH/CRITICAL 漏洞（tar/pacote/sigstore/brace-expansion/
#   picomatch/ip-address），apk upgrade 无法触及；运行时只需 node 本体，
#   直接移除以消除攻击面。依赖安装在 deps 阶段完成，不受影响。
# 必须在切换到非 root 的 node 用户之前执行。
RUN apk upgrade --no-cache \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY server.js ./
COPY NOTICE THIRD_PARTY_LICENSES.md ./

# Drop root: server.js only listens on 3000 (unprivileged) and needs no
# writable paths. The `node` user ships with the official node image.
USER node

EXPOSE 3000

# Quietly probe the running API. wget ships in the alpine base image.
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1 || exit 1

CMD ["node", "server.js"]
