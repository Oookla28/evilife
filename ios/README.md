# EviLife iPhone 健康同步桥

网页不能凭 Apple 账户直接读取“健康”数据。Apple 要求 iPhone 应用启用 HealthKit capability，并由用户在系统授权页按数据类型授权。正确流程是：用户在 iPhone 上使用 Apple 账户继续 → 系统显示 HealthKit 授权页 → 应用只读取获准的步数、睡眠、心率和体重聚合值 → 使用 EviLife 登录会话发送至服务端。

`HealthKitSyncService.swift` 是接入骨架。把文件加入 iOS App target，在 Signing & Capabilities 中加入 HealthKit，并在 `Info.plist` 配置 `NSHealthShareUsageDescription`。生产环境必须使用 HTTPS，服务端地址通过构建配置传入，不能写入密钥。

Apple 账户只负责身份认证；健康数据权限始终由 HealthKit 单独控制。用户拒绝某一类权限时，不得推断或绕过。
