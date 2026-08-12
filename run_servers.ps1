# Compatibility wrapper for the unified local launcher.
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall,
    [switch]$WithDockerInfra,
    [switch]$NoBrowser,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $Root "start_local_test.ps1"

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Local launcher not found: $Launcher"
}

$LauncherArgs = @(
    "-BackendPort", $BackendPort,
    "-FrontendPort", $FrontendPort
)
if ($SkipInstall) { $LauncherArgs += "-SkipInstall" }
if ($WithDockerInfra) { $LauncherArgs += "-WithDockerInfra" }
if ($NoBrowser) { $LauncherArgs += "-NoBrowser" }
if ($CheckOnly) { $LauncherArgs += "-CheckOnly" }

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Launcher @LauncherArgs
exit $LASTEXITCODE
