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

## 环境要求

- DevEco Studio 6.0+（本机已验证 6.1.1.300，HarmonyOS SDK 6.1.1 / API 24）
- 工程路径只能包含 ASCII 字符（字母、数字、`-`、`_`、`.`、空格、括号、`@`），不能放在中文目录下

## 编译（命令行）

PowerShell 示例（DevEco 自带工具链）：

```powershell
$env:NODE_HOME   = "D:\DevEco Studio\tools\node"
$env:JAVA_HOME   = "D:\DevEco Studio\jbr"
$env:DEVECO_SDK_HOME = "D:\DevEco Studio\sdk"
$env:Path = "$env:NODE_HOME;$env:JAVA_HOME\bin;" + $env:Path

cd harmony/EviLifeHarmony
# 首次构建先安装空依赖（无第三方包，离线可用）
D:\DevEco Studio\tools\ohpm\bin\ohpm.bat install
# 构建（未签名）
D:\DevEco Studio\tools\hvigor\bin\hvigorw.bat assembleHap --no-daemon
```

产物：`entry/build/default/outputs/default/entry-default-unsigned.hap`

首次命令行构建若报 `Invalid project path`，请检查工程路径是否含中文；若报 `spawn java ENOENT`，请确认 `JAVA_HOME` 指向 DevEco 自带 JBR（`D:\DevEco Studio\jbr`）。

## 打开与编译（DevEco Studio）

1. `File > Open` 选择 `harmony/EviLifeHarmony`，等待 Sync 完成。
2. `File > Project Structure > Signing Configs`，勾选自动签名（需华为开发者账号），生成签名配置。
3. `Build > Build Hap(s)/APP(s)`，产物：`entry/build/default/outputs/default/entry-default-signed.hap`。

## 签名：本地自签（仅验证） vs AGC 自动签名（真机安装）

> 结论：本地自签的 CA 不在华为信任链内，Pura 70 Ultra 安装时会报证书无效并拒绝安装；真机安装必须走 AGC 自动签名。

### AGC 自动签名（真机可安装）

