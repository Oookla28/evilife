# EviLife HarmonyOS

鸿蒙原生 ArkTS/ArkUI 客户端，目标系统 HarmonyOS 6（API 20），界面风格与 iOS/Android 版本保持一致（浅色分组卡片、底部标签栏）。

工程位于 `harmony/EviLifeHarmony`，详细打包与真机测试步骤见 [EviLifeHarmony/README.md](./EviLifeHarmony/README.md)。

## 当前能力

- 登录 / 注册（`/api/v1/auth/login|register`，复用会话 Cookie）
- 循证问答（`POST /api/v1/orchestrate`，渲染分级回答）
- 扫码绑定网页账号（HarmonyOS Scan Kit 相机扫码 + 6 位配对码 claim）
- 健康数据同步入口（华为 Health Kit 配置占位，需在 AGC 开通服务并安装 SDK）
- 服务器地址配置（持久化保存）

## 打包 HAP

使用 DevEco Studio 6.0+ 打开 `harmony/EviLifeHarmony`，配置签名后选择 `Build > Build Hap(s)/APP(s)`，产物位于 `entry/build/default/outputs/default/`。

> 当前开发机未安装 DevEco Studio / HarmonyOS SDK，因此无法在本环境直接生成 `.hap`；源码已按 HarmonyOS 6 工程结构整理，首次用 DevEco 打开时执行 Sync 即可补齐 hvigor 包装脚本并编译。