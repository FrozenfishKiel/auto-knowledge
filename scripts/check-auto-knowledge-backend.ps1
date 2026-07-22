$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot ".agents\logs"
$pidFile = Join-Path $logDir "auto-knowledge-backend.pid"
$outLog = Join-Path $logDir "auto-knowledge-backend.out.log"
$errLog = Join-Path $logDir "auto-knowledge-backend.err.log"

$result = [ordered]@{
    running = $false
    pid = $null
    health = $null
    out_log = $null
    err_log = $null
}

if (Test-Path $pidFile) {
    $backendPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($backendPid) {
        $result.pid = [int]$backendPid
        $process = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
        if ($process) {
            $result.running = $true
        }
    }
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8081/health" -TimeoutSec 5
    $result.health = $health
} catch {
    $result.health = $_.Exception.Message
}

if (Test-Path $outLog) {
    $result.out_log = Get-Content $outLog -Tail 40
}

if (Test-Path $errLog) {
    $result.err_log = Get-Content $errLog -Tail 40
}

$result | ConvertTo-Json -Depth 5
