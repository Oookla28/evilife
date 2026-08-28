# EviLifeHarmony

EviLife 鸿蒙原生客户端（ArkTS + ArkUI，Stage 模型），目标系统 HarmonyOS 6.0（API 20，compatibleSdkVersion `6.0.0(20)`），界面风格对齐 iOS 版本。

## 工程结构

```text
EviLifeHarmony/
├── AppScope/                  # 应用级配置（bundleName、图标、label）
│   ├── app.json5
│   └── resources/
├── entry/
│   ├── build-profile.json5    # 模块级构建配置（含 release 混淆开关）
│   ├── hvigorfile.ts
│   ├── oh-package.json5       # 模块依赖（Health Kit SDK 在此添加）
│   ├── obfuscation-rules.txt
│   └── src/main/
│       ├── module.json5       # 模块清单（权限、Ability）
│       ├── ets/
│       │   ├── entryability/EntryAbility.ets
│       │   ├── common/        # ApiClient / LocalStore / PairingParser / ScanService / HealthSyncService
│       │   └── pages/Index.ets
│       └── resources/
├── build-profile.json5        # 工程级构建配置
├── hvigor/hvigor-config.json5 # hvigor 版本配置
├── hvigorfile.ts
└── oh-package.json5
```

> `hvigorw` / `hvigorw.bat` 与 `hvigor/hvigor-wrapper.js` 为 DevEco 首次打开工程 Sync 时自动生成的包装脚本，未纳入 Git。

## 打开与编译（DevEco Studio 6.0+）

1. 安装 [DevEco Studio 6](https://developer.huawei.com/consumer/cn/deveco-studio/) 与 HarmonyOS SDK（API 20）。
2. `File > Open` 选择 `harmony/EviLifeHarmony`，等待 Sync 完成（会自动补齐 hvigor 包装脚本）。
3. `File > Project Structure > Signing Configs`，勾选自动签名（需华为开发者账号），生成签名配置。
4. `Build > Build Hap(s)/APP(s)`，产物：

```text
entry/build/default/outputs/default/entry-default-signed.hap
```

命令行方式（DevEco Terminal）：

```powershell
hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```

## 真机运行与测试

1. 手机开启「开发者模式 > USB 调试」，用 USB 连接电脑，在 DevEco 中 `File > Project Structure` 确认设备出现在 `Device Manager`。
2. 点击 DevEco 工具栏的 Run 按钮安装到设备；或使用 `hdc install entry/build/default/outputs/default/entry-default-signed.hap`。
3. 与后端联调：确保后端在局域网可达（默认 `http://172.20.10.10:8010`），在 App「设置」页修改服务器地址并保存。
4. 功能验收清单：
   - 登录 / 注册：邮箱 + 密码。
   - 循证问答：提交问题，等待分级回答渲染。
   - 扫码绑定：网页端「健康档案」页生成配对二维码（6 位码），鸿蒙端「打开相机扫码」或手动输入配对码，绑定后自动登录该网页账号。
   - 健康数据同步：完成下方 Health Kit 配置后授权读取并上传。
   - 服务器地址配置：修改后重启 App 仍生效。

## 华为 Health Kit 接入（待配置项）

后端已内置 `huawei_health_kit` 连接器（`backend/app/health_connectors.py`），鸿蒙端已实现上传协议（`HealthSyncService`），仅差华为侧 SDK 与授权：

1. 在 [AppGallery Connect](https://developer.huawei.com/consumer/cn/service/josp/agc/index.html) 创建应用，包名 `com.evilife.harmony`，开通「Health Kit」服务并配置签名证书指纹（SHA-256）。
2. 在 `entry/oh-package.json5` 添加依赖（版本以 AGC 控制台为准）：

```json5
"dependencies": {
  "@hms.health.healthService": "<最新版本>"
}
```

3. 在 DevEco Terminal 执行 `ohpm install`。
4. 按官方文档在 `entry/src/main/module.json5` 的 `requestPermissions` 添加运动健康权限，并在代码中调用授权与读取接口（示意代码见 `HealthSyncService.ets` 注释）。
5. 把读到的步数 / 睡眠 / 心率等聚合值映射为 `HealthObservation`，调用 `HealthSyncService.completePairing()` 上传到网页配对二维码中的 `pairing_url`。

> 注意：配对二维码有有效期（默认 10 分钟）且配对会话一次性使用，上传需要在有效期内完成。

## 关键实现说明

- `ApiClient.ets`：全局复用同一个 `HttpRequest`，保留服务端会话 Cookie；设备配对 claim 后即保持网页账号登录态。
- `PairingParser.ets`：与 iOS `Pairing.swift` 对齐，支持团队协议 JSON（`pairing_url` + `token`）、`code` JSON、URL 参数、URL 尾段、原始 6 位码五种格式。
- `ScanService.ets`：基于系统扫码服务 `@kit.ScanKit`（`scanBarcode.startScanForResult`），无需额外第三方 SDK。
- 界面：iOS 风格浅色分组背景 `#F2F2F7`、白色圆角卡片、底部标签栏、品牌青绿色 `#0F766E`。