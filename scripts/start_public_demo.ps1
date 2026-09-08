$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$EnvPath = Join-Path $ProjectRoot ".env"
$LogDir = Join-Path $ProjectRoot "logs\public-demo"
$StatePath = Join-Path $LogDir "state.json"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Require-Command($name, $message) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw $message
  }
}

Require-Command python "Python 未找到，请先安装或加入 PATH。"
Require-Command node "Node.js 未找到，请先安装或加入 PATH。"
Require-Command npm "npm 未找到，请先安装 Node.js。"
Require-Command cloudflared "cloudflared 未找到，请先安装 Cloudflare Tunnel 客户端。"

if (-not (Test-Path $EnvPath)) {
  throw ".env 不存在，请先在项目根目录创建并填写豆包配置。"
}

$envLines = Get-Content -Encoding UTF8 -Path $EnvPath
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
if (-not (Test-ToolConfigured "ffmpeg" "FFMPEG_PATH")) {
  Write-Warning "ffmpeg 未找到：音频转码和视频处理会不可用。"
}
if (-not (Test-ToolConfigured "ffprobe" "FFPROBE_PATH")) {
  Write-Warning "ffprobe 未找到：音视频真实格式验证会不可用。"
}
$arkLine = $envLines | Where-Object { $_ -match '^ARK_API_KEY=.+$' } | Select-Object -First 1
if (-not $arkLine) {
  throw "ARK_API_KEY 未配置。请在 .env 中填写，但不要把密钥发给他人。"
}
$accessLine = $envLines | Where-Object { $_ -match '^PUBLIC_ACCESS_CODE=.+$' } | Select-Object -First 1
if (-not $accessLine) {
  throw "PUBLIC_ACCESS_CODE 未配置。公网演示必须先在 .env 写入演示访问码。"
}

Push-Location $FrontendDir
try {
  npm install
  npm run build
} finally {
  Pop-Location
}

$backendOut = Join-Path $LogDir "backend.out.log"
$backendErr = Join-Path $LogDir "backend.err.log"
$tunnelOut = Join-Path $LogDir "cloudflared.out.log"
$tunnelErr = Join-Path $LogDir "cloudflared.err.log"

$backendCommand = "`$env:APP_ENV='public_demo'; `$env:PUBLIC_ACCESS_ENABLED='true'; `$env:SERVE_FRONTEND='true'; python -m uvicorn main:app --host 127.0.0.1 --port 8001"
$backend = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) -WorkingDirectory $BackendDir -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -WindowStyle Hidden -PassThru

$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/health" -TimeoutSec 3
    if ($health.status -eq "ok") {
      $healthy = $true
      break
    }
  } catch {}
}
if (-not $healthy) {
  Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
  throw "FastAPI 未能在 30 秒内通过 /api/health，请查看 logs\public-demo\backend.err.log。"
}

$tunnel = Start-Process -FilePath "cloudflared" -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8001") -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr -WindowStyle Hidden -PassThru

$publicUrl = ""
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep -Seconds 1
  $combined = ""
  if (Test-Path $tunnelOut) { $combined += Get-Content -Raw -Encoding UTF8 -Path $tunnelOut }
  if (Test-Path $tunnelErr) { $combined += Get-Content -Raw -Encoding UTF8 -Path $tunnelErr }
  $match = [regex]::Match($combined, "https://[a-zA-Z0-9-]+\.trycloudflare\.com")
  if ($match.Success) {
    $publicUrl = $match.Value
    break
  }
}

@{
  backend_pid = $backend.Id
  cloudflared_pid = $tunnel.Id
  local_url = "http://127.0.0.1:8001"
  public_url = $publicUrl
  started_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -Encoding UTF8 -Path $StatePath

Write-Host "Public demo local URL: http://127.0.0.1:8001"
if ($publicUrl) {
  Write-Host "Temporary HTTPS URL: $publicUrl"
} else {
  Write-Warning "cloudflared 已启动，但暂未解析到 HTTPS 地址，请查看 $tunnelErr。"
}
Write-Host "Quick Tunnel 是临时地址，进程停止后会失效。"
