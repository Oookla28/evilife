# EviLife 部署说明

## 推荐架构

- 前端：Vercel（Next.js 16）。
- 后端：Render Docker Web Service。
- 运行数据：Render 持久卷中的 SQLite，单实例运行。
- 医学证据：Docker 镜像内的只读 `authoritative_health.sqlite3`。

前端统一请求 `/api/v1/*`，由 Next.js 同源转发到 `BACKEND_ORIGIN`。这样登录 Cookie 不需要暴露给跨域 JavaScript。

## 1. 部署后端

在 Render 连接 GitHub 仓库并使用根目录的 `render.yaml`。在服务环境变量中填写：

```dotenv
DEEPSEEK_API_KEY=在平台密钥管理中填写，禁止提交到 GitHub
EVILIFE_ALLOWED_ORIGINS=https://你的前端域名.vercel.app
```

持久卷挂载到 `/var/data`；不得横向扩展多个实例。若比赛后需要多实例或高并发，将运行库迁移至 PostgreSQL，再把报告文件放入对象存储。

## 2. 部署前端

在 Vercel 导入同一仓库，Framework 选择 Next.js，添加：

```dotenv
BACKEND_ORIGIN=https://你的-render-服务.onrender.com
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_USE_MOCKS=false
```

留空 `NEXT_PUBLIC_API_BASE_URL` 很重要：浏览器始终访问同源 `/api/v1`，由服务端 rewrite 转发。

## 3. 上线验收

1. `GET /api/v1/health` 返回 `status=ok`。
2. 新建测试账号，退出后重新登录。
3. 保存一条生活版对话和一条专业版对话，重新登录后历史仍存在。
4. 导入同一份 Apple Health 数据两次，第二次应显示跳过重复项。
5. 检查权威库完整性、外键检查和 33 条可检索主张。

## 密钥处理

任何真实 API Key 只放在 Render/Vercel Secret 环境变量中。若密钥曾出现在聊天、截图、日志或提交历史中，应先撤销并生成新密钥再上线。
