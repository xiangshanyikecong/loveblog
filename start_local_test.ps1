param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall,
    [switch]$WithDockerInfra,
    [switch]$NoBrowser,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "    $Message"
}

function Quote-PS {
    param([string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Find-CommandPath {
    param(
        [string[]]$Names,
        [string]$InstallHint
    )

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    throw "Missing command: $($Names -join ' / '). $InstallHint"
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    Write-Info "$FilePath $($Arguments -join ' ')"
    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Ensure-EnvFile {
    param(
        [string]$Directory,
        [string]$Name
    )

    $envPath = Join-Path $Directory ".env"
    $examplePath = Join-Path $Directory ".env.example"

    if (Test-Path -LiteralPath $envPath) {
        Write-Info "$Name .env exists"
        return
    }

    if (-not (Test-Path -LiteralPath $examplePath)) {
        Write-Warning "$Name has no .env or .env.example"
        return
    }

    if ($CheckOnly) {
        Write-Info "$Name .env would be created from .env.example"
        return
    }

    Copy-Item -LiteralPath $examplePath -Destination $envPath
    Write-Info "$Name .env created from .env.example"
}

function Get-FileHashText {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Test-PortOpen {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(250, $false)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$Seconds = 45
    )

    for ($i = 0; $i -lt $Seconds; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 | Out-Null
            return $true
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    return $false
}

function Start-ConsoleWindow {
    param(
        [string]$Title,
        [string]$Command
    )

    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
    $safeTitle = $Title.Replace('"', "'")
    $cmdLine = 'start "' + $safeTitle + '" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + $encodedCommand
    & $env:ComSpec /d /c $cmdLine
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start console window: $Title"
    }
}

function Open-DefaultBrowser {
    param([string]$Url)

    $safeUrl = $Url.Replace('"', "")
    & $env:ComSpec /d /c ('start "" "' + $safeUrl + '"')
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Get-ChildItem -LiteralPath $Root -Directory |
    Where-Object {
        (Test-Path -LiteralPath (Join-Path $_.FullName "app\main.py")) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName "requirements.txt"))
    } |
    Select-Object -First 1 -ExpandProperty FullName
$WebDir = Get-ChildItem -LiteralPath $Root -Directory |
    Where-Object {
        (Test-Path -LiteralPath (Join-Path $_.FullName "package.json")) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName "src\main.js"))
    } |
    Select-Object -First 1 -ExpandProperty FullName
$StateDir = Join-Path $Root ".quickstart"

Write-Host "Love Journal local test launcher" -ForegroundColor Green
Write-Info "Project root: $Root"

if (-not $BackendDir) {
    throw "Backend directory not found. Expected a child directory with app\main.py and requirements.txt."
}
if (-not $WebDir) {
    throw "Frontend directory not found. Expected a child directory with package.json and src\main.js."
}

if ($CheckOnly) {
    Write-Info "CheckOnly mode: no installs or servers will be started"
}
else {
    Ensure-Directory $StateDir
}

Write-Step "Checking ports"
$busyPorts = @()
if (Test-PortOpen $BackendPort) {
    $busyPorts += $BackendPort
}
if (Test-PortOpen $FrontendPort) {
    $busyPorts += $FrontendPort
}
if ($busyPorts.Count -gt 0) {
    throw "Port(s) already in use: $($busyPorts -join ', '). Re-run with -BackendPort or -FrontendPort to use different ports."
}
Write-Info "Backend port $BackendPort and frontend port $FrontendPort are available"

Write-Step "Checking environment files"
Ensure-EnvFile -Directory $BackendDir -Name "Backend"
Ensure-EnvFile -Directory $WebDir -Name "Frontend"

if ($WithDockerInfra) {
    Write-Step "Starting Docker infrastructure"
    $dockerPath = Find-CommandPath -Names @("docker") -InstallHint "Install Docker Desktop, or run without -WithDockerInfra to use the app's SQLite fallback."
    if ($CheckOnly) {
        Write-Info "Would run: docker compose up -d postgres redis"
    }
    else {
        Invoke-Checked -FilePath $dockerPath -Arguments @("compose", "up", "-d", "postgres", "redis") -WorkingDirectory $Root
    }
}
else {
    Write-Step "Database mode"
    Write-Info "Docker infra is disabled. Backend will use local SQLite for quick testing."
}

Write-Step "Preparing backend"
$venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonPath = Find-CommandPath -Names @("py", "python") -InstallHint "Install Python 3.11+ and make it available in PATH."
    if ($CheckOnly) {
        Write-Info "Would create Python virtual environment at $venvPython"
    }
    elseif ((Split-Path -Leaf $pythonPath) -ieq "py.exe") {
        Invoke-Checked -FilePath $pythonPath -Arguments @("-3", "-m", "venv", ".venv") -WorkingDirectory $BackendDir
    }
    else {
        Invoke-Checked -FilePath $pythonPath -Arguments @("-m", "venv", ".venv") -WorkingDirectory $BackendDir
    }
}
else {
    Write-Info "Python virtual environment exists"
}

$requirementsPath = Join-Path $BackendDir "requirements.lock"
if (-not (Test-Path -LiteralPath $requirementsPath)) {
    $requirementsPath = Join-Path $BackendDir "requirements.txt"
}
$backendStamp = Join-Path $StateDir "backend_requirements.sha256"
$requirementsHash = Get-FileHashText $requirementsPath
$installedRequirementsHash = if (Test-Path -LiteralPath $backendStamp) { (Get-Content -Raw -LiteralPath $backendStamp).Trim() } else { "" }

