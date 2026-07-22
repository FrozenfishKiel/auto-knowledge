$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"
$logDir = Join-Path $repoRoot ".agents\logs"
$cacheDir = Join-Path $repoRoot ".agents\cache"
$hfCacheDir = Join-Path $cacheDir "huggingface"
$pidFile = Join-Path $logDir "auto-knowledge-backend.pid"
$outLog = Join-Path $logDir "auto-knowledge-backend.out.log"
$errLog = Join-Path $logDir "auto-knowledge-backend.err.log"
$localEnv = Join-Path $repoRoot ".env.local"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $hfCacheDir | Out-Null

$pythonExe = [Environment]::GetEnvironmentVariable("PYTHON_EXE", "Process")
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonExe = $pythonCommand.Source
        $pythonMode = "python"
    }
}
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonExe = $pythonCommand.Source
        $pythonMode = "py"
    }
}
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    throw "Python was not found. Install Python 3.11/3.12 or set PYTHON_EXE to your Python executable."
}

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $existing = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existing) {
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
    }
}

if (Test-Path $outLog) { Remove-Item $outLog -Force }
if (Test-Path $errLog) { Remove-Item $errLog -Force }

$env:PYTHONPATH = $backendRoot
$env:WEBUI_SECRET_KEY = "dev-auto-knowledge-local-secret"

if (Test-Path $localEnv) {
    Get-Content $localEnv | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"').Trim("'"), "Process")
        }
    }
}

$env:OPENAI_API_BASE_URL = $env:OPENAI_API_BASE_URL -replace "/+$", ""
if ($null -eq [Environment]::GetEnvironmentVariable("RAG_EMBEDDING_ENGINE", "Process")) {
    $env:RAG_EMBEDDING_ENGINE = ""
}
if ($null -eq [Environment]::GetEnvironmentVariable("BYPASS_EMBEDDING_AND_RETRIEVAL", "Process")) {
    $env:BYPASS_EMBEDDING_AND_RETRIEVAL = "false"
}
$env:HF_HOME = $hfCacheDir
$env:HUGGINGFACE_HUB_CACHE = Join-Path $hfCacheDir "hub"
$env:TRANSFORMERS_CACHE = Join-Path $hfCacheDir "transformers"
$env:SENTENCE_TRANSFORMERS_HOME = Join-Path $hfCacheDir "sentence-transformers"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:HF_HUB_DISABLE_XET = "1"

$pythonArgs = @("-m", "uvicorn", "open_webui.main:app", "--host", "127.0.0.1", "--port", "8081")
if ($pythonMode -eq "py") {
    $pythonArgs = @("-3") + $pythonArgs
}

$process = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $pythonArgs `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $pidFile -Value $process.Id
Write-Output "started:$($process.Id)"
