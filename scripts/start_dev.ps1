$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$LogDir = Join-Path $ProjectRoot "logs"
$StatePath = Join-Path $LogDir "dev-state.json"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$backendOut = Join-Path $LogDir "dev-backend.out.log"
$backendErr = Join-Path $LogDir "dev-backend.err.log"
$frontendOut = Join-Path $LogDir "dev-frontend.out.log"
$frontendErr = Join-Path $LogDir "dev-frontend.err.log"

$backendCommand = "`$env:APP_ENV='development'; `$env:BACKEND_PORT='8001'; python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload"
$backend = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) -WorkingDirectory $BackendDir -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -WindowStyle Hidden -PassThru

$frontendCommand = "npm run dev -- --host 127.0.0.1 --port 5173"
$frontend = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) -WorkingDirectory $FrontendDir -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -WindowStyle Hidden -PassThru

@{
  backend_pid = $backend.Id
  frontend_pid = $frontend.Id
  backend_url = "http://127.0.0.1:8001"
  frontend_url = "http://127.0.0.1:5173"
  started_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -Encoding UTF8 -Path $StatePath

Write-Host "Dev backend:  http://127.0.0.1:8001/api/health"
Write-Host "Dev frontend: http://127.0.0.1:5173"
Write-Host "PIDs saved to $StatePath"
