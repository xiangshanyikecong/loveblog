# Contributing to Love Journal

Thanks for your interest in contributing! This document covers the development
workflow, code style, and commit conventions for this project.

[简体中文](#贡献指南) | English

---

## Development Setup

### Prerequisites

- **Python** 3.11+ (server)
- **Node.js** 20+ and npm (web, netease-api)
- **Android Studio** (Android client, optional)
- **Docker** + **Docker Compose** (recommended for local Redis/PostgreSQL)

### Quick Start

The fastest way to get a working dev environment:

```bash
docker compose up --build          # starts postgres + redis + netease + backend + web
```

Or run components individually (see [README.md](./README.md) for details):

```bash
# Backend
cd server
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd web
npm install
cp .env.example .env
npm run dev
```

---

## Project Structure

```
server/          FastAPI backend (Python)
web/             Vue 3 + Vite frontend
Android/         Kotlin + Jetpack Compose client
netease-api/     NeteaseCloudMusicApi helper (Node.js, for listen-together)
nginx/           Production reverse-proxy config
tools/           Maintenance scripts (e.g. third-party notice generator)
docs/            User guides, security audit reports
```

---

## Code Style

### Python (server/)

- Lint with `flake8` and `pylint` (configs: `.flake8`, `.pylintrc`)
- Max line length: **120**
- Formatting follows **black**-compatible conventions (E203/W503 disabled)

```bash
flake8 server/app
pylint server/app
```

### JavaScript / Vue (web/)

- Lint with `eslint` (flat config) and `stylelint`
- Format with `prettier`
- Configs: `web/eslint.config.js`, `web/.stylelintrc.json`, `web/.prettierrc.json`

```bash
cd web
npm run lint          # eslint + stylelint
npm run lint:fix      # auto-fix where possible
npm run format        # prettier
```

### Kotlin (Android/)

- Follow the official [Kotlin coding conventions](https://kotlinlang.org/docs/coding-conventions.html)
- Build with `./gradlew assembleDebug`

---

## Testing

Run tests before submitting a pull request:

```bash
# Server (pytest)
cd server
pip install -r requirements.lock
pytest

# Web (vitest)
cd web
npm install
npm test
```

All new features or bug fixes should include appropriate test coverage.

---

## Commit Conventions

This project follows [**Conventional Commits**](https://www.conventionalcommits.org/).
Commit messages should use this format:

```
<type>(<scope>): <subject>

<body optional>
```

### Types

| Type | Description |
| --- | --- |
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Code style changes (formatting, no logic change) |
| `refactor` | Code refactoring without behavior change |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `chore` | Build, tooling, dependency changes |
| `ci` | CI/CD changes |
| `revert` | Reverting a previous commit |

### Examples

```
feat(cottage): add playlist shuffle for listen-together
fix(auth): prevent session fixation on partner role switch
docs(readme): add English summary section
chore(deps): bump SQLAlchemy to 2.0.49
```

### Rules

- Use **English** for the commit subject line (the `<subject>`)
- Keep the subject under **72 characters**
- Use imperative mood ("add", not "added" or "adds")
- Reference issues in the body: `Closes #123`, `Fixes #456`

---

## Pull Request Process

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Write tests** for your changes.
3. **Run linters and tests** locally (see above).
4. **Commit** using Conventional Commits format.
5. **Open a Pull Request** against the `main` branch with:
   - A clear title following Conventional Commits format
   - A description of what changed and why
   - Links to any related issues
6. Ensure CI checks pass. Maintainers will review and merge.

### Branch Naming

- Feature: `feat/<short-description>`
- Bug fix: `fix/<short-description>`
- Docs: `docs/<short-description>`
- Chore: `chore/<short-description>`

---

## License

The project is licensed under the **GNU Affero General Public License v3.0**
(AGPL-3.0-only); see the [LICENSE](./LICENSE) file. Contributions are accepted on
the understanding that they will be licensed under the same terms. Do not
contribute code you do not have the rights to license.

---

## 贡献指南

以上为英文贡献指南。要点速览：

- **开发环境**：`docker compose up --build` 一键启动，或按 README 分别启动各端
- **代码风格**：Python 用 flake8/pylint（行长 120）；JS/Vue 用 eslint/prettier/stylelint；Kotlin 遵循官方规范
- **提交规范**：遵循 [Conventional Commits](https://www.conventionalcommits.org/)，如 `feat(cottage): xxx`、`fix(auth): xxx`
- **提交信息用英文**，正文可中文
- **PR 流程**：Fork → 建分支 → 写测试 → 过 lint → 提 PR 到 `main`
- **许可证**：项目采用 AGPL-3.0-only，贡献内容按相同条款授权，详见 [LICENSE](./LICENSE)