1. 在 [AppGallery Connect](https://developer.huawei.com/consumer/cn/service/josp/agc/index.html) 创建应用，包名 `com.evilife.harmony`，开通所需服务（Health Kit 等）。
2. 用华为开发者账号登录 DevEco Studio。
3. `File > Project Structure > Signing Configs`，勾选 **Automatically generate signature（自动生成签名）**，选择调试证书与调试 Profile（自动签名会同步登记应用 SHA-256 指纹）。
4. `Build > Build Hap(s)/APP(s)` 重新构建，得到 `entry/build/default/outputs/default/entry-default-signed.hap`，此产物可直接 `hdc install` 到真机。

### 本地自签（演示/验证用，不装真机）

用 hap-sign-tool 生成自签证书链并给 HAP 打签名：

- 本工具版本的 `sign-app` 参数为：`-mode localSign`、`-keyAlias`、`-keyPwd`、`-keystoreFile`、`-keystorePwd`、`-appCertFile`、`-profileFile`、`-profileSigned 1`、`-inFile`、`-outFile`、`-signAlg`、`-compatibleVersion 20`、`-signCode 1`。旧文档中的 `-privateKey`、`-keystore`、`-keystorepasswd`、`-keypasswd` 不是本版本参数名。
- 完整可运行的签名脚本在仓库外（`Desktop\新建文件夹\sign-hap.ps1`，已填全部真实路径与密码），密码不提交到 Git。
- `verify-app -inFile <signed.hap> -outCertChain <cert>.cer -outProfile <profile>.p7b` 输出 `Verify success` 仅代表签名块完整可验证，**不代表真机可安装**。

## 真机运行与测试

## 真机运行与测试（Pura 70 Ultra / HarmonyOS 6.1）

1. 手机开启「开发者模式 > USB 调试」，用 USB 连接电脑（选择「传输文件」模式）。
2. 命令行安装（需先签名，否则系统拒绝安装）：
   ```powershell
   D:\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe install entry/build/default/outputs/default/entry-default-signed.hap
   ```
   或在 DevEco 中点击工具栏 Run 直接安装调试。
3. 与后端联调：确保后端在局域网可达（默认 `http://172.20.10.10:8010` 为开发环境示例地址），在 App「设置」页修改服务器地址并保存。
4. 功能验收清单：
   - 登录 / 注册：邮箱 + 密码。
   - 循证问答：提交问题，等待分级回答渲染。
   - 扫码绑定：网页端「健康档案」页生成配对二维码（6 位码），鸿蒙端「打开相机扫码」或手动输入配对码，绑定后自动登录该网页账号；取消扫码会提示「已取消扫码」。
   - 健康数据同步：完成下方 Health Kit 配置后授权读取并上传。
   - 服务器地址配置：修改后重启 App 仍生效。

## 华为 Health Kit 接入（需 AGC + SDK，当前为占位实现）

后端已内置 `huawei_health_kit` 连接器（`backend/app/health_connectors.py`），鸿蒙端已实现上传协议（`HealthSyncService.completePairing`），仅差华为侧 SDK 与授权。接入步骤如下：

1. 在 [AppGallery Connect](https://developer.huawei.com/consumer/cn/service/josp/agc/index.html) 创建应用，包名 `com.evilife.harmony`，开通「Health Kit」服务，并配置应用签名证书的 SHA-256 指纹。
2. 在 `entry/oh-package.json5` 添加依赖（版本以 AGC 控制台 / ohpm 最新为准）：

   ```json5
   "dependencies": {
     "@hms.health.healthService": "<最新版本>"
   }
   ```

3. 在 DevEco Terminal（或命令行）执行 `ohpm install`。
4. 在 `HealthSyncService.ets` 中替换占位实现，示例代码（以官方文档为准）：

   ```typescript
   import healthService from '@hms.health.healthService';

   // 1) 授权读取步数 / 睡眠 / 心率
   await healthService.authorize([
     healthService.HealthDataTypes.STEP_COUNT,
     healthService.HealthDataTypes.SLEEP,
     healthService.HealthDataTypes.HEART_RATE
   ]);

   // 2) 查询（聚合数据）
   const steps = await healthService.query(healthService.HealthDataTypes.STEP_COUNT, {
     startTime: startOfDay,
     endTime: Date.now(),
     intervalType: healthService.IntervalType.ONE_DAY
   });

   // 3) 映射为 HealthObservation 并上传
   const observations: HealthObservation[] = steps.map(item => new HealthObservation(
     'huawei-' + item.startTime, 'steps', item.value, 'HarmonyOS Health Kit', new Date(item.startTime).toISOString()
   ));
   const report = await HealthSyncService.completePairing(pairingURL, token, observations);
   ```

5. 运动健康权限由 Health Kit SDK 在运行时通过 `authorize()` 申请（`requestPermissions` 中无需额外声明），前提是 AGC 控制台已开通对应数据类型。

> 注意：网页配对二维码有有效期（默认 10 分钟）且配对会话一次性使用，上传需在有效期内完成。

## 关键实现说明

- `ApiClient.ets`：全局复用同一个 `HttpRequest`，保留服务端会话 Cookie；设备配对 claim 后即保持网页账号登录态。
- `PairingParser.ets`：与 iOS `Pairing.swift` 对齐，支持团队协议 JSON（`pairing_url` + `token`）、`code` JSON、URL 参数、URL 尾段、原始 6 位码五种格式。
- `ScanService.ets`：基于系统扫码服务 `@kit.ScanKit`（`scanBarcode.startScanForResult`），无需额外第三方 SDK。
- 界面：iOS 风格浅色分组背景 `#F2F2F7`、白色圆角卡片、底部标签栏、品牌青绿色 `#0F766E`。
