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

- 签名 HAP：用 DevEco Studio 6.0+ 打开 `harmony/EviLifeHarmony`，`File > Project Structure > Signing Configs` 完成自动签名（需华为开发者账号），然后 `Build > Build Hap(s)/APP(s)`。
- 未签名 HAP（仅本地验证）：命令行方式见 [EviLifeHarmony/README.md](./EviLifeHarmony/README.md)。
