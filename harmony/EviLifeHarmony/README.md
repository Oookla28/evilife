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

## 真机运行与测试（Pura 70 Ultra / HarmonyOS 6.1）

### 0. 准备条件

- 已用华为开发者账号登录 DevEco Studio 并完成自动签名（见上文「AGC 自动签名」），确认 `build-profile.json5` 的 `signingConfigs` 非空。
- 后端服务在局域网可达（开发示例地址 `http://172.20.10.10:8010`）。

### 1. 连接手机

1. 手机开启开发者模式：设置 > 关于本机 > 连续点击「版本号」7 次；设置 > 系统与更新 > 开发人员选项 > 打开「USB 调试」。
2. USB 连接电脑，手机弹窗选「传输文件」，在「是否允许 USB 调试」弹窗勾选「始终允许」。
3. 验证连接（输出设备序列号即成功；`[Empty]` 表示未识别）：

   ```powershell
   D:\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe list targets
   ```

   未识别时依次尝试：换 USB 线/接口、手机上撤销 USB 调试授权后重连、确认 DevEco 的 Device File Manager 能看到手机。

### 2. 构建签名 HAP

- IDE：`Build > Build Hap(s)/APP(s)`，产物 `entry/build/default/outputs/default/entry-default-signed.hap`。
- 命令行（自动签名配置写入工程后同样适用）：

  ```powershell
  $env:NODE_HOME = "D:\DevEco Studio\tools\node"; $env:JAVA_HOME = "D:\DevEco Studio\jbr"; $env:DEVECO_SDK_HOME = "D:\DevEco Studio\sdk"
  $env:Path = "$env:NODE_HOME;$env:JAVA_HOME\bin;" + $env:Path
  cd harmony/EviLifeHarmony
  D:\DevEco Studio\tools\hvigor\bin\hvigorw.bat assembleHap --no-daemon
  ```

- 确认产物存在：`entry/build/default/outputs/default/entry-default-signed.hap`。

### 3. 安装

```powershell
D:\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe install -r entry/build/default/outputs/default/entry-default-signed.hap
```

（`-r` 覆盖重装；也可在 DevEco 工具栏点 Run 安装调试。）

安装失败排查：

- `install failed due to invalid signature`：使用了本地自签 HAP 或未走 AGC 签名 → 完成自动签名后重新构建。
- `install failed due to incompatible application`：SDK/系统版本不匹配 → 确认工程 `compatibleSdkVersion 6.0.0(20)`，Pura 70 Ultra（HarmonyOS 6.1）兼容。
- 提示旧版本冲突：先 `hdc uninstall com.evilife.harmony` 再安装。

### 4. 启动

- 桌面点击应用图标；或命令行启动：

  ```powershell
  D:\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe shell aa start -a EntryAbility -b com.evilife.harmony
  ```

### 5. 查看日志

```powershell
D:\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe shell hilog | Select-String -Pattern "EviLife|ERROR"
```

### 6. 与后端联调

1. 电脑防火墙放行后端端口（默认 8010），手机与电脑连同一局域网。
2. 后端地址填电脑局域网 IP（如 `http://192.168.x.x:8010`），启动后端时确认监听 `0.0.0.0`。
3. 在 App「设置」页修改服务器地址并保存，重启 App 后仍生效。

### 7. 功能验收清单

- 登录 / 注册：邮箱 + 密码。
- 循证问答：提交问题，等待分级回答渲染。
- 扫码绑定：网页端「健康档案」页生成配对二维码（6 位码），鸿蒙端「打开相机扫码」或手动输入配对码，绑定后自动登录该网页账号；取消扫码会提示「已取消扫码」。
- 健康数据同步：完成下方「华为 Health Kit 接入」后授权读取并上传。
- 服务器地址配置：修改后重启 App 仍生效。
## 华为 Health Kit 接入（需 AGC 开通服务 + 私有 SDK）

后端已内置 `huawei_health_kit` 连接器，鸿蒙端已实现上传协议与「真实数据优先」的同步流程（`HealthSyncService.syncToDatabase`）。接入后点击「授权并同步健康数据」会读取华为运动健康真实数据并写入当前账号；未接入时保持演示数据流程。

代码侧已就绪，无需再改逻辑，只需要完成以下华为侧配置：

### 一、AGC 控制台（需华为开发者账号，本机无法代操作）

