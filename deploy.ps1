# ============================================
# Love Journal 生产环境部署脚本 (Windows / PowerShell)
# deploy.sh 的 Windows 等价版本。需安装 Docker Desktop for Windows。
# 用法: powershell -ExecutionPolicy Bypass -File deploy.ps1 [-Build]
#       或双击 deploy.bat
#   -Build   在本机构建应用镜像（默认拉取 ghcr.io 预构建镜像）
# ============================================

param(
    # 在本机构建应用镜像（默认拉取 GHCR 预构建镜像）
    [switch] $Build
)

$ErrorActionPreference = "Stop"

# 切换到脚本所在目录，保证相对路径与 docker-compose 上下文正确
Set-Location -LiteralPath $PSScriptRoot

Write-Host "🚀 开始部署 Love Journal..." -ForegroundColor Cyan

# -------------------- 检查必需文件 --------------------
Write-Host "📋 检查配置文件..."
if (-not (Test-Path ".env.production")) {
    Write-Host "❌ 错误：.env.production 文件不存在" -ForegroundColor Red
    Write-Host "请复制 .env.production.example 并填写配置：" -ForegroundColor Yellow
    Write-Host "    copy .env.production.example .env.production" -ForegroundColor Yellow
    exit 1
}

# -------------------- 检查 Docker 环境 --------------------
Write-Host "🔍 检查 Docker 环境..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 错误：未安装 Docker（请安装 Docker Desktop for Windows）" -ForegroundColor Red
    exit 1
}

# 检测 compose 命令：优先 `docker compose`（插件），回退 `docker-compose`
$ComposeArgs = $null
try {
    docker compose version *> $null
    if ($LASTEXITCODE -eq 0) { $ComposeArgs = @("compose") }
} catch { }
if (-not $ComposeArgs) {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $ComposeArgs = @()  # 表示使用独立的 docker-compose 可执行文件
    } else {
        Write-Host "❌ 错误：未安装 Docker Compose" -ForegroundColor Red
        exit 1
    }
}

# 统一的 compose 调用封装。-AllowFailure 时不抛异常，返回退出码由调用方处理。
function Invoke-Compose {
    param(
        [Parameter(ValueFromRemainingArguments = $true)] [string[]] $Args,
        [switch] $AllowFailure
    )
    if ($ComposeArgs.Count -gt 0) {
        & docker @ComposeArgs --env-file .env.production -f docker-compose.prod.yml @Args
    } else {
        & docker-compose --env-file .env.production -f docker-compose.prod.yml @Args
    }
    if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
        throw "Docker Compose 命令失败（退出码 $LASTEXITCODE）：$($Args -join ' ')"
    }
}

