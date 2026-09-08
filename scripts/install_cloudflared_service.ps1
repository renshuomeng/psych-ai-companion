$ErrorActionPreference = "Stop"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  throw "cloudflared 未找到，请先安装。"
}
if (-not $env:CLOUDFLARED_CONFIG) {
  throw "请先设置 CLOUDFLARED_CONFIG，指向你的 Named Tunnel config.yml。"
}
if (-not (Test-Path $env:CLOUDFLARED_CONFIG)) {
  throw "CLOUDFLARED_CONFIG 指向的文件不存在。"
}

cloudflared service install
Write-Host "cloudflared 服务已安装。请确认服务配置使用你的私有 config.yml。"
