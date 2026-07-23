$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"
$logDir = Join-Path $repoRoot ".agents\logs"
$localEnv = Join-Path $repoRoot ".env.local"
$backendLog = Join-Path $logDir "project-backend.log"
$backendErrLog = Join-Path $logDir "project-backend.err.log"
$frontendLog = Join-Path $logDir "project-frontend.log"
$frontendErrLog = Join-Path $logDir "project-frontend.err.log"
$backendUrl = "http://127.0.0.1:8080"
$frontendUrl = "http://localhost:5173"
$preferredLocalPython = "D:\Anaconda3\envs\ai-content-ops\python.exe"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Read-LocalEnv {
    if (-not (Test-Path $localEnv)) {
        return
    }

    Get-Content $localEnv | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($name) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Get-PythonVersion {
    param(
        [string]$File,
        [string[]]$ArgsPrefix
    )

    $output = & $File @ArgsPrefix --version 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $output) {
        return $null
    }

    try {
        $text = ($output | Select-Object -Last 1).ToString().Trim()
        if ($text.StartsWith("Python ")) {
            $text = $text.Substring(7).Trim()
        }
        return [version]$text
    } catch {
        return $null
    }
}

function Get-PythonCommand {
    $pythonExe = [Environment]::GetEnvironmentVariable("PYTHON_EXE", "Process")
    if ($pythonExe) {
        $pythonVersion = Get-PythonVersion -File $pythonExe -ArgsPrefix @()
        if ($pythonVersion -and $pythonVersion.Major -ge 3 -and $pythonVersion.Minor -ge 11) {
            return @{ File = $pythonExe; ArgsPrefix = @() }
        }
    }

    if (Test-Path $preferredLocalPython) {
        $pythonVersion = Get-PythonVersion -File $preferredLocalPython -ArgsPrefix @()
        if ($pythonVersion -and $pythonVersion.Major -ge 3 -and $pythonVersion.Minor -ge 11) {
            return @{ File = $preferredLocalPython; ArgsPrefix = @() }
        }
    }

    if (Test-Command "python") {
        $pythonVersion = Get-PythonVersion -File "python" -ArgsPrefix @()
        if ($pythonVersion -and $pythonVersion.Major -ge 3 -and $pythonVersion.Minor -ge 11) {
            return @{ File = "python"; ArgsPrefix = @() }
        }
    }

    if (Test-Command "py") {
        $pyList = & py -0p 2>$null
        if ($LASTEXITCODE -eq 0 -and $pyList) {
            foreach ($line in $pyList) {
                if ($line -notmatch '^\s*-V:(?<tag>[^\s]+).*?(?<path>[A-Za-z]:\\.*python\.exe)\s*$') {
                    continue
                }

                $path = $Matches['path']
                if (-not (Test-Path $path)) {
                    continue
                }

                $pythonVersion = Get-PythonVersion -File $path -ArgsPrefix @()
                if ($pythonVersion -and $pythonVersion.Major -ge 3 -and $pythonVersion.Minor -ge 11) {
                    return @{ File = $path; ArgsPrefix = @() }
                }
            }
        }
    }

    throw "Python 3.11/3.12 was not found. Install it, or set PYTHON_EXE to a compatible interpreter first."
}

function Get-NpmCommand {
    $npmCommand = Get-Command "npm" -ErrorAction SilentlyContinue
    if (-not $npmCommand) {
        throw "npm was not found. Install npm first."
    }

    if ($npmCommand.Source -and $npmCommand.Source.EndsWith(".cmd")) {
        return $npmCommand.Source
    }

    $npmCmd = Join-Path (Split-Path -Parent $npmCommand.Source) "npm.cmd"
    if (Test-Path $npmCmd) {
        return $npmCmd
    }

    return $npmCommand.Source
}

function Invoke-Python {
    param(
        [hashtable]$Python,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $repoRoot
    )

    $allArgs = @($Python.ArgsPrefix) + $Arguments
    & $Python.File @allArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Arguments -join ' ')"
    }
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    return $false
}

function Ensure-FrontendDeps {
    param([string]$Npm)

    if (Test-Path (Join-Path $repoRoot "node_modules")) {
        return
    }

    Write-Step "Installing frontend dependencies with npm ci"
    $process = Start-Process -FilePath $Npm -ArgumentList @("ci") -WorkingDirectory $repoRoot -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Frontend dependency install failed. Check Node.js/npm and run this launcher again."
    }
}

function Ensure-BackendDeps {
    param([hashtable]$Python)

    $checkArgs = @("-c", "import fastapi, uvicorn, sqlalchemy")
    $allArgs = @($Python.ArgsPrefix) + $checkArgs
    & $Python.File @allArgs
    if ($LASTEXITCODE -eq 0) {
        return
    }

    Write-Step "Installing backend dependencies from backend/requirements.txt"
    Invoke-Python -Python $Python -Arguments @("-m", "pip", "install", "-r", "backend/requirements.txt")
}

function Start-Backend {
    param([hashtable]$Python)

    if (Wait-Http "$backendUrl/health" 3) {
        Write-Host "Backend is already running at $backendUrl."
        return $null
    }

    Write-Step "Starting backend at $backendUrl"
    $env:PYTHONPATH = $backendRoot
    if (-not $env:WEBUI_SECRET_KEY) {
        $env:WEBUI_SECRET_KEY = "dev-local-secret"
    }
    if (-not $env:CORS_ALLOW_ORIGIN) {
        $env:CORS_ALLOW_ORIGIN = "http://localhost:5173;http://127.0.0.1:5173;http://localhost:8080"
    }

    $args = @($Python.ArgsPrefix) + @("-m", "uvicorn", "open_webui.main:app", "--host", "127.0.0.1", "--port", "8080")
    return Start-Process -FilePath $Python.File -ArgumentList $args -WorkingDirectory $backendRoot -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrLog -WindowStyle Hidden -PassThru
}

function Start-Frontend {
    param([string]$Npm)

    if (Wait-Http $frontendUrl 3) {
        Write-Host "Frontend is already running at $frontendUrl."
        return $null
    }

    Write-Step "Starting frontend at $frontendUrl"
    return Start-Process -FilePath $Npm -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") -WorkingDirectory $repoRoot -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrLog -WindowStyle Hidden -PassThru
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Read-LocalEnv

if (-not (Test-Command "node")) {
    throw "Node.js was not found. Install Node.js 18.13 to 22.x first."
}
$python = Get-PythonCommand
$npm = Get-NpmCommand
Ensure-FrontendDeps -Npm $npm
Ensure-BackendDeps -Python $python

$backendProcess = Start-Backend -Python $python
if (-not (Wait-Http "$backendUrl/health" 120)) {
    throw "Backend startup timed out. Logs: $backendLog / $backendErrLog"
}

$frontendProcess = Start-Frontend -Npm $npm
if (-not (Wait-Http $frontendUrl 120)) {
    throw "Frontend startup timed out. Logs: $frontendLog / $frontendErrLog"
}

Write-Step "Project is running"
Write-Host "Frontend: $frontendUrl"
Write-Host "Backend:  $backendUrl"
Write-Host "Backend logs:  $backendLog / $backendErrLog"
Write-Host "Frontend logs: $frontendLog / $frontendErrLog"
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "Keep this window open while using the project. Press Enter to stop services started by this launcher."
[void][Console]::ReadLine()

foreach ($process in @($frontendProcess, $backendProcess)) {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}
