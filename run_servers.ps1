# Love Journal 快速启动脚本
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "server"
$FrontendDir = Join-Path $Root "web"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Love Journal 服务启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查目录
if (-not (Test-Path $BackendDir)) {
    Write-Host "[错误] 后端目录不存在: $BackendDir" -ForegroundColor Red
    pause
    exit 1
}

if (-not (Test-Path $FrontendDir)) {
    Write-Host "[错误] 前端目录不存在: $FrontendDir" -ForegroundColor Red
    pause
    exit 1
}

# 检查虚拟环境
$venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[错误] 后端虚拟环境不存在" -ForegroundColor Red
    Write-Host "请先运行 start_project.bat 进行初始化" -ForegroundColor Yellow
    pause
    exit 1
}

# 检查前端依赖
$nodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "[错误] 前端依赖未安装" -ForegroundColor Red
    Write-Host "请先运行 start_project.bat 进行初始化" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[启动] 正在启动后端服务..." -ForegroundColor Green

# 启动后端
$backendCommand = @"
`$env:APP_ENV = 'development'
`$env:APP_PORT = '$BackendPort'
`$env:PYTHONUTF8 = '1'
`$env:DATABASE_URL = 'sqlite:///local_demo.db'
Set-Location -LiteralPath '$BackendDir'
& '$venvPython' -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BackendPort
"@

$encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($backendCommand))
Start-Process powershell.exe -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encodedCommand -WindowStyle Normal

Write-Host "[等待] 等待后端启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "[启动] 正在启动前端服务..." -ForegroundColor Green

# 启动前端
$npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
if (-not $npmPath) {
    $npmPath = "npm"
}

$frontendCommand = @"
`$env:VITE_API_BASE_URL = '/api'
`$env:BACKEND_PROXY_TARGET = 'http://127.0.0.1:$BackendPort'
Set-Location -LiteralPath '$FrontendDir'
& '$npmPath' run dev -- --host 0.0.0.0 --port $FrontendPort
"@

$encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($frontendCommand))
Start-Process powershell.exe -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encodedCommand -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "服务启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "后端地址: http://localhost:$BackendPort" -ForegroundColor Cyan
Write-Host "前端地址: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "API 文档: http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "默认测试账号:" -ForegroundColor Yellow
Write-Host "  - admin/admin" -ForegroundColor Yellow
Write-Host "  - partner/partner" -ForegroundColor Yellow
Write-Host ""
Write-Host "按任意键关闭此窗口（后端和前端窗口将继续运行）" -ForegroundColor Gray
pause
