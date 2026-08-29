# EviLife iOS 应用

基于 [Oookla28/evilife](https://github.com/Oookla28/evilife)（Next.js + FastAPI 循证健康平台）的**原生 iPhone 端**（SwiftUI，iOS 17+）。

```text
ios/
├── EviLife.xcodeproj/            # Xcode 工程（objectVersion 77，文件夹同步组）
├── EviLife/
│   ├── EviLifeApp.swift          # 入口
│   ├── RootView.swift            # 5 个标签页：问答 / 今日 / 健康 / 报告 / 设置
│   ├── AppState.swift            # 会话与登录状态（cookie 会话）
│   ├── Config.swift              # 服务器地址配置（默认 http://127.0.0.1:8000）
│   ├── Models.swift              # 与后端契约一一对应的 Codable 模型 + JSONValue
│   ├── APIClient.swift           # URLSession + cookie 会话 + multipart
│   ├── SSEClient.swift           # /runs/{id}/events 的 SSE 客户端
│   ├── Endpoints.swift           # 全部 REST 接口的强类型封装
│   ├── HealthKitSyncService.swift# 健康同步桥（授权 → 聚合查询 → ingest）
│   ├── Theme.swift               # 证据/裁决配色与标签
│   ├── Features/
│   │   ├── AuthView.swift        # 登录 / 注册（游客可跳过）
│   │   ├── ChatView.swift        # 循证问答：文字 + 餐食图片、模式切换
│   │   ├── ChatViewModel.swift   # orchestrate → SSE → 模块渲染 → 会话保存
│   │   ├── ModuleViews.swift     # 模块注册表：EvidenceAnswer / Verdict / 引用 /
│   │   │                         # SafetyCard / GeneralAnswerCard / Crisis /
│   │   │                         # Clarification / HealthRecordDraft / MealAnalyzer /
│   │   │                         # FastingTimer / DocumentSummary …
│   │   ├── TodayView.swift       # 今日：禁食计时、餐食、健康记录 + 快速记录
│   │   ├── HealthView.swift      # HealthKit 同步、健康档案分析、连接器
│   │   ├── ReportsView.swift     # 体检报告上传（PDF/TXT/CSV/图片）与历史
│   │   ├── HistoryView.swift     # 云端历史对话（登录后）
│   │   └── SettingsView.swift    # 账号、服务器地址、免责声明
│   ├── Assets.xcassets/
│   └── EviLife.entitlements      # com.apple.developer.healthkit
└── README.md
```

## 运行

### 1. 后端（FastAPI，本仓库 `backend/` 已就位）

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
# backend/.env 已生成；默认 EVILIFE_AUTH_REQUIRED=false（允许游客模式）
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend \
  --env-file backend/.env --host 127.0.0.1 --port 8000
```

健康检查：<http://127.0.0.1:8000/api/v1/health>

未配置 `DEEPSEEK_API_KEY` 时：命中预编译 Evidence Packet（钠、咖啡、睡眠、鸡蛋、地中海饮食、限时进食）走纯本地证据链；未命中主题由离线权威语料库给出 `hybrid_corpus` 双向证据回答；餐食图片识别需要独立的 `EVILIFE_VISION_*` 服务。

### 2. iOS 应用

```bash
cd ios
xcodebuild -project EviLife.xcodeproj -scheme EviLife \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build
xcrun simctl install booted \
  ~/Library/Developer/Xcode/DerivedData/EviLife-*/Build/Products/Debug-iphonesimulator/EviLife.app
xcrun simctl launch booted com.evilife.ios
```

或用 Xcode 直接打开 `ios/EviLife.xcodeproj` 运行。

- 模拟器可直连 `http://127.0.0.1:8000`（ATS 豁免回环地址）。
- 真机调试：在「设置 → 服务器」里改成 Mac 的局域网 IP，并把该来源加入后端
  `EVILIFE_ALLOWED_ORIGINS`（iOS 原生请求不受 CORS 限制，但建议保持一致），
  HTTP 明文需自行处理 ATS 例外；生产必须 HTTPS。
- 服务器地址仅存 UserDefaults，不写入任何密钥。

## 与网页端的功能对齐

| 网页端 | iOS 端 |
|---|---|
| `POST /orchestrate` + SSE 事件流 | `ChatViewModel.send` → `API.orchestrate` → `SSEClient`，事件驱动更新路由/证据快照/模块计划 |
| `EvidenceAnswer` + `VerdictCard` + 引用 | `EvidenceAnswerCard`：结论、三态 Gate、裁决（是/部分正确/否/证据不足）、支持/反对证据、适用人群、TCM 视角、引用链接 |
| 安全/通用/澄清/危机卡片 | `SafetyCardView` / `GeneralAnswerCardView` / `ClarificationCardView` / `CrisisCardView` |
| 健康记录草稿（确认后批量写入） | `HealthRecordDraftCard` → `POST /observations/batch` |
| 餐食识别 + 确认 | `MealAnalyzerCard` → `POST /actions/{id}/confirm` |
| 今日（禁食/餐食/记录） | `TodayView` + `ObservationSheet` |
| Apple 健康 XML 导入（网页） | HealthKit 原生桥（见下） |
| 健康档案分析 | `HealthView` → `POST /profile/analyze` |
| 体检报告分析 | `ReportsView` → `POST /reports/analyze` + `GET /reports` |
| 历史对话 | `HistoryView` → `GET/PUT/DELETE /conversations` |
| 账号 | `AuthView` → cookie 会话，与网页同一 `evilife_session` |

## HealthKit 同步（`HealthKitSyncService.swift`）

沿用仓库 `ios/` 骨架并补全实现：

1. `requestAccess()` 逐类申请：步数、睡眠、静息心率、体重（不写入任何类型）。
2. `query(days: 30)` 先逐类核对 `authorizationStatus`，只查询已授权类型
   （拒绝的类别不推断、不绕过）：
   - 步数：`HKStatisticsCollectionQuery` 日累计；
   - 静息心率：日离散平均；
   - 睡眠：仅统计 `Asleep*` 阶段（排除 InBed/Awake）；
   - 体重：每日最新样本（统一换算 kg）。
3. `sync()` 生成 `<500` 条聚合记录，带 `consent_receipt` POST 到
   `/api/v1/health-connectors/apple_healthkit/ingest`，`external_id` 形如
   `hk:steps:2026-08-28`（幂等，重复同步被服务端去重）。

Apple 账户只负责身份认证；健康数据权限始终由 HealthKit 单独控制。

**真机要求**：Signing & Capabilities 中加入 HealthKit 并配置团队签名
（工程已带 `EviLife.entitlements`，模拟器演示无需团队）。

## 说明

- 工程使用 Xcode 16+ 的**文件夹同步组**（file-system synchronized groups）：
  向 `EviLife/` 添加新 Swift 文件即可自动进入 target，无需改 pbxproj。
- `Info.plist` 由 `GENERATE_INFOPLIST_FILE` + `INFOPLIST_KEY_*` 生成，
  已含健康/相册用途描述与启动屏配置。
- 医学免责声明：本应用提供循证健康信息，不构成诊断或治疗建议。
