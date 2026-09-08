$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvPath = Join-Path $ProjectRoot ".env"
$StatePath = Join-Path $ProjectRoot "logs\public-demo\state.json"

$state = $null
if (Test-Path $StatePath) {
  $state = Get-Content -Encoding UTF8 -Path $StatePath | ConvertFrom-Json
}

function Test-Pid($processId) {
  if (-not $processId) { return $false }
  return [bool](Get-Process -Id $processId -ErrorAction SilentlyContinue)
}

$health = $null
try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/health" -TimeoutSec 5
} catch {}

$envLines = @()
if (Test-Path $EnvPath) {
  $envLines = Get-Content -Encoding UTF8 -Path $EnvPath
}

$arkConfigured = [bool]($envLines | Where-Object { $_ -match '^ARK_API_KEY=.+$' } | Select-Object -First 1)
$speechConfigured = [bool]($envLines | Where-Object { $_ -match '^(VOLC_SPEECH_API_KEY|VOLC_SPEECH_APP_ID|VOLC_SPEECH_ACCESS_KEY)=.+$' } | Select-Object -First 1)
function Get-EnvValue($name) {
  $line = $envLines | Where-Object { $_ -match "^$name=" } | Select-Object -First 1
  if ($line) { return ($line -split "=", 2)[1].Trim() }
  return ""
}
function Test-ToolConfigured($commandName, $envName) {
  $configuredPath = Get-EnvValue $envName
  if ($configuredPath -and (Test-Path $configuredPath)) { return $true }
  return [bool](Get-Command $commandName -ErrorAction SilentlyContinue)
}

[pscustomobject]@{
  fastapi_running = Test-Pid $state.backend_pid
  tunnel_running = Test-Pid $state.cloudflared_pid
  health_status = if ($health) { $health.status } else { "unreachable" }
  ffmpeg = if (Test-ToolConfigured "ffmpeg" "FFMPEG_PATH") { "ok" } else { "missing" }
  ffprobe = if (Test-ToolConfigured "ffprobe" "FFPROBE_PATH") { "ok" } else { "missing" }
  ark_text_configured = $arkConfigured
  doubao_speech_configured = $speechConfigured
  public_url = if ($state.public_url) { $state.public_url } else { "" }
  active_jobs = if ($health) { $health.dependencies.active_jobs } else { "" }
} | Format-List
