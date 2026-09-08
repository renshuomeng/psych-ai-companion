$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StatePath = Join-Path $ProjectRoot "logs\public-demo\state.json"

if (-not (Test-Path $StatePath)) {
  Write-Host "No public demo state file found."
  exit 0
}

$state = Get-Content -Encoding UTF8 -Path $StatePath | ConvertFrom-Json
foreach ($processId in @($state.cloudflared_pid, $state.backend_pid)) {
  if ($processId) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
      Stop-Process -Id $processId -Force
      Write-Host "Stopped process $processId"
    }
  }
}
Remove-Item -LiteralPath $StatePath -Force
Write-Host "Public demo stopped."
