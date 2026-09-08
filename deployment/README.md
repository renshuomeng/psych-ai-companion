# 部署说明

本目录提供稳定公网部署的基础文件。不要把 `.env`、数据库、上传文件、Cloudflare token 或真实 API Key 放进镜像或提交到仓库。

## Docker Compose

1. 在项目根目录准备 `.env`，至少填写 `ARK_API_KEY`、模型 ID、`PUBLIC_ACCESS_CODE`。
2. 设置域名：

```powershell
$env:PUBLIC_DOMAIN="your-domain.example.com"
```

3. 构建并启动：

```powershell
docker compose up --build -d
```

`app` 容器只暴露给 `reverse-proxy`，Caddy 负责公网 HTTPS、请求体大小限制和安全响应头。SQLite 与上传目录使用 volume 保存。

## 与 Cloudflare Tunnel 的关系

Docker Compose 适合云服务器或固定机器部署；Cloudflare Tunnel 适合不直接开放公网端口的演示环境。两种方式都指向同一个 FastAPI 单入口服务，不需要公开 Vite 5173。
