# BS pipeline driver (prereg/tests_v2.json): extraction (resumable, retried), BS0/BS1 analysis, BS2 aggregate, figures.
# Each step writes results/v2/BS_logs/<name>.log (+ .err) and appends a line to results/v2/trial_log_v2.csv
# (id, timestamp, script, prereg_v2 sha256, verdict or descriptive, seconds). Messages of this driver: results/v2/BS_logs/driver.log.
# Usage (from anywhere): powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bs_run_all.ps1
param([int]$MaxExtractPasses = 3)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = if ($env:ALTDATA_PYTHON) { $env:ALTDATA_PYTHON } else { 'C:/Users/Hamza/AppData/Local/Microsoft/WindowsApps/python3.11.exe' }
$v2 = Join-Path $root 'results/v2'
$logs = Join-Path $v2 'BS_logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$env:PYTHONUNBUFFERED = '1'; $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONWARNINGS = 'ignore'
$env:OPENBLAS_NUM_THREADS = '1'; $env:OMP_NUM_THREADS = '1'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$driverLog = Join-Path $logs 'driver.log'
$trial = Join-Path $v2 'trial_log_v2.csv'

function Log([string]$m) {
    $line = (Get-Date -Format 's') + ' ' + $m
    Write-Host $line
    [System.IO.File]::AppendAllText($driverLog, $line + "`n", $utf8)
}

$recorded = ((Get-Content (Join-Path $v2 'prereg_v2.sha256') -TotalCount 1) -split '\s+')[0].ToLower()
$sha = (Get-FileHash (Join-Path $root 'prereg/tests_v2.json') -Algorithm SHA256).Hash.ToLower()
if ($sha -ne $recorded) { Log "STOP: prereg/tests_v2.json $sha differs from the frozen hash $recorded"; exit 2 }
Log "driver start; prereg_v2 sha256 $sha"

function Add-Trial([string]$id, [string]$script, [string]$verdict, [double]$sec) {
    if (-not (Test-Path $trial)) { [System.IO.File]::AppendAllText($trial, "id,timestamp,script,prereg_v2_sha256,verdict,seconds`n", $utf8) }
    $line = '{0},{1},{2},{3},{4},{5}' -f $id, (Get-Date -Format 's'), $script, $sha, $verdict, $sec.ToString('F1', [Globalization.CultureInfo]::InvariantCulture)
    [System.IO.File]::AppendAllText($trial, $line + "`n", $utf8)
}

function Run-Step([string]$name, [string]$script) {
    $out = Join-Path $logs "$name.log"
    $err = Join-Path $logs "$name.err"
    Log "START $name ($script) -> $out"
    $t0 = Get-Date
    $p = Start-Process -FilePath $py -ArgumentList @('-u', $script) -RedirectStandardOutput $out -RedirectStandardError $err -NoNewWindow -Wait -PassThru
    $sec = ((Get-Date) - $t0).TotalSeconds
    Log ("END   {0} exit={1} seconds={2:F1}" -f $name, $p.ExitCode, $sec)
    return @{ code = $p.ExitCode; sec = $sec }
}

# 1. extraction: resumable, so a pass only retries what is missing; stop if something is still missing afterwards
$statusFile = Join-Path $v2 'BS1/extract_status.json'
$complete = $false
for ($i = 1; $i -le $MaxExtractPasses; $i++) {
    $name = if ($i -eq 1) { 'bs1_extract' } else { "bs1_extract_pass$i" }
    if (Test-Path $statusFile) { Remove-Item $statusFile }
    $r = Run-Step $name 'scripts/bs1_extract.py'
    Add-Trial 'BS1' "scripts/bs1_extract.py (pass $i)" 'descriptive' $r.sec
    $failed = -1
    if (Test-Path $statusFile) { $failed = [int]((Get-Content $statusFile -Raw | ConvertFrom-Json).n_failed) }
    if ($r.code -eq 0 -and $failed -eq 0) { $complete = $true; break }
    Log "extraction pass $i incomplete (exit $($r.code), failed acquisitions $failed); next pass after 120 s"
    Start-Sleep -Seconds 120
}
if (-not $complete) { Log 'STOP: extraction incomplete after all passes; analysis steps not run (see bs1_extract*.log and results/v2/BS1/extract_failures.csv)'; exit 3 }

# 2. descriptive analysis (BS0 availability, BS1 coverage, identifiability, stability); BS2 does not depend on it
$r = Run-Step 'bs1_analysis' 'scripts/bs1_analysis.py'
Add-Trial 'BS0+BS1' 'scripts/bs1_analysis.py' $(if ($r.code -eq 0) { 'descriptive' } else { "FAILED exit $($r.code)" }) $r.sec

# 3. BS2: the pre-registered statistic, computed once
$bs2Json = Join-Path $v2 'BS2/bs2.json'
if (Test-Path $bs2Json) { Remove-Item $bs2Json }
$r = Run-Step 'bs2_aggregate' 'scripts/bs2_aggregate.py'
$verdict = "FAILED exit $($r.code)"
if ($r.code -eq 0 -and (Test-Path $bs2Json)) { $verdict = (Get-Content $bs2Json -Raw | ConvertFrom-Json).primary.verdict }
Add-Trial 'BS2' 'scripts/bs2_aggregate.py' $verdict $r.sec

# 4. figures
$r = Run-Step 'fig_bs' 'scripts/fig_bs.py'
Add-Trial 'FIG' 'scripts/fig_bs.py' $(if ($r.code -eq 0) { 'descriptive' } else { "FAILED exit $($r.code)" }) $r.sec
Log "driver done; BS2 primary verdict: $verdict"