if ($SkipInstall) {
    Write-Info "Skipping backend dependency install"
}
elseif ($requirementsHash -and ($requirementsHash -ne $installedRequirementsHash)) {
    if ($CheckOnly) {
        Write-Info "Would install backend dependencies from $([System.IO.Path]::GetFileName($requirementsPath))"
    }
    else {
        Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", $requirementsPath) -WorkingDirectory $BackendDir
        Set-Content -LiteralPath $backendStamp -Value $requirementsHash -Encoding ASCII
    }
}
else {
    Write-Info "Backend dependencies are up to date"
}

Write-Step "Preparing frontend"
$nodePath = Find-CommandPath -Names @("node") -InstallHint "Install Node.js 20+ and make it available in PATH."
$npmPath = Find-CommandPath -Names @("npm.cmd", "npm") -InstallHint "Install Node.js/npm and make it available in PATH."
Write-Info "Node: $nodePath"

$nodeModulesPath = Join-Path $WebDir "node_modules"
$packageLockPath = Join-Path $WebDir "package-lock.json"
$packageJsonPath = Join-Path $WebDir "package.json"
$frontendStamp = Join-Path $StateDir "frontend_package.sha256"
$frontendHashSource = if (Test-Path -LiteralPath $packageLockPath) { $packageLockPath } else { $packageJsonPath }
$frontendHash = Get-FileHashText $frontendHashSource
$installedFrontendHash = if (Test-Path -LiteralPath $frontendStamp) { (Get-Content -Raw -LiteralPath $frontendStamp).Trim() } else { "" }

if ($SkipInstall) {
    Write-Info "Skipping frontend dependency install"
}
elseif ((-not (Test-Path -LiteralPath $nodeModulesPath)) -or ($frontendHash -and ($frontendHash -ne $installedFrontendHash))) {
    if ($CheckOnly) {
        if (Test-Path -LiteralPath $packageLockPath) {
            Write-Info "Would install frontend dependencies with npm ci"
        }
        else {
            Write-Info "Would install frontend dependencies with npm install"
        }
    }
    else {
        $npmInstallArguments = if (Test-Path -LiteralPath $packageLockPath) { @("ci") } else { @("install") }
        Invoke-Checked -FilePath $npmPath -Arguments $npmInstallArguments -WorkingDirectory $WebDir
        Set-Content -LiteralPath $frontendStamp -Value $frontendHash -Encoding ASCII
    }
}
else {
    Write-Info "Frontend dependencies are up to date"
}

if ($CheckOnly) {
    Write-Step "Check complete"
    Write-Info "Run .\start_project.bat or .\start_local_test.ps1 to start local testing."
    exit 0
}

Write-Step "Starting backend"
$databaseEnvCommand = ""
$redisEnvCommand = ""
if (-not $WithDockerInfra) {
    $sqlitePath = Join-Path $BackendDir "local_demo.db"
    $sqliteUrl = "sqlite:///" + ($sqlitePath -replace "\\", "/")
    $databaseEnvCommand = "`$env:DATABASE_URL = $(Quote-PS $sqliteUrl)"
}
else {
    # docker-compose.yml protects the development Redis instance with the
    # local-only password "love". Override server/.env so the two launch
    # modes use the same connection settings.
    $redisEnvCommand = "`$env:REDIS_URL = 'redis://:love@127.0.0.1:6379/0'"
}

$backendCommand = @"
`$env:APP_ENV = 'development'
`$env:APP_PORT = '$BackendPort'
`$env:PYTHONUTF8 = '1'
$databaseEnvCommand
$redisEnvCommand
Set-Location -LiteralPath $(Quote-PS $BackendDir)
& $(Quote-PS $venvPython) -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BackendPort
"@
Start-ConsoleWindow -Title "Love Backend" -Command $backendCommand

$healthUrl = "http://127.0.0.1:$BackendPort/health"
Write-Info "Waiting for backend: $healthUrl"
if (Wait-Http -Url $healthUrl -Seconds 45) {
    Write-Info "Backend is responding"
}
else {
    Write-Warning "Backend did not respond within 45 seconds. Check the backend window for details."
}

Write-Step "Starting frontend"
$frontendCommand = @"
`$env:VITE_API_BASE_URL = '/api'
`$env:BACKEND_PROXY_TARGET = 'http://127.0.0.1:$BackendPort'
Set-Location -LiteralPath $(Quote-PS $WebDir)
& $(Quote-PS $npmPath) run dev -- --host 0.0.0.0 --port $FrontendPort
"@
Start-ConsoleWindow -Title "Love Frontend" -Command $frontendCommand

$frontendUrl = "http://localhost:$FrontendPort"
Write-Info "Frontend: $frontendUrl"
Write-Info "API docs: http://localhost:$BackendPort/docs"
Write-Info "Default test accounts: admin/admin, partner/partner"

if (-not $NoBrowser) {
    Start-Sleep -Seconds 3
    Open-DefaultBrowser -Url $frontendUrl
}

Write-Host ""
Write-Host "Launcher finished. Backend and frontend are running in separate windows." -ForegroundColor Green
