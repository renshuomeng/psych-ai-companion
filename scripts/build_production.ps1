$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "Building React production assets..."
Push-Location $FrontendDir
try {
  npm install
  npm run build
} finally {
  Pop-Location
}

Write-Host "Production build created at frontend\dist"