1. 登录 [AppGallery Connect](https://developer.huawei.com/consumer/cn/service/josp/agc/index.html)，创建应用，包名必须为 `com.evilife.harmony`。
2. 开通「Health Kit」服务（签署协议后），在「数据权限」中勾选需要的类型：步数、睡眠、静息心率、饮水等。
3. 配置签名证书 SHA-256 指纹。本机当前调试证书（`C:\Users\liuch\.ohos\config\default_EviLifeHarmony_*.cer`）的指纹为：

   ```
   DF:21:A3:C0:9F:79:54:57:93:05:F8:5C:64:F8:0C:AD:86:F7:98:53:EE:3A:88:7C:1D:EC:95:D2:18:DF:3A:37
   ```

   > 注意：重新生成签名证书后指纹会变化，需在 AGC 同步更新；联调阶段请确认 AGC「应用信息」中的调试证书指纹与此一致。
4. 下载 `agconnect-services.json`，放到工程根目录 `harmony/EviLifeHarmony/`（与 `build-profile.json5` 同级）。
5. Health Kit SDK 为华为**私有 ohpm 包**（公共仓库查询返回 404），开通服务后 AGC/DevEco 会给出可用的私有仓库地址与版本号（形如 `@hms.health.healthService: 6.x.x.xxx`）。建议在 DevEco Studio 中打开工程，通过 AGC 相关向导完成 SDK 拉取，或在命令行执行：

   ```powershell
   $env:NODE_HOME = "D:\DevEco Studio\tools\node"
   $env:Path = "$env:NODE_HOME;" + $env:Path
   D:\DevEco Studio\tools\ohpm\bin\ohpm.bat config set registry "<AGC 提供的私有仓库地址>"
   cd harmony/EviLifeHarmony
   D:\DevEco Studio\tools\ohpm\bin\ohpm.bat install
   ```

### 二、启用 SDK 依赖与读取实现（本机操作）

1. 在 `entry/oh-package.json5` 的 `dependencies` 中启用：

   ```json5
   "dependencies": {
     "@hms.health.healthService": "<AGC 控制台给出的版本>"
   }
   ```

2. 将模板文件 `entry/src/main/ets/common/HealthKitService.ets.template` **重命名为 `HealthKitService.ets`**（去掉 `.template`）。
3. 在 `EntryAbility.ets` 的 `onWindowStageCreate`（或 `Index.ets` 的 `aboutToAppear`）中调用一次注册：

   ```typescript
   import { initHealthKit } from '../common/HealthKitService';
   // 登录后、同步前：
   initHealthKit(getContext(this) as common.UIAbilityContext);
   ```

   注册后 `HealthSyncService.healthKitConfigured()` 自动返回 true，同步按钮切换到真实数据读取。
4. 重新构建安装（签名证书指纹必须与 AGC 一致）：

   ```powershell
   D:\DevEco Studio\tools\hvigor\bin\hvigorw.bat assembleHap --no-daemon
   ```

### 三、真机验证

1. 手机上安装并登录「华为运动健康」App，正常记录步数/睡眠。
2. 打开 EviLife，进入「健康」Tab，点击「授权并同步健康数据」，首次会弹出 Health Kit 授权页。
3. 授权后 App 显示「已从华为运动健康同步真实数据」，网页端「健康档案」可见 `connector_id=huawei_health_kit` 的记录。
4. 若显示「未授权或今日暂无数据」：确认运动健康 App 已授权、AGC 数据权限已开通、签名指纹一致。

> 注意：网页配对二维码有效期 10 分钟且一次性使用；真实数据走当前登录账号的 `observations/batch`，无需配对码。

## 关键实现说明

- `ApiClient.ets`：全局复用同一个 `HttpRequest`；鸿蒙 `http` 模块不会自动回传 `Set-Cookie`（且响应头中 `set-cookie` 为数组），因此客户端在登录响应中手动捕获 `evilife_session` 并在后续请求的 `Cookie` 头中携带，登录后 `observations/batch` 等接口才会写入当前账号主体（而非 `sub-guest`）。
- `PairingParser.ets`：与 iOS `Pairing.swift` 对齐，支持团队协议 JSON（`pairing_url` + `token`）、`code` JSON、URL 参数、URL 尾段、原始 6 位码五种格式。
- `ScanService.ets`：基于系统扫码服务 `@kit.ScanKit`（`scanBarcode.startScanForResult`），无需额外第三方 SDK。
- 界面：iOS 风格浅色分组背景 `#F2F2F7`、白色圆角卡片、底部标签栏、品牌青绿色 `#0F766E`。
