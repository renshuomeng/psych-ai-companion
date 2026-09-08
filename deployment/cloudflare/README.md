# Cloudflare Tunnel 演示方案

## Quick Tunnel

Quick Tunnel 用于临时测试：

```powershell
.\scripts\start_public_demo.ps1
```

脚本会构建前端、启动 FastAPI 单端口服务，并运行：

```powershell
cloudflared tunnel --url http://127.0.0.1:8001
```

生成的 `trycloudflare.com` 地址是临时地址，进程停止后失效。公开演示时电脑必须保持开机和联网。

## Named Tunnel

Named Tunnel 用于固定比赛演示地址。步骤概览：

1. 登录 Cloudflare：

```powershell
cloudflared tunnel login
```

2. 创建隧道：

```powershell
cloudflared tunnel create psych-ai-companion
```

3. 复制 `deployment/cloudflare/config.example.yml` 为本机私有配置文件，填入 tunnel ID 和凭据文件路径。
4. 将自定义域名绑定到隧道：

```powershell
cloudflared tunnel route dns psych-ai-companion demo.example.com
```

5. 安装 Windows 服务：

```powershell
$env:CLOUDFLARED_CONFIG="C:\path\to\config.yml"
.\scripts\install_cloudflared_service.ps1
```

不要把 tunnel token、credentials JSON、账号 ID 或真实域名写进仓库。固定域名应转发到本机 `http://127.0.0.1:8001`。
