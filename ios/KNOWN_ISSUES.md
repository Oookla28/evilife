# iOS 端已知问题与踩坑记录（2026-08-28）

## 一、HealthKit 授权（iOS 26/27 隐私变更）⚠️ 最重要

**现象**：系统授权页允许后，同步仍报「没有任何已授权的健康数据类型」。

**根因**：iOS 26+ 出于隐私设计**隐藏了「读取」授权状态**——`HKHealthStore.authorizationStatus(for:)`
不再可靠报告读权限（只可靠报告写入状态；读取被拒时查询直接返回空结果）。
旧代码拿 `authorizationStatus == .sharingAuthorized` 当查询门槛，导致误报。

**正确姿势**（已在 `HealthKitSyncService.swift` 落地）：
1. 用 `getRequestStatusForAuthorization` 只判断「是否已请求过授权」（`.shouldRequest` / `.unnecessary`）；
2. 授权请求改用 iOS 17+ 官方 SwiftUI 修饰符 `healthDataAccessRequest(store:shareTypes:readTypes:trigger:completion:)`
   （HealthKitUI 框架），`trigger` 是 Equatable 值（每次 +1 触发），不是 Binding；
3. 授权后**直接查询**：查到数据即成功；查不到才提示「无数据或读取被拒，去 设置→健康→数据访问与设备→EviLife 检查」。

**参考**：Blake Crosley《HealthKit + SwiftUI on iOS 26》——
读权限不可观察是 Apple 官方隐私设计，勿再尝试逐类判断读授权。

## 二、CoreDevice USB 隧道前缀会变

**现象**：真机调试时 App 突然连不上 Mac 后端（此前隧道地址 `fd2f:e300:f785::2` 失效）。

**根因**：USB 隧道（utun 接口）每次重连/重建后 **IPv6 前缀随机变化**（如 `fd2f:e300:f785::2` → `fd10:5fb:a1d0::2`），
设备侧固定为 `::1`，Mac 侧固定为同前缀 `::2`，但前缀不能写死。

**解法**（已在 `Config.swift` 落地）：运行时用 `getifaddrs` 枚举自己的 utun 接口，
找 `fd..` 开头的 ULA 地址，把末段换成 `::2` 动态拼出 Mac 侧地址，按顺序探测
`/api/v1/health`，取第一个通的。App 回前台时也会自动重新探测。

## 三、真机签名与 Bundle ID

- 仓库默认 `com.evilife.ios` 已被开发者中心他人占用 → 真机包改用 `com.pthonhuang.evilife`。
- 钥匙串里的证书团队（TUKCR9KX52）与 Xcode 登录账号实际团队（39T9A8742U）不一致时，
  自动签名报 `No Account for Team`——以 Xcode → Settings → Accounts 里看到的团队为准。
- HealthKit capability 必须在 Signing & Capabilities 开启，自动签名才会把
  `com.apple.developer.healthkit` 写进描述文件（通配描述文件不含该能力）。

## 四、配对二维码里 127.0.0.1 手机不可达

网页端生成的 `pairing_url` 用的是 `request.base_url`：在电脑上用
`http://127.0.0.1:8000` 打开网页时，二维码里就是 127.0.0.1，手机扫到连的是自己。

**要求**：生成二维码的网页必须用「手机可达的地址」打开（同 Wi-Fi 用电脑局域网 IP，
或后端已公网化）。iOS 端扫码后是直接 POST `pairing_url`，不做地址改写。

## 五、Netlify 部署 Next 16 的坑

- `@netlify/plugin-nextjs`（默认插件）与 Next 16 不兼容、`@netlify/next-runtime` 要求装依赖；
  当前改用**静态导出**：`NEXT_STATIC_EXPORT=1` 时 `next.config.ts` 输出 `out/`（见 netlify.toml）。
- 静态导出模式下 rewrites 不生效、演示模式（`NEXT_PUBLIC_USE_MOCKS=true`）全浏览器端运行。
- `rsync --delete` 同步目录会误删 `.netlify/state.json` 导致 CLI 丢失站点链接、把代码部署到新站；
  用 `netlify link --id <site-id>` 重新链接（当前 site id: `f4dba350-3463-4e95-8e85-77098d6e1cba`）。

## 六、其他环境坑

- 开发环境默认端口为 **8000**（FastAPI 默认监听）；若本机 8000 被其他服务占用，可改用其他端口并同步修改 `Config.swift` 与启动参数。
- 后台 uvicorn 进程可能被系统回收：同步失败先 `curl /api/v1/health` 确认后端存活。
- 手机锁屏时通过 devicectl 启动的 App 会挂起（探测不会执行）：先解锁再启动/回前台。
- Swift 编译：`withUnsafePointer` 闭包内不能再访问被借用变量（ExclusivityViolation），先拷出 `sa_len`。
- 多尾随闭包 `Section("标题") { } footer: { }` 在部分 Swift 版本会推断失败，用 `Section { } header: { } footer: { }` 更稳。

## 七、iOS 27 beta：HKErrorDatabaseInaccessible（code 6）

- 现象：授权正常、证书齐全、设备已解锁，查询仍报「Protected health data is inaccessible」
  （com.apple.healthkit code 6 = 系统健康数据库保护态）。
- 结论：iOS 26/27 早期 beta 的系统级 HealthKit 回归（健康库重新加密/迁移卡住），
  与 App 代码无关；重启、重授权均无效。GPT/Claude 等第三方 App 在同设备同样失败。
- 出路：升级更新版 beta / 回退稳定版 / 换非 beta 设备验证。
- 排查手段：错误域 com.apple.healthkit code=6；`UIApplication.isProtectedDataAvailable`
  为 true 仍报错即系统库问题（锁屏场景是另一种触发方式）。
