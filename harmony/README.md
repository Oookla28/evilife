# EviLife HarmonyOS

鸿蒙原生 ArkTS/ArkUI 客户端，适配 HarmonyOS 6，界面与 iOS/Android 版保持一致。

## 当前能力

- 登录、循证问答、服务器地址配置
- 鸿蒙端扫码绑定入口
- 华为 Health Kit 同步入口（需要在 DevEco Studio 配置 Health Kit 能力和签名）

## 打包 HAP

使用 DevEco Studio 6.0+ 打开 `harmony/EviLifeHarmony`，配置签名后选择 `Build > Build Hap(s)/APP(s)`。输出的 `.hap` 位于 `entry/build/default/outputs/default/`。

本机未安装 DevEco Studio/HarmonyOS SDK，因此无法在当前环境直接生成签名 HAP。生产发布还需要华为开发者账号签名与 AppGallery 审核配置。
