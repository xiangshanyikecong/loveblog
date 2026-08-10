# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-07-30

### Added

- `.github/workflows/ci.yml` — automated CI for server tests, web tests, and linting
- `SECURITY.md` — vulnerability reporting policy (GitHub Private Advisories)
- `CONTRIBUTING.md` — development workflow and Conventional Commits conventions
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `web/eslint.config.js` and `web/.prettierrc.json` — JS/Vue lint and format configs
- English summary section in `README.md`
- Project metadata (`license`, `repository`, `author`, `bugs`) in `web/package.json` and `netease-api/package.json`

### Changed

- `docs/README.md` — removed stale reference to `.kiro/specs/` (not included in the public repo)
- `README.md` — marked iOS client as not open-sourced to match the `.gitignore` policy

## [1.0.0] - 2026-07-25

First public open-source release.

### Core Platform

- **Articles / Diary**: Vditor rich-text editor, draft auto-save, encrypted content,
  co-creation (`partner_can_edit`, `is_co_created`), optimistic concurrency with
  `If-Match`/`ETag` conflict resolution, content version history with rollback
- **Albums**: image/video media, encrypted albums and media items, private albums
- **Events / Timeline**: countdown and anniversary types, yearly repeats, visibility
  policy, `next_occurrence_days` computation
- **Messages**: visitor and authenticated user posting, public toggle, soft delete
- **Time Capsules**: scheduled unlock with `open_at`
- **Moments**:图文记录 unified into timeline, search, export, and recycle bin
- **Comments**: threaded (楼中楼) across articles, albums, and other content

### Cottage (Interaction Hub)

- **Check-in (报备)**: location reporting with privacy-first design (only city text persisted,
  raw IP/lat-lng never stored)
- **Listen Together (一起听)**: NetEase Cloud Music sync playback via WebSocket, search,
  daily recommendations, lyrics, queue management, play-progress sync, auto-pause
- **Watch Together (一起看)**: shared video library with poster wall, sync playback for
  local uploads and direct links (`.mp4` / `.m3u8`)
- **Whisper Chat (悄悄话)**: private two-person chat with text/images/stickers, optional
  AES-GCM end-to-end encryption with shared client key, no plaintext fallback
- **Mood Check-in**: daily mood recording with emotion calendar
- **Wishlist**: shared to-do list with completion toggle
- **Daily Question**: blind-answer reveal mechanism
- **Shared Plans / Reminders**: `/v1/cottage/plans`, `/v1/cottage/reminders`
- **Games (一起玩)**: Gomoku, Tic-Tac-Toe, Reversi, Memory, LinkLink, Draw-and-Guess —
  real-time WebSocket gameplay with persistent match records and cross-game stats aggregation

### Social & Discovery

- Notification center with read state and reminder types
- Full-text search across articles, albums, events, moments
- Unified visibility policy: `Public / PartnersOnly / Encrypted`

### Admin & Management

- Dual-role accounts (`PartnerA` / `PartnerB` / `Visitor`) with ban and permission controls
- JWT + session version, login failure lockout, last-login IP/time tracking
- Audit logs for key operations
- Privacy center with local recovery packages and recent privacy operations
- Recycle bin with soft-delete recovery
- Export/Backup v6 (full ZIP: `data.json` + Markdown + `uploads/`), scheduled auto-backup,
  idempotent restore for v1–v6 archives
- Site settings (love start date, base path)
- System health check with 0–100 scoring, component status, optimization recommendations,
  24h trend history, alert + auto-remediation

### Security

- JWT + HttpOnly Secure SameSite=strict cookies; token never exposed to client JS
- Rate limiting (global per-IP + stricter on sensitive routes)
- Key separation: `JWT_SECRET_KEY` vs `COOKIE_VAULT_KEY` (Fernet-encrypted NetEase cookies in Redis)
- E2EE vault: PBKDF2-SHA256 (210k iterations) + AES-GCM-256, keys never leave browser (`extractable=false`)
- Startup self-check: refuses default/weak secrets in production
- Nginx TLS-only with HSTS, `$uri`-based logging (no query-string secrets in logs)

### Clients

- **Web**: Vue 3 + Vite + Tailwind CSS + Vue Router + Pinia (primary client)
- **Android**: Kotlin + Jetpack Compose — full REST + WebSocket parity, offline-first with
  WorkManager sync, FCM push, Glance widget, camera/gallery upload, client-side encrypted vault
- **iOS**: SwiftUI client (not open-sourced in this repository)

### Infrastructure

- Docker Compose for development (`docker-compose.yml`) and production (`docker-compose.prod.yml`)
- PostgreSQL 16 + Redis 7 + Nginx + NeteaseCloudMusicApiEnhanced
- Alembic migrations (41 schema versions)
- Third-party notices for all four client tiers (Android 160 pkgs, Web 201 pkgs, Python 82 pkgs, Node 246 pkgs)