# -------------------- 加载环境变量 --------------------
# 与 deploy.sh 的 `export $(cat .env.production ...)` 等价：写入当前进程环境，
# 供 docker compose 的 ${VAR} 插值使用。
Write-Host "📦 加载环境变量..."
foreach ($line in Get-Content ".env.production") {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
    $idx = $trimmed.IndexOf("=")
    if ($idx -lt 1) { continue }
    $key = $trimmed.Substring(0, $idx).Trim()
    $value = $trimmed.Substring($idx + 1).Trim()
    if ($key -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
        Write-Host "❌ 错误：.env.production 中包含无效变量名：$key" -ForegroundColor Red
        exit 1
    }
    # 去除可选的成对引号
    if ($value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
         ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path "Env:$key" -Value $value
}

# -------------------- 校验必需变量 --------------------
$RequiredVars = @("POSTGRES_PASSWORD", "REDIS_PASSWORD", "JWT_SECRET_KEY", "COOKIE_VAULT_KEY", "CORS_ORIGINS", "BOOTSTRAP_SETUP_TOKEN", "DOMAIN", "COOKIE_SECURE")
foreach ($var in $RequiredVars) {
    $val = (Get-Item -Path "Env:$var" -ErrorAction SilentlyContinue).Value
    if ([string]::IsNullOrEmpty($val)) {
        Write-Host "❌ 错误：环境变量 $var 未设置" -ForegroundColor Red
        exit 1
    }
    if ($val -match "请设置|请生成|yourdomain\.com") {
        Write-Host "❌ 错误：环境变量 $var 仍是模板占位值" -ForegroundColor Red
        exit 1
    }
}

if ($env:POSTGRES_PASSWORD.Length -lt 16 -or $env:REDIS_PASSWORD.Length -lt 16 -or
    $env:JWT_SECRET_KEY.Length -lt 64 -or $env:COOKIE_VAULT_KEY.Length -lt 64) {
    Write-Host "❌ 错误：数据库/Redis 密码至少 16 位，JWT 与 Cookie Vault 密钥至少 64 位" -ForegroundColor Red
    exit 1
}
if ($env:JWT_SECRET_KEY -ceq $env:COOKIE_VAULT_KEY) {
    Write-Host "❌ 错误：COOKIE_VAULT_KEY 必须与 JWT_SECRET_KEY 不同" -ForegroundColor Red
    exit 1
}
if ($env:COOKIE_SECURE.ToLowerInvariant() -ne "true") {
    Write-Host "❌ 错误：生产 nginx 强制 HTTPS，COOKIE_SECURE 必须为 true" -ForegroundColor Red
    exit 1
}
foreach ($cert in @("nginx/ssl/fullchain.pem", "nginx/ssl/privkey.pem")) {
    if (-not (Test-Path -LiteralPath $cert) -or (Get-Item -LiteralPath $cert).Length -eq 0) {
        Write-Host "❌ 错误：缺少 TLS 文件 $cert（部署前先申请并放入证书）" -ForegroundColor Red
        exit 1
    }
}

# 在停止任何现有服务前完成 Compose 配置校验，避免配置错误造成停机。
Write-Host "🔎 校验生产 Compose 配置..."
Invoke-Compose config --quiet

# -------------------- 创建必需的目录 --------------------
Write-Host "📁 创建必需的目录..."
$Dirs = @(
    "server/uploads/albums", "server/uploads/articles", "server/uploads/avatars",
    "server/uploads/timeline", "server/uploads/videos",
    "server/backups", "nginx/ssl", "nginx/conf.d"
)
foreach ($d in $Dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
foreach ($stateFile in @("backup_history.json", "backup_schedule.json")) {
    $oldPath = Join-Path $PSScriptRoot "server/$stateFile"
    $newPath = Join-Path $PSScriptRoot "server/backups/$stateFile"
    if ((Test-Path -LiteralPath $oldPath -PathType Leaf) -and
        -not (Test-Path -LiteralPath $newPath)) {
        Move-Item -LiteralPath $oldPath -Destination $newPath
    } elseif (Test-Path -LiteralPath $oldPath -PathType Container) {
        if (Get-ChildItem -LiteralPath $oldPath -Force | Select-Object -First 1) {
            Write-Host "❌ 错误：$oldPath 本应是文件但现在是非空目录，请先人工检查" -ForegroundColor Red
            exit 1
        }
        Remove-Item -LiteralPath $oldPath
    }
}
if (-not (Test-Path -LiteralPath "server/backups/backup_history.json")) {
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "server/backups/backup_history.json"), "[]`n", $Utf8NoBom)
}
if (-not (Test-Path -LiteralPath "server/backups/backup_schedule.json")) {
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot "server/backups/backup_schedule.json"), "{}`n", $Utf8NoBom)
}

