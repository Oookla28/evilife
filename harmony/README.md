# EviLife HarmonyOS

鸿蒙原生 ArkTS/ArkUI 客户端，目标系统 HarmonyOS 6（API 20），界面风格与 iOS/Android 版本保持一致（浅色分组卡片、底部标签栏、品牌青绿色）。

工程位于 `harmony/EviLifeHarmony`，详细打包与真机测试步骤见 [EviLifeHarmony/README.md](./EviLifeHarmony/README.md)。

## 当前能力

- 登录 / 注册（`/api/v1/auth/login|register`，复用会话 Cookie）
- 循证问答（`POST /api/v1/orchestrate`，渲染分级回答）
- 扫码绑定网页账号（HarmonyOS Scan Kit 相机扫码 + 6 位配对码 claim）
- 健康数据同步入口（华为 Health Kit 配置占位，需在 AGC 开通服务并安装 SDK）
- 服务器地址配置（持久化保存）

## 构建状态

本机已安装 DevEco Studio 6.1.1（HarmonyOS SDK 6.1.1 / API 24），并已用命令行完成编译验证：

```powershell
# 产物（未签名）：harmony/EviLifeHarmony/entry/build/default/outputs/default/entry-default-unsigned.hap
```

> 注意：DevEco / hvigor 要求工程路径仅含 ASCII 字符（字母、数字、`-`、`_`、`.`、空格、括号、`@`），
> 工程不要放在含中文的目录下（例如 `Desktop\新建文件夹\...` 会导致 `Invalid project path` 报错）。

## 打包 HAP

- 真机可安装的 HAP：**必须使用 AGC 自动签名**（本地自签证书不在华为信任链内，真机会拒绝安装），详细步骤见 [EviLifeHarmony/README.md](./EviLifeHarmony/README.md) 的「签名」一节。
- 未签名 HAP（仅本地验证）：命令行方式见 [EviLifeHarmony/README.md](./EviLifeHarmony/README.md)。

## 签名说明（重要）

- **本地自签（演示/验证用）**：用 hap-sign-tool 生成自签证书链给 HAP 打签名，`verify-app` 可通过，但真机不信任该 CA，无法安装。完整可运行的签名脚本在仓库外（`Desktop\新建文件夹\sign-hap.ps1`），密码不提交到 Git。
- **AGC 自动签名（真机可安装）**：在 AppGallery Connect 创建应用 `com.evilife.harmony`，用华为开发者账号登录 DevEco Studio，在 `File > Project Structure > Signing Configs` 勾选自动生成签名，重新构建后得到可安装的 `entry-default-signed.hap`。
