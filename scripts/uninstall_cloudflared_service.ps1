$ErrorActionPreference = "Stop"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  throw "cloudflared 未找到。"
}

cloudflared service uninstall
Write-Host "cloudflared 服务已卸载。"