# -------------------- 备份旧上传文件 --------------------
if ((Test-Path "server/uploads") -and (Get-ChildItem "server/uploads" -Force | Select-Object -First 1)) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupDir = "backups/uploads_$timestamp"
    Write-Host "💾 备份现有上传文件到 $BackupDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    Copy-Item -Path "server/uploads/*" -Destination $BackupDir -Recurse -Force
}

# 先拉取/构建新版本。旧容器保持运行，拉取或构建失败时不会主动制造停机。
if ($Build) {
    # 本地构建（备用选项）：适合网络无法访问 ghcr.io、或自定义了
    # VITE_API_BASE_URL 等构建参数的场景。
    Write-Host "📥 拉取基础镜像..."
    Invoke-Compose pull postgres redis nginx

    Write-Host "🔨 在本机构建应用镜像..."
    Invoke-Compose build --no-cache
} else {
    # 默认：拉取 GitHub Actions 预构建镜像（公开包，无需登录），避免在
    # 本机构建（慢、易因环境差异失败）。
    Write-Host "📥 拉取预构建镜像（ghcr.io）..."
    Invoke-Compose pull -AllowFailure
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  镜像拉取失败（可能是网络无法访问 ghcr.io）。" -ForegroundColor Yellow
        Write-Host "   将尝试使用本地已有镜像继续；若本地无镜像，启动时会自动回退为本机构建。"
        Write-Host "   也可显式指定本机构建：powershell -ExecutionPolicy Bypass -File deploy.ps1 -Build"
    }
}

# -------------------- 启动服务 --------------------
Write-Host "🚀 启动服务..."
Invoke-Compose up -d --remove-orphans

# -------------------- 等待服务启动 --------------------
Write-Host "⏳ 等待服务启动..."
Start-Sleep -Seconds 10

# -------------------- 健康检查 --------------------
Write-Host "🏥 执行健康检查..."
$MaxRetries = 30
$RetryCount = 0
$Healthy = $false
while ($RetryCount -lt $MaxRetries) {
    try {
        # Traverse TLS termination and nginx routing, not only backend HTTP.
        Invoke-Compose exec -T nginx wget --no-check-certificate --quiet --tries=1 --spider https://127.0.0.1/health/ready *> $null
        Write-Host "✅ Nginx HTTPS 路由与后端服务健康" -ForegroundColor Green
        $Healthy = $true
        break
    } catch { }
    $RetryCount++
    Write-Host "等待后端启动... ($RetryCount/$MaxRetries)"
    Start-Sleep -Seconds 2
}

if (-not $Healthy) {
    Write-Host "❌ Nginx HTTPS 路由或后端服务启动失败" -ForegroundColor Red
    Write-Host "查看日志："
    Invoke-Compose logs nginx backend
    exit 1
}

# Do not bypass certificate validation here: this verifies public DNS, trust,
# hostname and expiry in addition to the reverse-proxy route checked above.
$PublicOrigin = "https://$($env:DOMAIN)"
if ($env:HTTPS_PORT -and $env:HTTPS_PORT -ne "443") {
    $PublicOrigin = "${PublicOrigin}:$($env:HTTPS_PORT)"
}
try {
    Invoke-WebRequest -UseBasicParsing -Uri "$PublicOrigin/health/ready" -TimeoutSec 15 | Out-Null
    Write-Host "✅ 公网 HTTPS、DNS 与证书校验通过" -ForegroundColor Green
} catch {
    Write-Host "❌ 公网 HTTPS 或证书校验失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# -------------------- 服务状态 --------------------
Write-Host ""
Write-Host "📊 服务状态："
Invoke-Compose ps

Write-Host ""
Write-Host "📝 最近日志："
Invoke-Compose logs --tail=20

# -------------------- 完成提示 --------------------
Write-Host ""
Write-Host "✅ 部署完成！" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 访问地址："
Write-Host "   前端: $PublicOrigin"
Write-Host "   API:  $PublicOrigin/api"
Write-Host "   API 文档: 生产环境默认不公开（本地开发访问 /docs）"
Write-Host ""
Write-Host "📋 常用命令（PowerShell）："
if ($ComposeArgs.Count -gt 0) { $cc = "docker compose" } else { $cc = "docker-compose" }
Write-Host "   查看日志: $cc -f docker-compose.prod.yml logs -f"
Write-Host "   重启服务: $cc -f docker-compose.prod.yml restart"
Write-Host "   停止服务: $cc -f docker-compose.prod.yml down"
Write-Host "   进入后端: $cc -f docker-compose.prod.yml exec backend bash"
Write-Host ""
Write-Host "⚠️  提醒：" -ForegroundColor Yellow
Write-Host "   1. 请定期验证自动备份可以实际恢复"
Write-Host "   2. 请设置证书自动续期并在续期后 reload nginx"
Write-Host "   3. 请修改默认管理员密码"
Write-Host "   4. 网易云「一起听」依赖社区上游镜像，如遇登录异常可执行："
Write-Host "      $cc -f docker-compose.prod.yml pull netease 拉取最新版后重启"
Write-Host ""
